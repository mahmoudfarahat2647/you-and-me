"""Port interface for project-isolated asset persistence."""
from abc import ABC, abstractmethod
from typing import List, Optional
from src.core.dto.asset_dto import ProjectAssetResult


class ProjectAssetRepository(ABC):
    """Abstract port for persisting and querying project-scoped assets."""

    @abstractmethod
    def save(self, asset: ProjectAssetResult) -> None:
        """Persist a plain project asset record."""
        pass

    @abstractmethod
    def get_by_id(self, asset_id: str) -> Optional[ProjectAssetResult]:
        """Retrieve an asset by its identifier."""
        pass

    @abstractmethod
    def list_by_project(
        self,
        project_id: str,
        asset_type: Optional[str] = None,
    ) -> List[ProjectAssetResult]:
        """List assets belonging strictly to the specified project."""
        pass

    @abstractmethod
    def delete(self, project_id: str, asset_id: str) -> bool:
        """Delete an asset only if it belongs to the specified project."""
        pass
