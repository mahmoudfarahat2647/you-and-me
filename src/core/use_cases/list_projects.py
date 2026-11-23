"""Use case for listing all projects."""
from typing import List
from src.core.dto.project_dto import ProjectResult
from src.core.ports.project_repository import ProjectRepository


class ListProjectsUseCase:
    """Lists all saved projects as plain result records."""

    def __init__(self, repository: ProjectRepository) -> None:
        self._repository = repository

    def execute(self) -> List[ProjectResult]:
        return self._repository.list_all()
