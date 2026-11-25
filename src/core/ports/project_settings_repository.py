"""Port interface for project-isolated settings persistence."""
from abc import ABC, abstractmethod
from typing import Optional
from src.core.dto.project_settings_dto import ProjectSettingsResult


class ProjectSettingsRepository(ABC):
    """Abstract port for persisting and retrieving per-project settings."""

    @abstractmethod
    def save(self, settings: ProjectSettingsResult) -> None:
        """Persist a project's isolated settings record."""
        pass

    @abstractmethod
    def get_by_project_id(self, project_id: str) -> Optional[ProjectSettingsResult]:
        """Retrieve settings for a given project identifier."""
        pass
