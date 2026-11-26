"""Port interface for executing workflow stages and querying external runs."""
from abc import ABC, abstractmethod
from src.core.dto.workflow_dto import (
    CheckStageRunInput,
    StageExecutionInput,
    StageExecutionResult,
    StageRunStatusResult,
)


class StageExecutor(ABC):
    """Abstract port for executing a workflow stage without coupling to adapters."""

    @abstractmethod
    def execute(self, request: StageExecutionInput) -> StageExecutionResult:
        """Execute or submit a stage and return a plain execution result."""
        pass

    def check_run_status(self, request: CheckStageRunInput) -> StageRunStatusResult:
        """Query the outcome of a previously submitted external run handle.

        Adapters that only run synchronously can rely on the default 'unknown'
        result, causing interrupted in-flight stages to pause for reconciliation.
        """
        return StageRunStatusResult(
            status="unknown",
            message="External run status lookup is not supported by this executor.",
        )

    def cancel_run(self, job_id: str, stage_id: str, external_run_id: str) -> bool:
        """Attempt best-effort cancellation of an external stage run."""
        return False
