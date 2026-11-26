"""SQLite implementation of the ProjectAssetRepository port."""
import json
import sqlite3
from typing import List, Optional

from src.adapters.storage.sqlite_base import SQLiteRepositoryBase
from src.core.dto.asset_dto import ProjectAssetResult
from src.core.ports.asset_repository import ProjectAssetRepository


class SQLiteProjectAssetRepository(SQLiteRepositoryBase, ProjectAssetRepository):
    """Persists and retrieves project-isolated assets in SQLite."""

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS project_assets (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    file_path TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_project_assets_project_id ON project_assets(project_id)"
            )
            conn.commit()

    def save(self, asset: ProjectAssetResult) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO project_assets (
                    id, project_id, asset_type, name, content,
                    file_path, metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    content = excluded.content,
                    file_path = excluded.file_path,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    asset.id,
                    asset.project_id,
                    asset.asset_type,
                    asset.name,
                    asset.content,
                    asset.file_path,
                    json.dumps(asset.metadata),
                    asset.created_at,
                    asset.updated_at,
                ),
            )
            conn.commit()

    def get_by_id(self, asset_id: str) -> Optional[ProjectAssetResult]:
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT id, project_id, asset_type, name, content,
                       file_path, metadata_json, created_at, updated_at
                FROM project_assets WHERE id = ?
                """,
                (asset_id,),
            ).fetchone()
            return self._row_to_asset(row) if row is not None else None

    def list_by_project(
        self,
        project_id: str,
        asset_type: Optional[str] = None,
    ) -> List[ProjectAssetResult]:
        with self._get_connection() as conn:
            if asset_type is not None:
                rows = conn.execute(
                    """
                    SELECT id, project_id, asset_type, name, content,
                           file_path, metadata_json, created_at, updated_at
                    FROM project_assets
                    WHERE project_id = ? AND asset_type = ?
                    ORDER BY created_at ASC
                    """,
                    (project_id, asset_type),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, project_id, asset_type, name, content,
                           file_path, metadata_json, created_at, updated_at
                    FROM project_assets
                    WHERE project_id = ?
                    ORDER BY created_at ASC
                    """,
                    (project_id,),
                ).fetchall()
            return [self._row_to_asset(row) for row in rows]

    def delete(self, project_id: str, asset_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM project_assets WHERE id = ? AND project_id = ?",
                (asset_id, project_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def _row_to_asset(row: sqlite3.Row) -> ProjectAssetResult:
        return ProjectAssetResult(
            id=row["id"],
            project_id=row["project_id"],
            asset_type=row["asset_type"],
            name=row["name"],
            content=row["content"],
            file_path=row["file_path"],
            metadata=json.loads(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
