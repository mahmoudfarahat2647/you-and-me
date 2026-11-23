"""Use case for listing all projects."""
from typing import List
from src.core.dto.project_dto import ProjectResult
from src.core.ports.project_repository import ProjectRepository


class ListProjectsUseCase:
    """Lists all saved projects as plain result records."""

    def __init__(self, repository: ProjectRepository) -> None:
        self._repository = repository

    def execute(self) -> List[ProjectResult]:
        projects = self._repository.list_all()
        return [
            ProjectResult(
                id=p.id,
                name=p.name,
                description=p.description,
                created_at=p.created_at.isoformat(),
                updated_at=p.updated_at.isoformat(),
                channel_profile_id=p.channel_profile_id,
            )
            for p in projects
        ]
