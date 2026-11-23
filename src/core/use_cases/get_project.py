"""Use case for retrieving an existing project by identifier."""
from typing import Optional
from src.core.dto.project_dto import GetProjectInput, ProjectResult
from src.core.ports.project_repository import ProjectRepository


class ProjectNotFoundError(Exception):
    """Raised when a requested project cannot be found."""
    pass


class GetProjectUseCase:
    """Retrieves a project entity and returns a plain result record."""

    def __init__(self, repository: ProjectRepository) -> None:
        self._repository = repository

    def execute(self, input_data: GetProjectInput) -> Optional[ProjectResult]:
        project = self._repository.get_by_id(input_data.id)
        if project is None:
            return None

        return ProjectResult(
            id=project.id,
            name=project.name,
            description=project.description,
            created_at=project.created_at.isoformat(),
            updated_at=project.updated_at.isoformat(),
            channel_profile_id=project.channel_profile_id,
        )
