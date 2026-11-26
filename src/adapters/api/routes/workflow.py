"""API routes for persisted workflow job orchestration, stage modes, and scene invalidation."""
import copy
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.adapters.storage.sqlite_workflow_repository import (
    SQLiteWorkflowRepository,
    WorkflowLogEntry,
)
from src.core.dto.project_settings_dto import GetProjectSettingsInput, UpdateProjectSettingsInput
from src.core.dto.workflow_dto import (
    ApproveStageInput,
    CreateWorkflowJobInput,
    InvalidateStageInput,
    RejectStageInput,
    StageArtifactDto,
    StageConfigInput,
    SubmitManualStageInput,
    WorkflowJobResult,
    WorkflowStageResult,
)
from src.core.entities.workflow import (
    DEFAULT_STAGE_ORDER,
    StageMode,
    WorkflowNotFoundError,
    WorkflowStateError,
    WorkflowValidationError,
)
from src.core.ports.channel_repository import ChannelRepository
from src.core.ports.execution_preflight import ExecutionPreflightPort
from src.core.ports.preset_repository import PresetRepository
from src.core.ports.project_repository import ProjectRepository
from src.core.ports.project_settings_repository import ProjectSettingsRepository
from src.core.ports.stage_executor import StageExecutor
from src.core.ports.workflow_repository import WorkflowRepository
from src.core.use_cases.project_settings_use_cases import (
    GetProjectSettingsUseCase,
    UpdateProjectSettingsUseCase,
)
from src.core.use_cases.workflow_engine import WorkflowEngine

router = APIRouter(prefix="/projects/{project_id}/workflow", tags=["workflow"])


class StageArtifactResponse(BaseModel):
    artifact_id: str
    stage_id: str
    artifact_type: str
    uri: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    schema_version: str = "1.0"
    compatible: bool = True
    stale: bool = False
    created_at: Optional[str] = None
    content_hash: Optional[str] = None


class StageItemResponse(BaseModel):
    item_id: str
    status: str
    artifact: Optional[StageArtifactResponse] = None
    input_data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class WorkflowStageResponse(BaseModel):
    stage_id: str
    mode: str
    status: str
    dependencies: List[str]
    required: bool
    artifact_type: str
    artifact: Optional[StageArtifactResponse] = None
    items: List[StageItemResponse] = Field(default_factory=list)
    params: Dict[str, Any] = Field(default_factory=dict)
    external_run_id: Optional[str] = None
    error: Optional[str] = None
    attempt_count: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_dto(cls, stage: WorkflowStageResult) -> "WorkflowStageResponse":
        art = (
            StageArtifactResponse(
                artifact_id=stage.artifact.artifact_id,
                stage_id=stage.artifact.stage_id,
                artifact_type=stage.artifact.artifact_type,
                uri=stage.artifact.uri,
                data=dict(stage.artifact.data),
                schema_version=stage.artifact.schema_version,
                compatible=stage.artifact.compatible,
                stale=stage.artifact.stale,
                created_at=stage.artifact.created_at,
                content_hash=stage.artifact.content_hash,
            )
            if stage.artifact is not None
            else None
        )
        items = [
            StageItemResponse(
                item_id=item.item_id,
                status=item.status,
                artifact=(
                    StageArtifactResponse(
                        artifact_id=item.artifact.artifact_id,
                        stage_id=item.artifact.stage_id,
                        artifact_type=item.artifact.artifact_type,
                        uri=item.artifact.uri,
                        data=dict(item.artifact.data),
                        schema_version=item.artifact.schema_version,
                        compatible=item.artifact.compatible,
                        stale=item.artifact.stale,
                        created_at=item.artifact.created_at,
                        content_hash=item.artifact.content_hash,
                    )
                    if item.artifact is not None
                    else None
                ),
                input_data=dict(item.input_data),
                error=item.error,
            )
            for item in stage.items
        ]
        return cls(
            stage_id=stage.stage_id,
            mode=stage.mode,
            status=stage.status,
            dependencies=list(stage.dependencies),
            required=stage.required,
            artifact_type=stage.artifact_type,
            artifact=art,
            items=items,
            params=dict(stage.params),
            external_run_id=stage.external_run_id,
            error=stage.error,
            attempt_count=stage.attempt_count,
            started_at=stage.started_at,
            completed_at=stage.completed_at,
            updated_at=stage.updated_at,
        )


class WorkflowJobResponse(BaseModel):
    id: str
    project_id: str
    status: str
    stage_order: List[str]
    stages: List[WorkflowStageResponse]
    created_at: str
    updated_at: str
    pause_requested: bool = False
    cancel_requested: bool = False
    completed_at: Optional[str] = None
    error: Optional[str] = None

    @classmethod
    def from_dto(cls, job: WorkflowJobResult) -> "WorkflowJobResponse":
        return cls(
            id=job.id,
            project_id=job.project_id,
            status=job.status,
            stage_order=list(job.stage_order),
            stages=[WorkflowStageResponse.from_dto(s) for s in job.stages],
            created_at=job.created_at,
            updated_at=job.updated_at,
            pause_requested=job.pause_requested,
            cancel_requested=job.cancel_requested,
            completed_at=job.completed_at,
            error=job.error,
        )


class WorkflowLogResponse(BaseModel):
    id: str
    job_id: str
    project_id: str
    stage_id: str
    level: str
    message: str
    created_at: str

    @classmethod
    def from_entry(cls, entry: WorkflowLogEntry) -> "WorkflowLogResponse":
        return cls(
            id=entry.id,
            job_id=entry.job_id,
            project_id=entry.project_id,
            stage_id=entry.stage_id,
            level=entry.level,
            message=entry.message,
            created_at=entry.created_at,
        )


class WorkflowStateResponse(BaseModel):
    project_id: str
    job: Optional[WorkflowJobResponse] = None
    logs: List[WorkflowLogResponse] = Field(default_factory=list)


class ReconcileWorkflowResponse(BaseModel):
    project_id: str
    job: Optional[WorkflowJobResponse] = None
    reconciled_job_ids: List[str] = Field(default_factory=list)
    needs_reconciliation_job_ids: List[str] = Field(default_factory=list)
    logs: List[WorkflowLogResponse] = Field(default_factory=list)


class RunWorkflowRequest(BaseModel):
    stage_modes: Optional[Dict[str, str]] = None
    force_new: bool = False


class UpdateStageModeRequest(BaseModel):
    mode: str


class SubmitManualStageRequest(BaseModel):
    content: Optional[str] = None
    uri: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    artifact_id: Optional[str] = None
    auto_resume: bool = True


class ApproveStageRequest(BaseModel):
    approved: bool = True
    edited_content: Optional[str] = None
    edited_data: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    rerun: bool = False
    auto_resume: bool = True


class UpdateSceneRequest(BaseModel):
    prompt: Optional[str] = None
    notes: Optional[str] = None
    title: Optional[str] = None
    input_data: Dict[str, Any] = Field(default_factory=dict)
    reason: Optional[str] = None


def get_workflow_repository() -> WorkflowRepository:
    raise NotImplementedError("WorkflowRepository dependency must be configured.")


def get_stage_executor() -> StageExecutor:
    raise NotImplementedError("StageExecutor dependency must be configured.")


def get_execution_preflight() -> ExecutionPreflightPort:
    raise NotImplementedError("ExecutionPreflightPort dependency must be configured.")


def get_workflow_project_repository() -> ProjectRepository:
    raise NotImplementedError("ProjectRepository dependency must be configured.")


def get_workflow_settings_repository() -> ProjectSettingsRepository:
    raise NotImplementedError("ProjectSettingsRepository dependency must be configured.")


def get_workflow_channel_repository() -> ChannelRepository:
    raise NotImplementedError("ChannelRepository dependency must be configured.")


def get_workflow_preset_repository() -> PresetRepository:
    raise NotImplementedError("PresetRepository dependency must be configured.")


def _require_project(project_id: str, project_repo: ProjectRepository) -> None:
    if project_repo.get_by_id(project_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )


def _build_engine(
    workflow_repo: WorkflowRepository,
    executor: StageExecutor,
    preflight: ExecutionPreflightPort,
) -> WorkflowEngine:
    return WorkflowEngine(
        repository=workflow_repo,
        executor=executor,
        preflight=preflight,
    )


def _list_logs(workflow_repo: WorkflowRepository, project_id: str) -> List[WorkflowLogResponse]:
    if isinstance(workflow_repo, SQLiteWorkflowRepository):
        return [
            WorkflowLogResponse.from_entry(entry)
            for entry in workflow_repo.list_logs(project_id)
        ]
    return []


def _latest_job(workflow_repo: WorkflowRepository, project_id: str) -> Optional[WorkflowJobResult]:
    jobs = workflow_repo.list_by_project(project_id)
    return jobs[0] if jobs else None


def _require_latest_job(workflow_repo: WorkflowRepository, project_id: str) -> WorkflowJobResult:
    job = _latest_job(workflow_repo, project_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No workflow job exists for project '{project_id}'.",
        )
    return job


def _build_stage_configs(
    project_id: str,
    project_repo: ProjectRepository,
    settings_repo: ProjectSettingsRepository,
    channel_repo: ChannelRepository,
    preset_repo: PresetRepository,
    override_modes: Optional[Dict[str, str]] = None,
) -> Dict[str, StageConfigInput]:
    settings = GetProjectSettingsUseCase(
        settings_repository=settings_repo,
        project_repository=project_repo,
        channel_repository=channel_repo,
        preset_repository=preset_repo,
    ).execute(GetProjectSettingsInput(project_id=project_id))

    configs: Dict[str, StageConfigInput] = {}
    for stage_id in DEFAULT_STAGE_ORDER:
        mode = (
            override_modes.get(stage_id)
            if override_modes and stage_id in override_modes
            else settings.stage_modes.get(stage_id, StageMode.AUTO.value)
        )
        params = dict(settings.stage_params.get(stage_id, {}))
        configs[stage_id] = StageConfigInput(mode=mode, params=params)
    return configs


def _sync_modes_into_job(
    job: WorkflowJobResult,
    modes: Dict[str, str],
    workflow_repo: WorkflowRepository,
) -> WorkflowJobResult:
    if not modes:
        return job
    updated_stages: List[WorkflowStageResult] = []
    changed = False
    for stage in job.stages:
        next_mode = modes.get(stage.stage_id, stage.mode)
        if next_mode != stage.mode:
            changed = True
            updated_stages.append(
                WorkflowStageResult(
                    stage_id=stage.stage_id,
                    mode=next_mode,
                    status=stage.status,
                    dependencies=stage.dependencies,
                    required=stage.required,
                    artifact_type=stage.artifact_type,
                    required_schema_version=stage.required_schema_version,
                    artifact=stage.artifact,
                    items=stage.items,
                    params=stage.params,
                    external_run_id=stage.external_run_id,
                    error=stage.error,
                    attempt_count=stage.attempt_count,
                    started_at=stage.started_at,
                    completed_at=stage.completed_at,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                )
            )
        else:
            updated_stages.append(stage)
    if not changed:
        return job
    updated_job = WorkflowJobResult(
        id=job.id,
        project_id=job.project_id,
        status=job.status,
        stage_order=job.stage_order,
        stages=tuple(updated_stages),
        created_at=job.created_at,
        updated_at=datetime.now(timezone.utc).isoformat(),
        pause_requested=job.pause_requested,
        cancel_requested=job.cancel_requested,
        completed_at=job.completed_at,
        error=job.error,
        metadata=job.metadata,
    )
    workflow_repo.save(updated_job)
    return updated_job


def _state_response(
    project_id: str,
    job: Optional[WorkflowJobResult],
    workflow_repo: WorkflowRepository,
) -> WorkflowStateResponse:
    return WorkflowStateResponse(
        project_id=project_id,
        job=WorkflowJobResponse.from_dto(job) if job is not None else None,
        logs=_list_logs(workflow_repo, project_id),
    )


def _map_domain_error(err: Exception) -> HTTPException:
    if isinstance(err, WorkflowNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    if isinstance(err, WorkflowValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))
    if isinstance(err, WorkflowStateError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get("", response_model=WorkflowStateResponse)
def get_project_workflow(
    project_id: str,
    workflow_repo: WorkflowRepository = Depends(get_workflow_repository),
    project_repo: ProjectRepository = Depends(get_workflow_project_repository),
) -> WorkflowStateResponse:
    _require_project(project_id, project_repo)
    return _state_response(project_id, _latest_job(workflow_repo, project_id), workflow_repo)


@router.post("/reconcile", response_model=ReconcileWorkflowResponse)
def reconcile_project_workflow(
    project_id: str,
    workflow_repo: WorkflowRepository = Depends(get_workflow_repository),
    executor: StageExecutor = Depends(get_stage_executor),
    preflight: ExecutionPreflightPort = Depends(get_execution_preflight),
    project_repo: ProjectRepository = Depends(get_workflow_project_repository),
) -> ReconcileWorkflowResponse:
    _require_project(project_id, project_repo)
    engine = _build_engine(workflow_repo, executor, preflight)
    result = engine.reconcile(project_id)
    latest = _latest_job(workflow_repo, project_id)
    return ReconcileWorkflowResponse(
        project_id=project_id,
        job=WorkflowJobResponse.from_dto(latest) if latest is not None else None,
        reconciled_job_ids=list(result.reconciled_job_ids),
        needs_reconciliation_job_ids=list(result.needs_reconciliation_job_ids),
        logs=_list_logs(workflow_repo, project_id),
    )


@router.post("/run", response_model=WorkflowStateResponse)
def run_project_workflow(
    project_id: str,
    request: Optional[RunWorkflowRequest] = None,
    workflow_repo: WorkflowRepository = Depends(get_workflow_repository),
    executor: StageExecutor = Depends(get_stage_executor),
    preflight: ExecutionPreflightPort = Depends(get_execution_preflight),
    project_repo: ProjectRepository = Depends(get_workflow_project_repository),
    settings_repo: ProjectSettingsRepository = Depends(get_workflow_settings_repository),
    channel_repo: ChannelRepository = Depends(get_workflow_channel_repository),
    preset_repo: PresetRepository = Depends(get_workflow_preset_repository),
) -> WorkflowStateResponse:
    _require_project(project_id, project_repo)
    req = request or RunWorkflowRequest()
    engine = _build_engine(workflow_repo, executor, preflight)
    latest = _latest_job(workflow_repo, project_id)

    try:
        has_stale = latest is not None and any(s.status == "stale" for s in latest.stages)
        should_create_new = (
            req.force_new
            or latest is None
            or (latest.status in ("completed", "canceled") and not has_stale)
        )
        if should_create_new:
            stage_configs = _build_stage_configs(
                project_id,
                project_repo,
                settings_repo,
                channel_repo,
                preset_repo,
                override_modes=req.stage_modes,
            )
            job = engine.create_job(
                CreateWorkflowJobInput(
                    project_id=project_id,
                    stage_configs=stage_configs,
                    auto_start=True,
                )
            )
            return _state_response(project_id, job, workflow_repo)

        assert latest is not None
        if req.stage_modes:
            latest = _sync_modes_into_job(latest, req.stage_modes, workflow_repo)

        if latest.status == "pending":
            job = engine.start_job(latest.id)
        elif latest.status == "paused":
            job = engine.resume(latest.id)
        elif latest.status == "failed":
            failed_stage = next((s for s in latest.stages if s.status == "failed"), None)
            if failed_stage is not None:
                job = engine.retry(latest.id, failed_stage.stage_id)
            else:
                job = engine.resume(latest.id)
        else:
            job = engine.resume(latest.id)
        return _state_response(project_id, job, workflow_repo)
    except (WorkflowValidationError, WorkflowStateError, WorkflowNotFoundError) as err:
        raise _map_domain_error(err)


@router.post("/stages/{stage_id}/run", response_model=WorkflowStateResponse)
def run_workflow_stage(
    project_id: str,
    stage_id: str,
    workflow_repo: WorkflowRepository = Depends(get_workflow_repository),
    executor: StageExecutor = Depends(get_stage_executor),
    preflight: ExecutionPreflightPort = Depends(get_execution_preflight),
    project_repo: ProjectRepository = Depends(get_workflow_project_repository),
    settings_repo: ProjectSettingsRepository = Depends(get_workflow_settings_repository),
    channel_repo: ChannelRepository = Depends(get_workflow_channel_repository),
    preset_repo: PresetRepository = Depends(get_workflow_preset_repository),
) -> WorkflowStateResponse:
    _require_project(project_id, project_repo)
    engine = _build_engine(workflow_repo, executor, preflight)
    latest = _latest_job(workflow_repo, project_id)

    try:
        if latest is None or latest.status == "canceled":
            stage_configs = _build_stage_configs(
                project_id, project_repo, settings_repo, channel_repo, preset_repo
            )
            if stage_id not in stage_configs:
                raise WorkflowNotFoundError(f"Unknown workflow stage '{stage_id}'.")
            job = engine.create_job(
                CreateWorkflowJobInput(
                    project_id=project_id,
                    stage_configs=stage_configs,
                    auto_start=True,
                )
            )
            return _state_response(project_id, job, workflow_repo)

        stage = latest.get_stage(stage_id)
        if stage is None:
            raise WorkflowNotFoundError(f"Stage '{stage_id}' does not exist on job '{latest.id}'.")

        if stage.status in ("failed", "stale", "unknown_outcome"):
            job = engine.retry(latest.id, stage_id)
        elif stage.status == "completed":
            engine.invalidate_stage(
                InvalidateStageInput(
                    job_id=latest.id,
                    stage_id=stage_id,
                    reason=f"Requested rerun of stage '{stage_id}'.",
                )
            )
            job = engine.resume(latest.id)
        elif latest.status == "paused":
            job = engine.resume(latest.id)
        elif latest.status == "pending":
            job = engine.start_job(latest.id)
        else:
            job = engine.resume(latest.id)

        return _state_response(project_id, job, workflow_repo)
    except (WorkflowValidationError, WorkflowStateError, WorkflowNotFoundError) as err:
        raise _map_domain_error(err)


@router.post("/pause", response_model=WorkflowStateResponse)
def pause_project_workflow(
    project_id: str,
    workflow_repo: WorkflowRepository = Depends(get_workflow_repository),
    executor: StageExecutor = Depends(get_stage_executor),
    preflight: ExecutionPreflightPort = Depends(get_execution_preflight),
    project_repo: ProjectRepository = Depends(get_workflow_project_repository),
) -> WorkflowStateResponse:
    _require_project(project_id, project_repo)
    latest = _require_latest_job(workflow_repo, project_id)
    engine = _build_engine(workflow_repo, executor, preflight)
    try:
        job = engine.pause(latest.id)
        return _state_response(project_id, job, workflow_repo)
    except (WorkflowValidationError, WorkflowStateError, WorkflowNotFoundError) as err:
        raise _map_domain_error(err)


@router.post("/cancel", response_model=WorkflowStateResponse)
def cancel_project_workflow(
    project_id: str,
    workflow_repo: WorkflowRepository = Depends(get_workflow_repository),
    executor: StageExecutor = Depends(get_stage_executor),
    preflight: ExecutionPreflightPort = Depends(get_execution_preflight),
    project_repo: ProjectRepository = Depends(get_workflow_project_repository),
) -> WorkflowStateResponse:
    _require_project(project_id, project_repo)
    latest = _require_latest_job(workflow_repo, project_id)
    engine = _build_engine(workflow_repo, executor, preflight)
    try:
        job = engine.cancel(latest.id)
        return _state_response(project_id, job, workflow_repo)
    except (WorkflowValidationError, WorkflowStateError, WorkflowNotFoundError) as err:
        raise _map_domain_error(err)


@router.post("/resume", response_model=WorkflowStateResponse)
def resume_project_workflow(
    project_id: str,
    workflow_repo: WorkflowRepository = Depends(get_workflow_repository),
    executor: StageExecutor = Depends(get_stage_executor),
    preflight: ExecutionPreflightPort = Depends(get_execution_preflight),
    project_repo: ProjectRepository = Depends(get_workflow_project_repository),
) -> WorkflowStateResponse:
    _require_project(project_id, project_repo)
    latest = _require_latest_job(workflow_repo, project_id)
    engine = _build_engine(workflow_repo, executor, preflight)
    try:
        job = engine.resume(latest.id)
        return _state_response(project_id, job, workflow_repo)
    except (WorkflowValidationError, WorkflowStateError, WorkflowNotFoundError) as err:
        raise _map_domain_error(err)


@router.post("/stages/{stage_id}/retry", response_model=WorkflowStateResponse)
def retry_workflow_stage(
    project_id: str,
    stage_id: str,
    workflow_repo: WorkflowRepository = Depends(get_workflow_repository),
    executor: StageExecutor = Depends(get_stage_executor),
    preflight: ExecutionPreflightPort = Depends(get_execution_preflight),
    project_repo: ProjectRepository = Depends(get_workflow_project_repository),
) -> WorkflowStateResponse:
    _require_project(project_id, project_repo)
    latest = _require_latest_job(workflow_repo, project_id)
    engine = _build_engine(workflow_repo, executor, preflight)
    try:
        job = engine.retry(latest.id, stage_id)
        return _state_response(project_id, job, workflow_repo)
    except (WorkflowValidationError, WorkflowStateError, WorkflowNotFoundError) as err:
        raise _map_domain_error(err)


@router.post("/stages/{stage_id}/manual", response_model=WorkflowStateResponse)
def submit_manual_stage(
    project_id: str,
    stage_id: str,
    request: SubmitManualStageRequest,
    workflow_repo: WorkflowRepository = Depends(get_workflow_repository),
    executor: StageExecutor = Depends(get_stage_executor),
    preflight: ExecutionPreflightPort = Depends(get_execution_preflight),
    project_repo: ProjectRepository = Depends(get_workflow_project_repository),
) -> WorkflowStateResponse:
    _require_project(project_id, project_repo)
    latest = _require_latest_job(workflow_repo, project_id)
    stage = latest.get_stage(stage_id)
    if stage is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stage '{stage_id}' does not exist.",
        )

    payload_data = copy.deepcopy(request.data)
    if request.content is not None:
        payload_data["content"] = request.content
    if not payload_data and not request.uri:
        payload_data = {"manual": True}

    artifact = StageArtifactDto(
        artifact_id=request.artifact_id or f"manual-{stage_id}-{uuid.uuid4().hex[:8]}",
        stage_id=stage_id,
        artifact_type=stage.artifact_type,
        uri=request.uri,
        data=payload_data,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    engine = _build_engine(workflow_repo, executor, preflight)
    try:
        job = engine.submit_manual_result(
            SubmitManualStageInput(
                job_id=latest.id,
                stage_id=stage_id,
                artifact=artifact,
                auto_resume=request.auto_resume,
            )
        )
        return _state_response(project_id, job, workflow_repo)
    except (WorkflowValidationError, WorkflowStateError, WorkflowNotFoundError) as err:
        raise _map_domain_error(err)


@router.post("/stages/{stage_id}/approve", response_model=WorkflowStateResponse)
def approve_or_reject_stage(
    project_id: str,
    stage_id: str,
    request: ApproveStageRequest,
    workflow_repo: WorkflowRepository = Depends(get_workflow_repository),
    executor: StageExecutor = Depends(get_stage_executor),
    preflight: ExecutionPreflightPort = Depends(get_execution_preflight),
    project_repo: ProjectRepository = Depends(get_workflow_project_repository),
) -> WorkflowStateResponse:
    _require_project(project_id, project_repo)
    latest = _require_latest_job(workflow_repo, project_id)
    stage = latest.get_stage(stage_id)
    if stage is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stage '{stage_id}' does not exist.",
        )

    engine = _build_engine(workflow_repo, executor, preflight)
    try:
        if not request.approved:
            job = engine.reject_stage(
                RejectStageInput(
                    job_id=latest.id,
                    stage_id=stage_id,
                    reason=request.reason,
                    rerun=request.rerun,
                )
            )
            return _state_response(project_id, job, workflow_repo)

        edited_artifact: Optional[StageArtifactDto] = None
        if request.edited_content is not None or request.edited_data is not None:
            base_data = dict(stage.artifact.data) if stage.artifact is not None else {}
            if request.edited_data:
                base_data.update(request.edited_data)
            if request.edited_content is not None:
                base_data["text"] = request.edited_content
                base_data["content"] = request.edited_content
            edited_artifact = StageArtifactDto(
                artifact_id=f"{stage_id}-approved-{uuid.uuid4().hex[:8]}",
                stage_id=stage_id,
                artifact_type=stage.artifact_type,
                uri=stage.artifact.uri if stage.artifact is not None else None,
                data=base_data,
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        job = engine.approve_stage(
            ApproveStageInput(
                job_id=latest.id,
                stage_id=stage_id,
                edited_artifact=edited_artifact,
                auto_resume=request.auto_resume,
            )
        )
        return _state_response(project_id, job, workflow_repo)
    except (WorkflowValidationError, WorkflowStateError, WorkflowNotFoundError) as err:
        raise _map_domain_error(err)


@router.put("/stages/{stage_id}/mode", response_model=WorkflowStateResponse)
def update_stage_mode(
    project_id: str,
    stage_id: str,
    request: UpdateStageModeRequest,
    workflow_repo: WorkflowRepository = Depends(get_workflow_repository),
    project_repo: ProjectRepository = Depends(get_workflow_project_repository),
    settings_repo: ProjectSettingsRepository = Depends(get_workflow_settings_repository),
    channel_repo: ChannelRepository = Depends(get_workflow_channel_repository),
    preset_repo: PresetRepository = Depends(get_workflow_preset_repository),
) -> WorkflowStateResponse:
    _require_project(project_id, project_repo)
    try:
        StageMode(request.mode)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported stage mode '{request.mode}'.",
        )

    if stage_id not in DEFAULT_STAGE_ORDER:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown workflow stage '{stage_id}'.",
        )

    UpdateProjectSettingsUseCase(
        settings_repository=settings_repo,
        project_repository=project_repo,
        channel_repository=channel_repo,
        preset_repository=preset_repo,
    ).execute(
        UpdateProjectSettingsInput(
            project_id=project_id,
            stage_modes={stage_id: request.mode},
        )
    )

    latest = _latest_job(workflow_repo, project_id)
    if latest is not None and latest.status != "canceled":
        latest = _sync_modes_into_job(latest, {stage_id: request.mode}, workflow_repo)

    return _state_response(project_id, latest, workflow_repo)


@router.put("/scenes/{scene_id}", response_model=WorkflowStateResponse)
def update_workflow_scene(
    project_id: str,
    scene_id: str,
    request: UpdateSceneRequest,
    workflow_repo: WorkflowRepository = Depends(get_workflow_repository),
    executor: StageExecutor = Depends(get_stage_executor),
    preflight: ExecutionPreflightPort = Depends(get_execution_preflight),
    project_repo: ProjectRepository = Depends(get_workflow_project_repository),
) -> WorkflowStateResponse:
    _require_project(project_id, project_repo)
    latest = _require_latest_job(workflow_repo, project_id)
    scenes_stage = latest.get_stage("scenes")
    if scenes_stage is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenes stage not found on active workflow job.",
        )

    existing_item = next((i for i in scenes_stage.items if i.item_id == scene_id), None)
    merged_input: Dict[str, Any] = dict(existing_item.input_data) if existing_item else {}
    merged_input.update(request.input_data)
    if request.prompt is not None:
        merged_input["prompt"] = request.prompt
    if request.notes is not None:
        merged_input["notes"] = request.notes
    if request.title is not None:
        merged_input["title"] = request.title

    engine = _build_engine(workflow_repo, executor, preflight)
    try:
        job = engine.invalidate_stage(
            InvalidateStageInput(
                job_id=latest.id,
                stage_id="scenes",
                item_ids=(scene_id,),
                item_inputs={scene_id: merged_input},
                reason=request.reason or f"Updated scene '{scene_id}'",
            )
        )
        return _state_response(project_id, job, workflow_repo)
    except (WorkflowValidationError, WorkflowStateError, WorkflowNotFoundError) as err:
        raise _map_domain_error(err)
