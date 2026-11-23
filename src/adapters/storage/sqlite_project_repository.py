"""SQLite implementation of the ProjectRepository port."""
import sqlite3
from pathlib import Path
from typing import List, Optional, Union
from src.core.dto.project_dto import ProjectResult
from src.core.ports.project_repository import ProjectRepository


class SQLiteProjectRepository(ProjectRepository):
    """Persists and retrieves projects from a SQLite database."""

    def __init__(self, db_path: Union[str, Path] = "studio.db") -> None:
        self.db_path = str(db_path)
        # Ensure parent directory exists if path contains directories
        parent_dir = Path(self.db_path).parent
        if parent_dir and not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    channel_profile_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save(self, project: ProjectResult) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO projects (id, name, description, channel_profile_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    channel_profile_id = excluded.channel_profile_id,
                    updated_at = excluded.updated_at
                """,
                (
                    project.id,
                    project.name,
                    project.description,
                    project.channel_profile_id,
                    project.created_at,
                    project.updated_at,
                ),
            )
            conn.commit()

    def get_by_id(self, project_id: str) -> Optional[ProjectResult]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, name, description, channel_profile_id, created_at, updated_at FROM projects WHERE id = ?",
                (project_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_project(row)

    def list_all(self) -> List[ProjectResult]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, name, description, channel_profile_id, created_at, updated_at FROM projects ORDER BY updated_at DESC"
            )
            rows = cursor.fetchall()
            return [self._row_to_project(row) for row in rows]

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
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
