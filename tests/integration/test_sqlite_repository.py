"""Integration tests for SQLiteProjectRepository verifying persistence across restarts."""
from datetime import datetime, timezone
import pytest
from src.adapters.storage.sqlite_project_repository import SQLiteProjectRepository
from src.core.dto.project_dto import CreateProjectInput, GetProjectInput, ProjectResult
from src.core.use_cases.create_project import CreateProjectUseCase
from src.core.use_cases.get_project import GetProjectUseCase
from src.core.use_cases.list_projects import ListProjectsUseCase


def test_use_cases_exchange_plain_records_with_sqlite(tmp_path) -> None:
    class BoundaryCheckingSQLiteRepository(SQLiteProjectRepository):
        def save(self, project: ProjectResult) -> None:
            assert isinstance(project, ProjectResult)
            super().save(project)

    repo = BoundaryCheckingSQLiteRepository(tmp_path / "boundary.db")
    created = CreateProjectUseCase(repo).execute(
        CreateProjectInput(
            name="  Boundary project  ",
            description="  Description  ",
            channel_profile_id="channel-1",
        )
    )

    stored = repo.get_by_id(created.id)
    assert isinstance(stored, ProjectResult)
    assert stored.name == "Boundary project"
    assert stored.description == "Description"
    assert stored.channel_profile_id == "channel-1"
    assert stored == created
    assert repo.list_all() == [created]
    assert GetProjectUseCase(repo).execute(GetProjectInput(id=created.id)) == created
    assert ListProjectsUseCase(repo).execute() == [created]


def test_sqlite_persistence_and_reopen_across_instances(tmp_path) -> None:
    db_file = tmp_path / "test_studio.db"

    # Instance 1: Create and save project
    repo1 = SQLiteProjectRepository(db_path=db_file)
    now = datetime.now(timezone.utc)
    project = ProjectResult(
        id="proj-12345",
        name="The Pyramids Mystery",
        description="Historical documentary",
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    )
    repo1.save(project)

    # Simulate closing the application and reopening with a fresh repository instance
    repo2 = SQLiteProjectRepository(db_path=db_file)
    retrieved = repo2.get_by_id("proj-12345")

    assert retrieved is not None
    assert retrieved.id == "proj-12345"
    assert retrieved.name == "The Pyramids Mystery"
    assert retrieved.description == "Historical documentary"

    # List projects in reopened instance
    all_projects = repo2.list_all()
    assert len(all_projects) == 1
    assert all_projects[0].id == "proj-12345"


def test_sqlite_delete_project(tmp_path) -> None:
    db_file = tmp_path / "test_delete.db"
    repo = SQLiteProjectRepository(db_path=db_file)
    now = datetime.now(timezone.utc)
    project = ProjectResult(
        id="proj-to-delete",
        name="Temp Project",
        description="",
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    )
    repo.save(project)
    assert repo.get_by_id("proj-to-delete") is not None

    deleted = repo.delete("proj-to-delete")
    assert deleted is True
    assert repo.get_by_id("proj-to-delete") is None
