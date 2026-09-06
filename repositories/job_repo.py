"""Repository for Automation Jobs.
Manages background job states, progress, metadata, and startup reconciliation.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from repositories.base import BaseRepository


class JobRepository(BaseRepository):
    def create_job(self, job: Dict[str, Any]) -> str:
        job_id = job.get("id") or uuid.uuid4().hex[:16]
        command = job.get("command", "")
        account_id = job.get("account_id")
        state = job.get("state", "queued")
        payload = job.get("payload") or {}
        def _redact_secrets(val):
            if isinstance(val, dict):
                res = {}
                for k, v in val.items():
                    k_lower = str(k).lower()
                    if any(s in k_lower for s in ("key", "token", "password", "secret", "cookie")):
                        res[k] = "***REDACTED***"
                    else:
                        res[k] = _redact_secrets(v)
                return res
            elif isinstance(val, list):
                return [_redact_secrets(x) for x in val]
            return val

        clean_payload = _redact_secrets(payload)
        payload_json = self.dumps(clean_payload) if isinstance(clean_payload, (dict, list)) else str(clean_payload)

        pid = job.get("pid")
        progress_current = int(job.get("progress_current", 0))
        progress_total = int(job.get("progress_total", 0))
        log_file = job.get("log_file", "")
        error_message = job.get("error_message")
        created_at = job.get("created_at") or datetime.now(timezone.utc).isoformat()
        started_at = job.get("started_at")
        finished_at = job.get("finished_at")

        clean_job = dict(job)
        if isinstance(clean_job.get("payload"), dict):
            clean_job["payload"] = clean_payload
        raw_json = self.dumps(clean_job)

        with self.transaction() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO automation_jobs
                (id, command, account_id, state, payload_json, pid, progress_current,
                 progress_total, log_file, error_message, created_at, started_at, finished_at, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    command,
                    account_id,
                    state,
                    payload_json,
                    pid,
                    progress_current,
                    progress_total,
                    log_file,
                    error_message,
                    created_at,
                    started_at,
                    finished_at,
                    raw_json,
                ),
            )
        return job_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM automation_jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if not row:
                return None
            data = dict(row)
            if data.get("payload_json"):
                data["payload"] = self.loads(data["payload_json"])
            return data
        finally:
            conn.close()

    def list_jobs(self, limit: int = 50, state: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self.get_conn()
        try:
            if state:
                rows = conn.execute(
                    "SELECT * FROM automation_jobs WHERE state = ? ORDER BY created_at DESC LIMIT ?",
                    (state, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM automation_jobs ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()

            result = []
            for r in rows:
                item = dict(r)
                if item.get("payload_json"):
                    item["payload"] = self.loads(item["payload_json"])
                result.append(item)
            return result
        finally:
            conn.close()

    def update_job(self, job_id: str, **kwargs) -> bool:
        if not kwargs:
            return False

        allowed = {
            "state",
            "pid",
            "progress_current",
            "progress_total",
            "log_file",
            "error_message",
            "started_at",
            "finished_at",
            "raw_json",
        }
        fields_to_update = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields_to_update:
            return False

        set_clause = ", ".join(f"{k} = ?" for k in fields_to_update)
        values = list(fields_to_update.values())
        values.append(job_id)

        with self.transaction() as conn:
            conn.execute(
                f"UPDATE automation_jobs SET {set_clause} WHERE id = ?",
                values,
            )
        return True

    def mark_running(self, job_id: str, pid: Optional[int] = None) -> bool:
        now_str = datetime.now(timezone.utc).isoformat()
        with self.transaction() as conn:
            cur = conn.execute(
                """
                UPDATE automation_jobs
                SET state = 'running', pid = ?, started_at = ?
                WHERE id = ? AND state = 'queued'
                """,
                (pid, now_str, job_id),
            )
            return cur.rowcount > 0

    def mark_finished(
        self,
        job_id: str,
        state: str = "success",
        error_message: Optional[str] = None,
        progress_current: Optional[int] = None,
        from_states: Optional[List[str]] = None,
    ) -> bool:
        now_str = datetime.now(timezone.utc).isoformat()
        with self.transaction() as conn:
            row = conn.execute("SELECT state FROM automation_jobs WHERE id = ?", (job_id,)).fetchone()
            if not row:
                return False
            curr_state = row["state"]
            if from_states and curr_state not in from_states:
                return False
            # Prevent overwriting a terminal cancelled or interrupted job with success/failed
            if curr_state in ("cancelled", "interrupted") and state in ("success", "failed"):
                return False

            set_parts = ["state = ?", "finished_at = ?"]
            params = [state, now_str]
            if error_message is not None:
                set_parts.append("error_message = ?")
                params.append(error_message)
            if progress_current is not None:
                set_parts.append("progress_current = ?")
                params.append(progress_current)
            params.append(job_id)

            conn.execute(f"UPDATE automation_jobs SET {', '.join(set_parts)} WHERE id = ?", params)
            return True

    def reconcile_running_jobs(self) -> int:
        now_str = datetime.now(timezone.utc).isoformat()
        with self.transaction() as conn:
            cur = conn.execute(
                """
                UPDATE automation_jobs
                SET state = 'interrupted',
                    finished_at = ?,
                    error_message = 'Tiến trình bị gián đoạn do ứng dụng khởi động lại.'
                WHERE state = 'running'
                """,
                (now_str,),
            )
            return cur.rowcount
