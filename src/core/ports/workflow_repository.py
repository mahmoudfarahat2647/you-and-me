"""Port interface for workflow job persistence."""
from abc import ABC, abstractmethod
from typing import List, Optional
from src.core.dto.workflow_dto import WorkflowJobResult


class WorkflowRepository(ABC):
    """Abstract port for persisting and querying workflow jobs."""

    @abstractmethod
    def save(self, job: WorkflowJobResult) -> None:
        """Persist a plain workflow job record."""
        pass

    @abstractmethod
    def get_by_id(self, job_id: str) -> Optional[WorkflowJobResult]:
        """Retrieve a workflow job by its identifier."""
        pass

    @abstractmethod
    def list_by_project(self, project_id: str) -> List[WorkflowJobResult]:
        """List all persisted workflow jobs belonging to a project."""
        pass

    @abstractmethod
    def delete(self, job_id: str) -> bool:
        """Delete a workflow job by its identifier."""
        pass
