"""Use cases for budget enforcement, spend reservations, idempotency, and guarded provider execution."""
from datetime import datetime, timezone
from typing import Optional, Tuple
import uuid

from src.core.dto.provider_dto import (
    ExecuteGuardedProviderCallInput,
    ExecuteGuardedProviderCallResult,
    ExternalRequestRecord,
    ProjectBudgetSummary,
    ProviderOperationRequest,
    ProviderOperationResponse,
    RecordSpendOutcomeInput,
    SetProjectBudgetInput,
    SpendPreflightInput,
    SpendPreflightResult,
    SpendReservationRecord,
)
from src.core.entities.budget import (
    BudgetPolicyDecision,
    BudgetValidationError,
    ExternalJobStatus,
    ProjectBudget,
    ReservationStatus,
    round_usd,
)
from src.core.entities.provider import (
    ProviderConnectionStatus,
    ProviderNotFoundError,
    ProviderType,
    ProviderValidationError,
    redact_secrets,
)
from src.core.ports.budget_repository import BudgetRepository, BudgetTransaction
from src.core.ports.credential_vault import CredentialVaultPort
from src.core.ports.provider_gateway import ProviderGateway
from src.core.ports.provider_repository import ProviderRepository


def _zero_budget_summary(project_id: str, now_iso: str) -> ProjectBudgetSummary:
    return ProjectBudgetSummary(
        project_id=project_id,
        budget_limit_usd=0.0,
        spent_usd=0.0,
        outstanding_reservations_usd=0.0,
        remaining_budget_usd=0.0,
        available_budget_usd=0.0,
        updated_at=now_iso,
    )


def _snapshot_to_entity(snapshot: ProjectBudgetSummary) -> ProjectBudget:
    return ProjectBudget(
        project_id=snapshot.project_id,
        budget_limit_usd=snapshot.budget_limit_usd,
        spent_usd=snapshot.spent_usd,
        reserved_usd=snapshot.outstanding_reservations_usd,
        updated_at=datetime.fromisoformat(snapshot.updated_at),
    )


def _paused_decision(
    *,
    decision: BudgetPolicyDecision,
    requires_user_approval: bool,
    allows_manual_fallback: bool,
    message: str,
    input_data: SpendPreflightInput,
    snapshot: ProjectBudgetSummary,
    attempts_used: int,
    available_actions: Tuple[str, ...],
    existing_request: Optional[ExternalRequestRecord] = None,
    existing_reservation: Optional[SpendReservationRecord] = None,
) -> SpendPreflightResult:
    return SpendPreflightResult(
        allowed=False,
        decision=decision,
        requires_user_approval=requires_user_approval,
        allows_manual_fallback=allows_manual_fallback,
        message=message,
        project_id=input_data.project_id,
        stage_run_id=input_data.stage_run_id,
        request_key=input_data.request_key,
        provider_id=input_data.provider_id,
        reservation_id=existing_reservation.id if existing_reservation else None,
        external_request_id=existing_request.id if existing_request else None,
        external_job_id=existing_request.external_job_id if existing_request else None,
        estimated_cost_usd=input_data.estimated_cost_usd,
        reserved_amount_usd=0.0,
        outstanding_reservations_usd=snapshot.outstanding_reservations_usd,
        remaining_budget_usd=snapshot.remaining_budget_usd,
        budget_limit_usd=snapshot.budget_limit_usd,
        spent_usd=snapshot.spent_usd,
        attempts_used=attempts_used,
        max_retries=input_data.max_retries,
        available_actions=available_actions,
    )


class SetProjectBudgetUseCase:
    """Create or update a project's USD spending limit."""

    def __init__(self, budget_repo: BudgetRepository) -> None:
        self._budget_repo = budget_repo

    def execute(self, input_data: SetProjectBudgetInput) -> ProjectBudgetSummary:
        cleaned_project_id = input_data.project_id.strip()
        if not cleaned_project_id:
            raise BudgetValidationError("Project ID cannot be empty.")
        if input_data.budget_limit_usd < 0:
            raise BudgetValidationError("Project budget limit cannot be negative.")

        now_iso = datetime.now(timezone.utc).isoformat()
        limit = round_usd(input_data.budget_limit_usd)
        return self._budget_repo.run_atomic(
            lambda tx: tx.upsert_budget(cleaned_project_id, limit, now_iso)
        )


class GetProjectBudgetUseCase:
    """Read a project's budget, spend, and active reservation totals."""

    def __init__(self, budget_repo: BudgetRepository) -> None:
        self._budget_repo = budget_repo

    def execute(self, project_id: str) -> Optional[ProjectBudgetSummary]:
        return self._budget_repo.get_budget_summary(project_id.strip())


class BudgetGuardUseCase:
    """Enforce project budget limits, unknown-cost pauses, and atomic idempotency locks."""

    def __init__(self, budget_repo: BudgetRepository) -> None:
        self._budget_repo = budget_repo

    def preflight_and_reserve(self, input_data: SpendPreflightInput) -> SpendPreflightResult:
        self._validate_preflight_input(input_data)
        now_iso = datetime.now(timezone.utc).isoformat()

        def _atomic(tx: BudgetTransaction) -> SpendPreflightResult:
            snapshot = tx.get_budget_snapshot(input_data.project_id) or _zero_budget_summary(
                input_data.project_id, now_iso
            )
            stage_requests = tx.list_requests_for_stage(input_data.stage_run_id)
            failed_attempts = sum(1 for r in stage_requests if r.status == ExternalJobStatus.FAILED)

            # 1. Request-key idempotency guard
            existing_req = tx.get_request_by_key(input_data.request_key)
            if existing_req is not None:
                existing_res = tx.get_reservation_by_key(input_data.request_key)
                return self._decision_for_existing_request(
                    existing_req=existing_req,
                    existing_res=existing_res,
                    input_data=input_data,
                    snapshot=snapshot,
                    attempts_used=len(stage_requests),
                )

            # 2. Stage-level concurrency, completion, uncertain-outcome, and retry-cap guards
            for req in stage_requests:
                if req.status == ExternalJobStatus.SUCCEEDED:
                    return _paused_decision(
                        decision=BudgetPolicyDecision.ALREADY_COMPLETED,
                        requires_user_approval=False,
                        allows_manual_fallback=False,
                        message=(
                            f"Stage run '{input_data.stage_run_id}' already completed via request "
                            f"'{req.request_key}'."
                        ),
                        input_data=input_data,
                        snapshot=snapshot,
                        attempts_used=len(stage_requests),
                        available_actions=(),
                        existing_request=req,
                    )
                if req.status in (ExternalJobStatus.PENDING, ExternalJobStatus.SUBMITTED):
                    return _paused_decision(
                        decision=BudgetPolicyDecision.DUPLICATE_IN_FLIGHT,
                        requires_user_approval=False,
                        allows_manual_fallback=False,
                        message=(
                            f"Stage run '{input_data.stage_run_id}' already has an in-flight request "
                            f"('{req.request_key}')."
                        ),
                        input_data=input_data,
                        snapshot=snapshot,
                        attempts_used=len(stage_requests),
                        available_actions=(),
                        existing_request=req,
                    )
                if req.status == ExternalJobStatus.UNCERTAIN:
                    return _paused_decision(
                        decision=BudgetPolicyDecision.PAUSE_UNCERTAIN_OUTCOME,
                        requires_user_approval=True,
                        allows_manual_fallback=True,
                        message=(
                            f"Prior request '{req.request_key}' has an uncertain outcome; reconcile "
                            "its external job before retrying to prevent duplicate charges."
                        ),
                        input_data=input_data,
                        snapshot=snapshot,
                        attempts_used=len(stage_requests),
                        available_actions=("poll_or_reconcile", "switch_to_manual", "cancel"),
                        existing_request=req,
                    )

            if failed_attempts > input_data.max_retries:
                return _paused_decision(
                    decision=BudgetPolicyDecision.BLOCKED_MAX_RETRIES,
                    requires_user_approval=False,
                    allows_manual_fallback=True,
                    message=(
                        f"Retry limit reached for stage run '{input_data.stage_run_id}' "
                        f"({failed_attempts} failed attempt(s), max_retries={input_data.max_retries})."
                    ),
                    input_data=input_data,
                    snapshot=snapshot,
                    attempts_used=len(stage_requests),
                    available_actions=("switch_to_manual", "cancel"),
                )

            # 3. Unknown cost guard (must never submit silently)
            budget_entity = _snapshot_to_entity(snapshot)
            if input_data.estimated_cost_usd is None:
                if not input_data.explicit_approval:
                    return _paused_decision(
                        decision=BudgetPolicyDecision.PAUSE_UNKNOWN_COST,
                        requires_user_approval=True,
                        allows_manual_fallback=True,
                        message=(
                            "Estimated cost is unknown. Explicit user approval or manual input is "
                            "required before sending a billable request."
                        ),
                        input_data=input_data,
                        snapshot=snapshot,
                        attempts_used=len(stage_requests),
                        available_actions=(
                            "approve_and_submit",
                            "enter_cost_estimate",
                            "switch_to_manual",
                            "cancel",
                        ),
                    )
                reserve_amount = round_usd(input_data.approved_cost_cap_usd or 0.0)
            else:
                # 4. Budget + outstanding reservations overrun guard
                estimated = round_usd(input_data.estimated_cost_usd)
                if budget_entity.would_exceed(estimated) and not input_data.explicit_approval:
                    projected_total = round_usd(estimated + snapshot.outstanding_reservations_usd)
                    return _paused_decision(
                        decision=BudgetPolicyDecision.PAUSE_BUDGET_EXCEEDED,
                        requires_user_approval=True,
                        allows_manual_fallback=True,
                        message=(
                            f"Estimated cost (${estimated:.4f}) + outstanding reservations "
                            f"(${snapshot.outstanding_reservations_usd:.4f}) = ${projected_total:.4f} "
                            f"exceeds remaining budget (${snapshot.remaining_budget_usd:.4f})."
                        ),
                        input_data=input_data,
                        snapshot=snapshot,
                        attempts_used=len(stage_requests),
                        available_actions=(
                            "approve_overrun",
                            "increase_budget",
                            "switch_to_manual",
                            "cancel",
                        ),
                    )
                reserve_amount = estimated

            # 5. Atomically create spend reservation and pending external request
            reservation = SpendReservationRecord(
                id=str(uuid.uuid4()),
                project_id=input_data.project_id,
                stage_run_id=input_data.stage_run_id,
                request_key=input_data.request_key,
                provider_id=input_data.provider_id,
                reserved_usd=reserve_amount,
                settled_usd=None,
                status=ReservationStatus.ACTIVE,
                created_at=now_iso,
                updated_at=now_iso,
            )
            request_record = ExternalRequestRecord(
                id=str(uuid.uuid4()),
                project_id=input_data.project_id,
                stage_run_id=input_data.stage_run_id,
                request_key=input_data.request_key,
                provider_id=input_data.provider_id,
                operation=input_data.operation,
                model=input_data.model,
                external_job_id=None,
                status=ExternalJobStatus.PENDING,
                attempt_number=failed_attempts + 1,
                estimated_cost_usd=input_data.estimated_cost_usd,
                reported_cost_usd=None,
                explicitly_approved=input_data.explicit_approval,
                error_message=None,
                created_at=now_iso,
                updated_at=now_iso,
            )
            tx.create_reservation_and_request(reservation, request_record)

            new_outstanding = round_usd(snapshot.outstanding_reservations_usd + reserve_amount)
            return SpendPreflightResult(
                allowed=True,
                decision=BudgetPolicyDecision.APPROVED,
                requires_user_approval=False,
                allows_manual_fallback=True,
                message="Spend preflight approved and reservation locked.",
                project_id=input_data.project_id,
                stage_run_id=input_data.stage_run_id,
                request_key=input_data.request_key,
                provider_id=input_data.provider_id,
                reservation_id=reservation.id,
                external_request_id=request_record.id,
                external_job_id=None,
                estimated_cost_usd=input_data.estimated_cost_usd,
                reserved_amount_usd=reserve_amount,
                outstanding_reservations_usd=new_outstanding,
                remaining_budget_usd=snapshot.remaining_budget_usd,
                budget_limit_usd=snapshot.budget_limit_usd,
                spent_usd=snapshot.spent_usd,
                attempts_used=failed_attempts + 1,
                max_retries=input_data.max_retries,
                available_actions=(),
            )

        return self._budget_repo.run_atomic(_atomic)

    def record_outcome(
        self, input_data: RecordSpendOutcomeInput
    ) -> Tuple[ExternalRequestRecord, ProjectBudgetSummary]:
        if not input_data.request_key or not input_data.request_key.strip():
            raise BudgetValidationError("request_key cannot be empty.")
        if input_data.reported_cost_usd is not None and input_data.reported_cost_usd < 0:
            raise BudgetValidationError("reported_cost_usd cannot be negative.")

        now_iso = datetime.now(timezone.utc).isoformat()

        def _atomic(tx: BudgetTransaction) -> Tuple[ExternalRequestRecord, ProjectBudgetSummary]:
            req = tx.get_request_by_key(input_data.request_key)
            res = tx.get_reservation_by_key(input_data.request_key)
            if req is None or res is None:
                raise BudgetValidationError(
                    f"No reservation/request found for request_key '{input_data.request_key}'."
                )

            snapshot = tx.get_budget_snapshot(req.project_id) or _zero_budget_summary(
                req.project_id, now_iso
            )

            # Prevent double-settlement if an already finalized request receives duplicate callback
            if req.status == ExternalJobStatus.SUCCEEDED and input_data.status == ExternalJobStatus.SUCCEEDED:
                return req, snapshot
            if req.status == ExternalJobStatus.FAILED and input_data.status == ExternalJobStatus.FAILED:
                return req, snapshot

            safe_error = redact_secrets(input_data.error_message)
            job_id = input_data.external_job_id or req.external_job_id

            if input_data.status == ExternalJobStatus.SUBMITTED:
                reservation_status = ReservationStatus.ACTIVE
                settled_usd: Optional[float] = None
                delta_spent_usd = 0.0
                reported_cost = req.reported_cost_usd
            elif input_data.status == ExternalJobStatus.SUCCEEDED:
                actual_cost = (
                    round_usd(input_data.reported_cost_usd)
                    if input_data.reported_cost_usd is not None
                    else round_usd(
                        req.estimated_cost_usd
                        if req.estimated_cost_usd is not None
                        else res.reserved_usd
                    )
                )
                reservation_status = ReservationStatus.SETTLED
                settled_usd = actual_cost
                delta_spent_usd = actual_cost
                reported_cost = actual_cost
            elif input_data.status == ExternalJobStatus.FAILED:
                actual_cost = (
                    round_usd(input_data.reported_cost_usd)
                    if input_data.reported_cost_usd is not None
                    else 0.0
                )
                if actual_cost > 0:
                    reservation_status = ReservationStatus.SETTLED
                    settled_usd = actual_cost
                    delta_spent_usd = actual_cost
                    reported_cost = actual_cost
                else:
                    reservation_status = ReservationStatus.RELEASED
                    settled_usd = 0.0
                    delta_spent_usd = 0.0
                    reported_cost = input_data.reported_cost_usd
            elif input_data.status == ExternalJobStatus.UNCERTAIN:
                reservation_status = ReservationStatus.UNCERTAIN
                settled_usd = None
                delta_spent_usd = 0.0
                reported_cost = req.reported_cost_usd
            else:
                raise BudgetValidationError(f"Unsupported outcome status: {input_data.status}")

            updated_req = ExternalRequestRecord(
                id=req.id,
                project_id=req.project_id,
                stage_run_id=req.stage_run_id,
                request_key=req.request_key,
                provider_id=req.provider_id,
                operation=req.operation,
                model=req.model,
                external_job_id=job_id,
                status=input_data.status,
                attempt_number=req.attempt_number,
                estimated_cost_usd=req.estimated_cost_usd,
                reported_cost_usd=reported_cost,
                explicitly_approved=req.explicitly_approved,
                error_message=safe_error,
                created_at=req.created_at,
                updated_at=now_iso,
            )
            updated_summary = tx.update_request_and_reservation(
                request=updated_req,
                reservation_status=reservation_status,
                settled_usd=settled_usd,
                delta_spent_usd=delta_spent_usd,
                now_iso=now_iso,
            )
            return updated_req, updated_summary

        return self._budget_repo.run_atomic(_atomic)

    @staticmethod
    def _validate_preflight_input(input_data: SpendPreflightInput) -> None:
        if not input_data.project_id or not input_data.project_id.strip():
            raise BudgetValidationError("project_id cannot be empty.")
        if not input_data.stage_run_id or not input_data.stage_run_id.strip():
            raise BudgetValidationError("stage_run_id cannot be empty.")
        if not input_data.request_key or not input_data.request_key.strip():
            raise BudgetValidationError("request_key cannot be empty.")
        if not input_data.provider_id or not input_data.provider_id.strip():
            raise BudgetValidationError("provider_id cannot be empty.")
        if input_data.max_retries < 0:
            raise BudgetValidationError("max_retries cannot be negative.")
        if input_data.estimated_cost_usd is not None and input_data.estimated_cost_usd < 0:
            raise BudgetValidationError("estimated_cost_usd cannot be negative.")
        if input_data.approved_cost_cap_usd is not None and input_data.approved_cost_cap_usd < 0:
            raise BudgetValidationError("approved_cost_cap_usd cannot be negative.")

    @staticmethod
    def _decision_for_existing_request(
        *,
        existing_req: ExternalRequestRecord,
        existing_res: Optional[SpendReservationRecord],
        input_data: SpendPreflightInput,
        snapshot: ProjectBudgetSummary,
        attempts_used: int,
    ) -> SpendPreflightResult:
        if existing_req.status == ExternalJobStatus.SUCCEEDED:
            return _paused_decision(
                decision=BudgetPolicyDecision.ALREADY_COMPLETED,
                requires_user_approval=False,
                allows_manual_fallback=False,
                message=f"Request '{input_data.request_key}' has already succeeded.",
                input_data=input_data,
                snapshot=snapshot,
                attempts_used=attempts_used,
                available_actions=(),
                existing_request=existing_req,
                existing_reservation=existing_res,
            )
        if existing_req.status == ExternalJobStatus.UNCERTAIN:
            return _paused_decision(
                decision=BudgetPolicyDecision.PAUSE_UNCERTAIN_OUTCOME,
                requires_user_approval=True,
                allows_manual_fallback=True,
                message=(
                    f"Request '{input_data.request_key}' has an uncertain outcome; reconcile before retrying."
                ),
                input_data=input_data,
                snapshot=snapshot,
                attempts_used=attempts_used,
                available_actions=("poll_or_reconcile", "switch_to_manual", "cancel"),
                existing_request=existing_req,
                existing_reservation=existing_res,
            )
        return _paused_decision(
            decision=BudgetPolicyDecision.DUPLICATE_IN_FLIGHT,
            requires_user_approval=False,
            allows_manual_fallback=False,
            message=(
                f"Duplicate request_key '{input_data.request_key}' already exists with status "
                f"'{existing_req.status.value}'."
            ),
            input_data=input_data,
            snapshot=snapshot,
            attempts_used=attempts_used,
            available_actions=(),
            existing_request=existing_req,
            existing_reservation=existing_res,
        )


class ExecuteGuardedProviderCallUseCase:
    """Coordinate budget preflight, credential lookup, provider submission, and spend settlement."""

    def __init__(
        self,
        provider_repo: ProviderRepository,
        credential_vault: CredentialVaultPort,
        provider_gateway: ProviderGateway,
        budget_repo: BudgetRepository,
    ) -> None:
        self._provider_repo = provider_repo
        self._credential_vault = credential_vault
        self._provider_gateway = provider_gateway
        self._budget_repo = budget_repo
        self._budget_guard = BudgetGuardUseCase(budget_repo)

    def execute(self, input_data: ExecuteGuardedProviderCallInput) -> ExecuteGuardedProviderCallResult:
        provider = self._provider_repo.get_by_id(input_data.provider_id)
        if provider is None:
            raise ProviderNotFoundError(f"Provider '{input_data.provider_id}' not found.")

        if provider.connection_status != ProviderConnectionStatus.VERIFIED:
            raise ProviderValidationError(
                f"Provider '{provider.name}' is not verified (status={provider.connection_status.value})."
            )
        if input_data.operation not in provider.supported_capabilities:
            raise ProviderValidationError(
                f"Provider '{provider.name}' does not support capability '{input_data.operation.value}'."
            )

        selected_model = (input_data.model or provider.selected_model or "").strip()
        if not selected_model:
            raise ProviderValidationError(f"No verified model selected for provider '{provider.name}'.")
        if provider.verified_models and selected_model not in provider.verified_models:
            raise ProviderValidationError(
                f"Model '{selected_model}' is not verified for provider '{provider.name}'."
            )

        preflight = self._budget_guard.preflight_and_reserve(
            SpendPreflightInput(
                project_id=input_data.project_id,
                stage_run_id=input_data.stage_run_id,
                request_key=input_data.request_key,
                provider_id=provider.id,
                operation=input_data.operation,
                estimated_cost_usd=input_data.estimated_cost_usd,
                model=selected_model,
                is_retry=input_data.is_retry,
                max_retries=input_data.max_retries,
                explicit_approval=input_data.explicit_approval,
                approved_cost_cap_usd=input_data.approved_cost_cap_usd,
            )
        )

        if not preflight.allowed:
            now_iso = datetime.now(timezone.utc).isoformat()
            summary = self._budget_repo.get_budget_summary(input_data.project_id) or _zero_budget_summary(
                input_data.project_id, now_iso
            )
            return ExecuteGuardedProviderCallResult(
                preflight=preflight,
                submitted=False,
                response=None,
                request_record=self._budget_repo.get_request_by_key(input_data.request_key),
                budget_summary=summary,
            )

        api_key: Optional[str] = None
        if provider.credential_ref:
            api_key = self._credential_vault.get_secret(provider.credential_ref)
        if provider.provider_type != ProviderType.LOCAL_OLLAMA and not api_key:
            updated_req, summary = self._budget_guard.record_outcome(
                RecordSpendOutcomeInput(
                    request_key=input_data.request_key,
                    status=ExternalJobStatus.FAILED,
                    reported_cost_usd=0.0,
                    error_message="Missing API credential in protected storage.",
                )
            )
            return ExecuteGuardedProviderCallResult(
                preflight=preflight,
                submitted=False,
                response=ProviderOperationResponse(
                    accepted=False,
                    external_job_id=None,
                    status=ExternalJobStatus.FAILED,
                    error_message="Missing API credential in protected storage.",
                ),
                request_record=updated_req,
                budget_summary=summary,
            )

        try:
            raw_response = self._provider_gateway.submit_operation(
                ProviderOperationRequest(
                    provider_id=provider.id,
                    provider_type=provider.provider_type,
                    base_url=provider.base_url,
                    capability=input_data.operation,
                    model=selected_model,
                    payload=input_data.payload,
                    request_key=input_data.request_key,
                    api_key=api_key,
                )
            )
            safe_error = redact_secrets(raw_response.error_message, [api_key])
            safe_response = ProviderOperationResponse(
                accepted=raw_response.accepted,
                external_job_id=raw_response.external_job_id,
                status=raw_response.status,
                output_summary=redact_secrets(raw_response.output_summary, [api_key]),
                reported_cost_usd=raw_response.reported_cost_usd,
                error_message=safe_error,
            )
        except Exception as exc:
            safe_error = redact_secrets(str(exc), [api_key]) or "Provider submission error; outcome uncertain."
            safe_response = ProviderOperationResponse(
                accepted=False,
                external_job_id=None,
                status=ExternalJobStatus.UNCERTAIN,
                error_message=safe_error,
            )

        updated_req, summary = self._budget_guard.record_outcome(
            RecordSpendOutcomeInput(
                request_key=input_data.request_key,
                status=safe_response.status,
                external_job_id=safe_response.external_job_id,
                reported_cost_usd=safe_response.reported_cost_usd,
                error_message=safe_response.error_message,
            )
        )
        return ExecuteGuardedProviderCallResult(
            preflight=preflight,
            submitted=True,
            response=safe_response,
            request_record=updated_req,
            budget_summary=summary,
        )

    def reconcile_request(self, request_key: str) -> Tuple[ExternalRequestRecord, ProjectBudgetSummary]:
        req = self._budget_repo.get_request_by_key(request_key)
        if req is None:
            raise BudgetValidationError(f"Request '{request_key}' not found.")

        if req.status not in (ExternalJobStatus.UNCERTAIN, ExternalJobStatus.SUBMITTED):
            now_iso = datetime.now(timezone.utc).isoformat()
            summary = self._budget_repo.get_budget_summary(req.project_id) or _zero_budget_summary(
                req.project_id, now_iso
            )
            return req, summary

        if not req.external_job_id:
            now_iso = datetime.now(timezone.utc).isoformat()
            summary = self._budget_repo.get_budget_summary(req.project_id) or _zero_budget_summary(
                req.project_id, now_iso
            )
            return req, summary

        provider = self._provider_repo.get_by_id(req.provider_id)
        if provider is None:
            raise ProviderNotFoundError(f"Provider '{req.provider_id}' not found.")

        api_key = (
            self._credential_vault.get_secret(provider.credential_ref)
            if provider.credential_ref
            else None
        )
        polled = self._provider_gateway.poll_operation(
            provider_type=provider.provider_type,
            base_url=provider.base_url,
            api_key=api_key,
            external_job_id=req.external_job_id,
        )
        return self._budget_guard.record_outcome(
            RecordSpendOutcomeInput(
                request_key=req.request_key,
                status=polled.status,
                external_job_id=polled.external_job_id or req.external_job_id,
                reported_cost_usd=polled.reported_cost_usd,
                error_message=redact_secrets(polled.error_message, [api_key]),
            )
        )
