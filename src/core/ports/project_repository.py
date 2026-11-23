"""Port interface for project persistence."""
from abc import ABC, abstractmethod
from typing import Optional, List
from src.core.dto.project_dto import ProjectResult


class ProjectRepository(ABC):
    """Abstract port for persisting and querying projects."""

    @abstractmethod
    def save(self, project: ProjectResult) -> None:
        """Persist a plain project record."""
        pass

    @abstractmethod
    def get_by_id(self, project_id: str) -> Optional[ProjectResult]:
        """Retrieve a project by its identifier."""
        pass

    @abstractmethod
    def list_all(self) -> List[ProjectResult]:
        """List all saved projects ordered by last updated descending."""
        pass

    @abstractmethod
    def delete(self, project_id: str) -> bool:
        """Delete a project by its identifier."""
        pass
