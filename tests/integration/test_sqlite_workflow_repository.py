"""Integration tests for SQLiteWorkflowRepository persistence, restart reconciliation, and logs."""
from pathlib import Path
from typing import Optional

from src.adapters.storage.sqlite_workflow_repository import SQLiteWorkflowRepository
from src.core.dto.workflow_dto import (
    CheckStageRunInput,
    CreateWorkflowJobInput,
    InvalidateStageInput,
    StageArtifactDto,
    StageConfigInput,
    StageExecutionInput,
    StageExecutionResult,
    StageItemStateDto,
    StageRunStatusResult,
    WorkflowJobResult,
)
from src.core.entities.workflow import JobStatus, StageMode, StageStatus
from src.core.ports.stage_executor import StageExecutor
from src.core.use_cases.workflow_engine import WorkflowEngine


class _RecordingExecutor(StageExecutor):
    def __init__(self, known_runs: Optional[dict[str, StageRunStatusResult]] = None) -> None:
        self.executed: list[str] = []
        self._known_runs = known_runs or {}

    def execute(self, request: StageExecutionInput) -> StageExecutionResult:
        self.executed.append(request.stage_id)
        if request.stage_id == "scenes":
            target_ids = request.stale_item_ids or ("scene-1", "scene-2")
            items = tuple(
                StageItemStateDto(
                    item_id=item_id,
                    status=StageStatus.COMPLETED.value,
                    artifact=StageArtifactDto(
                        artifact_id=f"{item_id}-v{request.attempt}",
                        stage_id="scenes",
                        artifact_type="scene_clip",
                        uri=f"file:///{item_id}_v{request.attempt}.mp4",
                    ),
                )
                for item_id in target_ids
            )
            return StageExecutionResult(
                status="completed",
                artifact=StageArtifactDto(
                    artifact_id=f"scenes-v{request.attempt}",
                    stage_id="scenes",
                    artifact_type="scene_clips",
                    data={"count": len(items)},
                ),
                items=items,
            )
        return StageExecutionResult(
            status="completed",
            artifact=StageArtifactDto(
                artifact_id=f"{request.stage_id}-v{request.attempt}",
                stage_id=request.stage_id,
                artifact_type=request.artifact_type,
                uri=f"file:///{request.stage_id}_v{request.attempt}.dat",
            ),
        )

    def check_run_status(self, request: CheckStageRunInput) -> StageRunStatusResult:
        return self._known_runs.get(
            request.external_run_id,
            StageRunStatusResult(status="unknown", message="No external record"),
        )


def test_sqlite_workflow_persists_jobs_artifacts_scene_items_and_logs_across_reopen(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "workflow.db"
    repo_1 = SQLiteWorkflowRepository(db_path=db_path)
    exec_1 = _RecordingExecutor()
    engine_1 = WorkflowEngine(repo_1, exec_1)

    job = engine_1.create_job(
        CreateWorkflowJobInput(
            project_id="proj-1",
            stage_configs={"script": StageConfigInput(mode=StageMode.APPROVAL.value)},
            auto_start=True,
        )
    )
    assert job.status == JobStatus.PAUSED.value
    assert job.get_stage("script").status == StageStatus.AWAITING_APPROVAL.value

    # Reopen repository from disk
    repo_2 = SQLiteWorkflowRepository(db_path=db_path)
    reloaded = repo_2.get_by_id(job.id)
    assert reloaded is not None
    assert reloaded.status == JobStatus.PAUSED.value
    assert reloaded.get_stage("idea").status == StageStatus.COMPLETED.value
    assert reloaded.get_stage("idea").artifact is not None
    assert reloaded.get_stage("script").status == StageStatus.AWAITING_APPROVAL.value

    logs = repo_2.list_logs("proj-1", job_id=job.id)
    assert len(logs) >= 3
    assert any(entry.stage_id == "script" and "awaiting_approval" in entry.message for entry in logs)


def test_sqlite_reconcile_across_restart_and_selective_scene_invalidation(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "reconcile.db"
    repo_1 = SQLiteWorkflowRepository(db_path=db_path)
    engine_1 = WorkflowEngine(repo_1, _RecordingExecutor())
    job = engine_1.create_job(CreateWorkflowJobInput(project_id="proj-r", auto_start=True))
    assert job.status == JobStatus.COMPLETED.value

    # Selectively invalidate scene-2 and reopen repository before resuming
    engine_1.invalidate_stage(
        InvalidateStageInput(
            job_id=job.id,
            stage_id="scenes",
            item_ids=("scene-2",),
            item_inputs={"scene-2": {"prompt": "Updated sunset clip"}},
            reason="Edited scene-2",
        )
    )

    repo_2 = SQLiteWorkflowRepository(db_path=db_path)
    exec_2 = _RecordingExecutor()
    engine_2 = WorkflowEngine(repo_2, exec_2)

    resumed = engine_2.resume(job.id)
    assert resumed.status == JobStatus.COMPLETED.value
    assert exec_2.executed == ["scenes", "edit", "export"]

    items = {item.item_id: item for item in resumed.get_stage("scenes").items}
    assert items["scene-1"].artifact.artifact_id == "scene-1-v1"
    assert items["scene-2"].artifact.artifact_id == "scene-2-v2"

    # Simulate an interrupted running stage persisted across crash
    persisted = repo_2.get_by_id(job.id)
    assert persisted is not None
    crashed_stages = []
    for s in persisted.stages:
        if s.stage_id == "voice":
            crashed_stages.append(
                type(s)(
                    stage_id=s.stage_id,
                    mode=s.mode,
                    status=StageStatus.RUNNING.value,
                    dependencies=s.dependencies,
                    required=s.required,
                    artifact_type=s.artifact_type,
                    external_run_id="ext-lost-run",
                )
            )
        else:
            crashed_stages.append(s)
    repo_2.save(
        WorkflowJobResult(
            id=persisted.id,
            project_id=persisted.project_id,
            status=JobStatus.RUNNING.value,
            stage_order=persisted.stage_order,
            stages=tuple(crashed_stages),
            created_at=persisted.created_at,
            updated_at=persisted.updated_at,
        )
    )

    repo_3 = SQLiteWorkflowRepository(db_path=db_path)
    engine_3 = WorkflowEngine(repo_3, _RecordingExecutor())
    reconcile = engine_3.reconcile("proj-r")
    assert job.id in reconcile.needs_reconciliation_job_ids
    reloaded = repo_3.get_by_id(job.id)
    assert reloaded is not None
    assert reloaded.status == JobStatus.NEEDS_RECONCILIATION.value
    assert reloaded.get_stage("voice").status == StageStatus.UNKNOWN_OUTCOME.value
