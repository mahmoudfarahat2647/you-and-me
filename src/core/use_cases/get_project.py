"""Use case for retrieving an existing project by identifier."""
from typing import Optional
from src.core.dto.project_dto import GetProjectInput, ProjectResult
from src.core.ports.project_repository import ProjectRepository


class ProjectNotFoundError(Exception):
    """Raised when a requested project cannot be found."""
    pass


class GetProjectUseCase:
    """Retrieves a plain project result record."""

    def __init__(self, repository: ProjectRepository) -> None:
        self._repository = repository

    def execute(self, input_data: GetProjectInput) -> Optional[ProjectResult]:
        return self._repository.get_by_id(input_data.id)
