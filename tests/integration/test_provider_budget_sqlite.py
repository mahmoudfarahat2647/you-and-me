"""Integration tests for SQLiteProviderRepository and SQLiteBudgetRepository concurrency & persistence."""
from concurrent.futures import ThreadPoolExecutor
import sys
import threading
import time

import httpx
import pytest

from src.adapters.providers.http_provider_gateway import HttpProviderGateway
from src.adapters.security.windows_dpapi_vault import WindowsDpapiVault
from src.adapters.storage.sqlite_budget_repository import SQLiteBudgetRepository
from src.adapters.storage.sqlite_provider_repository import SQLiteProviderRepository
from src.core.dto.provider_dto import (
    ConfigureProviderInput,
    ExecuteGuardedProviderCallInput,
    SetProjectBudgetInput,
    TestProviderConnectionInput,
)
from src.core.entities.budget import BudgetPolicyDecision, ExternalJobStatus
from src.core.entities.provider import ProviderCapability, ProviderType
from src.core.use_cases.budget_guard import (
    ExecuteGuardedProviderCallUseCase,
    GetProjectBudgetUseCase,
    SetProjectBudgetUseCase,
)
from src.core.use_cases.provider_use_cases import (
    ConfigureProviderUseCase,
    TestProviderConnectionUseCase,
)
from tests.unit.test_budget_guard import InMemoryCredentialVault


def _build_vault(tmp_path):
    if sys.platform == "win32":
        return WindowsDpapiVault(vault_path=tmp_path / "secrets.vault.json")
    return InMemoryCredentialVault()


def test_sqlite_concurrent_duplicate_requests_produce_single_paid_submission(tmp_path) -> None:
    db_file = tmp_path / "concurrent_guard.db"
    provider_repo = SQLiteProviderRepository(db_path=db_file)
    budget_repo = SQLiteBudgetRepository(db_path=db_file)
    vault = _build_vault(tmp_path)

    call_lock = threading.Lock()
    provider_calls = []

    def _transport_handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1beta/models":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "models/gemini-2.5-flash",
                            "supportedGenerationMethods": ["generateContent"],
                        }
                    ]
                },
            )
        if request.method == "POST" and request.url.path.endswith(":generateContent"):
            time.sleep(0.05)
            with call_lock:
                provider_calls.append(request.headers.get("x-request-key"))
            return httpx.Response(
                200,
                json={"responseId": "resp-sqlite-001", "cost_usd": 0.42},
            )
        return httpx.Response(404)

    gateway = HttpProviderGateway(transport=httpx.MockTransport(_transport_handler))
    provider = ConfigureProviderUseCase(provider_repo, vault).execute(
        ConfigureProviderInput(
            name="Gemini SQLite",
            provider_type=ProviderType.GEMINI,
            api_key="AIzaSySqliteConcurrencyKey1234",
        )
    )
    TestProviderConnectionUseCase(provider_repo, vault, gateway).execute(
        TestProviderConnectionInput(provider_id=provider.id)
    )
    SetProjectBudgetUseCase(budget_repo).execute(
        SetProjectBudgetInput(project_id="proj-sqlite-1", budget_limit_usd=2.0)
    )

    uc = ExecuteGuardedProviderCallUseCase(provider_repo, vault, gateway, budget_repo)
    barrier = threading.Barrier(10)

    def _run_concurrent(idx: int):
        barrier.wait()
        return uc.execute(
            ExecuteGuardedProviderCallInput(
                project_id="proj-sqlite-1",
                stage_run_id="stage-script-1",
                request_key="idemp-key-1" if idx < 5 else f"idemp-key-{idx}",
                provider_id=provider.id,
                operation=ProviderCapability.TEXT_GENERATION,
                model="gemini-2.5-flash",
                payload={"contents": [{"parts": [{"text": "Write intro"}]}]},
                estimated_cost_usd=0.50,
            )
        )

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(_run_concurrent, range(10)))

    assert len(provider_calls) == 1
    assert sum(1 for r in results if r.submitted) == 1

    # Reopen SQLiteBudgetRepository to verify durable ledger across restarts
    reopened_budget_repo = SQLiteBudgetRepository(db_path=db_file)
    summary = GetProjectBudgetUseCase(reopened_budget_repo).execute("proj-sqlite-1")
    assert summary is not None
    assert summary.spent_usd == 0.42
    assert summary.outstanding_reservations_usd == 0.0
    assert summary.remaining_budget_usd == 1.58

    requests = reopened_budget_repo.list_requests_by_project("proj-sqlite-1")
    assert len(requests) == 1
    assert requests[0].provider_id == provider.id
    assert requests[0].external_job_id == "resp-sqlite-001"
    assert requests[0].estimated_cost_usd == 0.50
    assert requests[0].reported_cost_usd == 0.42


def test_sqlite_competing_stages_never_exceed_project_budget(tmp_path) -> None:
    db_file = tmp_path / "budget_race.db"
    provider_repo = SQLiteProviderRepository(db_path=db_file)
    budget_repo = SQLiteBudgetRepository(db_path=db_file)
    vault = _build_vault(tmp_path)

    def _transport_handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "models/gemini-2.5-flash",
                            "supportedGenerationMethods": ["generateContent"],
                        }
                    ]
                },
            )
        time.sleep(0.03)
        return httpx.Response(200, json={"responseId": "resp-ok", "cost_usd": 0.40})

    gateway = HttpProviderGateway(transport=httpx.MockTransport(_transport_handler))
    provider = ConfigureProviderUseCase(provider_repo, vault).execute(
        ConfigureProviderInput(
            name="Gemini Race",
            provider_type=ProviderType.GEMINI,
            api_key="AIzaSyBudgetRaceKey9999",
        )
    )
    TestProviderConnectionUseCase(provider_repo, vault, gateway).execute(
        TestProviderConnectionInput(provider_id=provider.id)
    )
    # Budget allows at most 2 calls of $0.40 ($0.80 <= $1.00), 3rd must pause ($1.20 > $1.00)
    SetProjectBudgetUseCase(budget_repo).execute(
        SetProjectBudgetInput(project_id="proj-race", budget_limit_usd=1.00)
    )

    uc = ExecuteGuardedProviderCallUseCase(provider_repo, vault, gateway, budget_repo)
    barrier = threading.Barrier(6)

    def _run_stage(idx: int):
        barrier.wait()
        return uc.execute(
            ExecuteGuardedProviderCallInput(
                project_id="proj-race",
                stage_run_id=f"stage-independent-{idx}",
                request_key=f"req-independent-{idx}",
                provider_id=provider.id,
                operation=ProviderCapability.RESEARCH,
                model="gemini-2.5-flash",
                payload={"contents": [{"parts": [{"text": f"Topic {idx}"}]}]},
                estimated_cost_usd=0.40,
            )
        )

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(_run_stage, range(6)))

    submitted_count = sum(1 for r in results if r.submitted)
    paused_overrun = [
        r for r in results if not r.submitted and r.preflight.decision == BudgetPolicyDecision.PAUSE_BUDGET_EXCEEDED
    ]
    assert submitted_count == 2
    assert len(paused_overrun) == 4

    summary = budget_repo.get_budget_summary("proj-race")
    assert summary is not None
    assert summary.spent_usd == 0.80
    assert summary.remaining_budget_usd == 0.20


def test_sqlite_uncertain_outcome_persists_and_reconciles_across_restarts(tmp_path) -> None:
    db_file = tmp_path / "uncertain_reconcile.db"
    provider_repo = SQLiteProviderRepository(db_path=db_file)
    budget_repo = SQLiteBudgetRepository(db_path=db_file)
    vault = _build_vault(tmp_path)

    poll_calls = 0

    def _transport_handler(request: httpx.Request) -> httpx.Response:
        nonlocal poll_calls
        if request.method == "GET" and request.url.path == "/v1beta/models":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "models/veo-2.0-generate-001",
                            "supportedGenerationMethods": ["predictLongRunning"],
                        }
                    ]
                },
            )
        if request.method == "POST":
            return httpx.Response(
                504,
                headers={"x-request-id": "operations/veo-timeout-99"},
                text="Gateway timeout",
            )
        if request.method == "GET" and request.url.path == "/v1beta/operations/veo-timeout-99":
            poll_calls += 1
            return httpx.Response(
                200,
                json={
                    "name": "operations/veo-timeout-99",
                    "done": True,
                    "cost_usd": 0.95,
                },
            )
        return httpx.Response(404)

    gateway = HttpProviderGateway(transport=httpx.MockTransport(_transport_handler))
    provider = ConfigureProviderUseCase(provider_repo, vault).execute(
        ConfigureProviderInput(
            name="Gemini Veo",
            provider_type=ProviderType.GEMINI,
            api_key="AIzaSyVeoTimeoutKey2222",
        )
    )
    TestProviderConnectionUseCase(provider_repo, vault, gateway).execute(
        TestProviderConnectionInput(provider_id=provider.id)
    )
    SetProjectBudgetUseCase(budget_repo).execute(
        SetProjectBudgetInput(project_id="proj-veo", budget_limit_usd=2.00)
    )

    uc_1 = ExecuteGuardedProviderCallUseCase(provider_repo, vault, gateway, budget_repo)
    first = uc_1.execute(
        ExecuteGuardedProviderCallInput(
            project_id="proj-veo",
            stage_run_id="stage-veo",
            request_key="veo-req-1",
            provider_id=provider.id,
            operation=ProviderCapability.VIDEO_GENERATION,
            model="veo-2.0-generate-001",
            payload={"prompt": "City skyline"},
            estimated_cost_usd=1.10,
        )
    )
    assert first.submitted is True
    assert first.request_record is not None
    assert first.request_record.status == ExternalJobStatus.UNCERTAIN
    assert first.request_record.external_job_id == "operations/veo-timeout-99"

    # Reopen all adapters (simulating app restart) and reconcile uncertain job
    provider_repo_2 = SQLiteProviderRepository(db_path=db_file)
    budget_repo_2 = SQLiteBudgetRepository(db_path=db_file)
    vault_2 = WindowsDpapiVault(vault_path=tmp_path / "secrets.vault.json") if sys.platform == "win32" else vault
    uc_2 = ExecuteGuardedProviderCallUseCase(provider_repo_2, vault_2, gateway, budget_repo_2)

    # Retrying before reconciliation must pause
    blocked_retry = uc_2.execute(
        ExecuteGuardedProviderCallInput(
            project_id="proj-veo",
            stage_run_id="stage-veo",
            request_key="veo-req-2",
            provider_id=provider.id,
            operation=ProviderCapability.VIDEO_GENERATION,
            model="veo-2.0-generate-001",
            payload={"prompt": "City skyline"},
            estimated_cost_usd=1.10,
            is_retry=True,
        )
    )
    assert blocked_retry.submitted is False
    assert blocked_retry.preflight.decision == BudgetPolicyDecision.PAUSE_UNCERTAIN_OUTCOME

    reconciled_req, reconciled_summary = uc_2.reconcile_request("veo-req-1")
    assert poll_calls == 1
    assert reconciled_req.status == ExternalJobStatus.SUCCEEDED
    assert reconciled_req.reported_cost_usd == 0.95
    assert reconciled_summary.spent_usd == 0.95
    assert reconciled_summary.outstanding_reservations_usd == 0.0
    assert reconciled_summary.remaining_budget_usd == 1.05
