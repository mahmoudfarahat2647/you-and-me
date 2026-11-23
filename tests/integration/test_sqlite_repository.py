"""Integration tests for SQLiteProjectRepository verifying persistence across restarts."""
from datetime import datetime, timezone
import pytest
from src.adapters.storage.sqlite_project_repository import SQLiteProjectRepository
from src.core.entities.project import Project


def test_sqlite_persistence_and_reopen_across_instances(tmp_path) -> None:
    db_file = tmp_path / "test_studio.db"

    # Instance 1: Create and save project
    repo1 = SQLiteProjectRepository(db_path=db_file)
    now = datetime.now(timezone.utc)
    project = Project(
        id="proj-12345",
        name="The Pyramids Mystery",
        description="Historical documentary",
        created_at=now,
        updated_at=now,
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
    project = Project(
        id="proj-to-delete",
        name="Temp Project",
        description="",
        created_at=now,
        updated_at=now,
    )
    repo.save(project)
    assert repo.get_by_id("proj-to-delete") is not None

    deleted = repo.delete("proj-to-delete")
    assert deleted is True
    assert repo.get_by_id("proj-to-delete") is None
