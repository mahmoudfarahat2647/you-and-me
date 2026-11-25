"""SQLite implementation of the ProjectSettingsRepository port."""
import json
import sqlite3
from typing import Optional

from src.adapters.storage.sqlite_base import SQLiteRepositoryBase
from src.core.dto.project_settings_dto import ProjectSettingsResult
from src.core.ports.project_settings_repository import ProjectSettingsRepository


class SQLiteProjectSettingsRepository(SQLiteRepositoryBase, ProjectSettingsRepository):
    """Persists and retrieves per-project isolated settings in SQLite."""

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS project_settings (
                    project_id TEXT PRIMARY KEY,
                    channel_profile_id TEXT,
                    preset_id TEXT,
                    topic_focus TEXT NOT NULL DEFAULT '',
                    language TEXT NOT NULL DEFAULT 'Arabic',
                    narrator TEXT NOT NULL DEFAULT '',
                    visual_style TEXT NOT NULL DEFAULT '',
                    video_format TEXT NOT NULL DEFAULT '16:9',
                    budget_limit_usd REAL NOT NULL DEFAULT 10.0,
                    upload_destination TEXT NOT NULL DEFAULT 'Local MP4',
                    stage_modes_json TEXT NOT NULL,
                    stage_params_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save(self, settings: ProjectSettingsResult) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO project_settings (
                    project_id, channel_profile_id, preset_id, topic_focus,
                    language, narrator, visual_style, video_format,
                    budget_limit_usd, upload_destination,
                    stage_modes_json, stage_params_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    channel_profile_id = excluded.channel_profile_id,
                    preset_id = excluded.preset_id,
                    topic_focus = excluded.topic_focus,
                    language = excluded.language,
                    narrator = excluded.narrator,
                    visual_style = excluded.visual_style,
                    video_format = excluded.video_format,
                    budget_limit_usd = excluded.budget_limit_usd,
                    upload_destination = excluded.upload_destination,
                    stage_modes_json = excluded.stage_modes_json,
                    stage_params_json = excluded.stage_params_json,
                    updated_at = excluded.updated_at
                """,
                (
                    settings.project_id,
                    settings.channel_profile_id,
                    settings.preset_id,
                    settings.topic_focus,
                    settings.language,
                    settings.narrator,
                    settings.visual_style,
                    settings.video_format,
                    settings.budget_limit_usd,
                    settings.upload_destination,
                    json.dumps(settings.stage_modes),
                    json.dumps(settings.stage_params),
                    settings.updated_at,
                ),
            )
            conn.commit()

    def get_by_project_id(self, project_id: str) -> Optional[ProjectSettingsResult]:
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT project_id, channel_profile_id, preset_id, topic_focus,
                       language, narrator, visual_style, video_format,
                       budget_limit_usd, upload_destination,
                       stage_modes_json, stage_params_json, updated_at
                FROM project_settings WHERE project_id = ?
                """,
                (project_id,),
            ).fetchone()
            return self._row_to_settings(row) if row is not None else None

    @staticmethod
    def _row_to_settings(row: sqlite3.Row) -> ProjectSettingsResult:
        return ProjectSettingsResult(
            project_id=row["project_id"],
            channel_profile_id=row["channel_profile_id"],
            preset_id=row["preset_id"],
            topic_focus=row["topic_focus"],
            language=row["language"],
            narrator=row["narrator"],
            visual_style=row["visual_style"],
            video_format=row["video_format"],
            budget_limit_usd=float(row["budget_limit_usd"]),
            upload_destination=row["upload_destination"],
            stage_modes=json.loads(row["stage_modes_json"]),
            stage_params=json.loads(row["stage_params_json"]),
            updated_at=row["updated_at"],
        )
