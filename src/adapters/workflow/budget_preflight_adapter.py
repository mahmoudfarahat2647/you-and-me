"""Adapter implementing ExecutionPreflightPort on top of BudgetGuardUseCase."""
from dataclasses import asdict
import math
from typing import Optional, Tuple

from src.core.dto.provider_dto import (
    ExternalRequestRecord,
    ProjectBudgetSummary,
    RecordSpendOutcomeInput,
    SpendPreflightInput,
    SpendPreflightResult,
)
from src.core.dto.workflow_dto import PreflightCheckInput, PreflightDecision
from src.core.entities.budget import ExternalJobStatus
from src.core.entities.provider import ProviderCapability, ProviderType
from src.core.ports.budget_repository import BudgetRepository
from src.core.ports.credential_vault import CredentialVaultPort
from src.core.ports.execution_preflight import ExecutionPreflightPort
from src.core.ports.provider_gateway import ProviderGateway
from src.core.ports.provider_repository import ProviderRepository
from src.core.use_cases.budget_guard import (
    BudgetGuardUseCase,
    ExecuteGuardedProviderCallUseCase,
)

_STAGE_CAPABILITY_MAP = {
    "idea": ProviderCapability.RESEARCH,
    "research": ProviderCapability.RESEARCH,
    "script": ProviderCapability.TEXT_GENERATION,
    "voice": ProviderCapability.TTS,
    "scenes": ProviderCapability.VIDEO_GENERATION,
    "edit": ProviderCapability.VIDEO_GENERATION,
    "export": ProviderCapability.VIDEO_GENERATION,
}

def _parse_optional_float(value: object) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        cost = float(value)  # type: ignore[arg-type]
        return cost if math.isfinite(cost) and cost >= 0 else None
    except (TypeError, ValueError):
        return None


class BudgetPreflightAdapter(ExecutionPreflightPort):
    """Bridges workflow stage preflight checks to BudgetGuardUseCase."""

    def __init__(
        self,
        budget_repo: BudgetRepository,
        provider_repo: Optional[ProviderRepository] = None,
        credential_vault: Optional[CredentialVaultPort] = None,
        provider_gateway: Optional[ProviderGateway] = None,
        default_max_retries: int = 2,
    ) -> None:
        self._budget_repo = budget_repo
        self._provider_repo = provider_repo
        self._credential_vault = credential_vault
        self._provider_gateway = provider_gateway
        self._default_max_retries = default_max_retries
        self._budget_guard = BudgetGuardUseCase(budget_repo)

    def check(self, request: PreflightCheckInput) -> PreflightDecision:
        if request.mode == "manual" or request.mode == "off":
            return PreflightDecision(allowed=True)

        provider_id = str(
            request.params.get("provider_id")
            or request.metadata.get("provider_id")
            or ""
        ).strip()

        has_cost_param = "estimated_cost_usd" in request.params
        estimated_cost_usd = _parse_optional_float(request.params.get("estimated_cost_usd"))
        has_metadata_cost = "estimated_cost_usd" in request.metadata
        if not has_cost_param and has_metadata_cost:
            estimated_cost_usd = _parse_optional_float(request.metadata.get("estimated_cost_usd"))

        # Phase 1's built-in stages use local inputs unless a provider or cost is configured.
        if not provider_id and (not (has_cost_param or has_metadata_cost) or estimated_cost_usd == 0):
            return PreflightDecision(allowed=True)

        provider = self._provider_repo.get_by_id(provider_id) if provider_id and self._provider_repo else None
        if provider is not None and provider.provider_type == ProviderType.LOCAL_OLLAMA:
            if estimated_cost_usd == 0 or not (has_cost_param or has_metadata_cost):
                return PreflightDecision(allowed=True)

        operation = _STAGE_CAPABILITY_MAP.get(request.stage_id, ProviderCapability.TEXT_GENERATION)
        stage_run_id = f"{request.job_id}:{request.stage_id}"
        request_key = f"{stage_run_id}:{request.attempt}"

        preflight: SpendPreflightResult = self._budget_guard.preflight_and_reserve(
            SpendPreflightInput(
                project_id=request.project_id,
                stage_run_id=stage_run_id,
                request_key=request_key,
                provider_id=provider_id or "unconfigured-provider",
                operation=operation,
                estimated_cost_usd=estimated_cost_usd,
                model=provider.selected_model if provider else None,
                is_retry=request.attempt > 1,
                max_retries=self._default_max_retries,
                explicit_approval=request.confirmation_key == request_key,
            )
        )

        if preflight.allowed:
            return PreflightDecision(allowed=True)

        actions = ",".join(preflight.available_actions)
        reason = f"{preflight.message} [decision={preflight.decision.value}; request_key={preflight.request_key}"
        if actions:
            reason += f"; actions={actions}"
        reason += "]"
        return PreflightDecision(
            allowed=False,
            reason=reason,
            requires_confirmation=preflight.requires_user_approval,
            details=asdict(preflight),
        )

    def record_completion(
        self,
        request_key: str,
        external_job_id: Optional[str] = None,
        reported_cost_usd: Optional[float] = None,
    ) -> Tuple[ExternalRequestRecord, ProjectBudgetSummary]:
        return self._budget_guard.record_outcome(
            RecordSpendOutcomeInput(
                request_key=request_key,
                status=ExternalJobStatus.SUCCEEDED,
                external_job_id=external_job_id,
                reported_cost_usd=reported_cost_usd,
            )
        )

    def record_failure(
        self,
        request_key: str,
        error_message: Optional[str] = None,
        reported_cost_usd: Optional[float] = 0.0,
    ) -> Tuple[ExternalRequestRecord, ProjectBudgetSummary]:
        return self._budget_guard.record_outcome(
            RecordSpendOutcomeInput(
                request_key=request_key,
                status=ExternalJobStatus.FAILED,
                reported_cost_usd=reported_cost_usd,
                error_message=error_message,
            )
        )

    def mark_uncertain(
        self,
        request_key: str,
        external_job_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Tuple[ExternalRequestRecord, ProjectBudgetSummary]:
        return self._budget_guard.record_outcome(
            RecordSpendOutcomeInput(
                request_key=request_key,
                status=ExternalJobStatus.UNCERTAIN,
                external_job_id=external_job_id,
                error_message=error_message,
            )
        )

    def reconcile_request(
        self, request_key: str
    ) -> Tuple[ExternalRequestRecord, ProjectBudgetSummary]:
        if (
            self._provider_repo is not None
            and self._credential_vault is not None
            and self._provider_gateway is not None
        ):
            uc = ExecuteGuardedProviderCallUseCase(
                provider_repo=self._provider_repo,
                credential_vault=self._credential_vault,
                provider_gateway=self._provider_gateway,
                budget_repo=self._budget_repo,
            )
            return uc.reconcile_request(request_key)

        req = self._budget_repo.get_request_by_key(request_key)
        if req is None:
            raise ValueError(f"Request '{request_key}' not found.")
        summary = self._budget_repo.get_budget_summary(req.project_id)
        if summary is None:
            raise ValueError(f"Budget for project '{req.project_id}' not found.")
        return req, summary
