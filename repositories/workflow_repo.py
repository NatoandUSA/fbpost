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

    def membership_ineligible_profiles(self, target_url: str):
        """Profiles already proven not to be members of this exact group target."""
        from utils import normalize_target_url
        wanted = normalize_target_url(target_url or "")
        if not wanted:
            return set()
        conn = self.get_conn()
        try:
            rows = conn.execute(
                """SELECT profile_id,target_url FROM workflow_tasks
                   WHERE action='group' AND error_code='GROUP_MEMBERSHIP_UNVERIFIED'
                     AND profile_id IS NOT NULL AND profile_id!=''"""
            ).fetchall()
            return {str(r["profile_id"]) for r in rows
                    if normalize_target_url(r["target_url"] or "") == wanted}
        finally:
            conn.close()

    def profile_group_scores(self, target_url: str):
        """Evidence score for profile × group; membership mismatch is a hard exclusion elsewhere."""
        from utils import normalize_target_url
        wanted = normalize_target_url(target_url or "")
        if not wanted:
            return {}
        conn = self.get_conn()
        try:
            rows = conn.execute(
                """SELECT profile_id,target_url,state,error_code FROM workflow_tasks
                   WHERE action='group' AND profile_id IS NOT NULL AND profile_id!=''"""
            ).fetchall()
            scores = {}
            weights = {"published": 4, "pending": 2, "unverified": -1, "failed": -2}
            for row in rows:
                if normalize_target_url(row["target_url"] or "") != wanted:
                    continue
                profile_id = str(row["profile_id"])
                delta = -6 if str(row["error_code"] or "") == "GROUP_MEMBERSHIP_UNVERIFIED" else weights.get(str(row["state"] or ""), 0)
                scores[profile_id] = scores.get(profile_id, 0) + delta
            return scores
        finally:
            conn.close()

    def system_posting_summary(self):
        """Authoritative persisted totals for dashboard audit/operations."""
        conn = self.get_conn()
        try:
            post = {r["publish_state"]: int(r["n"]) for r in conn.execute(
                "SELECT publish_state,COUNT(*) n FROM posted_links GROUP BY publish_state"
            ).fetchall()}
            mod = conn.execute(
                """SELECT COUNT(*) groups_known,
                          SUM(CASE WHEN requires_approval=1 THEN 1 ELSE 0 END) approval_groups,
                          SUM(CASE WHEN pending_count>=skip_threshold THEN 1 ELSE 0 END) capacity_blocked_groups,
                          COALESCE(SUM(pending_count),0) tracked_pending_posts
                   FROM group_moderation_registry"""
            ).fetchone()
            return {
                "published": int(post.get("published", 0)),
                "pending": int(post.get("pending", 0)),
                "submitted_unverified": int(post.get("submitted_unverified", 0)),
                "groups_known_moderated": int(mod["groups_known"] or 0),
                "approval_groups": int(mod["approval_groups"] or 0),
                "capacity_blocked_groups": int(mod["capacity_blocked_groups"] or 0),
                "tracked_pending_posts": int(mod["tracked_pending_posts"] or 0),
                "configured_profiles": int(conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]),
                "configured_groups": int(conn.execute("SELECT COUNT(*) FROM groups").fetchone()[0]),
            }
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
                       SUM(CASE WHEN state='failed' AND COALESCE(error_code,'')!='GROUP_MEMBERSHIP_UNVERIFIED' THEN 1 ELSE 0 END) AS failed,
                       SUM(CASE WHEN state='failed' AND error_code='GROUP_MEMBERSHIP_UNVERIFIED' THEN 1 ELSE 0 END) AS membership_unverified,
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
                # Membership mismatch is target/profile compatibility, not a posting-engine failure.
                # Keep it visible but exclude it from the posting success denominator.
                item['membership_unverified'] = int(item.get('membership_unverified') or 0)
                terminal = item['published'] + item['pending'] + item['unverified'] + item['failed']
                item['published_rate'] = round((item['published'] * 100.0 / terminal), 1) if terminal else 0.0
                result.append(item)
            return result
        finally:
            conn.close()
