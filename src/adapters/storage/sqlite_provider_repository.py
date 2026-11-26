"""SQLite implementation of ProviderRepository (stores non-secret metadata only)."""
import json
from pathlib import Path
import sqlite3
from typing import List, Optional, Union

from src.core.dto.provider_dto import ProviderSummaryResult
from src.core.entities.provider import (
    CredentialStatus,
    ProviderCapability,
    ProviderConnectionStatus,
    ProviderType,
)
from src.core.ports.provider_repository import ProviderRepository


class SQLiteProviderRepository(ProviderRepository):
    """Persists provider configurations and verified capabilities in SQLite without secrets."""

    def __init__(self, db_path: Union[str, Path] = "studio.db") -> None:
        self.db_path = str(db_path)
        parent_dir = Path(self.db_path).parent
        if parent_dir and not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS providers (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    provider_type TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    credential_ref TEXT,
                    credential_preview TEXT,
                    credential_status TEXT NOT NULL,
                    connection_status TEXT NOT NULL,
                    supported_capabilities_json TEXT NOT NULL DEFAULT '[]',
                    verified_models_json TEXT NOT NULL DEFAULT '[]',
                    selected_model TEXT,
                    last_error TEXT,
                    last_tested_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save(self, provider: ProviderSummaryResult) -> None:
        capabilities_json = json.dumps([cap.value for cap in provider.supported_capabilities])
        models_json = json.dumps(list(provider.verified_models))
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO providers (
                    id, name, provider_type, base_url,
                    credential_ref, credential_preview, credential_status,
                    connection_status, supported_capabilities_json, verified_models_json,
                    selected_model, last_error, last_tested_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    provider_type = excluded.provider_type,
                    base_url = excluded.base_url,
                    credential_ref = excluded.credential_ref,
                    credential_preview = excluded.credential_preview,
                    credential_status = excluded.credential_status,
                    connection_status = excluded.connection_status,
                    supported_capabilities_json = excluded.supported_capabilities_json,
                    verified_models_json = excluded.verified_models_json,
                    selected_model = excluded.selected_model,
                    last_error = excluded.last_error,
                    last_tested_at = excluded.last_tested_at,
                    updated_at = excluded.updated_at
                """,
                (
                    provider.id,
                    provider.name,
                    provider.provider_type.value,
                    provider.base_url,
                    provider.credential_ref,
                    provider.credential_preview,
                    provider.credential_status.value,
                    provider.connection_status.value,
                    capabilities_json,
                    models_json,
                    provider.selected_model,
                    provider.last_error,
                    provider.last_tested_at,
                    provider.created_at,
                    provider.updated_at,
                ),
            )
            conn.commit()

    def get_by_id(self, provider_id: str) -> Optional[ProviderSummaryResult]:
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    id, name, provider_type, base_url,
                    credential_ref, credential_preview, credential_status,
                    connection_status, supported_capabilities_json, verified_models_json,
                    selected_model, last_error, last_tested_at, created_at, updated_at
                FROM providers
                WHERE id = ?
                """,
                (provider_id,),
            ).fetchone()
            if row is None:
                return None
            return self._row_to_summary(row)

    def list_all(self) -> List[ProviderSummaryResult]:
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    id, name, provider_type, base_url,
                    credential_ref, credential_preview, credential_status,
                    connection_status, supported_capabilities_json, verified_models_json,
                    selected_model, last_error, last_tested_at, created_at, updated_at
                FROM providers
                ORDER BY updated_at DESC
                """
            ).fetchall()
            return [self._row_to_summary(row) for row in rows]

    def delete(self, provider_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM providers WHERE id = ?", (provider_id,))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def _row_to_summary(row: sqlite3.Row) -> ProviderSummaryResult:
        caps = tuple(
            ProviderCapability(item)
            for item in json.loads(row["supported_capabilities_json"] or "[]")
        )
        models = tuple(str(m) for m in json.loads(row["verified_models_json"] or "[]"))
        return ProviderSummaryResult(
            id=row["id"],
            name=row["name"],
            provider_type=ProviderType(row["provider_type"]),
            base_url=row["base_url"],
            credential_ref=row["credential_ref"],
            credential_preview=row["credential_preview"],
            credential_status=CredentialStatus(row["credential_status"]),
            connection_status=ProviderConnectionStatus(row["connection_status"]),
            supported_capabilities=caps,
            verified_models=models,
            selected_model=row["selected_model"],
            last_error=row["last_error"],
            last_tested_at=row["last_tested_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
