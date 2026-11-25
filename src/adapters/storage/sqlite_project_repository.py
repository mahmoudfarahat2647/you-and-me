"""SQLite implementation of the ProjectRepository port."""
import sqlite3
from typing import List, Optional

from src.adapters.storage.sqlite_base import SQLiteRepositoryBase
from src.core.dto.project_dto import ProjectResult
from src.core.ports.project_repository import ProjectRepository


class SQLiteProjectRepository(SQLiteRepositoryBase, ProjectRepository):
    """Persists and retrieves projects from a SQLite database."""

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    channel_profile_id TEXT,
                    preset_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(projects)").fetchall()
            }
            if "preset_id" not in columns:
                conn.execute("ALTER TABLE projects ADD COLUMN preset_id TEXT")
            conn.commit()

    def save(self, project: ProjectResult) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO projects (
                    id, name, description, channel_profile_id, preset_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    channel_profile_id = excluded.channel_profile_id,
                    preset_id = excluded.preset_id,
                    updated_at = excluded.updated_at
                """,
                (
                    project.id,
                    project.name,
                    project.description,
                    project.channel_profile_id,
                    project.preset_id,
                    project.created_at,
                    project.updated_at,
                ),
            )
            conn.commit()

    def get_by_id(self, project_id: str) -> Optional[ProjectResult]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, name, description, channel_profile_id, preset_id, created_at, updated_at
                FROM projects WHERE id = ?
                """,
                (project_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_project(row)

    def list_all(self) -> List[ProjectResult]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, name, description, channel_profile_id, preset_id, created_at, updated_at
                FROM projects ORDER BY updated_at DESC
                """
            )
            return [self._row_to_project(row) for row in cursor.fetchall()]

    def delete(self, project_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def _row_to_project(row: sqlite3.Row) -> ProjectResult:
        return ProjectResult(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            channel_profile_id=row["channel_profile_id"],
            preset_id=row["preset_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
