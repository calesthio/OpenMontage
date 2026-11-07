"""SQLite state store — durable runtime state for the factory pipeline.

V8 §8.2: runtime status lives in SQLite, not only in Git commits or BUILD_LOG.
Git holds source code, schemas, configs, docs and small golden manifests.
Generated media stays out of ordinary Git history as artefacts.

The state store is the source of truth for stage transitions; checkpoint JSON
(``lib/checkpoint.py``) is the human-readable mirror written after each
durable transition.

Statuses:
    PENDING, RUNNING, PASSED, DEGRADED, BLOCKED, FAILED, NEEDS_REVIEW, SKIPPED

Failure classes (V8 §8.3):
    REQUIRED   — error blocks downstream stages
    OPTIONAL   — fallback allowed, continue
    DEGRADABLE — continue only with explicit warning
    MANUAL_REVIEW — needs a human decision before proceeding
"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_STATUSES = frozenset({
    "PENDING", "RUNNING", "PASSED", "DEGRADED", "BLOCKED", "FAILED",
    "NEEDS_REVIEW", "SKIPPED",
})

FAILURE_CLASSES = frozenset({"REQUIRED", "OPTIONAL", "DEGRADABLE", "MANUAL_REVIEW"})

SCHEMA = """
CREATE TABLE IF NOT EXISTS stage_state (
    project_id       TEXT NOT NULL,
    stage            TEXT NOT NULL,
    pipeline_type    TEXT NOT NULL DEFAULT 'unknown',
    status           TEXT NOT NULL,
    failure_class    TEXT,
    input_fingerprint TEXT,
    output_artifacts  TEXT,      -- JSON: list of artifact paths
    checksums        TEXT,      -- JSON: {path: sha256}
    qc_passed        INTEGER NOT NULL DEFAULT 0,
    retry_count      INTEGER NOT NULL DEFAULT 0,
    reason_code      TEXT,
    warning          TEXT,
    requires_approval INTEGER NOT NULL DEFAULT 0,
    started_at       TEXT,
    finished_at      TEXT,
    updated_at       TEXT NOT NULL,
    PRIMARY KEY (project_id, stage, pipeline_type)
);

CREATE TABLE IF NOT EXISTS events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   TEXT NOT NULL,
    stage        TEXT,
    event_type   TEXT NOT NULL,
    message      TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stage_state_project
    ON stage_state(project_id);
CREATE INDEX IF NOT EXISTS idx_events_project
    ON events(project_id, created_at);
"""


@dataclass
class StageRecord:
    project_id: str
    stage: str
    pipeline_type: str = "unknown"
    status: str = "PENDING"
    failure_class: str | None = None
    input_fingerprint: str | None = None
    output_artifacts: list[str] = field(default_factory=list)
    checksums: dict[str, str] = field(default_factory=dict)
    qc_passed: bool = False
    retry_count: int = 0
    reason_code: str | None = None
    warning: str | None = None
    requires_approval: bool = False
    started_at: str | None = None
    finished_at: str | None = None
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["output_artifacts"] = list(self.output_artifacts)
        d["checksums"] = dict(self.checksums)
        return d


class StateStore:
    """Thread-unfriendly (single-process) SQLite wrapper for pipeline state.

    All writes are single transactions. Callers commit explicitly via
    :meth:`commit`. Use :meth:`transition` for atomic status changes.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Stage lifecycle
    # ------------------------------------------------------------------

    def upsert(self, record: StageRecord) -> None:
        """Insert or replace a stage record (full replace)."""
        if record.status not in VALID_STATUSES:
            raise ValueError(f"Invalid status {record.status!r}; valid: {sorted(VALID_STATUSES)}")
        if record.failure_class is not None and record.failure_class not in FAILURE_CLASSES:
            raise ValueError(
                f"Invalid failure_class {record.failure_class!r}; valid: {sorted(FAILURE_CLASSES)}"
            )
        self._conn.execute(
            """
            INSERT INTO stage_state (
                project_id, stage, pipeline_type, status, failure_class,
                input_fingerprint, output_artifacts, checksums, qc_passed,
                retry_count, reason_code, warning, requires_approval,
                started_at, finished_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, stage, pipeline_type) DO UPDATE SET
                status=excluded.status,
                failure_class=excluded.failure_class,
                input_fingerprint=excluded.input_fingerprint,
                output_artifacts=excluded.output_artifacts,
                checksums=excluded.checksums,
                qc_passed=excluded.qc_passed,
                retry_count=excluded.retry_count,
                reason_code=excluded.reason_code,
                warning=excluded.warning,
                requires_approval=excluded.requires_approval,
                started_at=excluded.started_at,
                finished_at=excluded.finished_at,
                updated_at=excluded.updated_at
            """,
            (
                record.project_id, record.stage, record.pipeline_type,
                record.status, record.failure_class,
                record.input_fingerprint,
                ",".join(record.output_artifacts),
                __import__("json").dumps(record.checksums, ensure_ascii=False),
                int(record.qc_passed),
                record.retry_count, record.reason_code, record.warning,
                int(record.requires_approval),
                record.started_at, record.finished_at, record.updated_at,
            ),
        )

    def get(self, project_id: str, stage: str,
            pipeline_type: str = "unknown") -> StageRecord | None:
        row = self._conn.execute(
            """
            SELECT project_id, stage, pipeline_type, status, failure_class,
                   input_fingerprint, output_artifacts, checksums, qc_passed,
                   retry_count, reason_code, warning, requires_approval,
                   started_at, finished_at, updated_at
            FROM stage_state
            WHERE project_id=? AND stage=? AND pipeline_type=?
            """,
            (project_id, stage, pipeline_type),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def get_completed(self, project_id: str,
                      pipeline_type: str = "unknown") -> list[StageRecord]:
        rows = self._conn.execute(
            """
            SELECT project_id, stage, pipeline_type, status, failure_class,
                   input_fingerprint, output_artifacts, checksums, qc_passed,
                   retry_count, reason_code, warning, requires_approval,
                   started_at, finished_at, updated_at
            FROM stage_state
            WHERE project_id=? AND pipeline_type=? AND status='PASSED'
            ORDER BY updated_at
            """,
            (project_id, pipeline_type),
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def transition(
        self,
        project_id: str,
        stage: str,
        new_status: str,
        *,
        pipeline_type: str = "unknown",
        failure_class: str | None = None,
        input_fingerprint: str | None = None,
        output_artifacts: list[str] | None = None,
        checksums: dict[str, str] | None = None,
        qc_passed: bool = False,
        reason_code: str | None = None,
        warning: str | None = None,
        requires_approval: bool = False,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> StageRecord:
        """Atomically transition a stage to ``new_status``.

        Merges with the existing record if one exists; otherwise creates a
        PENDING record first. Returns the updated :class:`StageRecord`.
        """
        if new_status not in VALID_STATUSES:
            raise ValueError(f"Invalid status {new_status!r}")
        existing = self.get(project_id, stage, pipeline_type)
        now = datetime.now(timezone.utc).isoformat()
        rec = existing or StageRecord(
            project_id=project_id, stage=stage, pipeline_type=pipeline_type,
        )
        rec.status = new_status
        rec.updated_at = now
        if failure_class is not None:
            rec.failure_class = failure_class
        if input_fingerprint is not None:
            rec.input_fingerprint = input_fingerprint
        if output_artifacts is not None:
            rec.output_artifacts = list(output_artifacts)
        if checksums is not None:
            rec.checksums = dict(checksums)
        rec.qc_passed = qc_passed
        if reason_code is not None:
            rec.reason_code = reason_code
        if warning is not None:
            rec.warning = warning
        rec.requires_approval = requires_approval
        if new_status == "RUNNING" and rec.started_at is None:
            rec.started_at = now
        if new_status in ("PASSED", "FAILED", "BLOCKED", "DEGRADED", "SKIPPED"):
            rec.finished_at = finished_at or now
        self.upsert(rec)
        return rec

    def complete(self, project_id: str, stage: str,
                 *, pipeline_type: str = "unknown",
                 checksums: dict[str, str] | None = None,
                 qc_passed: bool = True,
                 output_artifacts: list[str] | None = None,
                 **kwargs: Any) -> StageRecord:
        """Mark a stage PASSED. V8 §8.1: requires checksums and qc_passed."""
        if not checksums:
            raise ValueError("complete() requires a non-empty checksums map (V8 §8.1)")
        if not qc_passed:
            raise ValueError("complete() requires qc_passed=True (V8 §8.1)")
        return self.transition(
            project_id, stage, "PASSED",
            pipeline_type=pipeline_type,
            checksums=checksums, qc_passed=True,
            output_artifacts=output_artifacts, **kwargs,
        )

    def fail(self, project_id: str, stage: str, *,
             pipeline_type: str = "unknown",
             failure_class: str = "REQUIRED",
             reason_code: str | None = None,
             warning: str | None = None,
             **kwargs: Any) -> StageRecord:
        """Mark a stage FAILED with a failure class (V8 §8.3)."""
        return self.transition(
            project_id, stage, "FAILED",
            pipeline_type=pipeline_type,
            failure_class=failure_class,
            reason_code=reason_code, warning=warning, **kwargs,
        )

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def event(self, project_id: str, event_type: str, message: str,
              stage: str | None = None) -> None:
        """Append an event to the append-only event log."""
        self._conn.execute(
            "INSERT INTO events (project_id, stage, event_type, message, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (project_id, stage, event_type, message,
             datetime.now(timezone.utc).isoformat()),
        )

    # ------------------------------------------------------------------
    # Commit / close
    # ------------------------------------------------------------------

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self.commit()
        self._conn.close()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_record(row: tuple) -> StageRecord:
        json_mod = __import__("json")
        return StageRecord(
            project_id=row[0],
            stage=row[1],
            pipeline_type=row[2],
            status=row[3],
            failure_class=row[4],
            input_fingerprint=row[5],
            output_artifacts=row[6].split(",") if row[6] else [],
            checksums=json_mod.loads(row[7]) if row[7] else {},
            qc_passed=bool(row[8]),
            retry_count=row[9],
            reason_code=row[10],
            warning=row[11],
            requires_approval=bool(row[12]),
            started_at=row[13],
            finished_at=row[14],
            updated_at=row[15],
        )
