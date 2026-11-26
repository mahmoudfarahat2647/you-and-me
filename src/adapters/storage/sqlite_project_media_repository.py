"""SQLite implementation of the ProjectMediaRepository port."""
import json
import sqlite3
from pathlib import Path
from typing import List, Optional, Union

from src.core.dto.media_dto import ExportMp4Result, ProjectMediaItem
from src.core.entities.media import MEDIA_KIND_AUDIO, MEDIA_KIND_CLIP
from src.core.ports.project_media_repository import ProjectMediaRepository


class SQLiteProjectMediaRepository(ProjectMediaRepository):
    """Persists ordered project clips, narration audio, and verified export records in SQLite."""

    def __init__(self, db_path: Union[str, Path] = "studio.db") -> None:
        self.db_path = str(db_path)
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
                CREATE TABLE IF NOT EXISTS project_media_items (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    position INTEGER NOT NULL DEFAULT 0,
                    duration_seconds REAL NOT NULL,
                    width INTEGER,
                    height INTEGER,
                    fps REAL,
                    has_video INTEGER NOT NULL,
                    has_audio INTEGER NOT NULL,
                    video_codec TEXT,
                    audio_codec TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_project_media_project_kind_pos
                ON project_media_items (project_id, kind, position)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS project_exports (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    output_path TEXT NOT NULL,
                    duration_seconds REAL NOT NULL,
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    fps REAL NOT NULL,
                    has_video INTEGER NOT NULL,
                    has_audio INTEGER NOT NULL,
                    video_codec TEXT,
                    audio_codec TEXT,
                    file_size_bytes INTEGER NOT NULL,
                    clip_ids_json TEXT NOT NULL,
                    audio_id TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_project_exports_project
                ON project_exports (project_id)
                """
            )
            conn.commit()

    def add_clip(self, item: ProjectMediaItem) -> ProjectMediaItem:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO project_media_items (
                    id, project_id, kind, file_path, original_filename, position,
                    duration_seconds, width, height, fps, has_video, has_audio,
                    video_codec, audio_codec, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.project_id,
                    MEDIA_KIND_CLIP,
                    item.file_path,
                    item.original_filename,
                    item.position,
                    item.duration_seconds,
                    item.width,
                    item.height,
                    item.fps,
                    1 if item.has_video else 0,
                    1 if item.has_audio else 0,
                    item.video_codec,
                    item.audio_codec,
                    item.created_at,
                ),
            )
            conn.commit()
        return item

    def set_audio(self, item: ProjectMediaItem) -> ProjectMediaItem:
        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM project_media_items WHERE project_id = ? AND kind = ?",
                (item.project_id, MEDIA_KIND_AUDIO),
            )
            conn.execute(
                """
                INSERT INTO project_media_items (
                    id, project_id, kind, file_path, original_filename, position,
                    duration_seconds, width, height, fps, has_video, has_audio,
                    video_codec, audio_codec, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.project_id,
                    MEDIA_KIND_AUDIO,
                    item.file_path,
                    item.original_filename,
                    0,
                    item.duration_seconds,
                    item.width,
                    item.height,
                    item.fps,
                    1 if item.has_video else 0,
                    1 if item.has_audio else 0,
                    item.video_codec,
                    item.audio_codec,
                    item.created_at,
                ),
            )
            conn.commit()
        return item

    def list_clips(self, project_id: str) -> List[ProjectMediaItem]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM project_media_items
                WHERE project_id = ? AND kind = ?
                ORDER BY position ASC, created_at ASC
                """,
                (project_id, MEDIA_KIND_CLIP),
            )
            return [self._row_to_item(row) for row in cursor.fetchall()]

    def get_audio(self, project_id: str) -> Optional[ProjectMediaItem]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM project_media_items
                WHERE project_id = ? AND kind = ?
                ORDER BY rowid DESC LIMIT 1
                """,
                (project_id, MEDIA_KIND_AUDIO),
            )
            row = cursor.fetchone()
            return self._row_to_item(row) if row is not None else None

    def get_item(self, project_id: str, item_id: str) -> Optional[ProjectMediaItem]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM project_media_items WHERE project_id = ? AND id = ?",
                (project_id, item_id),
            )
            row = cursor.fetchone()
            return self._row_to_item(row) if row is not None else None

    def reorder_clips(self, project_id: str, clip_ids: List[str]) -> List[ProjectMediaItem]:
        with self._get_connection() as conn:
            for pos, clip_id in enumerate(clip_ids):
                conn.execute(
                    """
                    UPDATE project_media_items
                    SET position = ?
                    WHERE project_id = ? AND id = ? AND kind = ?
                    """,
                    (pos, project_id, clip_id, MEDIA_KIND_CLIP),
                )
            conn.commit()
        return self.list_clips(project_id)

    def delete_item(self, project_id: str, item_id: str) -> Optional[ProjectMediaItem]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM project_media_items WHERE project_id = ? AND id = ?",
                (project_id, item_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            removed = self._row_to_item(row)
            conn.execute(
                "DELETE FROM project_media_items WHERE project_id = ? AND id = ?",
                (project_id, item_id),
            )
            if removed.kind == MEDIA_KIND_CLIP:
                remaining = conn.execute(
                    """
                    SELECT id FROM project_media_items
                    WHERE project_id = ? AND kind = ?
                    ORDER BY position ASC, created_at ASC
                    """,
                    (project_id, MEDIA_KIND_CLIP),
                ).fetchall()
                for pos, rem in enumerate(remaining):
                    conn.execute(
                        "UPDATE project_media_items SET position = ? WHERE id = ?",
                        (pos, rem["id"]),
                    )
            conn.commit()
            return removed

    def save_export(self, export_result: ExportMp4Result) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO project_exports (
                    id, project_id, output_path, duration_seconds, width, height, fps,
                    has_video, has_audio, video_codec, audio_codec, file_size_bytes,
                    clip_ids_json, audio_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    export_result.id,
                    export_result.project_id,
                    export_result.output_path,
                    export_result.duration_seconds,
                    export_result.width,
                    export_result.height,
                    export_result.fps,
                    1 if export_result.has_video else 0,
                    1 if export_result.has_audio else 0,
                    export_result.video_codec,
                    export_result.audio_codec,
                    export_result.file_size_bytes,
                    json.dumps(export_result.clip_ids),
                    export_result.audio_id,
                    export_result.created_at,
                ),
            )
            conn.commit()

    def get_latest_export(self, project_id: str) -> Optional[ExportMp4Result]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM project_exports
                WHERE project_id = ?
                ORDER BY rowid DESC LIMIT 1
                """,
                (project_id,),
            )
            row = cursor.fetchone()
            return self._row_to_export(row) if row is not None else None

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> ProjectMediaItem:
        return ProjectMediaItem(
            id=row["id"],
            project_id=row["project_id"],
            kind=row["kind"],
            file_path=row["file_path"],
            original_filename=row["original_filename"],
            position=int(row["position"]),
            duration_seconds=float(row["duration_seconds"]),
            has_video=bool(row["has_video"]),
            has_audio=bool(row["has_audio"]),
            created_at=row["created_at"],
            width=int(row["width"]) if row["width"] is not None else None,
            height=int(row["height"]) if row["height"] is not None else None,
            fps=float(row["fps"]) if row["fps"] is not None else None,
            video_codec=row["video_codec"],
            audio_codec=row["audio_codec"],
        )

    @staticmethod
    def _row_to_export(row: sqlite3.Row) -> ExportMp4Result:
        return ExportMp4Result(
            id=row["id"],
            project_id=row["project_id"],
            output_path=row["output_path"],
            duration_seconds=float(row["duration_seconds"]),
            width=int(row["width"]),
            height=int(row["height"]),
            fps=float(row["fps"]),
            has_video=bool(row["has_video"]),
            has_audio=bool(row["has_audio"]),
            file_size_bytes=int(row["file_size_bytes"]),
            clip_ids=list(json.loads(row["clip_ids_json"])),
            created_at=row["created_at"],
            video_codec=row["video_codec"],
            audio_codec=row["audio_codec"],
            audio_id=row["audio_id"],
        )
