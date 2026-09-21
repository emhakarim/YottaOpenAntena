"""Tiny sqlite3-backed run store (stdlib only).

One row per solver run.  JSON documents are stored as text and are *not*
normalised: the point is a durable trail of what was run, with which project
document, and with which status, so that a later report can be traced back to
its inputs.
"""

from __future__ import annotations

import datetime as _dt
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    project_name TEXT,
    project_json TEXT NOT NULL,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    results_json TEXT,
    note        TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs (created_at);
"""


class ResultsStore:
    """Store and retrieve run records."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self.path))
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript(SCHEMA)
        self._connection.commit()

    # ------------------------------------------------------------- lifecycle
    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "ResultsStore":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    # ----------------------------------------------------------------- write
    def save_run(
        self,
        run_id: str,
        project: Dict[str, Any],
        status: str,
        results: Optional[Dict[str, Any]] = None,
        created_at: Optional[str] = None,
        note: str = "",
    ) -> str:
        if not run_id:
            raise ValueError("run_id must be a non-empty string")
        if status not in ("not_run", "ok", "failed", "dry_run"):
            raise ValueError("status must be one of not_run/ok/failed/dry_run")
        timestamp = created_at or _dt.datetime.now().isoformat(timespec="seconds")
        self._connection.execute(
            """
            INSERT INTO runs (run_id, project_name, project_json, status, created_at,
                              results_json, note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                project_name = excluded.project_name,
                project_json = excluded.project_json,
                status = excluded.status,
                created_at = excluded.created_at,
                results_json = excluded.results_json,
                note = excluded.note
            """,
            (
                run_id,
                str(project.get("name", "")),
                json.dumps(project),
                status,
                timestamp,
                json.dumps(results) if results is not None else None,
                note,
            ),
        )
        self._connection.commit()
        return run_id

    # ------------------------------------------------------------------ read
    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        cursor = self._connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        return self._row_to_dict(row) if row else None

    def list_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        cursor = self._connection.execute(
            "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (int(limit),)
        )
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def count(self) -> int:
        cursor = self._connection.execute("SELECT COUNT(*) AS n FROM runs")
        return int(cursor.fetchone()["n"])

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        results = row["results_json"]
        return {
            "run_id": row["run_id"],
            "project_name": row["project_name"],
            "project": json.loads(row["project_json"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "results": json.loads(results) if results else None,
            "note": row["note"],
        }

    def describe(self, limit: int = 10) -> str:
        rows = self.list_runs(limit=limit)
        if not rows:
            return f"store {self.path}: no runs recorded"
        lines = [f"store {self.path}: {self.count()} run(s); newest {len(rows)}:"]
        for row in rows:
            lines.append(
                f"  {row['created_at']}  {row['run_id']:<40} {row['status']:<8} "
                f"{row['project_name']}"
            )
        return "\n".join(lines)
