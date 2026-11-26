"""Integration tests for Providers/Budget API routes and WorkflowEngine BudgetPreflightAdapter."""
from concurrent.futures import ThreadPoolExecutor
import logging
import sys
import threading
from typing import Dict, List

import httpx
import pytest

from src.adapters.api.app import create_app
from src.adapters.providers.http_provider_gateway import HttpProviderGateway
from src.adapters.security.windows_dpapi_vault import WindowsDpapiVault
from src.adapters.storage.sqlite_budget_repository import SQLiteBudgetRepository
from src.adapters.storage.sqlite_provider_repository import SQLiteProviderRepository
from src.adapters.workflow.budget_preflight_adapter import BudgetPreflightAdapter
from src.core.dto.workflow_dto import (
    CheckStageRunInput,
    CreateWorkflowJobInput,
    StageArtifactDto,
    StageConfigInput,
    StageExecutionInput,
    StageExecutionResult,
    StageRunStatusResult,
    WorkflowJobResult,
)
from src.core.entities.workflow import JobStatus, StageStatus
from src.core.ports.stage_executor import StageExecutor
from src.core.ports.workflow_repository import WorkflowRepository
from src.core.use_cases.workflow_engine import WorkflowEngine
from tests.unit.test_budget_guard import InMemoryCredentialVault


def _mock_gemini_gateway(expected_secret: str) -> HttpProviderGateway:
    def _handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1beta/models":
            if request.headers.get("x-goog-api-key") != expected_secret:
                return httpx.Response(401, text=f"Invalid key {expected_secret}")
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "models/gemini-2.5-flash",
                            "supportedGenerationMethods": ["generateContent"],
                        },
                        {
                            "name": "models/veo-2.0-generate-001",
                            "supportedGenerationMethods": ["predictLongRunning"],
                        },
                    ]
                },
            )
        if request.method == "GET" and request.url.path == "/v1beta/operations/ext-job-42":
            return httpx.Response(
                200,
                json={"name": "operations/ext-job-42", "done": True, "cost_usd": 0.65},
            )
        return httpx.Response(404)

    return HttpProviderGateway(transport=httpx.MockTransport(_handler))


async def test_providers_api_dpapi_reload_and_zero_plaintext_secrets(tmp_path, caplog) -> None:
    db_file = tmp_path / "studio.db"
    vault_file = tmp_path / "secrets.vault.json"
    secret = "AIzaSyApiRouteSecretValue-8899"

    app1 = create_app(
        db_path=str(db_file),
        vault_path=vault_file,
        credential_vault=None if sys.platform == "win32" else InMemoryCredentialVault(),
        provider_gateway=_mock_gemini_gateway(secret),
    )

    with caplog.at_level(logging.DEBUG):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app1), base_url="http://testserver"
        ) as client:
            create_resp = await client.post(
                "/api/providers",
                json={
                    "name": "Gemini Main",
                    "provider_type": "gemini",
                    "api_key": secret,
                },
            )
            assert create_resp.status_code == 201
            created = create_resp.json()
            assert created["credential_preview"] == "••••8899"
            assert created["credential_status"] == "stored"
            assert secret not in create_resp.text

            list_resp = await client.get("/api/providers")
            assert list_resp.status_code == 200
            assert secret not in list_resp.text

    # Simulate app restart with fresh app + SQLite + DPAPI vault reading from disk
    if sys.platform == "win32":
        app2 = create_app(
            db_path=str(db_file),
            vault_path=vault_file,
            provider_gateway=_mock_gemini_gateway(secret),
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app2), base_url="http://testserver"
        ) as client2:
            test_resp = await client2.post(f"/api/providers/{created['id']}/test")
            assert test_resp.status_code == 200
            tested = test_resp.json()
            assert tested["success"] is True
            assert tested["connection_status"] == "verified"
            assert "video_generation" in tested["supported_capabilities"]
            assert "veo-2.0-generate-001" in tested["verified_models"]
            assert secret not in test_resp.text

            model_resp = await client2.put(
                f"/api/providers/{created['id']}/model",
                json={"model": "veo-2.0-generate-001"},
            )
            assert model_resp.status_code == 200
            assert model_resp.json()["selected_model"] == "veo-2.0-generate-001"

        assert secret.encode("utf-8") not in db_file.read_bytes()
        assert secret not in vault_file.read_text(encoding="utf-8")

    for rec in caplog.records:
        assert secret not in rec.getMessage()


async def test_budget_and_spend_api_pause_approve_and_reconcile(tmp_path) -> None:
    db_file = tmp_path / "budget_api.db"
    vault_file = tmp_path / "secrets.vault.json"
    secret = "AIzaSyBudgetApiKey1234"

    app = create_app(
        db_path=str(db_file),
        vault_path=vault_file,
        credential_vault=None if sys.platform == "win32" else InMemoryCredentialVault(),
        provider_gateway=_mock_gemini_gateway(secret),
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        prov_resp = await client.post(
            "/api/providers",
            json={"name": "Gemini", "provider_type": "gemini", "api_key": secret},
        )
        provider_id = prov_resp.json()["id"]

        budget_resp = await client.put(
            "/api/projects/proj-api-1/budget",
            json={"budget_limit_usd": 1.50},
        )
        assert budget_resp.status_code == 200
        assert budget_resp.json()["remaining_budget_usd"] == 1.50

        # 1. Unknown cost pauses
        unknown_resp = await client.post(
            "/api/projects/proj-api-1/spend/preflight",
            json={
                "stage_run_id": "stage-idea-1",
                "request_key": "req-unknown-api",
                "provider_id": provider_id,
                "operation": "research",
                "estimated_cost_usd": None,
            },
        )
        assert unknown_resp.status_code == 200
        unknown_data = unknown_resp.json()
        assert unknown_data["allowed"] is False
        assert unknown_data["decision"] == "pause_unknown_cost"
        assert unknown_data["requires_user_approval"] is True

        # 2. Explicit approval authorizes reservation
        approve_resp = await client.post(
            "/api/projects/proj-api-1/spend/req-unknown-api/approve",
            json={
                "stage_run_id": "stage-idea-1",
                "provider_id": provider_id,
                "operation": "research",
                "approved_cost_cap_usd": 0.90,
            },
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["allowed"] is True
        assert approve_resp.json()["outstanding_reservations_usd"] == 0.90

        # 3. Second request ($0.80) + active reservation ($0.90) = $1.70 > $1.50 -> overrun pause
        overrun_resp = await client.post(
            "/api/projects/proj-api-1/spend/preflight",
            json={
                "stage_run_id": "stage-scenes-1",
                "request_key": "req-overrun-api",
                "provider_id": provider_id,
                "operation": "video_generation",
                "estimated_cost_usd": 0.80,
            },
        )
        assert overrun_resp.status_code == 200
        assert overrun_resp.json()["allowed"] is False
        assert overrun_resp.json()["decision"] == "pause_budget_exceeded"

        # 4. Reconcile req-unknown-api as uncertain -> then poll external_job_id to settle
        uncertain_resp = await client.post(
            "/api/projects/proj-api-1/spend/req-unknown-api/reconcile",
            json={
                "status": "uncertain",
                "external_job_id": "operations/ext-job-42",
                "error_message": "Read timeout",
            },
        )
        assert uncertain_resp.status_code == 200
        assert uncertain_resp.json()["request"]["status"] == "uncertain"

        poll_reconcile_resp = await client.post(
            "/api/projects/proj-api-1/spend/req-unknown-api/reconcile",
            json={},
        )
        assert poll_reconcile_resp.status_code == 200
        reconciled = poll_reconcile_resp.json()
        assert reconciled["request"]["status"] == "succeeded"
        assert reconciled["request"]["reported_cost_usd"] == 0.65
        assert reconciled["budget"]["spent_usd"] == 0.65
        assert reconciled["budget"]["outstanding_reservations_usd"] == 0.0
        assert reconciled["budget"]["remaining_budget_usd"] == 0.85

        ledger_resp = await client.get("/api/projects/proj-api-1/spend")
        assert ledger_resp.status_code == 200
        assert len(ledger_resp.json()["requests"]) == 1


class _InMemoryWorkflowRepo(WorkflowRepository):
    def __init__(self) -> None:
        self._jobs: Dict[str, WorkflowJobResult] = {}

    def save(self, job: WorkflowJobResult) -> None:
        self._jobs[job.id] = job

    def get_by_id(self, job_id: str) -> WorkflowJobResult | None:
        return self._jobs.get(job_id)

    def list_by_project(self, project_id: str) -> List[WorkflowJobResult]:
        return [j for j in self._jobs.values() if j.project_id == project_id]

    def delete(self, job_id: str) -> bool:
        return self._jobs.pop(job_id, None) is not None


class _RecordingStageExecutor(StageExecutor):
    def __init__(self) -> None:
        self.calls: List[str] = []

    def execute(self, stage_input: StageExecutionInput) -> StageExecutionResult:
        self.calls.append(stage_input.stage_id)
        return StageExecutionResult(
            status=StageStatus.COMPLETED.value,
            artifact=StageArtifactDto(
                artifact_id=f"art-{stage_input.stage_id}",
                stage_id=stage_input.stage_id,
                artifact_type=stage_input.artifact_type,
                data={"ok": True},
            ),
        )

    def check_run_status(self, query: CheckStageRunInput) -> StageRunStatusResult:
        return StageRunStatusResult(status=StageStatus.UNKNOWN_OUTCOME.value)


def test_workflow_engine_with_budget_preflight_adapter_pauses_before_submission(tmp_path) -> None:
    budget_repo = SQLiteBudgetRepository(db_path=tmp_path / "wf_budget.db")
    provider_repo = SQLiteProviderRepository(db_path=tmp_path / "wf_budget.db")
    preflight = BudgetPreflightAdapter(budget_repo=budget_repo, provider_repo=provider_repo)

    workflow_repo = _InMemoryWorkflowRepo()
    executor = _RecordingStageExecutor()
    engine = WorkflowEngine(workflow_repo, executor, preflight=preflight)

    # Create job with only 'idea' auto and unknown cost (no estimated_cost_usd) -> must PAUSE before executor!
    job = engine.create_job(
        CreateWorkflowJobInput(
            project_id="proj-wf-1",
            stage_configs={
                "idea": StageConfigInput(mode="auto", params={"provider_id": "prov-1"}),
                "script": StageConfigInput(mode="manual"),
                "voice": StageConfigInput(mode="manual"),
                "scenes": StageConfigInput(mode="manual"),
                "edit": StageConfigInput(mode="manual"),
                "export": StageConfigInput(mode="manual"),
            },
            auto_start=True,
        )
    )

    assert job.status == JobStatus.PAUSED
    assert executor.calls == []
    assert job.error is not None
    assert "pause_unknown_cost" in job.error
    assert "approve_and_submit" in job.error

    # Confirm this specific request and resume.
    resumed = engine.resume(job.id, confirmation_key=f"{job.id}:idea:1")
    assert executor.calls == ["idea"]
    idea_stage = resumed.get_stage("idea")
    assert idea_stage is not None
    assert idea_stage.status == StageStatus.COMPLETED


@pytest.mark.parametrize(
    ("stage_params", "expected_decision"),
    [
        ({"provider_id": "paid-provider", "explicit_approval": True}, "pause_unknown_cost"),
        ({"provider_id": "paid-provider", "estimated_cost_usd": 2.0}, "pause_budget_exceeded"),
    ],
)
async def test_default_workflow_preflight_pauses_and_requires_matching_confirmation(
    tmp_path, stage_params, expected_decision,
) -> None:
    db_file = tmp_path / "workflow_budget.db"
    executor = _RecordingStageExecutor()
    app = create_app(db_path=str(db_file), stage_executor=executor)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        project = (await client.post("/api/projects", json={"name": "Spend review"})).json()
        project_path = f"/api/projects/{project['id']}"
        workflow_path = f"{project_path}/workflow"
        settings = await client.patch(f"{project_path}/settings", json={
            "stage_params": {"idea": stage_params},
            "stage_modes": {"script": "manual"},
        })
        assert settings.status_code == 200
        assert (await client.put(f"{project_path}/budget", json={"budget_limit_usd": 1})).status_code == 200
        result = await client.post(f"{workflow_path}/run")
        assert result.status_code == 200, result.text
        blocked = result.json()["job"]
        assert blocked["status"] == "paused"
        assert blocked["budget_block"]["stage_id"] == "idea"
        preflight = blocked["budget_block"]["preflight"]
        assert preflight["decision"] == expected_decision
        assert executor.calls == []
        assert (await client.get(workflow_path)).json()["job"]["budget_block"] == blocked["budget_block"]
        assert (await client.post(f"{workflow_path}/resume")).json()["job"]["budget_block"]
        wrong_key = await client.post(f"{workflow_path}/resume", json={"approve_budget_request_key": "stale-key"})
        assert wrong_key.status_code == 409
        assert executor.calls == []

        if expected_decision == "pause_unknown_cost":
            approved = await client.post(f"{workflow_path}/resume", json={
                "approve_budget_request_key": preflight["request_key"],
            })
            assert approved.status_code == 200, approved.text
            assert approved.json()["job"]["budget_block"] is None
            assert executor.calls == ["idea"]
            ledger = (await client.get(f"{project_path}/spend")).json()
            assert ledger["requests"][0]["explicitly_approved"] is True
        else:
            manual = await client.put(f"{workflow_path}/stages/idea/mode", json={"mode": "manual"})
            assert manual.status_code == 200, manual.text
            assert manual.json()["job"]["budget_block"] is None
            supplied = await client.post(f"{workflow_path}/stages/idea/manual", json={"content": "A manual idea"})
            assert supplied.status_code == 200, supplied.text
            assert supplied.json()["job"]["stages"][0]["status"] == "completed"
            assert executor.calls == []
