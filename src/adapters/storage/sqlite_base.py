"""Shared SQLite connection and initialization base helper."""
import sqlite3
from pathlib import Path
from typing import Union


class SQLiteRepositoryBase:
    """Base helper providing SQLite connection management and schema setup."""

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
        raise NotImplementedError
