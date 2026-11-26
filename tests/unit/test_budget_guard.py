"""Unit tests for BudgetGuardUseCase, ExecuteGuardedProviderCallUseCase, and Clean Architecture."""
import ast
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import threading
import time
from typing import Callable, Dict, List, Optional, TypeVar

import pytest

from src.core.dto.provider_dto import (
    ConfigureProviderInput,
    ExecuteGuardedProviderCallInput,
    ExecuteGuardedProviderCallResult,
    ExternalRequestRecord,
    GatewayConnectionProbeResult,
    ProjectBudgetSummary,
    ProviderOperationRequest,
    ProviderOperationResponse,
    ProviderSummaryResult,
    RecordSpendOutcomeInput,
    SetProjectBudgetInput,
    SpendPreflightInput,
    SpendReservationRecord,
    TestProviderConnectionInput,
)
from src.core.entities.budget import (
    BudgetPolicyDecision,
    ExternalJobStatus,
    ReservationStatus,
    round_usd,
)
from src.core.entities.provider import (
    ProviderCapability,
    ProviderType,
)
from src.core.ports.budget_repository import BudgetRepository, BudgetTransaction
from src.core.ports.credential_vault import CredentialVaultPort
from src.core.ports.provider_gateway import ProviderGateway
from src.core.ports.provider_repository import ProviderRepository
from src.core.use_cases.budget_guard import (
    BudgetGuardUseCase,
    ExecuteGuardedProviderCallUseCase,
    SetProjectBudgetUseCase,
)
from src.core.use_cases.provider_use_cases import (
    ConfigureProviderUseCase,
    TestProviderConnectionUseCase,
)

T = TypeVar("T")


class InMemoryCredentialVault(CredentialVaultPort):
    def __init__(self) -> None:
        self._secrets: Dict[str, str] = {}

    def store_secret(self, credential_ref: str, secret: str) -> None:
        self._secrets[credential_ref] = secret

    def get_secret(self, credential_ref: str) -> Optional[str]:
        return self._secrets.get(credential_ref)

    def delete_secret(self, credential_ref: str) -> bool:
        return self._secrets.pop(credential_ref, None) is not None

    def has_secret(self, credential_ref: str) -> bool:
        return credential_ref in self._secrets


class InMemoryProviderRepository(ProviderRepository):
    def __init__(self) -> None:
        self._providers: Dict[str, ProviderSummaryResult] = {}

    def save(self, provider: ProviderSummaryResult) -> None:
        self._providers[provider.id] = provider

    def get_by_id(self, provider_id: str) -> Optional[ProviderSummaryResult]:
        return self._providers.get(provider_id)

    def list_all(self) -> List[ProviderSummaryResult]:
        return sorted(self._providers.values(), key=lambda p: p.updated_at, reverse=True)

    def delete(self, provider_id: str) -> bool:
        return self._providers.pop(provider_id, None) is not None


class InMemoryBudgetTransaction(BudgetTransaction):
    def __init__(self, repo: "InMemoryBudgetRepository") -> None:
        self._repo = repo

    def get_budget_snapshot(self, project_id: str) -> Optional[ProjectBudgetSummary]:
        budget = self._repo._budgets.get(project_id)
        if budget is None:
            return None
        limit, spent, updated_at = budget
        outstanding = round_usd(
            sum(
                r.reserved_usd
                for r in self._repo._reservations.values()
                if r.project_id == project_id
                and r.status in (ReservationStatus.ACTIVE, ReservationStatus.UNCERTAIN)
            )
        )
        remaining = max(0.0, round_usd(limit - spent))
        available = max(0.0, round_usd(limit - spent - outstanding))
        return ProjectBudgetSummary(
            project_id=project_id,
            budget_limit_usd=limit,
            spent_usd=spent,
            outstanding_reservations_usd=outstanding,
            remaining_budget_usd=remaining,
            available_budget_usd=available,
            updated_at=updated_at,
        )

    def upsert_budget(
        self, project_id: str, budget_limit_usd: float, updated_at: str
    ) -> ProjectBudgetSummary:
        _, spent, _ = self._repo._budgets.get(project_id, (0.0, 0.0, updated_at))
        self._repo._budgets[project_id] = (round_usd(budget_limit_usd), spent, updated_at)
        summary = self.get_budget_snapshot(project_id)
        assert summary is not None
        return summary

    def get_request_by_key(self, request_key: str) -> Optional[ExternalRequestRecord]:
        return self._repo._requests.get(request_key)

    def get_reservation_by_key(self, request_key: str) -> Optional[SpendReservationRecord]:
        return self._repo._reservations.get(request_key)

    def list_requests_for_stage(self, stage_run_id: str) -> List[ExternalRequestRecord]:
        return [r for r in self._repo._requests.values() if r.stage_run_id == stage_run_id]

    def create_reservation_and_request(
        self, reservation: SpendReservationRecord, request: ExternalRequestRecord
    ) -> None:
        if request.request_key in self._repo._requests:
            raise RuntimeError(f"Duplicate request_key {request.request_key}")
        self._repo._reservations[reservation.request_key] = reservation
        self._repo._requests[request.request_key] = request

    def update_request_and_reservation(
        self,
        request: ExternalRequestRecord,
        reservation_status: ReservationStatus,
        settled_usd: Optional[float],
        delta_spent_usd: float,
        now_iso: str,
    ) -> ProjectBudgetSummary:
        self._repo._requests[request.request_key] = request
        res = self._repo._reservations[request.request_key]
        self._repo._reservations[request.request_key] = SpendReservationRecord(
            id=res.id,
            project_id=res.project_id,
            stage_run_id=res.stage_run_id,
            request_key=res.request_key,
            provider_id=res.provider_id,
            reserved_usd=res.reserved_usd,
            settled_usd=settled_usd,
            status=reservation_status,
            created_at=res.created_at,
            updated_at=now_iso,
        )
        limit, spent, _ = self._repo._budgets.get(request.project_id, (0.0, 0.0, now_iso))
        self._repo._budgets[request.project_id] = (
            limit,
            round_usd(spent + delta_spent_usd),
            now_iso,
        )
        summary = self.get_budget_snapshot(request.project_id)
        assert summary is not None
        return summary


class InMemoryBudgetRepository(BudgetRepository):
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._budgets: Dict[str, tuple[float, float, str]] = {}
        self._reservations: Dict[str, SpendReservationRecord] = {}
        self._requests: Dict[str, ExternalRequestRecord] = {}

    def run_atomic(self, fn: Callable[[BudgetTransaction], T]) -> T:
        with self._lock:
            return fn(InMemoryBudgetTransaction(self))

    def get_budget_summary(self, project_id: str) -> Optional[ProjectBudgetSummary]:
        with self._lock:
            return InMemoryBudgetTransaction(self).get_budget_snapshot(project_id)

    def get_request_by_key(self, request_key: str) -> Optional[ExternalRequestRecord]:
        with self._lock:
            return self._requests.get(request_key)

    def list_requests_by_project(self, project_id: str) -> List[ExternalRequestRecord]:
        with self._lock:
            return [r for r in self._requests.values() if r.project_id == project_id]

    def list_reservations_by_project(self, project_id: str) -> List[SpendReservationRecord]:
        with self._lock:
            return [r for r in self._reservations.values() if r.project_id == project_id]


class StubProviderGateway(ProviderGateway):
    def __init__(self, handler: Optional[Callable[[ProviderOperationRequest], ProviderOperationResponse]] = None) -> None:
        self.submission_count = 0
        self.submitted_keys: List[str] = []
        self._count_lock = threading.Lock()
        self._handler = handler
        self.poll_response: Optional[ProviderOperationResponse] = None

    def test_connection(
        self, provider_type: ProviderType, base_url: str, api_key: Optional[str]
    ) -> GatewayConnectionProbeResult:
        return GatewayConnectionProbeResult(
            success=True,
            supported_capabilities=(
                ProviderCapability.TEXT_GENERATION,
                ProviderCapability.RESEARCH,
                ProviderCapability.VIDEO_GENERATION,
            ),
            verified_models=("gemini-2.5-flash", "veo-2.0-generate-001"),
            message="OK",
            endpoint_checked=base_url,
        )

    def submit_operation(self, request: ProviderOperationRequest) -> ProviderOperationResponse:
        with self._count_lock:
            self.submission_count += 1
            self.submitted_keys.append(request.request_key)
        if self._handler is not None:
            return self._handler(request)
        return ProviderOperationResponse(
            accepted=True,
            external_job_id=f"job-{request.request_key}",
            status=ExternalJobStatus.SUCCEEDED,
            output_summary="Done",
            reported_cost_usd=0.25,
        )

    def poll_operation(
        self, provider_type: ProviderType, base_url: str, api_key: Optional[str], external_job_id: str
    ) -> ProviderOperationResponse:
        if self.poll_response is not None:
            return self.poll_response
        return ProviderOperationResponse(
            accepted=True,
            external_job_id=external_job_id,
            status=ExternalJobStatus.SUCCEEDED,
            output_summary="Reconciled",
            reported_cost_usd=0.40,
        )


def _setup_verified_provider(
    provider_repo: InMemoryProviderRepository,
    vault: InMemoryCredentialVault,
    gateway: ProviderGateway,
) -> ProviderSummaryResult:
    configured = ConfigureProviderUseCase(provider_repo, vault).execute(
        ConfigureProviderInput(
            name="Gemini Primary",
            provider_type=ProviderType.GEMINI,
            api_key="AIzaSyTestSecretKey9876",
        )
    )
    TestProviderConnectionUseCase(provider_repo, vault, gateway).execute(
        TestProviderConnectionInput(provider_id=configured.id)
    )
    provider = provider_repo.get_by_id(configured.id)
    assert provider is not None
    return provider


def test_core_layer_has_no_framework_or_adapter_imports() -> None:
    forbidden = {"fastapi", "pydantic", "sqlite3", "ctypes", "httpx", "urllib"}
    core_root = Path("src/core")
    for py_file in core_root.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    assert top not in forbidden, f"{py_file} imports forbidden module {top}"
                    assert not alias.name.startswith("src.adapters"), f"{py_file} imports adapter"
            elif isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                assert top not in forbidden, f"{py_file} imports forbidden module {top}"
                assert not node.module.startswith("src.adapters"), f"{py_file} imports adapter"


def test_unknown_cost_pauses_unless_explicit_approval_is_given() -> None:
    budget_repo = InMemoryBudgetRepository()
    SetProjectBudgetUseCase(budget_repo).execute(
        SetProjectBudgetInput(project_id="proj-1", budget_limit_usd=5.0)
    )
    guard = BudgetGuardUseCase(budget_repo)

    paused = guard.preflight_and_reserve(
        SpendPreflightInput(
            project_id="proj-1",
            stage_run_id="stage-research-1",
            request_key="req-unknown-1",
            provider_id="prov-1",
            operation=ProviderCapability.RESEARCH,
            estimated_cost_usd=None,
        )
    )

    assert paused.allowed is False
    assert paused.decision == BudgetPolicyDecision.PAUSE_UNKNOWN_COST
    assert paused.requires_user_approval is True
    assert paused.allows_manual_fallback is True
    assert "approve_and_submit" in paused.available_actions
    assert "switch_to_manual" in paused.available_actions
    assert budget_repo.get_request_by_key("req-unknown-1") is None

    approved = guard.preflight_and_reserve(
        SpendPreflightInput(
            project_id="proj-1",
            stage_run_id="stage-research-1",
            request_key="req-unknown-approved-1",
            provider_id="prov-1",
            operation=ProviderCapability.RESEARCH,
            estimated_cost_usd=None,
            explicit_approval=True,
            approved_cost_cap_usd=1.25,
        )
    )
    assert approved.allowed is True
    assert approved.decision == BudgetPolicyDecision.APPROVED
    assert approved.reserved_amount_usd == 1.25

    req, summary = guard.record_outcome(
        RecordSpendOutcomeInput(
            request_key="req-unknown-approved-1",
            status=ExternalJobStatus.SUCCEEDED,
            external_job_id="ext-101",
            reported_cost_usd=0.80,
        )
    )
    assert req.explicitly_approved is True
    assert req.reported_cost_usd == 0.80
    assert summary.spent_usd == 0.80
    assert summary.outstanding_reservations_usd == 0.0
    assert summary.remaining_budget_usd == 4.20


def test_budget_overrun_accounts_for_spent_and_outstanding_reservations() -> None:
    budget_repo = InMemoryBudgetRepository()
    SetProjectBudgetUseCase(budget_repo).execute(
        SetProjectBudgetInput(project_id="proj-2", budget_limit_usd=2.0)
    )
    guard = BudgetGuardUseCase(budget_repo)

    # First call succeeds and spends $0.80 -> remaining = $1.20
    p1 = guard.preflight_and_reserve(
        SpendPreflightInput(
            project_id="proj-2",
            stage_run_id="stage-1",
            request_key="req-1",
            provider_id="prov-1",
            operation=ProviderCapability.TEXT_GENERATION,
            estimated_cost_usd=0.80,
        )
    )
    assert p1.allowed is True
    guard.record_outcome(
        RecordSpendOutcomeInput(
            request_key="req-1",
            status=ExternalJobStatus.SUCCEEDED,
            reported_cost_usd=0.80,
        )
    )

    # Second call reserves $0.75 (still active) -> remaining=$1.20, outstanding=$0.75
    p2 = guard.preflight_and_reserve(
        SpendPreflightInput(
            project_id="proj-2",
            stage_run_id="stage-2",
            request_key="req-2",
            provider_id="prov-1",
            operation=ProviderCapability.VIDEO_GENERATION,
            estimated_cost_usd=0.75,
        )
    )
    assert p2.allowed is True
    assert p2.outstanding_reservations_usd == 0.75

    # Third call needs $0.60: 0.60 + 0.75 = 1.35 > 1.20 remaining -> PAUSE_BUDGET_EXCEEDED
    p3 = guard.preflight_and_reserve(
        SpendPreflightInput(
            project_id="proj-2",
            stage_run_id="stage-3",
            request_key="req-3",
            provider_id="prov-1",
            operation=ProviderCapability.VIDEO_GENERATION,
            estimated_cost_usd=0.60,
        )
    )
    assert p3.allowed is False
    assert p3.decision == BudgetPolicyDecision.PAUSE_BUDGET_EXCEEDED
    assert p3.requires_user_approval is True
    assert p3.allows_manual_fallback is True
    assert p3.outstanding_reservations_usd == 0.75
    assert p3.remaining_budget_usd == 1.20

    # When stage-2 fails and releases its $0.75 reservation, stage-3 fits within $1.20!
    guard.record_outcome(
        RecordSpendOutcomeInput(
            request_key="req-2",
            status=ExternalJobStatus.FAILED,
            reported_cost_usd=0.0,
        )
    )
    p3_retry = guard.preflight_and_reserve(
        SpendPreflightInput(
            project_id="proj-2",
            stage_run_id="stage-3",
            request_key="req-3-after-release",
            provider_id="prov-1",
            operation=ProviderCapability.VIDEO_GENERATION,
            estimated_cost_usd=0.60,
        )
    )
    assert p3_retry.allowed is True


def test_capped_retries_enforced_and_blocked_after_limit() -> None:
    budget_repo = InMemoryBudgetRepository()
    SetProjectBudgetUseCase(budget_repo).execute(
        SetProjectBudgetInput(project_id="proj-retry", budget_limit_usd=10.0)
    )
    guard = BudgetGuardUseCase(budget_repo)

    # Attempt 1 + 2 retries allowed (max_retries=2)
    for idx, key in enumerate(["r0", "r1", "r2"]):
        res = guard.preflight_and_reserve(
            SpendPreflightInput(
                project_id="proj-retry",
                stage_run_id="stage-retry-1",
                request_key=key,
                provider_id="prov-1",
                operation=ProviderCapability.TEXT_GENERATION,
                estimated_cost_usd=0.10,
                is_retry=(idx > 0),
                max_retries=2,
            )
        )
        assert res.allowed is True
        guard.record_outcome(
            RecordSpendOutcomeInput(
                request_key=key,
                status=ExternalJobStatus.FAILED,
                reported_cost_usd=0.0,
                error_message="Transient 429",
            )
        )

    # Retry 3 exceeds max_retries=2
    blocked = guard.preflight_and_reserve(
        SpendPreflightInput(
            project_id="proj-retry",
            stage_run_id="stage-retry-1",
            request_key="r3",
            provider_id="prov-1",
            operation=ProviderCapability.TEXT_GENERATION,
            estimated_cost_usd=0.10,
            is_retry=True,
            max_retries=2,
        )
    )
    assert blocked.allowed is False
    assert blocked.decision == BudgetPolicyDecision.BLOCKED_MAX_RETRIES
    assert blocked.allows_manual_fallback is True


def test_uncertain_outcome_locks_reservation_blocks_duplicate_retry_and_reconciles() -> None:
    budget_repo = InMemoryBudgetRepository()
    provider_repo = InMemoryProviderRepository()
    vault = InMemoryCredentialVault()

    def _timeout_then_poll(req: ProviderOperationRequest) -> ProviderOperationResponse:
        return ProviderOperationResponse(
            accepted=False,
            external_job_id="operations/veo-job-77",
            status=ExternalJobStatus.UNCERTAIN,
            error_message="Gateway read timeout after request dispatch",
        )

    gateway = StubProviderGateway(handler=_timeout_then_poll)
    provider = _setup_verified_provider(provider_repo, vault, gateway)
    SetProjectBudgetUseCase(budget_repo).execute(
        SetProjectBudgetInput(project_id="proj-uncertain", budget_limit_usd=3.0)
    )
    uc = ExecuteGuardedProviderCallUseCase(provider_repo, vault, gateway, budget_repo)

    first = uc.execute(
        ExecuteGuardedProviderCallInput(
            project_id="proj-uncertain",
            stage_run_id="stage-veo-1",
            request_key="req-veo-1",
            provider_id=provider.id,
            operation=ProviderCapability.VIDEO_GENERATION,
            model="veo-2.0-generate-001",
            payload={"prompt": "Golden dunes"},
            estimated_cost_usd=1.50,
            max_retries=2,
        )
    )
    assert first.submitted is True
    assert first.request_record is not None
    assert first.request_record.status == ExternalJobStatus.UNCERTAIN
    assert first.request_record.external_job_id == "operations/veo-job-77"
    assert first.budget_summary.outstanding_reservations_usd == 1.50
    assert first.budget_summary.available_budget_usd == 1.50

    # Retrying while UNCERTAIN must pause and NEVER submit a second paid call
    retry = uc.execute(
        ExecuteGuardedProviderCallInput(
            project_id="proj-uncertain",
            stage_run_id="stage-veo-1",
            request_key="req-veo-2",
            provider_id=provider.id,
            operation=ProviderCapability.VIDEO_GENERATION,
            model="veo-2.0-generate-001",
            payload={"prompt": "Golden dunes"},
            estimated_cost_usd=1.50,
            is_retry=True,
            max_retries=2,
        )
    )
    assert retry.submitted is False
    assert retry.preflight.decision == BudgetPolicyDecision.PAUSE_UNCERTAIN_OUTCOME
    assert gateway.submission_count == 1

    # Reconcile uncertain request via external_job_id polling
    gateway.poll_response = ProviderOperationResponse(
        accepted=True,
        external_job_id="operations/veo-job-77",
        status=ExternalJobStatus.SUCCEEDED,
        output_summary="Video ready",
        reported_cost_usd=1.35,
    )
    reconciled_req, reconciled_budget = uc.reconcile_request("req-veo-1")
    assert reconciled_req.status == ExternalJobStatus.SUCCEEDED
    assert reconciled_req.reported_cost_usd == 1.35
    assert reconciled_budget.spent_usd == 1.35
    assert reconciled_budget.outstanding_reservations_usd == 0.0
    assert reconciled_budget.remaining_budget_usd == 1.65


def test_concurrent_duplicate_requests_never_submit_twice() -> None:
    budget_repo = InMemoryBudgetRepository()
    provider_repo = InMemoryProviderRepository()
    vault = InMemoryCredentialVault()

    def _slow_submit(req: ProviderOperationRequest) -> ProviderOperationResponse:
        time.sleep(0.05)
        return ProviderOperationResponse(
            accepted=True,
            external_job_id="job-unique-1",
            status=ExternalJobStatus.SUCCEEDED,
            reported_cost_usd=0.50,
        )

    gateway = StubProviderGateway(handler=_slow_submit)
    provider = _setup_verified_provider(provider_repo, vault, gateway)
    SetProjectBudgetUseCase(budget_repo).execute(
        SetProjectBudgetInput(project_id="proj-conc", budget_limit_usd=5.0)
    )
    uc = ExecuteGuardedProviderCallUseCase(provider_repo, vault, gateway, budget_repo)

    barrier = threading.Barrier(8)

    def _worker(idx: int) -> ExecuteGuardedProviderCallResult:
        barrier.wait()
        return uc.execute(
            ExecuteGuardedProviderCallInput(
                project_id="proj-conc",
                stage_run_id="stage-conc-1",
                # Mix identical request_key and distinct request_keys on same stage_run_id
                request_key="same-key" if idx < 4 else f"distinct-key-{idx}",
                provider_id=provider.id,
                operation=ProviderCapability.TEXT_GENERATION,
                model="gemini-2.5-flash",
                payload={"prompt": "Hello"},
                estimated_cost_usd=0.50,
            )
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_worker, range(8)))

    submitted = [r for r in results if r.submitted]
    assert len(submitted) == 1
    assert gateway.submission_count == 1
    summary = budget_repo.get_budget_summary("proj-conc")
    assert summary is not None
    assert summary.spent_usd == 0.50
    assert summary.outstanding_reservations_usd == 0.0
