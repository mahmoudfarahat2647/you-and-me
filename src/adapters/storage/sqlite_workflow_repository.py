"""SQLite implementation of the WorkflowRepository port with persisted execution logs."""
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from src.adapters.storage.sqlite_base import SQLiteRepositoryBase
from src.core.dto.workflow_dto import (
    StageArtifactDto,
    StageItemStateDto,
    WorkflowJobResult,
    WorkflowStageResult,
)
from src.core.ports.workflow_repository import WorkflowRepository


@dataclass(frozen=True)
class WorkflowLogEntry:
    """Plain record representing a persisted workflow log row."""

    id: str
    job_id: str
    project_id: str
    stage_id: str
    level: str
    message: str
    created_at: str


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize_artifact(artifact: Optional[StageArtifactDto]) -> Optional[str]:
    if artifact is None:
        return None
    return json.dumps(
        {
            "artifact_id": artifact.artifact_id,
            "stage_id": artifact.stage_id,
            "artifact_type": artifact.artifact_type,
            "uri": artifact.uri,
            "data": artifact.data,
            "schema_version": artifact.schema_version,
            "compatible": artifact.compatible,
            "stale": artifact.stale,
            "created_at": artifact.created_at,
            "content_hash": artifact.content_hash,
        }
    )


def _deserialize_artifact(raw: Optional[str]) -> Optional[StageArtifactDto]:
    if not raw:
        return None
    payload = json.loads(raw)
    return StageArtifactDto(
        artifact_id=payload["artifact_id"],
        stage_id=payload["stage_id"],
        artifact_type=payload["artifact_type"],
        uri=payload.get("uri"),
        data=payload.get("data") or {},
        schema_version=payload.get("schema_version", "1.0"),
        compatible=bool(payload.get("compatible", True)),
        stale=bool(payload.get("stale", False)),
        created_at=payload.get("created_at"),
        content_hash=payload.get("content_hash"),
    )


class SQLiteWorkflowRepository(SQLiteRepositoryBase, WorkflowRepository):
    """Persists workflow jobs, stage runs, artifacts, scene items, and logs in SQLite."""

    def __init__(self, db_path: Union[str, Path] = "studio.db") -> None:
        super().__init__(db_path=db_path)

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_jobs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stage_order_json TEXT NOT NULL,
                    pause_requested INTEGER NOT NULL DEFAULT 0,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    error TEXT,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_workflow_jobs_project
                ON workflow_jobs (project_id, updated_at)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_stage_runs (
                    job_id TEXT NOT NULL,
                    stage_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    dependencies_json TEXT NOT NULL,
                    required INTEGER NOT NULL,
                    artifact_type TEXT NOT NULL,
                    required_schema_version TEXT,
                    params_json TEXT NOT NULL,
                    external_run_id TEXT,
                    error TEXT,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    started_at TEXT,
                    completed_at TEXT,
                    updated_at TEXT,
                    PRIMARY KEY (job_id, stage_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_artifacts (
                    job_id TEXT NOT NULL,
                    stage_id TEXT NOT NULL,
                    artifact_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    uri TEXT,
                    data_json TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    compatible INTEGER NOT NULL,
                    stale INTEGER NOT NULL,
                    created_at TEXT,
                    content_hash TEXT,
                    PRIMARY KEY (job_id, stage_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_scene_items (
                    job_id TEXT NOT NULL,
                    stage_id TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    artifact_json TEXT,
                    input_data_json TEXT NOT NULL,
                    error TEXT,
                    PRIMARY KEY (job_id, stage_id, item_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_logs (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    stage_id TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_workflow_logs_project
                ON workflow_logs (project_id, created_at)
                """
            )
            conn.commit()

    def save(self, job: WorkflowJobResult) -> None:
        with self._get_connection() as conn:
            prev_job_row = conn.execute(
                "SELECT status, pause_requested, cancel_requested FROM workflow_jobs WHERE id = ?",
                (job.id,),
            ).fetchone()
            prev_stage_rows = conn.execute(
                "SELECT stage_id, status, error FROM workflow_stage_runs WHERE job_id = ?",
                (job.id,),
            ).fetchall()
            prev_stages: Dict[str, Tuple[str, Optional[str]]] = {
                row["stage_id"]: (row["status"], row["error"])
                for row in prev_stage_rows
            }

            conn.execute(
                """
                INSERT INTO workflow_jobs (
                    id, project_id, status, stage_order_json,
                    pause_requested, cancel_requested,
                    created_at, updated_at, completed_at, error, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    project_id = excluded.project_id,
                    status = excluded.status,
                    stage_order_json = excluded.stage_order_json,
                    pause_requested = excluded.pause_requested,
                    cancel_requested = excluded.cancel_requested,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    completed_at = excluded.completed_at,
                    error = excluded.error,
                    metadata_json = excluded.metadata_json
                """,
                (
                    job.id,
                    job.project_id,
                    job.status,
                    json.dumps(list(job.stage_order)),
                    1 if job.pause_requested else 0,
                    1 if job.cancel_requested else 0,
                    job.created_at,
                    job.updated_at,
                    job.completed_at,
                    job.error,
                    json.dumps(job.metadata),
                ),
            )

            conn.execute("DELETE FROM workflow_stage_runs WHERE job_id = ?", (job.id,))
            conn.execute("DELETE FROM workflow_artifacts WHERE job_id = ?", (job.id,))
            conn.execute("DELETE FROM workflow_scene_items WHERE job_id = ?", (job.id,))

            for position, stage in enumerate(job.stages):
                conn.execute(
                    """
                    INSERT INTO workflow_stage_runs (
                        job_id, stage_id, position, mode, status, dependencies_json,
                        required, artifact_type, required_schema_version, params_json,
                        external_run_id, error, attempt_count, started_at, completed_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job.id,
                        stage.stage_id,
                        position,
                        stage.mode,
                        stage.status,
                        json.dumps(list(stage.dependencies)),
                        1 if stage.required else 0,
                        stage.artifact_type,
                        stage.required_schema_version,
                        json.dumps(stage.params),
                        stage.external_run_id,
                        stage.error,
                        stage.attempt_count,
                        stage.started_at,
                        stage.completed_at,
                        stage.updated_at,
                    ),
                )

                if stage.artifact is not None:
                    art = stage.artifact
                    conn.execute(
                        """
                        INSERT INTO workflow_artifacts (
                            job_id, stage_id, artifact_id, artifact_type, uri,
                            data_json, schema_version, compatible, stale, created_at, content_hash
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            job.id,
                            stage.stage_id,
                            art.artifact_id,
                            art.artifact_type,
                            art.uri,
                            json.dumps(art.data),
                            art.schema_version,
                            1 if art.compatible else 0,
                            1 if art.stale else 0,
                            art.created_at,
                            art.content_hash,
                        ),
                    )

                for item_pos, item in enumerate(stage.items):
                    conn.execute(
                        """
                        INSERT INTO workflow_scene_items (
                            job_id, stage_id, item_id, position, status,
                            artifact_json, input_data_json, error
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            job.id,
                            stage.stage_id,
                            item.item_id,
                            item_pos,
                            item.status,
                            _serialize_artifact(item.artifact),
                            json.dumps(item.input_data),
                            item.error,
                        ),
                    )

            self._record_transition_logs(conn, job, prev_job_row, prev_stages)
            conn.commit()

    def get_by_id(self, job_id: str) -> Optional[WorkflowJobResult]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM workflow_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                return None
            return self._hydrate_job(conn, row)

    def list_by_project(self, project_id: str) -> List[WorkflowJobResult]:
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM workflow_jobs
                WHERE project_id = ?
                ORDER BY updated_at DESC, created_at DESC
                """,
                (project_id,),
            ).fetchall()
            return [self._hydrate_job(conn, row) for row in rows]

    def delete(self, job_id: str) -> bool:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM workflow_scene_items WHERE job_id = ?", (job_id,))
            conn.execute("DELETE FROM workflow_artifacts WHERE job_id = ?", (job_id,))
            conn.execute("DELETE FROM workflow_stage_runs WHERE job_id = ?", (job_id,))
            conn.execute("DELETE FROM workflow_logs WHERE job_id = ?", (job_id,))
            cursor = conn.execute("DELETE FROM workflow_jobs WHERE id = ?", (job_id,))
            conn.commit()
            return cursor.rowcount > 0

    def append_log(
        self,
        project_id: str,
        job_id: str,
        stage_id: str,
        level: str,
        message: str,
    ) -> WorkflowLogEntry:
        entry = WorkflowLogEntry(
            id=str(uuid.uuid4()),
            job_id=job_id,
            project_id=project_id,
            stage_id=stage_id,
            level=level,
            message=message,
            created_at=_utc_iso(),
        )
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO workflow_logs (id, job_id, project_id, stage_id, level, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.job_id,
                    entry.project_id,
                    entry.stage_id,
                    entry.level,
                    entry.message,
                    entry.created_at,
                ),
            )
            conn.commit()
        return entry

    def list_logs(
        self,
        project_id: str,
        job_id: Optional[str] = None,
        limit: int = 200,
    ) -> List[WorkflowLogEntry]:
        with self._get_connection() as conn:
            if job_id:
                rows = conn.execute(
                    """
                    SELECT * FROM workflow_logs
                    WHERE project_id = ? AND job_id = ?
                    ORDER BY created_at DESC, rowid DESC
                    LIMIT ?
                    """,
                    (project_id, job_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM workflow_logs
                    WHERE project_id = ?
                    ORDER BY created_at DESC, rowid DESC
                    LIMIT ?
                    """,
                    (project_id, limit),
                ).fetchall()
        return [
            WorkflowLogEntry(
                id=row["id"],
                job_id=row["job_id"],
                project_id=row["project_id"],
                stage_id=row["stage_id"],
                level=row["level"],
                message=row["message"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def _hydrate_job(self, conn: object, job_row: object) -> WorkflowJobResult:
        # Use sqlite3.Connection methods via duck typing to keep helpers concise.
        job_id = job_row["id"]
        stage_rows = conn.execute(
            """
            SELECT * FROM workflow_stage_runs
            WHERE job_id = ?
            ORDER BY position ASC
            """,
            (job_id,),
        ).fetchall()
        art_rows = conn.execute(
            "SELECT * FROM workflow_artifacts WHERE job_id = ?",
            (job_id,),
        ).fetchall()
        item_rows = conn.execute(
            """
            SELECT * FROM workflow_scene_items
            WHERE job_id = ?
            ORDER BY position ASC
            """,
            (job_id,),
        ).fetchall()

        artifacts_by_stage: Dict[str, StageArtifactDto] = {}
        for art in art_rows:
            artifacts_by_stage[art["stage_id"]] = StageArtifactDto(
                artifact_id=art["artifact_id"],
                stage_id=art["stage_id"],
                artifact_type=art["artifact_type"],
                uri=art["uri"],
                data=json.loads(art["data_json"]),
                schema_version=art["schema_version"],
                compatible=bool(art["compatible"]),
                stale=bool(art["stale"]),
                created_at=art["created_at"],
                content_hash=art["content_hash"],
            )

        items_by_stage: Dict[str, List[StageItemStateDto]] = {}
        for item in item_rows:
            items_by_stage.setdefault(item["stage_id"], []).append(
                StageItemStateDto(
                    item_id=item["item_id"],
                    status=item["status"],
                    artifact=_deserialize_artifact(item["artifact_json"]),
                    input_data=json.loads(item["input_data_json"]),
                    error=item["error"],
                )
            )

        stages = tuple(
            WorkflowStageResult(
                stage_id=row["stage_id"],
                mode=row["mode"],
                status=row["status"],
                dependencies=tuple(json.loads(row["dependencies_json"])),
                required=bool(row["required"]),
                artifact_type=row["artifact_type"],
                required_schema_version=row["required_schema_version"],
                artifact=artifacts_by_stage.get(row["stage_id"]),
                items=tuple(items_by_stage.get(row["stage_id"], ())),
                params=json.loads(row["params_json"]),
                external_run_id=row["external_run_id"],
                error=row["error"],
                attempt_count=int(row["attempt_count"]),
                started_at=row["started_at"],
                completed_at=row["completed_at"],
                updated_at=row["updated_at"],
            )
            for row in stage_rows
        )

        return WorkflowJobResult(
            id=job_row["id"],
            project_id=job_row["project_id"],
            status=job_row["status"],
            stage_order=tuple(json.loads(job_row["stage_order_json"])),
            stages=stages,
            created_at=job_row["created_at"],
            updated_at=job_row["updated_at"],
            pause_requested=bool(job_row["pause_requested"]),
            cancel_requested=bool(job_row["cancel_requested"]),
            completed_at=job_row["completed_at"],
            error=job_row["error"],
            metadata=json.loads(job_row["metadata_json"]),
        )

    def _record_transition_logs(
        self,
        conn: object,
        job: WorkflowJobResult,
        prev_job_row: Optional[object],
        prev_stages: Dict[str, Tuple[str, Optional[str]]],
    ) -> None:
        now = _utc_iso()
        if prev_job_row is None:
            conn.execute(
                """
                INSERT INTO workflow_logs (id, job_id, project_id, stage_id, level, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    job.id,
                    job.project_id,
                    "workflow",
                    "info",
                    f"Created workflow job ({job.status}).",
                    now,
                ),
            )
        elif prev_job_row["status"] != job.status:
            level = "error" if job.status in ("failed", "needs_reconciliation") else "info"
            detail = f" ({job.error})" if job.error and level == "error" else ""
            conn.execute(
                """
                INSERT INTO workflow_logs (id, job_id, project_id, stage_id, level, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    job.id,
                    job.project_id,
                    "workflow",
                    level,
                    f"Workflow job transitioned {prev_job_row['status']} -> {job.status}{detail}.",
                    now,
                ),
            )

        for stage in job.stages:
            prev_status, prev_err = prev_stages.get(stage.stage_id, (None, None))
            if prev_status == stage.status and prev_err == stage.error:
                continue
            if prev_status is None and stage.status == "pending":
                continue
            level = (
                "error"
                if stage.status in ("failed", "unknown_outcome")
                else "warning"
                if stage.status in ("stale", "waiting_manual", "awaiting_approval")
                else "info"
            )
            msg = f"Stage '{stage.stage_id}' is {stage.status}"
            if stage.error:
                msg = f"{msg}: {stage.error}"
            conn.execute(
                """
                INSERT INTO workflow_logs (id, job_id, project_id, stage_id, level, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    job.id,
                    job.project_id,
                    stage.stage_id,
                    level,
                    msg,
                    now,
                ),
            )
