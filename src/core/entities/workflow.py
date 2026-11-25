"""Core workflow domain entities, enums, DAG validation, and domain rules."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


class WorkflowError(Exception):
    """Base exception for workflow domain errors."""


class WorkflowValidationError(WorkflowError):
    """Raised when workflow configuration, DAG, or artifact validation fails."""


class WorkflowNotFoundError(WorkflowError):
    """Raised when a referenced workflow job or stage cannot be found."""


class WorkflowStateError(WorkflowError):
    """Raised when an operation is invalid for the current job or stage state."""


class StageMode(str, Enum):
    """Execution mode configured for a workflow stage."""

    AUTO = "auto"
    MANUAL = "manual"
    APPROVAL = "approval"
    OFF = "off"


class JobStatus(str, Enum):
    """Lifecycle statuses for a workflow job."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    NEEDS_RECONCILIATION = "needs_reconciliation"


class StageStatus(str, Enum):
    """Lifecycle statuses for an individual workflow stage."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_MANUAL = "waiting_manual"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    SKIPPED = "skipped"
    STALE = "stale"
    UNKNOWN_OUTCOME = "unknown_outcome"


DEFAULT_STAGE_ORDER: Tuple[str, ...] = (
    "idea",
    "script",
    "voice",
    "scenes",
    "edit",
    "export",
)


@dataclass(frozen=True)
class StageDefinition:
    """Immutable definition of a stage node within a workflow DAG."""

    stage_id: str
    dependencies: Tuple[str, ...] = ()
    required: bool = True
    artifact_type: str = ""
    default_mode: StageMode = StageMode.AUTO
    required_schema_version: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.stage_id or not self.stage_id.strip():
            raise WorkflowValidationError("Stage ID cannot be empty.")
        if not self.artifact_type:
            object.__setattr__(self, "artifact_type", self.stage_id)


DEFAULT_STAGE_DEFINITIONS: Tuple[StageDefinition, ...] = (
    StageDefinition(
        stage_id="idea",
        dependencies=(),
        required=False,
        artifact_type="topic",
        default_mode=StageMode.AUTO,
    ),
    StageDefinition(
        stage_id="script",
        dependencies=("idea",),
        required=True,
        artifact_type="script",
        default_mode=StageMode.AUTO,
    ),
    StageDefinition(
        stage_id="voice",
        dependencies=("script",),
        required=True,
        artifact_type="narration",
        default_mode=StageMode.AUTO,
    ),
    StageDefinition(
        stage_id="scenes",
        dependencies=("script",),
        required=True,
        artifact_type="scene_clips",
        default_mode=StageMode.AUTO,
    ),
    StageDefinition(
        stage_id="edit",
        dependencies=("voice", "scenes"),
        required=True,
        artifact_type="edited_video",
        default_mode=StageMode.AUTO,
    ),
    StageDefinition(
        stage_id="export",
        dependencies=("edit",),
        required=True,
        artifact_type="final_video",
        default_mode=StageMode.AUTO,
    ),
)


@dataclass
class StageArtifact:
    """Domain entity representing an output artifact produced or supplied for a stage."""

    artifact_id: str
    stage_id: str
    artifact_type: str
    uri: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = "1.0"
    compatible: bool = True
    stale: bool = False
    created_at: Optional[datetime] = None
    content_hash: Optional[str] = None

    def is_valid_for(
        self,
        expected_artifact_type: str,
        required_schema_version: Optional[str] = None,
    ) -> bool:
        """Return True when this artifact is compatible, non-stale, and matches type/schema."""
        if not self.compatible or self.stale:
            return False
        if expected_artifact_type and self.artifact_type != expected_artifact_type:
            return False
        if required_schema_version and self.schema_version != required_schema_version:
            return False
        return bool(self.artifact_id or self.uri or self.data)


@dataclass
class StageItemState:
    """State of an individual item within a multi-item stage (e.g. a single scene)."""

    item_id: str
    status: StageStatus = StageStatus.PENDING
    artifact: Optional[StageArtifact] = None
    input_data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class StageState:
    """Mutable runtime state for a single stage in a workflow job."""

    stage_id: str
    mode: StageMode = StageMode.AUTO
    status: StageStatus = StageStatus.PENDING
    dependencies: Tuple[str, ...] = ()
    required: bool = True
    artifact_type: str = ""
    required_schema_version: Optional[str] = None
    artifact: Optional[StageArtifact] = None
    items: Dict[str, StageItemState] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    external_run_id: Optional[str] = None
    error: Optional[str] = None
    attempt_count: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.artifact_type:
            self.artifact_type = self.stage_id

    def has_valid_artifact(self) -> bool:
        """Return True if this stage holds a compatible, non-stale artifact."""
        if self.status == StageStatus.STALE or self.artifact is None:
            return False
        return self.artifact.is_valid_for(
            expected_artifact_type=self.artifact_type,
            required_schema_version=self.required_schema_version,
        )

    def has_reusable_completion(self) -> bool:
        """Return True if this stage is completed with a valid non-stale artifact."""
        return self.status == StageStatus.COMPLETED and self.has_valid_artifact()

    def mark_stale(self, item_ids: Optional[Iterable[str]] = None) -> None:
        """Mark this stage (or specific items within it) as stale."""
        target_items = tuple(item_ids) if item_ids is not None else ()
        if target_items and self.items:
            unknown = [item_id for item_id in target_items if item_id not in self.items]
            if unknown:
                raise WorkflowValidationError(
                    f"Unknown item ID(s) {unknown} for stage '{self.stage_id}'."
                )
            for item_id in target_items:
                item = self.items[item_id]
                item.status = StageStatus.STALE
                if item.artifact is not None:
                    item.artifact.stale = True
            self.status = StageStatus.STALE
            if self.artifact is not None:
                self.artifact.stale = True
            return

        self.status = StageStatus.STALE
        if self.artifact is not None:
            self.artifact.stale = True
        for item in self.items.values():
            item.status = StageStatus.STALE
            if item.artifact is not None:
                item.artifact.stale = True


def validate_stage_dag(definitions: Sequence[StageDefinition]) -> Tuple[str, ...]:
    """Validate stage definitions form an acyclic DAG and return topological order."""
    if not definitions:
        raise WorkflowValidationError("Workflow must define at least one stage.")

    by_id: Dict[str, StageDefinition] = {}
    for definition in definitions:
        if definition.stage_id in by_id:
            raise WorkflowValidationError(
                f"Duplicate stage definition '{definition.stage_id}'."
            )
        by_id[definition.stage_id] = definition

    for definition in definitions:
        for dep in definition.dependencies:
            if dep not in by_id:
                raise WorkflowValidationError(
                    f"Stage '{definition.stage_id}' depends on unknown stage '{dep}'."
                )
            if dep == definition.stage_id:
                raise WorkflowValidationError(
                    f"Stage '{definition.stage_id}' cannot depend on itself."
                )

    in_degree: Dict[str, int] = {d.stage_id: len(d.dependencies) for d in definitions}
    dependents: Dict[str, List[str]] = {d.stage_id: [] for d in definitions}
    for definition in definitions:
        for dep in definition.dependencies:
            dependents[dep].append(definition.stage_id)

    queue: List[str] = [d.stage_id for d in definitions if in_degree[d.stage_id] == 0]
    ordered: List[str] = []

    while queue:
        current = queue.pop(0)
        ordered.append(current)
        for nxt in dependents[current]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)

    if len(ordered) != len(definitions):
        raise WorkflowValidationError("Workflow stage dependencies contain a cycle.")

    return tuple(ordered)


def compute_downstream_stages(
    stages: Mapping[str, StageState],
    root_stage_id: str,
) -> Set[str]:
    """Return all stage IDs strictly downstream of root_stage_id in the DAG."""
    dependents: Dict[str, List[str]] = {stage_id: [] for stage_id in stages}
    for stage in stages.values():
        for dep_id in stage.dependencies:
            if dep_id in dependents:
                dependents[dep_id].append(stage.stage_id)

    visited: Set[str] = set()
    stack: List[str] = list(dependents.get(root_stage_id, ()))
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        stack.extend(dependents.get(current, ()))
    return visited


@dataclass
class WorkflowJob:
    """Aggregate root representing a persisted workflow job and its stages."""

    id: str
    project_id: str
    status: JobStatus
    stage_order: Tuple[str, ...]
    stages: Dict[str, StageState]
    created_at: datetime
    updated_at: datetime
    pause_requested: bool = False
    cancel_requested: bool = False
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise WorkflowValidationError("Workflow job ID cannot be empty.")
        if not self.project_id or not self.project_id.strip():
            raise WorkflowValidationError("Workflow project ID cannot be empty.")
        definitions = tuple(
            StageDefinition(
                stage_id=stage_id,
                dependencies=self.stages[stage_id].dependencies,
                required=self.stages[stage_id].required,
                artifact_type=self.stages[stage_id].artifact_type,
                default_mode=self.stages[stage_id].mode,
                required_schema_version=self.stages[stage_id].required_schema_version,
            )
            for stage_id in self.stage_order
        )
        validate_stage_dag(definitions)

    def validate_off_stages(self) -> None:
        """Ensure every required stage in OFF mode has a valid compatible saved artifact."""
        for stage_id in self.stage_order:
            stage = self.stages[stage_id]
            if stage.mode != StageMode.OFF:
                continue
            if stage.required and not stage.has_valid_artifact():
                expected = stage.artifact_type or stage.stage_id
                raise WorkflowValidationError(
                    f"Stage '{stage.stage_id}' is required and configured as 'off', "
                    f"but no valid compatible '{expected}' artifact is present."
                )

    def are_dependencies_satisfied(self, stage_id: str) -> bool:
        """Return True if every upstream dependency of stage_id is satisfied."""
        stage = self.stages[stage_id]
        for dep_id in stage.dependencies:
            dep = self.stages[dep_id]
            if dep.has_reusable_completion():
                continue
            if dep.status == StageStatus.SKIPPED:
                if dep.has_valid_artifact() or not dep.required:
                    continue
            return False
        return True
