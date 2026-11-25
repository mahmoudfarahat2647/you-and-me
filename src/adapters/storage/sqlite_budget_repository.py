"""SQLite implementation of BudgetRepository with atomic BEGIN IMMEDIATE locking."""
from pathlib import Path
import sqlite3
import threading
from typing import Callable, Dict, List, Optional, TypeVar, Union

from src.core.dto.provider_dto import (
    ExternalRequestRecord,
    ProjectBudgetSummary,
    SpendReservationRecord,
)
from src.core.entities.budget import (
    ExternalJobStatus,
    ReservationStatus,
    round_usd,
)
from src.core.entities.provider import ProviderCapability
from src.core.ports.budget_repository import BudgetRepository, BudgetTransaction

T = TypeVar("T")

_REGISTRY_LOCK = threading.Lock()
_DB_LOCKS: Dict[str, threading.RLock] = {}


def _lock_for_db(db_path: str) -> threading.RLock:
    resolved = str(Path(db_path).resolve()) if db_path != ":memory:" else db_path
    with _REGISTRY_LOCK:
        lock = _DB_LOCKS.get(resolved)
        if lock is None:
            lock = threading.RLock()
            _DB_LOCKS[resolved] = lock
        return lock


def _row_to_request(row: sqlite3.Row) -> ExternalRequestRecord:
    return ExternalRequestRecord(
        id=row["id"],
        project_id=row["project_id"],
        stage_run_id=row["stage_run_id"],
        request_key=row["request_key"],
        provider_id=row["provider_id"],
        operation=ProviderCapability(row["operation"]),
        model=row["model"],
        external_job_id=row["external_job_id"],
        status=ExternalJobStatus(row["status"]),
        attempt_number=int(row["attempt_number"]),
        estimated_cost_usd=row["estimated_cost_usd"],
        reported_cost_usd=row["reported_cost_usd"],
        explicitly_approved=bool(row["explicitly_approved"]),
        error_message=row["error_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_reservation(row: sqlite3.Row) -> SpendReservationRecord:
    return SpendReservationRecord(
        id=row["id"],
        project_id=row["project_id"],
        stage_run_id=row["stage_run_id"],
        request_key=row["request_key"],
        provider_id=row["provider_id"],
        reserved_usd=float(row["reserved_usd"]),
        settled_usd=row["settled_usd"],
        status=ReservationStatus(row["status"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _read_budget_snapshot(conn: sqlite3.Connection, project_id: str) -> Optional[ProjectBudgetSummary]:
    budget_row = conn.execute(
        """
        SELECT project_id, budget_limit_usd, spent_usd, updated_at
        FROM project_budgets
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchone()
    if budget_row is None:
        return None

    res_row = conn.execute(
        """
        SELECT COALESCE(SUM(reserved_usd), 0.0) AS outstanding
        FROM spend_reservations
        WHERE project_id = ? AND status IN (?, ?)
        """,
        (project_id, ReservationStatus.ACTIVE.value, ReservationStatus.UNCERTAIN.value),
    ).fetchone()
    outstanding = round_usd(res_row["outstanding"] if res_row else 0.0)
    limit = round_usd(budget_row["budget_limit_usd"])
    spent = round_usd(budget_row["spent_usd"])
    remaining = max(0.0, round_usd(limit - spent))
    available = max(0.0, round_usd(limit - spent - outstanding))
    return ProjectBudgetSummary(
        project_id=budget_row["project_id"],
        budget_limit_usd=limit,
        spent_usd=spent,
        outstanding_reservations_usd=outstanding,
        remaining_budget_usd=remaining,
        available_budget_usd=available,
        updated_at=budget_row["updated_at"],
    )


class _SQLiteBudgetTransaction(BudgetTransaction):
    """Transaction-scoped queries executed inside an exclusive BEGIN IMMEDIATE transaction."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_budget_snapshot(self, project_id: str) -> Optional[ProjectBudgetSummary]:
        return _read_budget_snapshot(self._conn, project_id)

    def upsert_budget(
        self,
        project_id: str,
        budget_limit_usd: float,
        updated_at: str,
    ) -> ProjectBudgetSummary:
        self._conn.execute(
            """
            INSERT INTO project_budgets (project_id, budget_limit_usd, spent_usd, updated_at)
            VALUES (?, ?, 0.0, ?)
            ON CONFLICT(project_id) DO UPDATE SET
                budget_limit_usd = excluded.budget_limit_usd,
                updated_at = excluded.updated_at
            """,
            (project_id, round_usd(budget_limit_usd), updated_at),
        )
        summary = _read_budget_snapshot(self._conn, project_id)
        assert summary is not None
        return summary

    def get_request_by_key(self, request_key: str) -> Optional[ExternalRequestRecord]:
        row = self._conn.execute(
            "SELECT * FROM external_requests WHERE request_key = ?",
            (request_key,),
        ).fetchone()
        return _row_to_request(row) if row is not None else None

    def get_reservation_by_key(self, request_key: str) -> Optional[SpendReservationRecord]:
        row = self._conn.execute(
            "SELECT * FROM spend_reservations WHERE request_key = ?",
            (request_key,),
        ).fetchone()
        return _row_to_reservation(row) if row is not None else None

    def list_requests_for_stage(self, stage_run_id: str) -> List[ExternalRequestRecord]:
        rows = self._conn.execute(
            "SELECT * FROM external_requests WHERE stage_run_id = ? ORDER BY created_at ASC",
            (stage_run_id,),
        ).fetchall()
        return [_row_to_request(row) for row in rows]

    def create_reservation_and_request(
        self,
        reservation: SpendReservationRecord,
        request: ExternalRequestRecord,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO spend_reservations (
                id, project_id, stage_run_id, request_key, provider_id,
                reserved_usd, settled_usd, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reservation.id,
                reservation.project_id,
                reservation.stage_run_id,
                reservation.request_key,
                reservation.provider_id,
                round_usd(reservation.reserved_usd),
                reservation.settled_usd,
                reservation.status.value,
                reservation.created_at,
                reservation.updated_at,
            ),
        )
        self._conn.execute(
            """
            INSERT INTO external_requests (
                id, project_id, stage_run_id, request_key, provider_id,
                operation, model, external_job_id, status, attempt_number,
                estimated_cost_usd, reported_cost_usd, explicitly_approved,
                error_message, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.id,
                request.project_id,
                request.stage_run_id,
                request.request_key,
                request.provider_id,
                request.operation.value,
                request.model,
                request.external_job_id,
                request.status.value,
                request.attempt_number,
                request.estimated_cost_usd,
                request.reported_cost_usd,
                1 if request.explicitly_approved else 0,
                request.error_message,
                request.created_at,
                request.updated_at,
            ),
        )

    def update_request_and_reservation(
        self,
        request: ExternalRequestRecord,
        reservation_status: ReservationStatus,
        settled_usd: Optional[float],
        delta_spent_usd: float,
        now_iso: str,
    ) -> ProjectBudgetSummary:
        self._conn.execute(
            """
            UPDATE external_requests
            SET external_job_id = ?,
                status = ?,
                reported_cost_usd = ?,
                error_message = ?,
                updated_at = ?
            WHERE request_key = ?
            """,
            (
                request.external_job_id,
                request.status.value,
                request.reported_cost_usd,
                request.error_message,
                now_iso,
                request.request_key,
            ),
        )
        self._conn.execute(
            """
            UPDATE spend_reservations
            SET status = ?,
                settled_usd = ?,
                updated_at = ?
            WHERE request_key = ?
            """,
            (
                reservation_status.value,
                round_usd(settled_usd) if settled_usd is not None else None,
                now_iso,
                request.request_key,
            ),
        )

        # Ensure budget row exists if spend occurred on an unconfigured project
        self._conn.execute(
            """
            INSERT INTO project_budgets (project_id, budget_limit_usd, spent_usd, updated_at)
            VALUES (?, 0.0, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
                spent_usd = ROUND(project_budgets.spent_usd + ?, 6),
                updated_at = excluded.updated_at
            """,
            (
                request.project_id,
                round_usd(delta_spent_usd),
                now_iso,
                round_usd(delta_spent_usd),
            ),
        )
        summary = _read_budget_snapshot(self._conn, request.project_id)
        assert summary is not None
        return summary


class SQLiteBudgetRepository(BudgetRepository):
    """Persists project budgets, spend reservations, and external request records in SQLite."""

    def __init__(self, db_path: Union[str, Path] = "studio.db") -> None:
        self.db_path = str(db_path)
        parent_dir = Path(self.db_path).parent
        if parent_dir and not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)
        self._lock = _lock_for_db(self.db_path)
        self._init_db()

    def _get_connection(self, *, isolation_level: Optional[str] = "") -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            isolation_level=isolation_level,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("PRAGMA journal_mode = WAL")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS project_budgets (
                        project_id TEXT PRIMARY KEY,
                        budget_limit_usd REAL NOT NULL,
                        spent_usd REAL NOT NULL DEFAULT 0.0,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS spend_reservations (
                        id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        stage_run_id TEXT NOT NULL,
                        request_key TEXT NOT NULL UNIQUE,
                        provider_id TEXT NOT NULL,
                        reserved_usd REAL NOT NULL,
                        settled_usd REAL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS external_requests (
                        id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        stage_run_id TEXT NOT NULL,
                        request_key TEXT NOT NULL UNIQUE,
                        provider_id TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        model TEXT,
                        external_job_id TEXT,
                        status TEXT NOT NULL,
                        attempt_number INTEGER NOT NULL,
                        estimated_cost_usd REAL,
                        reported_cost_usd REAL,
                        explicitly_approved INTEGER NOT NULL DEFAULT 0,
                        error_message TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_ext_req_stage_run ON external_requests (stage_run_id)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_ext_req_project ON external_requests (project_id)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_res_project_status ON spend_reservations (project_id, status)"
                )
                conn.commit()
            finally:
                conn.close()

    def run_atomic(self, fn: Callable[[BudgetTransaction], T]) -> T:
        with self._lock:
            conn = self._get_connection(isolation_level=None)
            try:
                conn.execute("BEGIN IMMEDIATE")
                tx = _SQLiteBudgetTransaction(conn)
                result = fn(tx)
                conn.execute("COMMIT")
                return result
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
            finally:
                conn.close()

    def get_budget_summary(self, project_id: str) -> Optional[ProjectBudgetSummary]:
        with self._lock:
            conn = self._get_connection()
            try:
                return _read_budget_snapshot(conn, project_id)
            finally:
                conn.close()

    def get_request_by_key(self, request_key: str) -> Optional[ExternalRequestRecord]:
        with self._lock:
            conn = self._get_connection()
            try:
                row = conn.execute(
                    "SELECT * FROM external_requests WHERE request_key = ?",
                    (request_key,),
                ).fetchone()
                return _row_to_request(row) if row is not None else None
            finally:
                conn.close()

    def list_requests_by_project(self, project_id: str) -> List[ExternalRequestRecord]:
        with self._lock:
            conn = self._get_connection()
            try:
                rows = conn.execute(
                    "SELECT * FROM external_requests WHERE project_id = ? ORDER BY created_at ASC",
                    (project_id,),
                ).fetchall()
                return [_row_to_request(row) for row in rows]
            finally:
                conn.close()

    def list_reservations_by_project(self, project_id: str) -> List[SpendReservationRecord]:
        with self._lock:
            conn = self._get_connection()
            try:
                rows = conn.execute(
                    "SELECT * FROM spend_reservations WHERE project_id = ? ORDER BY created_at ASC",
                    (project_id,),
                ).fetchall()
                return [_row_to_reservation(row) for row in rows]
            finally:
                conn.close()
