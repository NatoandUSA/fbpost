"""Persistence helpers for task state and event timelines."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from repositories.base import BaseRepository


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowRepository(BaseRepository):
    def get_task(self, task_id: str):
        conn = self.get_conn()
        try:
            row = conn.execute("SELECT * FROM workflow_tasks WHERE id=?", (task_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    def create_task(self, job_id=None, action="", profile_id=None, target_url="", task_key=None, metadata=None):
        task_id = uuid.uuid4().hex
        key = task_key or f"{job_id or 'manual'}:{action}:{profile_id or ''}:{task_id[:8]}"
        now = now_iso()
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO workflow_tasks (id,job_id,task_key,action,profile_id,target_url,phase,submission_status,verification_status,state,progress,metadata_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (task_id, job_id, key, action, profile_id, target_url, "QUEUED",
                 "NOT_SUBMITTED", "NOT_STARTED", "queued", 0,
                 json.dumps(metadata or {}, ensure_ascii=False), now, now),
            )
        return self.get_task(task_id)

    def update_task(self, task_id: str, **fields):
        allowed = {"phase","submission_status","verification_status","state","progress","result_url","error_code","error_message","evidence_dir","metadata_json","started_at","finished_at"}
        clean = {k: v for k, v in fields.items() if k in allowed}
        if not clean:
            return self.get_task(task_id)
        clean["updated_at"] = now_iso()
        names = list(clean)
        sql = "UPDATE workflow_tasks SET " + ", ".join(f"{name}=?" for name in names) + " WHERE id=?"
        values = [clean[name] for name in names] + [task_id]
        with self.transaction() as conn:
            conn.execute(sql, values)
        return self.get_task(task_id)

    def add_event(self, task_id: str, event_type: str, phase: str = "", message: str = "", payload=None):
        with self.transaction() as conn:
            row = conn.execute("SELECT COALESCE(MAX(seq),0)+1 AS next_seq FROM workflow_events WHERE task_id=?", (task_id,)).fetchone()
            seq = int(row["next_seq"])
            conn.execute(
                "INSERT INTO workflow_events(task_id,seq,event_type,phase,message,payload_json,created_at) VALUES(?,?,?,?,?,?,?)",
                (task_id, seq, event_type, phase, message,
                 json.dumps(payload or {}, ensure_ascii=False), now_iso()),
            )
        return seq
    def list_tasks(self, job_id=None, states=None, limit=500):
        conn = self.get_conn()
        try:
            clauses = []
            params = []
            if job_id:
                clauses.append("job_id=?")
                params.append(job_id)
            if states:
                marks = ",".join("?" for _ in states)
                clauses.append(f"state IN ({marks})")
                params.extend(states)
            where = " WHERE " + " AND ".join(clauses) if clauses else ""
            rows = conn.execute(
                f"SELECT * FROM workflow_tasks{where} ORDER BY updated_at DESC LIMIT ?",
                (*params, int(limit)),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def list_events(self, task_id: str):
        conn = self.get_conn()
        try:
            rows = conn.execute("SELECT * FROM workflow_events WHERE task_id=? ORDER BY seq", (task_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def profile_posting_performance(self, limit=200):
        """Evidence-based posting totals; pending is reported separately from success."""
        conn = self.get_conn()
        try:
            rows = conn.execute(
                """
                SELECT profile_id,
                       COUNT(*) AS total,
                       SUM(CASE WHEN state='published' THEN 1 ELSE 0 END) AS published,
                       SUM(CASE WHEN state='pending' THEN 1 ELSE 0 END) AS pending,
                       SUM(CASE WHEN state='unverified' THEN 1 ELSE 0 END) AS unverified,
                       SUM(CASE WHEN state='failed' THEN 1 ELSE 0 END) AS failed,
                       SUM(CASE WHEN state IN ('running','queued') THEN 1 ELSE 0 END) AS active,
                       ROUND(AVG(CASE WHEN finished_at IS NOT NULL AND started_at IS NOT NULL
                           THEN (julianday(finished_at)-julianday(started_at))*86400 END), 1) AS avg_seconds,
                       MAX(updated_at) AS last_activity
                FROM workflow_tasks
                WHERE action IN ('group','page') AND profile_id IS NOT NULL AND profile_id != ''
                GROUP BY profile_id
                ORDER BY published DESC, total DESC
                LIMIT ?
                """, (int(limit),)
            ).fetchall()
            rejected_rows = conn.execute(
                """SELECT profile_id, COUNT(*) AS rejected_comments
                   FROM comment_delivery_events
                   WHERE status='rejected' AND profile_id IS NOT NULL AND profile_id != ''
                   GROUP BY profile_id"""
            ).fetchall()
            rejected_by_profile = {row["profile_id"]: row["rejected_comments"] for row in rejected_rows}
            result = []
            for row in rows:
                item = dict(row)
                item['comment_rejected'] = int(rejected_by_profile.get(item['profile_id'], 0))
                terminal = item['published'] + item['pending'] + item['unverified'] + item['failed']
                item['published_rate'] = round((item['published'] * 100.0 / terminal), 1) if terminal else 0.0
                result.append(item)
            return result
        finally:
            conn.close()
