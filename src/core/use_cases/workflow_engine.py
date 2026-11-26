"""Pure domain workflow engine orchestrating stages, modes, pause/cancel, reconciliation, and invalidation."""
import copy
import uuid
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from src.core.dto.workflow_dto import (
    ApproveStageInput,
    CheckStageRunInput,
    CreateWorkflowJobInput,
    InvalidateStageInput,
    PreflightCheckInput,
    ReconcileProjectResult,
    RejectStageInput,
    ResolveUnknownStageInput,
    StageArtifactDto,
    StageConfigInput,
    StageDefinitionInput,
    StageExecutionInput,
    StageExecutionResult,
    StageItemStateDto,
    SubmitManualStageInput,
    WorkflowJobResult,
    WorkflowStageResult,
)
from src.core.entities.workflow import (
    DEFAULT_STAGE_DEFINITIONS,
    JobStatus,
    StageArtifact,
    StageDefinition,
    StageItemState,
    StageMode,
    StageState,
    StageStatus,
    WorkflowJob,
    WorkflowNotFoundError,
    WorkflowStateError,
    WorkflowValidationError,
    compute_downstream_stages,
    validate_stage_dag,
)
from src.core.ports.execution_preflight import (
    AllowAllExecutionPreflight,
    ExecutionPreflightPort,
)
from src.core.ports.stage_executor import StageExecutor
from src.core.ports.workflow_repository import WorkflowRepository


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_dt(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value is not None else None


def _parse_stage_mode(raw: str) -> StageMode:
    try:
        return StageMode(raw)
    except ValueError as exc:
        raise WorkflowValidationError(f"Unsupported stage mode '{raw}'.") from exc


def _artifact_from_dto(dto: Optional[StageArtifactDto]) -> Optional[StageArtifact]:
    if dto is None:
        return None
    return StageArtifact(
        artifact_id=dto.artifact_id,
        stage_id=dto.stage_id,
        artifact_type=dto.artifact_type,
        uri=dto.uri,
        data=copy.deepcopy(dto.data),
        schema_version=dto.schema_version,
        compatible=dto.compatible,
        stale=dto.stale,
        created_at=_parse_dt(dto.created_at),
        content_hash=dto.content_hash,
    )


def _artifact_to_dto(entity: Optional[StageArtifact]) -> Optional[StageArtifactDto]:
    if entity is None:
        return None
    return StageArtifactDto(
        artifact_id=entity.artifact_id,
        stage_id=entity.stage_id,
        artifact_type=entity.artifact_type,
        uri=entity.uri,
        data=copy.deepcopy(entity.data),
        schema_version=entity.schema_version,
        compatible=entity.compatible,
        stale=entity.stale,
        created_at=_format_dt(entity.created_at),
        content_hash=entity.content_hash,
    )


def _item_from_dto(dto: StageItemStateDto) -> StageItemState:
    return StageItemState(
        item_id=dto.item_id,
        status=StageStatus(dto.status),
        artifact=_artifact_from_dto(dto.artifact),
        input_data=copy.deepcopy(dto.input_data),
        error=dto.error,
    )


def _item_to_dto(entity: StageItemState) -> StageItemStateDto:
    return StageItemStateDto(
        item_id=entity.item_id,
        status=entity.status.value,
        artifact=_artifact_to_dto(entity.artifact),
        input_data=copy.deepcopy(entity.input_data),
        error=entity.error,
    )


def _job_to_dto(job: WorkflowJob) -> WorkflowJobResult:
    stage_results: List[WorkflowStageResult] = []
    for stage_id in job.stage_order:
        stage = job.stages[stage_id]
        items_dto = tuple(_item_to_dto(stage.items[k]) for k in stage.items)
        stage_results.append(
            WorkflowStageResult(
                stage_id=stage.stage_id,
                mode=stage.mode.value,
                status=stage.status.value,
                dependencies=stage.dependencies,
                required=stage.required,
                artifact_type=stage.artifact_type,
                required_schema_version=stage.required_schema_version,
                artifact=_artifact_to_dto(stage.artifact),
                items=items_dto,
                params=copy.deepcopy(stage.params),
                external_run_id=stage.external_run_id,
                error=stage.error,
                attempt_count=stage.attempt_count,
                started_at=_format_dt(stage.started_at),
                completed_at=_format_dt(stage.completed_at),
                updated_at=_format_dt(stage.updated_at),
            )
        )
    return WorkflowJobResult(
        id=job.id,
        project_id=job.project_id,
        status=job.status.value,
        stage_order=job.stage_order,
        stages=tuple(stage_results),
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
        pause_requested=job.pause_requested,
        cancel_requested=job.cancel_requested,
        completed_at=_format_dt(job.completed_at),
        error=job.error,
        metadata=copy.deepcopy(job.metadata),
    )


def _job_from_dto(dto: WorkflowJobResult) -> WorkflowJob:
    stages: Dict[str, StageState] = {}
    for stage_dto in dto.stages:
        items = {item_dto.item_id: _item_from_dto(item_dto) for item_dto in stage_dto.items}
        stages[stage_dto.stage_id] = StageState(
            stage_id=stage_dto.stage_id,
            mode=StageMode(stage_dto.mode),
            status=StageStatus(stage_dto.status),
            dependencies=stage_dto.dependencies,
            required=stage_dto.required,
            artifact_type=stage_dto.artifact_type,
            required_schema_version=stage_dto.required_schema_version,
            artifact=_artifact_from_dto(stage_dto.artifact),
            items=items,
            params=copy.deepcopy(stage_dto.params),
            external_run_id=stage_dto.external_run_id,
            error=stage_dto.error,
            attempt_count=stage_dto.attempt_count,
            started_at=_parse_dt(stage_dto.started_at),
            completed_at=_parse_dt(stage_dto.completed_at),
            updated_at=_parse_dt(stage_dto.updated_at),
        )
    return WorkflowJob(
        id=dto.id,
        project_id=dto.project_id,
        status=JobStatus(dto.status),
        stage_order=dto.stage_order,
        stages=stages,
        created_at=datetime.fromisoformat(dto.created_at),
        updated_at=datetime.fromisoformat(dto.updated_at),
        pause_requested=dto.pause_requested,
        cancel_requested=dto.cancel_requested,
        completed_at=_parse_dt(dto.completed_at),
        error=dto.error,
        metadata=copy.deepcopy(dto.metadata),
    )


def _build_stage_definitions(
    custom: Optional[Tuple[StageDefinitionInput, ...]],
) -> Tuple[StageDefinition, ...]:
    if custom is None:
        return DEFAULT_STAGE_DEFINITIONS
    return tuple(
        StageDefinition(
            stage_id=item.stage_id,
            dependencies=item.dependencies,
            required=item.required,
            artifact_type=item.artifact_type or item.stage_id,
            default_mode=_parse_stage_mode(item.default_mode),
            required_schema_version=item.required_schema_version,
        )
        for item in custom
    )


class WorkflowEngine:
    """Core scheduler and lifecycle manager for persisted workflow jobs."""

    def __init__(
        self,
        repository: WorkflowRepository,
        executor: StageExecutor,
        preflight: Optional[ExecutionPreflightPort] = None,
    ) -> None:
        self._repository = repository
        self._executor = executor
        self._preflight = preflight or AllowAllExecutionPreflight()

    def create_job(self, input_data: CreateWorkflowJobInput) -> WorkflowJobResult:
        """Create, validate, and persist a new workflow job."""
        if not input_data.project_id or not input_data.project_id.strip():
            raise WorkflowValidationError("Project ID cannot be empty.")

        definitions = _build_stage_definitions(input_data.stage_definitions)
        stage_order = validate_stage_dag(definitions)
        def_by_id = {d.stage_id: d for d in definitions}

        unknown_configs = [
            stage_id
            for stage_id in input_data.stage_configs
            if stage_id not in def_by_id
        ]
        if unknown_configs:
            raise WorkflowValidationError(
                f"Unknown stage(s) in stage_configs: {unknown_configs}."
            )

        now = _utc_now()
        stages: Dict[str, StageState] = {}
        for stage_id in stage_order:
            definition = def_by_id[stage_id]
            cfg = input_data.stage_configs.get(stage_id, StageConfigInput())
            stages[stage_id] = self._build_initial_stage(definition, cfg, now)

        job = WorkflowJob(
            id=str(uuid.uuid4()),
            project_id=input_data.project_id.strip(),
            status=JobStatus.PENDING,
            stage_order=stage_order,
            stages=stages,
            created_at=now,
            updated_at=now,
            metadata=copy.deepcopy(input_data.metadata),
        )
        job.validate_off_stages()
        self._repository.save(_job_to_dto(job))

        if input_data.auto_start:
            return self.start_job(job.id)
        return _job_to_dto(job)

    def get_job(self, job_id: str) -> Optional[WorkflowJobResult]:
        """Retrieve a persisted workflow job by ID."""
        return self._repository.get_by_id(job_id)

    def list_project_jobs(self, project_id: str) -> List[WorkflowJobResult]:
        """List all persisted workflow jobs for a project."""
        return self._repository.list_by_project(project_id)

    def start_job(self, job_id: str, *, through_stage_id: Optional[str] = None) -> WorkflowJobResult:
        """Start or continue running an eligible pending/paused workflow job."""
        job = self._require_job(job_id)
        self._ensure_runnable_for_start(job)
        if job.pause_requested or job.status == JobStatus.PAUSED:
            return _job_to_dto(job)

        job.validate_off_stages()
        job.status = JobStatus.RUNNING
        job.updated_at = _utc_now()
        self._repository.save(_job_to_dto(job))
        return self._advance_job(job.id, through_stage_id=through_stage_id)

    def resume(
        self,
        job_id: str,
        *,
        through_stage_id: Optional[str] = None,
        confirmation_key: Optional[str] = None,
    ) -> WorkflowJobResult:
        """Clear a pause and resume executing eligible/stale stages."""
        job = self._require_job(job_id)
        if job.cancel_requested or job.status == JobStatus.CANCELED:
            raise WorkflowStateError("Cannot resume a canceled workflow job.")
        if job.status == JobStatus.NEEDS_RECONCILIATION:
            raise WorkflowStateError(
                "Job has stages with unknown outcome and requires reconciliation before resuming."
            )

        job.validate_off_stages()
        job.pause_requested = False
        job.error = None
        job.metadata.pop("preflight_block", None)
        job.status = JobStatus.RUNNING
        job.updated_at = _utc_now()
        self._repository.save(_job_to_dto(job))
        return self._advance_job(
            job.id, through_stage_id=through_stage_id, confirmation_key=confirmation_key
        )

    def pause(self, job_id: str) -> WorkflowJobResult:
        """Pause a job so no new stage submissions occur."""
        job = self._require_job(job_id)
        if job.status in (JobStatus.COMPLETED, JobStatus.CANCELED):
            raise WorkflowStateError(
                f"Cannot pause workflow job in '{job.status.value}' state."
            )
        job.pause_requested = True
        if job.status != JobStatus.NEEDS_RECONCILIATION:
            job.status = JobStatus.PAUSED
        job.updated_at = _utc_now()
        self._repository.save(_job_to_dto(job))
        return _job_to_dto(job)

    def cancel(self, job_id: str) -> WorkflowJobResult:
        """Cancel a job so no new stage submissions occur."""
        job = self._require_job(job_id)
        if job.status == JobStatus.COMPLETED:
            raise WorkflowStateError("Cannot cancel an already completed workflow job.")

        now = _utc_now()
        job.cancel_requested = True
        job.pause_requested = False
        job.status = JobStatus.CANCELED
        for stage in job.stages.values():
            if stage.status == StageStatus.RUNNING and stage.external_run_id:
                self._executor.cancel_run(job.id, stage.stage_id, stage.external_run_id)
            if stage.status not in (
                StageStatus.COMPLETED,
                StageStatus.SKIPPED,
                StageStatus.FAILED,
            ):
                stage.status = StageStatus.CANCELED
                stage.updated_at = now
        job.updated_at = now
        self._repository.save(_job_to_dto(job))
        return _job_to_dto(job)

    def retry(
        self,
        job_id: str,
        stage_id: str,
        *,
        auto_resume: bool = True,
    ) -> WorkflowJobResult:
        """Retry a failed, stale, canceled, or unknown-outcome stage without rerunning valid upstream stages."""
        job = self._require_job(job_id)
        stage = self._require_stage(job, stage_id)
        if job.cancel_requested or job.status == JobStatus.CANCELED:
            raise WorkflowStateError("Cannot retry a stage on a canceled workflow job.")
        if stage.status == StageStatus.RUNNING:
            raise WorkflowStateError(f"Stage '{stage_id}' is currently running.")
        if stage.status not in (
            StageStatus.FAILED,
            StageStatus.UNKNOWN_OUTCOME,
            StageStatus.STALE,
            StageStatus.CANCELED,
            StageStatus.COMPLETED,
        ):
            raise WorkflowStateError(
                f"Stage '{stage_id}' in status '{stage.status.value}' cannot be retried."
            )

        now = _utc_now()
        self._reset_stage_for_retry(stage, now)
        self._mark_downstream_stale(job, stage_id, now)

        has_remaining_unknown = any(
            s.status == StageStatus.UNKNOWN_OUTCOME for s in job.stages.values()
        )
        job.updated_at = now
        if not has_remaining_unknown:
            job.error = None

        if auto_resume and not has_remaining_unknown and not job.pause_requested:
            job.status = JobStatus.RUNNING
            self._repository.save(_job_to_dto(job))
            return self._advance_job(job.id)

        if has_remaining_unknown:
            job.status = JobStatus.NEEDS_RECONCILIATION
        elif job.status in (JobStatus.FAILED, JobStatus.COMPLETED, JobStatus.NEEDS_RECONCILIATION):
            job.status = JobStatus.PAUSED
        self._repository.save(_job_to_dto(job))
        return _job_to_dto(job)

    def reconcile(self, project_id: str) -> ReconcileProjectResult:
        """Reconcile persisted jobs for a project after an interrupted restart."""
        persisted = self._repository.list_by_project(project_id)
        updated_jobs: List[WorkflowJobResult] = []
        reconciled_ids: List[str] = []
        needs_review_ids: List[str] = []
        now = _utc_now()

        for job_dto in persisted:
            job = _job_from_dto(job_dto)
            if job.status in (JobStatus.COMPLETED, JobStatus.CANCELED):
                updated_jobs.append(job_dto)
                continue

            touched = self._reconcile_single_job(job, now)
            if touched:
                reconciled_ids.append(job.id)
                self._repository.save(_job_to_dto(job))
            if job.status == JobStatus.NEEDS_RECONCILIATION:
                needs_review_ids.append(job.id)
            updated_jobs.append(_job_to_dto(job))

        return ReconcileProjectResult(
            project_id=project_id,
            jobs=updated_jobs,
            reconciled_job_ids=tuple(reconciled_ids),
            needs_reconciliation_job_ids=tuple(needs_review_ids),
        )

    def submit_manual_result(
        self,
        input_data: SubmitManualStageInput,
    ) -> WorkflowJobResult:
        """Supply a user-provided artifact for a manual stage and optionally resume."""
        job = self._require_job(input_data.job_id)
        stage = self._require_stage(job, input_data.stage_id)
        if job.cancel_requested or job.status == JobStatus.CANCELED:
            raise WorkflowStateError("Cannot submit manual result to a canceled job.")
        if stage.status not in (
            StageStatus.WAITING_MANUAL,
            StageStatus.PENDING,
            StageStatus.STALE,
            StageStatus.FAILED,
        ):
            raise WorkflowStateError(
                f"Stage '{stage.stage_id}' in status '{stage.status.value}' cannot accept manual input."
            )

        artifact = _artifact_from_dto(input_data.artifact)
        if artifact is None or not artifact.is_valid_for(
            stage.artifact_type, stage.required_schema_version
        ):
            raise WorkflowValidationError(
                f"Manual artifact for stage '{stage.stage_id}' is not valid or compatible with '{stage.artifact_type}'."
            )

        now = _utc_now()
        stage.artifact = artifact
        stage.artifact.stale = False
        if input_data.items:
            stage.items = {item.item_id: _item_from_dto(item) for item in input_data.items}
        stage.status = StageStatus.COMPLETED
        stage.error = None
        stage.completed_at = now
        stage.updated_at = now

        self._mark_downstream_stale(job, stage.stage_id, now)
        job.updated_at = now

        if (
            input_data.auto_resume
            and not job.pause_requested
            and job.status != JobStatus.NEEDS_RECONCILIATION
        ):
            job.status = JobStatus.RUNNING
            self._repository.save(_job_to_dto(job))
            return self._advance_job(job.id)

        self._refresh_non_running_job_status(job, now)
        self._repository.save(_job_to_dto(job))
        return _job_to_dto(job)

    def approve_stage(self, input_data: ApproveStageInput) -> WorkflowJobResult:
        """Approve (and optionally edit) a stage paused in awaiting_approval."""
        job = self._require_job(input_data.job_id)
        stage = self._require_stage(job, input_data.stage_id)
        if stage.status != StageStatus.AWAITING_APPROVAL:
            raise WorkflowStateError(
                f"Stage '{stage.stage_id}' is '{stage.status.value}', not 'awaiting_approval'."
            )

        now = _utc_now()
        if input_data.edited_artifact is not None:
            edited = _artifact_from_dto(input_data.edited_artifact)
            if edited is None or not edited.is_valid_for(
                stage.artifact_type, stage.required_schema_version
            ):
                raise WorkflowValidationError(
                    f"Edited artifact for stage '{stage.stage_id}' is not compatible with '{stage.artifact_type}'."
                )
            stage.artifact = edited
        if input_data.edited_items:
            stage.items = {
                item.item_id: _item_from_dto(item) for item in input_data.edited_items
            }
        if stage.artifact is None:
            raise WorkflowValidationError(
                f"Cannot approve stage '{stage.stage_id}' without an artifact."
            )

        stage.artifact.stale = False
        stage.status = StageStatus.COMPLETED
        stage.error = None
        stage.completed_at = now
        stage.updated_at = now
        if input_data.edited_artifact is not None or input_data.edited_items:
            self._mark_downstream_stale(job, stage.stage_id, now)
        job.updated_at = now

        if (
            input_data.auto_resume
            and not job.pause_requested
            and job.status != JobStatus.NEEDS_RECONCILIATION
        ):
            job.status = JobStatus.RUNNING
            self._repository.save(_job_to_dto(job))
            return self._advance_job(job.id)

        self._refresh_non_running_job_status(job, now)
        self._repository.save(_job_to_dto(job))
        return _job_to_dto(job)

    def reject_stage(self, input_data: RejectStageInput) -> WorkflowJobResult:
        """Reject a stage output awaiting approval, pausing for review or rerunning it."""
        job = self._require_job(input_data.job_id)
        stage = self._require_stage(job, input_data.stage_id)
        if stage.status != StageStatus.AWAITING_APPROVAL:
            raise WorkflowStateError(
                f"Stage '{stage.stage_id}' is '{stage.status.value}', not 'awaiting_approval'."
            )

        now = _utc_now()
        if stage.artifact is not None:
            stage.artifact.compatible = False
            stage.artifact.stale = True
        stage.error = input_data.reason or "Stage output rejected by owner."
        stage.updated_at = now
        job.updated_at = now

        if input_data.rerun and not job.cancel_requested:
            stage.status = StageStatus.STALE
            job.pause_requested = False
            job.error = None
            job.status = JobStatus.RUNNING
            self._repository.save(_job_to_dto(job))
            return self._advance_job(job.id)

        stage.status = StageStatus.FAILED
        job.status = JobStatus.PAUSED
        job.error = stage.error
        self._repository.save(_job_to_dto(job))
        return _job_to_dto(job)

    def invalidate_stage(self, input_data: InvalidateStageInput) -> WorkflowJobResult:
        """Selectively mark a stage (or specific scene items) and downstream dependents stale."""
        job = self._require_job(input_data.job_id)
        stage = self._require_stage(job, input_data.stage_id)
        if job.cancel_requested or job.status == JobStatus.CANCELED:
            raise WorkflowStateError("Cannot invalidate stages on a canceled job.")

        now = _utc_now()
        if input_data.updated_params is not None:
            stage.params = copy.deepcopy(input_data.updated_params)

        target_item_ids = input_data.item_ids or tuple(input_data.item_inputs.keys())
        for item_id, updated_input in input_data.item_inputs.items():
            if item_id not in stage.items:
                raise WorkflowValidationError(
                    f"Unknown item ID '{item_id}' for stage '{stage.stage_id}'."
                )
            stage.items[item_id].input_data = copy.deepcopy(updated_input)

        stage.mark_stale(item_ids=target_item_ids if target_item_ids else None)
        stage.updated_at = now
        if input_data.reason:
            stage.error = None

        self._mark_downstream_stale(job, stage.stage_id, now)

        if job.status == JobStatus.COMPLETED:
            job.status = JobStatus.PAUSED
            job.completed_at = None
        job.updated_at = now
        self._repository.save(_job_to_dto(job))
        return _job_to_dto(job)

    def resolve_unknown_stage(
        self,
        input_data: ResolveUnknownStageInput,
    ) -> WorkflowJobResult:
        """Resolve an unknown_outcome stage after human review."""
        job = self._require_job(input_data.job_id)
        stage = self._require_stage(job, input_data.stage_id)
        if stage.status != StageStatus.UNKNOWN_OUTCOME:
            raise WorkflowStateError(
                f"Stage '{stage.stage_id}' is '{stage.status.value}', not 'unknown_outcome'."
            )

        if input_data.outcome == "retry":
            return self.retry(
                input_data.job_id,
                input_data.stage_id,
                auto_resume=input_data.auto_resume,
            )

        now = _utc_now()
        if input_data.outcome == "completed":
            artifact = _artifact_from_dto(input_data.artifact)
            if artifact is None or not artifact.is_valid_for(
                stage.artifact_type, stage.required_schema_version
            ):
                raise WorkflowValidationError(
                    f"Resolved artifact for '{stage.stage_id}' is not compatible with '{stage.artifact_type}'."
                )
            stage.artifact = artifact
            stage.artifact.stale = False
            if input_data.items:
                stage.items = {
                    item.item_id: _item_from_dto(item) for item in input_data.items
                }
            stage.status = (
                StageStatus.AWAITING_APPROVAL
                if stage.mode == StageMode.APPROVAL
                else StageStatus.COMPLETED
            )
            stage.completed_at = now if stage.status == StageStatus.COMPLETED else None
            stage.error = None
        elif input_data.outcome == "failed":
            stage.status = StageStatus.FAILED
            stage.error = input_data.error or "Marked failed during reconciliation."
        else:
            raise WorkflowValidationError(
                f"Unsupported resolution outcome '{input_data.outcome}'."
            )

        stage.updated_at = now
        job.updated_at = now
        has_unknown = any(
            s.status == StageStatus.UNKNOWN_OUTCOME for s in job.stages.values()
        )
        if has_unknown:
            job.status = JobStatus.NEEDS_RECONCILIATION
            self._repository.save(_job_to_dto(job))
            return _job_to_dto(job)

        job.error = None
        if input_data.auto_resume and not job.pause_requested and stage.status == StageStatus.COMPLETED:
            job.status = JobStatus.RUNNING
            self._repository.save(_job_to_dto(job))
            return self._advance_job(job.id)

        self._refresh_non_running_job_status(job, now)
        self._repository.save(_job_to_dto(job))
        return _job_to_dto(job)

    def _build_initial_stage(
        self,
        definition: StageDefinition,
        cfg: StageConfigInput,
        now: datetime,
    ) -> StageState:
        mode = _parse_stage_mode(cfg.mode) if cfg.mode else definition.default_mode
        artifact = _artifact_from_dto(cfg.saved_artifact)
        items = {item.item_id: _item_from_dto(item) for item in cfg.items}
        has_valid_saved = artifact is not None and artifact.is_valid_for(
            definition.artifact_type, definition.required_schema_version
        )

        if mode == StageMode.OFF:
            status = StageStatus.SKIPPED
            completed_at = None
        elif cfg.precompleted and has_valid_saved:
            status = StageStatus.COMPLETED
            completed_at = now
        else:
            status = StageStatus.PENDING
            completed_at = None

        return StageState(
            stage_id=definition.stage_id,
            mode=mode,
            status=status,
            dependencies=definition.dependencies,
            required=definition.required,
            artifact_type=definition.artifact_type,
            required_schema_version=definition.required_schema_version,
            artifact=artifact,
            items=items,
            params=copy.deepcopy(cfg.params),
            completed_at=completed_at,
            updated_at=now,
        )

    def _require_job(self, job_id: str) -> WorkflowJob:
        dto = self._repository.get_by_id(job_id)
        if dto is None:
            raise WorkflowNotFoundError(f"Workflow job '{job_id}' was not found.")
        return _job_from_dto(dto)

    def _require_stage(self, job: WorkflowJob, stage_id: str) -> StageState:
        stage = job.stages.get(stage_id)
        if stage is None:
            raise WorkflowNotFoundError(
                f"Stage '{stage_id}' does not exist on workflow job '{job.id}'."
            )
        return stage

    def _ensure_runnable_for_start(self, job: WorkflowJob) -> None:
        if job.cancel_requested or job.status == JobStatus.CANCELED:
            raise WorkflowStateError("Cannot start a canceled workflow job.")
        if job.status == JobStatus.NEEDS_RECONCILIATION:
            raise WorkflowStateError(
                "Job has stages with unknown outcome and requires reconciliation."
            )

    def _advance_job(
        self,
        job_id: str,
        *,
        through_stage_id: Optional[str] = None,
        confirmation_key: Optional[str] = None,
    ) -> WorkflowJobResult:
        eligible_ids = None
        if through_stage_id is not None:
            job = self._require_job(job_id)
            eligible_ids = {through_stage_id}
            for stage_id in reversed(job.stage_order):
                if stage_id in eligible_ids:
                    eligible_ids.update(job.stages[stage_id].dependencies)

        while True:
            job = self._require_job(job_id)
            job.validate_off_stages()
            now = _utc_now()

            if job.cancel_requested or job.status == JobStatus.CANCELED:
                job.status = JobStatus.CANCELED
                job.updated_at = now
                self._repository.save(_job_to_dto(job))
                return _job_to_dto(job)

            if job.pause_requested or job.status == JobStatus.PAUSED:
                job.status = JobStatus.PAUSED
                job.updated_at = now
                self._repository.save(_job_to_dto(job))
                return _job_to_dto(job)

            if job.status == JobStatus.NEEDS_RECONCILIATION:
                return _job_to_dto(job)

            next_stage = self._pick_next_stage(job, eligible_ids)
            if next_stage is None:
                self._refresh_non_running_job_status(job, now)
                job.updated_at = now
                self._repository.save(_job_to_dto(job))
                return _job_to_dto(job)

            should_continue = self._process_stage(job, next_stage, confirmation_key)
            if not should_continue:
                return _job_to_dto(self._require_job(job_id))

    def _pick_next_stage(
        self, job: WorkflowJob, eligible_ids: Optional[set[str]] = None
    ) -> Optional[StageState]:
        for stage_id in job.stage_order:
            if eligible_ids is not None and stage_id not in eligible_ids:
                continue
            stage = job.stages[stage_id]
            if stage.has_reusable_completion() or stage.status == StageStatus.SKIPPED:
                continue
            if stage.status not in (
                StageStatus.PENDING,
                StageStatus.QUEUED,
                StageStatus.STALE,
                StageStatus.COMPLETED,
            ):
                continue
            if job.are_dependencies_satisfied(stage_id):
                return stage
        return None

    def _process_stage(
        self, job: WorkflowJob, stage: StageState, confirmation_key: Optional[str]
    ) -> bool:
        now = _utc_now()
        job.metadata.pop("preflight_block", None)
        if stage.mode == StageMode.OFF:
            stage.status = StageStatus.SKIPPED
            stage.updated_at = now
            job.updated_at = now
            self._repository.save(_job_to_dto(job))
            return True

        if stage.mode == StageMode.MANUAL:
            stage.status = StageStatus.WAITING_MANUAL
            stage.updated_at = now
            job.updated_at = now
            self._repository.save(_job_to_dto(job))
            return True

        prior_status = stage.status
        stage.status = StageStatus.QUEUED
        stage.updated_at = now
        job.updated_at = now
        self._repository.save(_job_to_dto(job))

        preflight_decision = self._preflight.check(
            PreflightCheckInput(
                job_id=job.id,
                project_id=job.project_id,
                stage_id=stage.stage_id,
                mode=stage.mode.value,
                artifact_type=stage.artifact_type,
                params=copy.deepcopy(stage.params),
                metadata=copy.deepcopy(job.metadata),
                attempt=stage.attempt_count + 1,
                confirmation_key=confirmation_key,
            )
        )

        # Re-read persisted state in case a hook triggered pause/cancel.
        latest_job = self._require_job(job.id)
        latest_stage = latest_job.stages[stage.stage_id]
        if latest_job.cancel_requested or latest_job.status == JobStatus.CANCELED:
            latest_stage.status = StageStatus.CANCELED
            latest_job.status = JobStatus.CANCELED
            latest_job.updated_at = _utc_now()
            self._repository.save(_job_to_dto(latest_job))
            return False

        if latest_job.pause_requested or latest_job.status == JobStatus.PAUSED:
            latest_stage.status = (
                StageStatus.STALE
                if prior_status == StageStatus.STALE
                else StageStatus.PENDING
            )
            latest_job.status = JobStatus.PAUSED
            latest_job.updated_at = _utc_now()
            self._repository.save(_job_to_dto(latest_job))
            return False

        if not preflight_decision.allowed:
            reason = preflight_decision.reason or "Blocked by execution preflight."
            if preflight_decision.requires_confirmation:
                latest_stage.status = (
                    StageStatus.STALE
                    if prior_status == StageStatus.STALE
                    else StageStatus.PENDING
                )
                latest_job.status = JobStatus.PAUSED
                latest_job.error = reason
                latest_job.metadata["preflight_block"] = {
                    "stage_id": stage.stage_id,
                    "details": preflight_decision.details,
                    "reason": reason,
                }
            else:
                latest_stage.status = StageStatus.FAILED
                latest_stage.error = reason
                latest_job.status = JobStatus.FAILED
                latest_job.error = reason
            latest_stage.updated_at = _utc_now()
            latest_job.updated_at = _utc_now()
            self._repository.save(_job_to_dto(latest_job))
            return False

        exec_input, preserved_items = self._build_execution_input(latest_job, latest_stage)
        latest_stage.status = StageStatus.RUNNING
        latest_stage.attempt_count += 1
        latest_stage.started_at = _utc_now()
        latest_stage.error = None
        latest_stage.updated_at = latest_stage.started_at
        latest_job.updated_at = latest_stage.started_at
        self._repository.save(_job_to_dto(latest_job))

        try:
            exec_result = self._executor.execute(exec_input)
        except Exception as exc:
            exec_result = StageExecutionResult(status="failed", error=str(exc))

        after_job = self._require_job(job.id)
        after_stage = after_job.stages[stage.stage_id]
        self._apply_execution_result(after_job, after_stage, exec_result, preserved_items)

        if after_job.cancel_requested or after_job.status == JobStatus.CANCELED:
            after_job.status = JobStatus.CANCELED
            for candidate in after_job.stages.values():
                if candidate.status not in (
                    StageStatus.COMPLETED,
                    StageStatus.SKIPPED,
                    StageStatus.FAILED,
                ):
                    candidate.status = StageStatus.CANCELED
            self._repository.save(_job_to_dto(after_job))
            return False

        if after_job.pause_requested or after_job.status == JobStatus.PAUSED:
            after_job.status = JobStatus.PAUSED
            self._repository.save(_job_to_dto(after_job))
            return False

        self._repository.save(_job_to_dto(after_job))
        return after_stage.status in (StageStatus.COMPLETED, StageStatus.AWAITING_APPROVAL)

    def _build_execution_input(
        self,
        job: WorkflowJob,
        stage: StageState,
    ) -> Tuple[StageExecutionInput, Dict[str, StageItemState]]:
        dependency_artifacts: Dict[str, StageArtifactDto] = {}
        for dep_id in stage.dependencies:
            dep_stage = job.stages[dep_id]
            if dep_stage.has_valid_artifact():
                dep_dto = _artifact_to_dto(dep_stage.artifact)
                if dep_dto is not None:
                    dependency_artifacts[dep_id] = dep_dto

        stale_ids: List[str] = []
        preserved_entities: Dict[str, StageItemState] = {}
        preserved_dtos: Dict[str, StageItemStateDto] = {}
        for item_id, item in stage.items.items():
            is_valid_item = (
                item.status == StageStatus.COMPLETED
                and item.artifact is not None
                and item.artifact.compatible
                and not item.artifact.stale
            )
            if is_valid_item:
                preserved_entities[item_id] = item
                preserved_dtos[item_id] = _item_to_dto(item)
            else:
                stale_ids.append(item_id)

        exec_input = StageExecutionInput(
            job_id=job.id,
            project_id=job.project_id,
            stage_id=stage.stage_id,
            mode=stage.mode.value,
            artifact_type=stage.artifact_type,
            dependency_artifacts=dependency_artifacts,
            existing_artifact=_artifact_to_dto(stage.artifact),
            stale_item_ids=tuple(stale_ids),
            preserved_items=preserved_dtos,
            params=copy.deepcopy(stage.params),
            attempt=stage.attempt_count + 1,
            item_inputs={item_id: copy.deepcopy(stage.items[item_id].input_data) for item_id in stale_ids},
        )
        return exec_input, preserved_entities

    def _apply_execution_result(
        self,
        job: WorkflowJob,
        stage: StageState,
        result: StageExecutionResult,
        preserved_items: Dict[str, StageItemState],
    ) -> None:
        now = _utc_now()
        stage.updated_at = now
        job.updated_at = now
        if result.external_run_id is not None:
            stage.external_run_id = result.external_run_id

        if result.items:
            merged_items: Dict[str, StageItemState] = dict(preserved_items)
            for item_dto in result.items:
                item_entity = _item_from_dto(item_dto)
                if item_entity.artifact is not None:
                    item_entity.artifact.stale = False
                merged_items[item_entity.item_id] = item_entity
            stage.items = merged_items

        if result.status == "running":
            stage.status = StageStatus.RUNNING
            return

        if result.status == "failed":
            stage.status = StageStatus.FAILED
            stage.error = result.error or "Stage execution failed."
            job.status = JobStatus.FAILED
            job.error = stage.error
            return

        if result.status != "completed":
            stage.status = StageStatus.FAILED
            stage.error = f"Unsupported executor result status '{result.status}'."
            job.status = JobStatus.FAILED
            job.error = stage.error
            return

        artifact = _artifact_from_dto(result.artifact)
        if artifact is None:
            artifact = StageArtifact(
                artifact_id=f"{job.id}-{stage.stage_id}-v{stage.attempt_count}",
                stage_id=stage.stage_id,
                artifact_type=stage.artifact_type,
                data={"generated": True},
                created_at=now,
            )
        artifact.stale = False
        stage.artifact = artifact
        stage.error = None

        if stage.mode == StageMode.APPROVAL:
            stage.status = StageStatus.AWAITING_APPROVAL
        else:
            stage.status = StageStatus.COMPLETED
            stage.completed_at = now

    def _reconcile_single_job(self, job: WorkflowJob, now: datetime) -> bool:
        touched = False
        for stage_id in job.stage_order:
            stage = job.stages[stage_id]
            if stage.status == StageStatus.QUEUED and not stage.external_run_id:
                stage.status = StageStatus.PENDING
                stage.updated_at = now
                touched = True
                continue

            if stage.status not in (
                StageStatus.RUNNING,
                StageStatus.QUEUED,
                StageStatus.UNKNOWN_OUTCOME,
            ):
                continue

            touched = True
            if not stage.external_run_id:
                stage.status = StageStatus.UNKNOWN_OUTCOME
                stage.error = (
                    "Stage was left running across restart without a verifiable external run handle."
                )
                stage.updated_at = now
                continue

            try:
                status_res = self._executor.check_run_status(
                    CheckStageRunInput(
                        job_id=job.id,
                        project_id=job.project_id,
                        stage_id=stage.stage_id,
                        external_run_id=stage.external_run_id,
                        artifact_type=stage.artifact_type,
                    )
                )
            except Exception as exc:
                stage.status = StageStatus.UNKNOWN_OUTCOME
                stage.error = f"Failed to verify external run outcome: {exc}"
                stage.updated_at = now
                continue

            if status_res.status == "completed":
                artifact = _artifact_from_dto(status_res.artifact)
                if artifact is None:
                    artifact = StageArtifact(
                        artifact_id=f"{job.id}-{stage.stage_id}-reconciled",
                        stage_id=stage.stage_id,
                        artifact_type=stage.artifact_type,
                        data={"reconciled": True},
                        created_at=now,
                    )
                artifact.stale = False
                stage.artifact = artifact
                if status_res.items:
                    stage.items = {
                        item.item_id: _item_from_dto(item) for item in status_res.items
                    }
                stage.status = (
                    StageStatus.AWAITING_APPROVAL
                    if stage.mode == StageMode.APPROVAL
                    else StageStatus.COMPLETED
                )
                stage.completed_at = now if stage.status == StageStatus.COMPLETED else None
                stage.error = None
            elif status_res.status == "failed":
                stage.status = StageStatus.FAILED
                stage.error = status_res.error or "External stage run failed before restart."
            elif status_res.status == "canceled":
                stage.status = StageStatus.CANCELED
            else:
                stage.status = StageStatus.UNKNOWN_OUTCOME
                stage.error = (
                    status_res.message
                    or "External run outcome is unknown across restart; review required."
                )
            stage.updated_at = now

        if not touched and job.status != JobStatus.RUNNING:
            return False

        has_unknown = any(
            s.status == StageStatus.UNKNOWN_OUTCOME for s in job.stages.values()
        )
        if has_unknown:
            job.status = JobStatus.NEEDS_RECONCILIATION
            job.error = "Interrupted stage outcome is unknown; paused for reconciliation."
        else:
            self._refresh_non_running_job_status(job, now, interrupted_running=True)
        job.updated_at = now
        return True

    def _reset_stage_for_retry(self, stage: StageState, now: datetime) -> None:
        stage.error = None
        stage.external_run_id = None
        stage.updated_at = now
        if stage.items:
            for item in stage.items.values():
                if item.status != StageStatus.COMPLETED or (
                    item.artifact is None or item.artifact.stale or not item.artifact.compatible
                ):
                    item.status = StageStatus.STALE
                    item.error = None
                    if item.artifact is not None:
                        item.artifact.stale = True
            stage.status = StageStatus.STALE
            if stage.artifact is not None:
                stage.artifact.stale = True
            return

        stage.status = StageStatus.PENDING
        stage.artifact = None

    def _mark_downstream_stale(
        self,
        job: WorkflowJob,
        root_stage_id: str,
        now: datetime,
    ) -> None:
        downstream_ids = compute_downstream_stages(job.stages, root_stage_id)
        for stage_id in job.stage_order:
            if stage_id not in downstream_ids:
                continue
            ds = job.stages[stage_id]
            if ds.status == StageStatus.PENDING:
                continue
            if (
                ds.status == StageStatus.SKIPPED
                and ds.mode == StageMode.OFF
                and not ds.has_valid_artifact()
            ):
                continue
            ds.mark_stale()
            ds.updated_at = now

    def _refresh_non_running_job_status(
        self,
        job: WorkflowJob,
        now: datetime,
        *,
        interrupted_running: bool = False,
    ) -> None:
        statuses = {s.status for s in job.stages.values()}
        if StageStatus.UNKNOWN_OUTCOME in statuses:
            job.status = JobStatus.NEEDS_RECONCILIATION
            return
        if StageStatus.FAILED in statuses:
            job.status = JobStatus.FAILED
            return
        if StageStatus.RUNNING in statuses and not interrupted_running:
            job.status = JobStatus.RUNNING
            return
        all_done = all(
            stage.has_reusable_completion() or stage.status == StageStatus.SKIPPED
            for stage in job.stages.values()
        )
        if all_done:
            job.status = JobStatus.COMPLETED
            job.completed_at = now
            job.error = None
            return
        if (
            StageStatus.WAITING_MANUAL in statuses
            or StageStatus.AWAITING_APPROVAL in statuses
            or interrupted_running
            or job.pause_requested
            or any(s.status in (StageStatus.COMPLETED, StageStatus.STALE) for s in job.stages.values())
        ):
            job.status = JobStatus.PAUSED
            return
        job.status = JobStatus.PENDING
