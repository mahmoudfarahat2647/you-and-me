"""Plain frozen input and result DTOs at the workflow application boundary."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class StageDefinitionInput:
    """Plain input record defining a custom stage node in a workflow DAG."""

    stage_id: str
    dependencies: Tuple[str, ...] = ()
    required: bool = True
    artifact_type: str = ""
    default_mode: str = "auto"
    required_schema_version: Optional[str] = None


@dataclass(frozen=True)
class StageArtifactDto:
    """Plain record describing a stage artifact across application boundaries."""

    artifact_id: str
    stage_id: str
    artifact_type: str
    uri: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = "1.0"
    compatible: bool = True
    stale: bool = False
    created_at: Optional[str] = None
    content_hash: Optional[str] = None


@dataclass(frozen=True)
class StageItemStateDto:
    """Plain record describing an individual item inside a stage (e.g. a scene)."""

    item_id: str
    status: str = "pending"
    artifact: Optional[StageArtifactDto] = None
    input_data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass(frozen=True)
class StageConfigInput:
    """Plain input record configuring a stage when creating a workflow job."""

    mode: str = "auto"
    params: Dict[str, Any] = field(default_factory=dict)
    saved_artifact: Optional[StageArtifactDto] = None
    precompleted: bool = False
    items: Tuple[StageItemStateDto, ...] = ()


@dataclass(frozen=True)
class CreateWorkflowJobInput:
    """Plain input record for creating a persisted workflow job."""

    project_id: str
    stage_configs: Dict[str, StageConfigInput] = field(default_factory=dict)
    stage_definitions: Optional[Tuple[StageDefinitionInput, ...]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    auto_start: bool = False


@dataclass(frozen=True)
class WorkflowStageResult:
    """Plain result record representing one stage of a persisted workflow job."""

    stage_id: str
    mode: str
    status: str
    dependencies: Tuple[str, ...]
    required: bool
    artifact_type: str
    required_schema_version: Optional[str] = None
    artifact: Optional[StageArtifactDto] = None
    items: Tuple[StageItemStateDto, ...] = ()
    params: Dict[str, Any] = field(default_factory=dict)
    external_run_id: Optional[str] = None
    error: Optional[str] = None
    attempt_count: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass(frozen=True)
class WorkflowJobResult:
    """Plain result record representing a workflow job across repository and API boundaries."""

    id: str
    project_id: str
    status: str
    stage_order: Tuple[str, ...]
    stages: Tuple[WorkflowStageResult, ...]
    created_at: str
    updated_at: str
    pause_requested: bool = False
    cancel_requested: bool = False
    completed_at: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_stage(self, stage_id: str) -> Optional[WorkflowStageResult]:
        """Return the stage result matching stage_id, or None."""
        for stage in self.stages:
            if stage.stage_id == stage_id:
                return stage
        return None


@dataclass(frozen=True)
class StageExecutionInput:
    """Plain input record passed to StageExecutor when running a stage."""

    job_id: str
    project_id: str
    stage_id: str
    mode: str
    artifact_type: str
    dependency_artifacts: Dict[str, StageArtifactDto] = field(default_factory=dict)
    existing_artifact: Optional[StageArtifactDto] = None
    stale_item_ids: Tuple[str, ...] = ()
    preserved_items: Dict[str, StageItemStateDto] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    attempt: int = 1


@dataclass(frozen=True)
class StageExecutionResult:
    """Plain result record returned by StageExecutor after executing or submitting a stage."""

    status: str
    artifact: Optional[StageArtifactDto] = None
    items: Tuple[StageItemStateDto, ...] = ()
    external_run_id: Optional[str] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class CheckStageRunInput:
    """Plain input record for querying an external run handle during reconciliation."""

    job_id: str
    project_id: str
    stage_id: str
    external_run_id: str
    artifact_type: str


@dataclass(frozen=True)
class StageRunStatusResult:
    """Plain result record describing the external state of an interrupted run."""

    status: str
    artifact: Optional[StageArtifactDto] = None
    items: Tuple[StageItemStateDto, ...] = ()
    error: Optional[str] = None
    message: Optional[str] = None


@dataclass(frozen=True)
class PreflightCheckInput:
    """Plain input record passed to ExecutionPreflightPort before stage submission."""

    job_id: str
    project_id: str
    stage_id: str
    mode: str
    artifact_type: str
    params: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PreflightDecision:
    """Plain result record returned by ExecutionPreflightPort."""

    allowed: bool
    reason: Optional[str] = None
    requires_confirmation: bool = False


@dataclass(frozen=True)
class SubmitManualStageInput:
    """Plain input record for supplying manual output to a waiting_manual stage."""

    job_id: str
    stage_id: str
    artifact: StageArtifactDto
    items: Tuple[StageItemStateDto, ...] = ()
    auto_resume: bool = True


@dataclass(frozen=True)
class ApproveStageInput:
    """Plain input record for approving (and optionally editing) an awaiting_approval stage."""

    job_id: str
    stage_id: str
    edited_artifact: Optional[StageArtifactDto] = None
    edited_items: Tuple[StageItemStateDto, ...] = ()
    auto_resume: bool = True


@dataclass(frozen=True)
class RejectStageInput:
    """Plain input record for rejecting an awaiting_approval stage."""

    job_id: str
    stage_id: str
    reason: Optional[str] = None
    rerun: bool = False


@dataclass(frozen=True)
class InvalidateStageInput:
    """Plain input record for invalidating a stage or specific scene items."""

    job_id: str
    stage_id: str
    item_ids: Tuple[str, ...] = ()
    item_inputs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    updated_params: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None


@dataclass(frozen=True)
class ResolveUnknownStageInput:
    """Plain input record for manually resolving an unknown_outcome stage after restart."""

    job_id: str
    stage_id: str
    outcome: str
    artifact: Optional[StageArtifactDto] = None
    items: Tuple[StageItemStateDto, ...] = ()
    error: Optional[str] = None
    auto_resume: bool = False


@dataclass(frozen=True)
class ReconcileProjectResult:
    """Plain result record returned after reconciling a project's persisted jobs."""

    project_id: str
    jobs: List[WorkflowJobResult]
    reconciled_job_ids: Tuple[str, ...]
    needs_reconciliation_job_ids: Tuple[str, ...]
