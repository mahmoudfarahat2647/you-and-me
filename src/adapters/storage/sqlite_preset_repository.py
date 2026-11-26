"""SQLite implementation of the PresetRepository port."""
import json
import sqlite3
from typing import List, Optional

from src.adapters.storage.sqlite_base import SQLiteRepositoryBase
from src.core.dto.preset_dto import WorkflowPresetResult
from src.core.entities.preset import get_builtin_presets
from src.core.ports.preset_repository import PresetRepository


class SQLitePresetRepository(SQLiteRepositoryBase, PresetRepository):
    """Persists and retrieves workflow presets from a SQLite database."""

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS presets (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    default_stage_modes_json TEXT NOT NULL,
                    default_stage_params_json TEXT NOT NULL DEFAULT '{}',
                    is_builtin INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            count = conn.execute("SELECT COUNT(*) FROM presets").fetchone()[0]
            if count == 0:
                for preset in get_builtin_presets():
                    conn.execute(
                        """
                        INSERT INTO presets (
                            id, name, description, default_stage_modes_json,
                            default_stage_params_json, is_builtin
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            preset.id,
                            preset.name,
                            preset.description,
                            json.dumps(preset.default_stage_modes),
                            json.dumps(preset.default_stage_params),
                            1 if preset.is_builtin else 0,
                        ),
                    )
            conn.commit()

    def save(self, preset: WorkflowPresetResult) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO presets (
                    id, name, description, default_stage_modes_json,
                    default_stage_params_json, is_builtin
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    default_stage_modes_json = excluded.default_stage_modes_json,
                    default_stage_params_json = excluded.default_stage_params_json,
                    is_builtin = excluded.is_builtin
                """,
                (
                    preset.id,
                    preset.name,
                    preset.description,
                    json.dumps(preset.default_stage_modes),
                    json.dumps(preset.default_stage_params),
                    1 if preset.is_builtin else 0,
                ),
            )
            conn.commit()

    def get_by_id(self, preset_id: str) -> Optional[WorkflowPresetResult]:
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT id, name, description, default_stage_modes_json,
                       default_stage_params_json, is_builtin
                FROM presets WHERE id = ?
                """,
                (preset_id,),
            ).fetchone()
            return self._row_to_preset(row) if row is not None else None

    def list_all(self) -> List[WorkflowPresetResult]:
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, name, description, default_stage_modes_json,
                       default_stage_params_json, is_builtin
                FROM presets ORDER BY is_builtin DESC, name ASC
                """
            ).fetchall()
            return [self._row_to_preset(row) for row in rows]

    @staticmethod
    def _row_to_preset(row: sqlite3.Row) -> WorkflowPresetResult:
        return WorkflowPresetResult(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            default_stage_modes=json.loads(row["default_stage_modes_json"]),
            default_stage_params=json.loads(row["default_stage_params_json"]),
            is_builtin=bool(row["is_builtin"]),
        )
