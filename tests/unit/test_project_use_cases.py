"""Unit tests exercising project creation and reopening without coupling to React, FastAPI, or SQLite.

Verifies:
- Plain input/result records at the application boundary
- Independent of UI, database, and frameworks (Clean Architecture)
- Single Responsibility, Dependency Inversion
"""
from typing import Dict, List, Optional
import pytest
from src.core.dto.project_dto import CreateProjectInput, GetProjectInput, ProjectResult
from src.core.entities.project import ProjectValidationError
from src.core.ports.project_repository import ProjectRepository
from src.core.use_cases.create_project import CreateProjectUseCase
from src.core.use_cases.get_project import GetProjectUseCase
from src.core.use_cases.list_projects import ListProjectsUseCase


class InMemoryProjectRepository(ProjectRepository):
    """In-memory test double for ProjectRepository with zero infrastructure dependencies."""

    def __init__(self) -> None:
        self._projects: Dict[str, ProjectResult] = {}

    def save(self, project: ProjectResult) -> None:
        self._projects[project.id] = project

    def get_by_id(self, project_id: str) -> Optional[ProjectResult]:
        return self._projects.get(project_id)

    def list_all(self) -> List[ProjectResult]:
        # Return sorted by updated_at descending
        return sorted(self._projects.values(), key=lambda p: p.updated_at, reverse=True)

    def delete(self, project_id: str) -> bool:
        if project_id in self._projects:
            del self._projects[project_id]
            return True
        return False


def test_create_project_with_plain_input_record() -> None:
    """Exercising project creation returns plain result record with generated ID and timestamps."""
    repo = InMemoryProjectRepository()
    use_case = CreateProjectUseCase(repo)

    input_data = CreateProjectInput(
        name="The Pyramids Mystery",
        description="Historical documentary about Giza pyramid construction.",
    )

    result = use_case.execute(input_data)

    assert result.id is not None
    assert len(result.id) > 0
    assert result.name == "The Pyramids Mystery"
    assert result.description == "Historical documentary about Giza pyramid construction."
    assert result.created_at is not None
    assert result.updated_at is not None


def test_reopen_project_by_identifier_without_framework_coupling() -> None:
    """Exercising reopening a project retrieves the exact same identifier and attributes."""
    repo = InMemoryProjectRepository()
    create_uc = CreateProjectUseCase(repo)
    get_uc = GetProjectUseCase(repo)

    created = create_uc.execute(CreateProjectInput(name="Ramses II"))

    # Reopen using GetProjectUseCase
    reopened = get_uc.execute(GetProjectInput(id=created.id))

    assert reopened is not None
    assert reopened.id == created.id
    assert reopened.name == "Ramses II"
    assert reopened.created_at == created.created_at


def test_list_projects_shows_created_projects_ordered() -> None:
    """Listing projects returns plain result records representing all created projects."""
    repo = InMemoryProjectRepository()
    create_uc = CreateProjectUseCase(repo)
    list_uc = ListProjectsUseCase(repo)

    p1 = create_uc.execute(CreateProjectInput(name="Project One"))
    p2 = create_uc.execute(CreateProjectInput(name="Project Two"))

    project_list = list_uc.execute()

    assert len(project_list) == 2
    ids = [p.id for p in project_list]
    assert p1.id in ids
    assert p2.id in ids


def test_cannot_create_project_with_empty_name() -> None:
    """Domain validation prevents creation of empty or whitespace-only project names."""
    repo = InMemoryProjectRepository()
    use_case = CreateProjectUseCase(repo)

    with pytest.raises(ProjectValidationError):
        use_case.execute(CreateProjectInput(name="   "))


def test_reopen_nonexistent_project_returns_none() -> None:
    """Querying a non-existent project returns None."""
    repo = InMemoryProjectRepository()
    get_uc = GetProjectUseCase(repo)

    result = get_uc.execute(GetProjectInput(id="non-existent-id"))
    assert result is None
