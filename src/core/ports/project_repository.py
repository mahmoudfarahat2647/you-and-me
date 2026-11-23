"""Port interface for project persistence."""
from abc import ABC, abstractmethod
from typing import Optional, List
from src.core.entities.project import Project


class ProjectRepository(ABC):
    """Abstract port for persisting and querying projects."""

    @abstractmethod
    def save(self, project: Project) -> None:
        """Persist a project entity."""
        pass

    @abstractmethod
    def get_by_id(self, project_id: str) -> Optional[Project]:
        """Retrieve a project by its identifier."""
        pass

    @abstractmethod
    def list_all(self) -> List[Project]:
        """List all saved projects ordered by last updated descending."""
        pass

    @abstractmethod
    def delete(self, project_id: str) -> bool:
        """Delete a project by its identifier."""
        pass
