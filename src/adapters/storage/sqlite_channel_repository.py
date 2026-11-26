"""SQLite implementation of the ChannelRepository port."""
import sqlite3
from typing import List, Optional

from src.adapters.storage.sqlite_base import SQLiteRepositoryBase
from src.core.dto.channel_dto import ChannelProfileResult
from src.core.ports.channel_repository import ChannelRepository


class SQLiteChannelRepository(SQLiteRepositoryBase, ChannelRepository):
    """Persists and retrieves channel profiles from a SQLite database."""

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS channels (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    topic_focus TEXT NOT NULL DEFAULT '',
                    language TEXT NOT NULL DEFAULT 'Arabic',
                    default_narrator TEXT NOT NULL DEFAULT '',
                    visual_style TEXT NOT NULL DEFAULT '',
                    video_format TEXT NOT NULL DEFAULT '16:9',
                    budget_limit_usd REAL NOT NULL DEFAULT 10.0,
                    upload_destination TEXT NOT NULL DEFAULT 'YouTube',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save(self, channel: ChannelProfileResult) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO channels (
                    id, name, topic_focus, language, default_narrator,
                    visual_style, video_format, budget_limit_usd,
                    upload_destination, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    topic_focus = excluded.topic_focus,
                    language = excluded.language,
                    default_narrator = excluded.default_narrator,
                    visual_style = excluded.visual_style,
                    video_format = excluded.video_format,
                    budget_limit_usd = excluded.budget_limit_usd,
                    upload_destination = excluded.upload_destination,
                    updated_at = excluded.updated_at
                """,
                (
                    channel.id,
                    channel.name,
                    channel.topic_focus,
                    channel.language,
                    channel.default_narrator,
                    channel.visual_style,
                    channel.video_format,
                    channel.budget_limit_usd,
                    channel.upload_destination,
                    channel.created_at,
                    channel.updated_at,
                ),
            )
            conn.commit()

    def get_by_id(self, channel_id: str) -> Optional[ChannelProfileResult]:
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT id, name, topic_focus, language, default_narrator,
                       visual_style, video_format, budget_limit_usd,
                       upload_destination, created_at, updated_at
                FROM channels WHERE id = ?
                """,
                (channel_id,),
            ).fetchone()
            return self._row_to_channel(row) if row is not None else None

    def list_all(self) -> List[ChannelProfileResult]:
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, name, topic_focus, language, default_narrator,
                       visual_style, video_format, budget_limit_usd,
                       upload_destination, created_at, updated_at
                FROM channels ORDER BY updated_at DESC
                """
            ).fetchall()
            return [self._row_to_channel(row) for row in rows]

    def delete(self, channel_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def _row_to_channel(row: sqlite3.Row) -> ChannelProfileResult:
        return ChannelProfileResult(
            id=row["id"],
            name=row["name"],
            topic_focus=row["topic_focus"],
            language=row["language"],
            default_narrator=row["default_narrator"],
            visual_style=row["visual_style"],
            video_format=row["video_format"],
            budget_limit_usd=float(row["budget_limit_usd"]),
            upload_destination=row["upload_destination"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
