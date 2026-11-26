"""Pure unit tests for the core Workflow Jobs Engine without database, HTTP server, or UI."""
import ast
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional
import pytest

from src.core.dto.workflow_dto import (
    ApproveStageInput,
    CheckStageRunInput,
    CreateWorkflowJobInput,
    InvalidateStageInput,
    PreflightCheckInput,
    PreflightDecision,
    RejectStageInput,
    ResolveUnknownStageInput,
    StageArtifactDto,
    StageConfigInput,
    StageDefinitionInput,
    StageExecutionInput,
    StageExecutionResult,
    StageItemStateDto,
    StageRunStatusResult,
    SubmitManualStageInput,
    WorkflowJobResult,
)
from src.core.entities.workflow import (
    DEFAULT_STAGE_ORDER,
    JobStatus,
    StageMode,
    StageStatus,
    WorkflowStateError,
    WorkflowValidationError,
)
from src.core.ports.execution_preflight import ExecutionPreflightPort
from src.core.ports.stage_executor import StageExecutor
from src.core.ports.workflow_repository import WorkflowRepository
from src.core.use_cases.workflow_engine import WorkflowEngine


class InMemoryWorkflowRepository(WorkflowRepository):
    """In-memory repository double for pure core tests."""

    def __init__(self) -> None:
        self._jobs: Dict[str, WorkflowJobResult] = {}

    def save(self, job: WorkflowJobResult) -> None:
        self._jobs[job.id] = job

    def get_by_id(self, job_id: str) -> Optional[WorkflowJobResult]:
        return self._jobs.get(job_id)

    def list_by_project(self, project_id: str) -> List[WorkflowJobResult]:
        return [job for job in self._jobs.values() if job.project_id == project_id]

    def delete(self, job_id: str) -> bool:
        return self._jobs.pop(job_id, None) is not None


class FakeStageExecutor(StageExecutor):
    """Configurable fake executor recording submissions and optional callbacks."""

    def __init__(
        self,
        handler: Optional[Callable[[StageExecutionInput], StageExecutionResult]] = None,
        status_lookup: Optional[Callable[[CheckStageRunInput], StageRunStatusResult]] = None,
    ) -> None:
        self.executed_stages: List[str] = []
        self.requests: List[StageExecutionInput] = []
        self.canceled_runs: List[tuple[str, str, str]] = []
        self._handler = handler
        self._status_lookup = status_lookup

    def execute(self, request: StageExecutionInput) -> StageExecutionResult:
        self.executed_stages.append(request.stage_id)
        self.requests.append(request)
        if self._handler is not None:
            return self._handler(request)
        return StageExecutionResult(
            status="completed",
            artifact=StageArtifactDto(
                artifact_id=f"{request.stage_id}-art-{request.attempt}",
                stage_id=request.stage_id,
                artifact_type=request.artifact_type,
                uri=f"memory://{request.job_id}/{request.stage_id}/v{request.attempt}",
                data={"stage": request.stage_id, "attempt": request.attempt},
            ),
        )

    def check_run_status(self, request: CheckStageRunInput) -> StageRunStatusResult:
        if self._status_lookup is not None:
            return self._status_lookup(request)
        return super().check_run_status(request)

    def cancel_run(self, job_id: str, stage_id: str, external_run_id: str) -> bool:
        self.canceled_runs.append((job_id, stage_id, external_run_id))
        return True


class RecordingPreflight(ExecutionPreflightPort):
    """Test preflight hook that can block specific stages."""

    def __init__(
        self,
        blocked_stages: Optional[Dict[str, PreflightDecision]] = None,
    ) -> None:
        self.calls: List[PreflightCheckInput] = []
        self._blocked = blocked_stages or {}

    def check(self, request: PreflightCheckInput) -> PreflightDecision:
        self.calls.append(request)
        if request.stage_id in self._blocked:
            return self._blocked[request.stage_id]
        return PreflightDecision(allowed=True)


def _make_engine(
    executor: Optional[FakeStageExecutor] = None,
    preflight: Optional[ExecutionPreflightPort] = None,
) -> tuple[WorkflowEngine, InMemoryWorkflowRepository, FakeStageExecutor]:
    repo = InMemoryWorkflowRepository()
    exec_double = executor or FakeStageExecutor()
    engine = WorkflowEngine(repository=repo, executor=exec_double, preflight=preflight)
    return engine, repo, exec_double


# ---------------------------------------------------------------------------
# 1. Clean Architecture & DAG integrity
# ---------------------------------------------------------------------------


def test_core_workflow_modules_have_no_framework_or_adapter_imports() -> None:
    """Verify src/core/ workflow files import zero forbidden framework/adapter modules."""
    forbidden = {"fastapi", "pydantic", "sqlite3", "subprocess", "ffmpeg", "httpx", "sqlalchemy"}
    core_files = [
        Path("src/core/entities/workflow.py"),
        Path("src/core/dto/workflow_dto.py"),
        Path("src/core/ports/workflow_repository.py"),
        Path("src/core/ports/stage_executor.py"),
        Path("src/core/ports/execution_preflight.py"),
        Path("src/core/use_cases/workflow_engine.py"),
    ]
    for file_path in core_files:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    assert top not in forbidden, f"{file_path} imports forbidden '{top}'"
                    assert not alias.name.startswith("src.adapters"), (
                        f"{file_path} imports adapter '{alias.name}'"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                assert top not in forbidden, f"{file_path} imports forbidden '{top}'"
                assert not node.module.startswith("src.adapters"), (
                    f"{file_path} imports adapter '{node.module}'"
                )


def test_cyclic_stage_dag_is_rejected() -> None:
    """Custom stage DAGs containing cycles must fail validation before persistence."""
    engine, _, _ = _make_engine()
    with pytest.raises(WorkflowValidationError, match="cycle"):
        engine.create_job(
            CreateWorkflowJobInput(
                project_id="proj-1",
                stage_definitions=(
                    StageDefinitionInput(stage_id="a", dependencies=("b",)),
                    StageDefinitionInput(stage_id="b", dependencies=("a",)),
                ),
            )
        )


# ---------------------------------------------------------------------------
# 2. Execution modes: auto, manual, approval, off (AC 1)
# ---------------------------------------------------------------------------


def test_full_auto_pipeline_runs_all_six_stages_in_dependency_order() -> None:
    """Default six stages run in topological order and pass upstream artifacts downstream."""
    engine, _, executor = _make_engine()
    job = engine.create_job(CreateWorkflowJobInput(project_id="proj-1", auto_start=True))

    assert job.status == JobStatus.COMPLETED.value
    assert job.stage_order == DEFAULT_STAGE_ORDER
    assert tuple(executor.executed_stages) == DEFAULT_STAGE_ORDER
    for stage_id in DEFAULT_STAGE_ORDER:
        stage = job.get_stage(stage_id)
        assert stage is not None
        assert stage.status == StageStatus.COMPLETED.value
        assert stage.artifact is not None

    edit_req = next(req for req in executor.requests if req.stage_id == "edit")
    assert set(edit_req.dependency_artifacts.keys()) == {"voice", "scenes"}
    export_req = next(req for req in executor.requests if req.stage_id == "export")
    assert set(export_req.dependency_artifacts.keys()) == {"edit"}


def test_manual_mode_pauses_in_waiting_manual_and_resumes_when_supplied() -> None:
    """Manual stage pauses in waiting_manual without calling executor and resumes once supplied."""
    engine, _, executor = _make_engine()
    job = engine.create_job(
        CreateWorkflowJobInput(
            project_id="proj-1",
            stage_configs={
                "script": StageConfigInput(mode=StageMode.MANUAL.value),
            },
            auto_start=True,
        )
    )

    # idea completes; script waits for manual input; downstream stages do not run yet
    assert executor.executed_stages == ["idea"]
    assert job.status == JobStatus.PAUSED.value
    assert job.get_stage("idea").status == StageStatus.COMPLETED.value
    assert job.get_stage("script").status == StageStatus.WAITING_MANUAL.value
    assert job.get_stage("voice").status == StageStatus.PENDING.value

    resumed = engine.submit_manual_result(
        SubmitManualStageInput(
            job_id=job.id,
            stage_id="script",
            artifact=StageArtifactDto(
                artifact_id="manual-script-1",
                stage_id="script",
                artifact_type="script",
                data={"text": "User-authored documentary script"},
            ),
        )
    )

    assert resumed.status == JobStatus.COMPLETED.value
    assert resumed.get_stage("script").status == StageStatus.COMPLETED.value
    assert executor.executed_stages == ["idea", "voice", "scenes", "edit", "export"]
    voice_req = next(r for r in executor.requests if r.stage_id == "voice")
    assert voice_req.dependency_artifacts["script"].artifact_id == "manual-script-1"


def test_approval_mode_generates_then_pauses_until_approved_edited_or_rejected() -> None:
    """Approval stage runs generation, pauses in awaiting_approval, supports edit and reject."""
    engine, _, executor = _make_engine()
    job = engine.create_job(
        CreateWorkflowJobInput(
            project_id="proj-1",
            stage_configs={
                "script": StageConfigInput(mode=StageMode.APPROVAL.value),
            },
            auto_start=True,
        )
    )

    assert executor.executed_stages == ["idea", "script"]
    assert job.status == JobStatus.PAUSED.value
    assert job.get_stage("script").status == StageStatus.AWAITING_APPROVAL.value
    assert job.get_stage("voice").status == StageStatus.PENDING.value

    # Reject without rerun -> marks script failed and keeps job paused without downstream execution
    rejected = engine.reject_stage(
        RejectStageInput(job_id=job.id, stage_id="script", reason="Tone is too informal")
    )
    assert rejected.status == JobStatus.PAUSED.value
    assert rejected.get_stage("script").status == StageStatus.FAILED.value
    assert "Tone is too informal" in (rejected.get_stage("script").error or "")
    assert executor.executed_stages == ["idea", "script"]

    # Retry script -> regenerates and lands back in awaiting_approval (without rerunning idea!)
    retried = engine.retry(job.id, "script")
    assert retried.status == JobStatus.PAUSED.value
    assert retried.get_stage("script").status == StageStatus.AWAITING_APPROVAL.value
    assert executor.executed_stages == ["idea", "script", "script"]

    # Approve with owner edit -> downstream stages run using edited script artifact
    approved = engine.approve_stage(
        ApproveStageInput(
            job_id=job.id,
            stage_id="script",
            edited_artifact=StageArtifactDto(
                artifact_id="script-edited-v1",
                stage_id="script",
                artifact_type="script",
                data={"text": "Edited approved script"},
            ),
        )
    )
    assert approved.status == JobStatus.COMPLETED.value
    assert approved.get_stage("script").status == StageStatus.COMPLETED.value
    assert executor.executed_stages == ["idea", "script", "script", "voice", "scenes", "edit", "export"]
    scenes_req = next(r for r in executor.requests if r.stage_id == "scenes")
    assert scenes_req.dependency_artifacts["script"].artifact_id == "script-edited-v1"


def test_off_mode_skips_optional_stage() -> None:
    """Setting off on an optional stage skips it cleanly and runs dependent stages."""
    engine, _, executor = _make_engine()
    job = engine.create_job(
        CreateWorkflowJobInput(
            project_id="proj-1",
            stage_configs={"idea": StageConfigInput(mode=StageMode.OFF.value)},
            auto_start=True,
        )
    )

    assert job.status == JobStatus.COMPLETED.value
    assert job.get_stage("idea").status == StageStatus.SKIPPED.value
    assert executor.executed_stages == ["script", "voice", "scenes", "edit", "export"]


def test_off_mode_on_required_stage_without_valid_artifact_fails_before_submission() -> None:
    """Off on a required stage without a valid compatible artifact fails before submission and names the artifact."""
    engine, repo, executor = _make_engine()

    # Missing artifact completely
    with pytest.raises(WorkflowValidationError) as exc_info:
        engine.create_job(
            CreateWorkflowJobInput(
                project_id="proj-1",
                stage_configs={"voice": StageConfigInput(mode=StageMode.OFF.value)},
                auto_start=True,
            )
        )
    msg = str(exc_info.value)
    assert "voice" in msg
    assert "narration" in msg
    assert executor.executed_stages == []
    assert repo.list_by_project("proj-1") == []

    # Incompatible or wrong-type saved artifact also rejected before submission
    with pytest.raises(WorkflowValidationError) as wrong_type_exc:
        engine.create_job(
            CreateWorkflowJobInput(
                project_id="proj-1",
                stage_configs={
                    "scenes": StageConfigInput(
                        mode=StageMode.OFF.value,
                        saved_artifact=StageArtifactDto(
                            artifact_id="bad-1",
                            stage_id="scenes",
                            artifact_type="script",
                            uri="memory://wrong",
                            compatible=True,
                        ),
                    )
                },
                auto_start=True,
            )
        )
    assert "scenes" in str(wrong_type_exc.value)
    assert "scene_clips" in str(wrong_type_exc.value)
    assert executor.executed_stages == []


def test_off_mode_on_required_stage_with_valid_compatible_artifact_reuses_it() -> None:
    """Off on a required stage is allowed when a valid compatible saved artifact is supplied."""
    engine, _, executor = _make_engine()
    saved_narration = StageArtifactDto(
        artifact_id="saved-narration-1",
        stage_id="voice",
        artifact_type="narration",
        uri="file:///narration.wav",
        compatible=True,
    )
    job = engine.create_job(
        CreateWorkflowJobInput(
            project_id="proj-1",
            stage_configs={
                "voice": StageConfigInput(
                    mode=StageMode.OFF.value,
                    saved_artifact=saved_narration,
                )
            },
            auto_start=True,
        )
    )

    assert job.status == JobStatus.COMPLETED.value
    assert job.get_stage("voice").status == StageStatus.SKIPPED.value
    assert "voice" not in executor.executed_stages
    assert executor.executed_stages == ["idea", "script", "scenes", "edit", "export"]
    edit_req = next(r for r in executor.requests if r.stage_id == "edit")
    assert edit_req.dependency_artifacts["voice"].artifact_id == "saved-narration-1"


# ---------------------------------------------------------------------------
# 3. Pause, Cancel, Retry, Restart Reconciliation (AC 2)
# ---------------------------------------------------------------------------


def test_pause_prevents_new_stage_submissions_and_resume_reuses_completed_stages() -> None:
    """Pausing during execution halts further submissions; resume skips already-completed stages."""
    holder: Dict[str, WorkflowEngine] = {}

    def handler(req: StageExecutionInput) -> StageExecutionResult:
        if req.stage_id == "script":
            holder["engine"].pause(req.job_id)
        return StageExecutionResult(
            status="completed",
            artifact=StageArtifactDto(
                artifact_id=f"{req.stage_id}-art",
                stage_id=req.stage_id,
                artifact_type=req.artifact_type,
                uri=f"memory://{req.stage_id}",
            ),
        )

    engine, _, executor = _make_engine(FakeStageExecutor(handler=handler))
    holder["engine"] = engine

    job = engine.create_job(CreateWorkflowJobInput(project_id="proj-1", auto_start=True))
    assert job.status == JobStatus.PAUSED.value
    assert job.pause_requested is True
    assert executor.executed_stages == ["idea", "script"]
    assert job.get_stage("idea").status == StageStatus.COMPLETED.value
    assert job.get_stage("script").status == StageStatus.COMPLETED.value
    assert job.get_stage("voice").status == StageStatus.PENDING.value

    # Calling start_job while paused must NOT submit any stage
    still_paused = engine.start_job(job.id)
    assert still_paused.status == JobStatus.PAUSED.value
    assert executor.executed_stages == ["idea", "script"]

    # Resuming continues from voice and reuses idea + script
    resumed = engine.resume(job.id)
    assert resumed.status == JobStatus.COMPLETED.value
    assert executor.executed_stages == ["idea", "script", "voice", "scenes", "edit", "export"]


def test_cancel_prevents_any_further_stage_submissions() -> None:
    """Canceling stops scheduling immediately and rejects subsequent start/resume."""
    holder: Dict[str, WorkflowEngine] = {}

    def handler(req: StageExecutionInput) -> StageExecutionResult:
        if req.stage_id == "idea":
            holder["engine"].cancel(req.job_id)
        return StageExecutionResult(
            status="completed",
            artifact=StageArtifactDto(
                artifact_id=f"{req.stage_id}-art",
                stage_id=req.stage_id,
                artifact_type=req.artifact_type,
                uri=f"memory://{req.stage_id}",
            ),
        )

    engine, _, executor = _make_engine(FakeStageExecutor(handler=handler))
    holder["engine"] = engine

    job = engine.create_job(CreateWorkflowJobInput(project_id="proj-1", auto_start=True))
    assert job.status == JobStatus.CANCELED.value
    assert job.cancel_requested is True
    assert executor.executed_stages == ["idea"]
    assert job.get_stage("script").status == StageStatus.CANCELED.value

    with pytest.raises(WorkflowStateError):
        engine.resume(job.id)
    with pytest.raises(WorkflowStateError):
        engine.start_job(job.id)
    assert executor.executed_stages == ["idea"]


def test_reconcile_reuses_verified_completed_stages_and_flags_unknown_outcome_for_review() -> None:
    """Restart reconciliation reuses verified completed work and pauses unknown in-flight runs."""
    repo = InMemoryWorkflowRepository()
    now_iso = datetime.now(timezone.utc).isoformat()

    # Build two persisted interrupted jobs via engine first, then simulate crash state in repo
    setup_engine = WorkflowEngine(repo, FakeStageExecutor())
    job_known = setup_engine.create_job(CreateWorkflowJobInput(project_id="proj-1"))
    job_unknown = setup_engine.create_job(CreateWorkflowJobInput(project_id="proj-1"))

    # Job A: idea & script completed, voice running with external handle that completed externally
    def _with_stage_updates(
        job: WorkflowJobResult,
        updates: Dict[str, tuple[str, Optional[StageArtifactDto], Optional[str]]],
        job_status: str = JobStatus.RUNNING.value,
    ) -> WorkflowJobResult:
        new_stages = []
        for s in job.stages:
            if s.stage_id in updates:
                st, art, ext = updates[s.stage_id]
                new_stages.append(
                    type(s)(
                        stage_id=s.stage_id,
                        mode=s.mode,
                        status=st,
                        dependencies=s.dependencies,
                        required=s.required,
                        artifact_type=s.artifact_type,
                        required_schema_version=s.required_schema_version,
                        artifact=art,
                        items=s.items,
                        params=s.params,
                        external_run_id=ext,
                        error=s.error,
                        attempt_count=1,
                        started_at=now_iso,
                        completed_at=now_iso if st == StageStatus.COMPLETED.value else None,
                        updated_at=now_iso,
                    )
                )
            else:
                new_stages.append(s)
        return WorkflowJobResult(
            id=job.id,
            project_id=job.project_id,
            status=job_status,
            stage_order=job.stage_order,
            stages=tuple(new_stages),
            created_at=job.created_at,
            updated_at=now_iso,
        )

    repo.save(
        _with_stage_updates(
            job_known,
            {
                "idea": (
                    StageStatus.COMPLETED.value,
                    StageArtifactDto("idea-1", "idea", "topic", uri="memory://idea-1"),
                    None,
                ),
                "script": (
                    StageStatus.COMPLETED.value,
                    StageArtifactDto("script-1", "script", "script", uri="memory://script-1"),
                    None,
                ),
                "voice": (StageStatus.RUNNING.value, None, "ext-voice-123"),
            },
        )
    )

    # Job B: idea completed, script running with unknown external outcome
    repo.save(
        _with_stage_updates(
            job_unknown,
            {
                "idea": (
                    StageStatus.COMPLETED.value,
                    StageArtifactDto("idea-2", "idea", "topic", uri="memory://idea-2"),
                    None,
                ),
                "script": (StageStatus.RUNNING.value, None, "ext-script-999"),
            },
        )
    )

    def lookup(req: CheckStageRunInput) -> StageRunStatusResult:
        if req.external_run_id == "ext-voice-123":
            return StageRunStatusResult(
                status="completed",
                artifact=StageArtifactDto(
                    artifact_id="voice-ext-ok",
                    stage_id="voice",
                    artifact_type="narration",
                    uri="memory://voice-ext-ok",
                ),
            )
        return StageRunStatusResult(
            status="unknown",
            message="Provider run state unavailable after process crash",
        )

    restarted_executor = FakeStageExecutor(status_lookup=lookup)
    restarted_engine = WorkflowEngine(repo, restarted_executor)

    reconcile_result = restarted_engine.reconcile("proj-1")
    assert job_unknown.id in reconcile_result.needs_reconciliation_job_ids

    # Job A: idea, script, voice are ALL completed and NOT blindly resubmitted
    reconciled_a = restarted_engine.get_job(job_known.id)
    assert reconciled_a is not None
    assert reconciled_a.status == JobStatus.PAUSED.value
    assert reconciled_a.get_stage("voice").status == StageStatus.COMPLETED.value
    assert restarted_executor.executed_stages == []

    # Resuming Job A runs ONLY scenes, edit, export (reusing idea, script, voice)
    finished_a = restarted_engine.resume(job_known.id)
    assert finished_a.status == JobStatus.COMPLETED.value
    assert restarted_executor.executed_stages == ["scenes", "edit", "export"]

    # Job B: marked needs_reconciliation & script marked unknown_outcome; resume is blocked
    reconciled_b = restarted_engine.get_job(job_unknown.id)
    assert reconciled_b is not None
    assert reconciled_b.status == JobStatus.NEEDS_RECONCILIATION.value
    assert reconciled_b.get_stage("script").status == StageStatus.UNKNOWN_OUTCOME.value
    assert reconciled_b.get_stage("idea").status == StageStatus.COMPLETED.value

    with pytest.raises(WorkflowStateError, match="reconciliation"):
        restarted_engine.resume(job_unknown.id)

    # Resolving via explicit retry reruns script..export while reusing completed idea
    restarted_executor.executed_stages.clear()
    resolved_b = restarted_engine.retry(job_unknown.id, "script")
    assert resolved_b.status == JobStatus.COMPLETED.value
    assert restarted_executor.executed_stages == ["script", "voice", "scenes", "edit", "export"]


def test_resolve_unknown_stage_with_recovered_artifact_resumes_downstream() -> None:
    """Owner confirming an interrupted external run succeeded reuses that artifact without rerunning."""
    repo = InMemoryWorkflowRepository()
    executor = FakeStageExecutor()
    engine = WorkflowEngine(repo, executor)

    job = engine.create_job(CreateWorkflowJobInput(project_id="proj-1"))
    # Simulate idea completed, script interrupted without external handle
    now_iso = datetime.now(timezone.utc).isoformat()
    persisted = repo.get_by_id(job.id)
    assert persisted is not None
    stages = []
    for s in persisted.stages:
        if s.stage_id == "idea":
            stages.append(
                type(s)(
                    stage_id=s.stage_id,
                    mode=s.mode,
                    status=StageStatus.COMPLETED.value,
                    dependencies=s.dependencies,
                    required=s.required,
                    artifact_type=s.artifact_type,
                    artifact=StageArtifactDto("idea-ok", "idea", "topic", uri="memory://idea"),
                )
            )
        elif s.stage_id == "script":
            stages.append(
                type(s)(
                    stage_id=s.stage_id,
                    mode=s.mode,
                    status=StageStatus.RUNNING.value,
                    dependencies=s.dependencies,
                    required=s.required,
                    artifact_type=s.artifact_type,
                    external_run_id=None,
                )
            )
        else:
            stages.append(s)
    repo.save(
        WorkflowJobResult(
            id=persisted.id,
            project_id=persisted.project_id,
            status=JobStatus.RUNNING.value,
            stage_order=persisted.stage_order,
            stages=tuple(stages),
            created_at=persisted.created_at,
            updated_at=now_iso,
        )
    )

    rec = engine.reconcile("proj-1")
    assert job.id in rec.needs_reconciliation_job_ids
    assert engine.get_job(job.id).get_stage("script").status == StageStatus.UNKNOWN_OUTCOME.value

    resolved = engine.resolve_unknown_stage(
        ResolveUnknownStageInput(
            job_id=job.id,
            stage_id="script",
            outcome="completed",
            artifact=StageArtifactDto("script-recovered", "script", "script", uri="memory://recovered"),
            auto_resume=True,
        )
    )
    assert resolved.status == JobStatus.COMPLETED.value
    assert executor.executed_stages == ["voice", "scenes", "edit", "export"]


# ---------------------------------------------------------------------------
# 4. Selective Invalidation (AC 3)
# ---------------------------------------------------------------------------


def test_single_scene_item_change_invalidates_only_affected_scene_and_downstream_assembly() -> None:
    """Changing scene #2 marks only scene #2, scenes, edit, and export stale; idea/script/voice/scene #1,#3 are reused."""

    def handler(req: StageExecutionInput) -> StageExecutionResult:
        if req.stage_id == "scenes":
            target_ids = req.stale_item_ids or ("scene-1", "scene-2", "scene-3")
            generated_items = tuple(
                StageItemStateDto(
                    item_id=item_id,
                    status=StageStatus.COMPLETED.value,
                    artifact=StageArtifactDto(
                        artifact_id=f"{item_id}-v{req.attempt}",
                        stage_id="scenes",
                        artifact_type="scene_clip",
                        uri=f"memory://{item_id}/v{req.attempt}",
                    ),
                )
                for item_id in target_ids
            )
            return StageExecutionResult(
                status="completed",
                artifact=StageArtifactDto(
                    artifact_id=f"scenes-bundle-v{req.attempt}",
                    stage_id="scenes",
                    artifact_type="scene_clips",
                    uri=f"memory://scenes/v{req.attempt}",
                ),
                items=generated_items,
            )
        return StageExecutionResult(
            status="completed",
            artifact=StageArtifactDto(
                artifact_id=f"{req.stage_id}-v{req.attempt}",
                stage_id=req.stage_id,
                artifact_type=req.artifact_type,
                uri=f"memory://{req.stage_id}/v{req.attempt}",
            ),
        )

    engine, _, executor = _make_engine(FakeStageExecutor(handler=handler))
    job = engine.create_job(CreateWorkflowJobInput(project_id="proj-1", auto_start=True))
    assert job.status == JobStatus.COMPLETED.value
    executor.executed_stages.clear()
    executor.requests.clear()

    # Update only scene-2
    invalidated = engine.invalidate_stage(
        InvalidateStageInput(
            job_id=job.id,
            stage_id="scenes",
            item_ids=("scene-2",),
            item_inputs={"scene-2": {"prompt": "Revised pyramid aerial shot"}},
            reason="Updated scene 2 prompt",
        )
    )

    assert invalidated.status == JobStatus.PAUSED.value
    # Unaffected stages remain completed
    assert invalidated.get_stage("idea").status == StageStatus.COMPLETED.value
    assert invalidated.get_stage("script").status == StageStatus.COMPLETED.value
    assert invalidated.get_stage("voice").status == StageStatus.COMPLETED.value
    # Affected stages are stale
    assert invalidated.get_stage("scenes").status == StageStatus.STALE.value
    assert invalidated.get_stage("edit").status == StageStatus.STALE.value
    assert invalidated.get_stage("export").status == StageStatus.STALE.value

    scene_items = {item.item_id: item for item in invalidated.get_stage("scenes").items}
    assert scene_items["scene-1"].status == StageStatus.COMPLETED.value
    assert scene_items["scene-2"].status == StageStatus.STALE.value
    assert scene_items["scene-3"].status == StageStatus.COMPLETED.value

    # Rerun only affected stages
    rerun = engine.resume(job.id)
    assert rerun.status == JobStatus.COMPLETED.value
    assert executor.executed_stages == ["scenes", "edit", "export"]

    scenes_req = next(r for r in executor.requests if r.stage_id == "scenes")
    assert scenes_req.stale_item_ids == ("scene-2",)
    assert set(scenes_req.preserved_items.keys()) == {"scene-1", "scene-3"}

    final_items = {item.item_id: item for item in rerun.get_stage("scenes").items}
    assert final_items["scene-1"].artifact.artifact_id == "scene-1-v1"
    assert final_items["scene-2"].artifact.artifact_id == "scene-2-v2"
    assert final_items["scene-3"].artifact.artifact_id == "scene-3-v1"


def test_configurable_per_scene_dag_invalidates_only_changed_scene_and_assembly() -> None:
    """Configurable DAG with per-scene nodes reruns only the changed scene, edit, and export."""
    custom_dag = (
        StageDefinitionInput(stage_id="script", dependencies=(), artifact_type="script"),
        StageDefinitionInput(stage_id="voice", dependencies=("script",), artifact_type="narration"),
        StageDefinitionInput(stage_id="scene_1", dependencies=("script",), artifact_type="scene_clip"),
        StageDefinitionInput(stage_id="scene_2", dependencies=("script",), artifact_type="scene_clip"),
        StageDefinitionInput(stage_id="edit", dependencies=("voice", "scene_1", "scene_2"), artifact_type="edited_video"),
        StageDefinitionInput(stage_id="export", dependencies=("edit",), artifact_type="final_video"),
    )
    engine, _, executor = _make_engine()
    job = engine.create_job(
        CreateWorkflowJobInput(
            project_id="proj-1",
            stage_definitions=custom_dag,
            auto_start=True,
        )
    )
    assert job.status == JobStatus.COMPLETED.value
    executor.executed_stages.clear()

    invalidated = engine.invalidate_stage(
        InvalidateStageInput(job_id=job.id, stage_id="scene_2", reason="Regenerate scene 2")
    )
    assert invalidated.get_stage("script").status == StageStatus.COMPLETED.value
    assert invalidated.get_stage("voice").status == StageStatus.COMPLETED.value
    assert invalidated.get_stage("scene_1").status == StageStatus.COMPLETED.value
    assert invalidated.get_stage("scene_2").status == StageStatus.STALE.value
    assert invalidated.get_stage("edit").status == StageStatus.STALE.value
    assert invalidated.get_stage("export").status == StageStatus.STALE.value

    rerun = engine.resume(job.id)
    assert rerun.status == JobStatus.COMPLETED.value
    assert executor.executed_stages == ["scene_2", "edit", "export"]


def test_voice_invalidation_preserves_idea_script_and_scenes() -> None:
    """Invalidating voice marks only voice, edit, and export stale, preserving scenes."""
    engine, _, executor = _make_engine()
    job = engine.create_job(CreateWorkflowJobInput(project_id="proj-1", auto_start=True))
    executor.executed_stages.clear()

    invalidated = engine.invalidate_stage(
        InvalidateStageInput(job_id=job.id, stage_id="voice", reason="Changed narrator voice")
    )
    assert invalidated.get_stage("idea").status == StageStatus.COMPLETED.value
    assert invalidated.get_stage("script").status == StageStatus.COMPLETED.value
    assert invalidated.get_stage("scenes").status == StageStatus.COMPLETED.value
    assert invalidated.get_stage("voice").status == StageStatus.STALE.value
    assert invalidated.get_stage("edit").status == StageStatus.STALE.value
    assert invalidated.get_stage("export").status == StageStatus.STALE.value

    rerun = engine.resume(job.id)
    assert rerun.status == JobStatus.COMPLETED.value
    assert executor.executed_stages == ["voice", "edit", "export"]


# ---------------------------------------------------------------------------
# 5. Pluggable ExecutionPreflightPort (OCP / DIP for Issue #9)
# ---------------------------------------------------------------------------


def test_preflight_port_blocks_submission_without_modifying_engine() -> None:
    """Preflight hook can deny or request confirmation before StageExecutor is invoked."""
    preflight = RecordingPreflight(
        blocked_stages={
            "voice": PreflightDecision(
                allowed=False,
                reason="Project budget cap reached ($5.00 limit)",
                requires_confirmation=True,
            )
        }
    )
    engine, _, executor = _make_engine(preflight=preflight)
    job = engine.create_job(CreateWorkflowJobInput(project_id="proj-1", auto_start=True))

    assert job.status == JobStatus.PAUSED.value
    assert "budget cap" in (job.error or "").lower()
    assert executor.executed_stages == ["idea", "script"]
    assert job.get_stage("voice").status == StageStatus.PENDING.value
    assert [c.stage_id for c in preflight.calls] == ["idea", "script", "voice"]

    # Hard block (requires_confirmation=False) fails stage before submission
    hard_preflight = RecordingPreflight(
        blocked_stages={
            "script": PreflightDecision(
                allowed=False,
                reason="Daily spend quota exceeded",
                requires_confirmation=False,
            )
        }
    )
    engine_hard, _, exec_hard = _make_engine(preflight=hard_preflight)
    job_hard = engine_hard.create_job(CreateWorkflowJobInput(project_id="proj-1", auto_start=True))

    assert job_hard.status == JobStatus.FAILED.value
    assert job_hard.get_stage("script").status == StageStatus.FAILED.value
    assert exec_hard.executed_stages == ["idea"]
