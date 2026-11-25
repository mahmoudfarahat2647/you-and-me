"""Use case for listing projects, optionally filtered by channel profile."""
from typing import List, Optional
from src.core.dto.project_dto import ProjectResult
from src.core.ports.project_repository import ProjectRepository


class ListProjectsUseCase:
    """Lists saved projects as plain result records."""

    def __init__(self, repository: ProjectRepository) -> None:
        self._repository = repository

    def execute(self, channel_profile_id: Optional[str] = None) -> List[ProjectResult]:
        projects = self._repository.list_all()
        if channel_profile_id is not None:
            return [p for p in projects if p.channel_profile_id == channel_profile_id]
        return projects
