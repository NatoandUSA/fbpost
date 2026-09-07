"""Repository for Campaigns, Publication Queue, and Manual Group Queue."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from repositories.base import BaseRepository


class CampaignRepository(BaseRepository):
    # Campaigns
    def list_campaigns(self) -> List[Dict[str, Any]]:
        conn = self.get_conn()
        try:
            rows = conn.execute("SELECT raw_json FROM campaigns ORDER BY created_at ASC").fetchall()
            return [self.loads(r["raw_json"]) for r in rows if r["raw_json"]]
        finally:
            conn.close()

    def save_campaigns(self, campaigns: List[Dict[str, Any]]) -> bool:
        with self.transaction() as conn:
            conn.execute("DELETE FROM campaigns")
            for c in campaigns:
                cid = c.get("id")
                if not cid:
                    continue
                name = c.get("name", "")
                brand = c.get("brand", "")
                target = c.get("target", "")
                status = c.get("status", "active")
                created_at = c.get("created_at") or datetime.now().isoformat()
                updated_at = c.get("updated_at") or datetime.now().isoformat()
                raw_json = self.dumps(c)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO campaigns
                    (id, name, brand, target, status, created_at, updated_at, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (cid, name, brand, target, status, created_at, updated_at, raw_json),
                )
        return True

    # Publication Queue
    def list_queue(self) -> List[Dict[str, Any]]:
        conn = self.get_conn()
        try:
            rows = conn.execute("SELECT raw_json FROM publication_jobs ORDER BY created_at ASC").fetchall()
            return [self.loads(r["raw_json"]) for r in rows if r["raw_json"]]
        finally:
            conn.close()

    def save_queue(self, queue: List[Dict[str, Any]]) -> bool:
        with self.transaction() as conn:
            conn.execute("DELETE FROM publication_jobs")
            for item in queue:
                jid = item.get("id")
                if not jid:
                    continue
                cid = item.get("campaign_id")
                target = item.get("target", "")
                content = item.get("content", "")
                image_url = item.get("image_url")
                state = item.get("state", "draft")
                created_at = item.get("created_at") or datetime.now().isoformat()
                approved_at = item.get("approved_at")
                published_at = item.get("published_at")
                error = item.get("error")
                idempotency_key = item.get("idempotency_key")
                raw_json = self.dumps(item)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO publication_jobs
                    (id, campaign_id, target, content, image_url, state, created_at, approved_at, published_at, error, idempotency_key, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (jid, cid, target, content, image_url, state, created_at, approved_at, published_at, error, idempotency_key, raw_json),
                )
        return True

    def get_queue_item(self, item_id: str):
        conn = self.get_conn()
        try:
            row = conn.execute("SELECT raw_json FROM publication_jobs WHERE id = ?", (item_id,)).fetchone()
            return self.loads(row["raw_json"]) if row and row["raw_json"] else None
        finally:
            conn.close()

    def insert_queue_item(self, item: Dict[str, Any]) -> bool:
        jid = item.get("id")
        if not jid:
            return False
        with self.transaction() as conn:
            exists = conn.execute("SELECT 1 FROM publication_jobs WHERE id = ?", (jid,)).fetchone()
            if exists:
                return False
            conn.execute(
                """INSERT INTO publication_jobs
                (id, campaign_id, target, content, image_url, state, created_at, approved_at, published_at, error, idempotency_key, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (jid, item.get("campaign_id"), item.get("target", ""), item.get("content", ""), item.get("image_url"),
                 item.get("state", "draft"), item.get("created_at") or datetime.now().isoformat(), item.get("approved_at"),
                 item.get("published_at"), item.get("error"), item.get("idempotency_key"), self.dumps(item)),
            )
        return True

    def transition_queue_item(self, item_id: str, from_states, to_state: str, updates=None, audit_event: str = "state_transition"):
        updates = dict(updates or {})
        allowed_from = tuple(from_states or ())
        with self.transaction() as conn:
            row = conn.execute("SELECT raw_json, state FROM publication_jobs WHERE id = ?", (item_id,)).fetchone()
            if not row or (allowed_from and row["state"] not in allowed_from):
                return None
            item = self.loads(row["raw_json"], {}) or {}
            item.update(updates)
            item["state"] = to_state
            item["updated_at"] = datetime.now().isoformat()
            item.setdefault("audit", []).append({"at": item["updated_at"], "event": audit_event, "state": to_state})
            conn.execute(
                """UPDATE publication_jobs SET state=?, approved_at=?, published_at=?, error=?, raw_json=? WHERE id=?""",
                (to_state, item.get("approved_at"), item.get("published_at"), item.get("error"), self.dumps(item), item_id),
            )
            return item

    def approve_campaign_drafts_atomic(self, campaign_id: str) -> int:
        now = datetime.now().isoformat()
        approved = 0
        with self.transaction() as conn:
            rows = conn.execute(
                "SELECT id, raw_json FROM publication_jobs WHERE campaign_id = ? AND state = 'draft'",
                (campaign_id,),
            ).fetchall()
            for row in rows:
                item = self.loads(row["raw_json"], {}) or {}
                item["state"] = "approved"
                item["approved_at"] = now
                item["updated_at"] = now
                item.setdefault("audit", []).append({"at": now, "event": "approved_batch", "state": "approved"})
                conn.execute(
                    "UPDATE publication_jobs SET state='approved', approved_at=?, error=NULL, raw_json=? WHERE id=? AND state='draft'",
                    (now, self.dumps(item), row["id"]),
                )
                approved += 1
        return approved

    def reconcile_processing_queue(self) -> int:
        now = datetime.now().isoformat()
        recovered = 0
        with self.transaction() as conn:
            rows = conn.execute("SELECT id, raw_json FROM publication_jobs WHERE state='processing'").fetchall()
            for row in rows:
                item = self.loads(row["raw_json"], {}) or {}
                item["state"] = "unverified"
                item["updated_at"] = now
                item["error"] = "Tiến trình bị gián đoạn khi đang đăng; không tự động retry để tránh bài trùng. Hãy đối soát permalink."
                item.setdefault("audit", []).append({"at": now, "event": "processing_recovered", "state": "unverified"})
                conn.execute(
                    "UPDATE publication_jobs SET state='unverified', error=?, raw_json=? WHERE id=? AND state='processing'",
                    (item["error"], self.dumps(item), row["id"]),
                )
                recovered += 1
        return recovered

    # Manual Group Queue
    def list_manual_group_queue(self) -> List[Dict[str, Any]]:
        conn = self.get_conn()
        try:
            rows = conn.execute("SELECT raw_json FROM manual_group_queue ORDER BY created_at ASC").fetchall()
            return [self.loads(r["raw_json"]) for r in rows if r["raw_json"]]
        finally:
            conn.close()

    def save_manual_group_queue(self, queue: List[Dict[str, Any]]) -> bool:
        with self.transaction() as conn:
            conn.execute("DELETE FROM manual_group_queue")
            for item in queue:
                mid = item.get("id")
                if not mid:
                    continue
                pid = item.get("profile_id", "")
                gurl = item.get("group_url", "")
                content = item.get("content", "")
                state = item.get("state", "pending")
                created_at = item.get("created_at") or datetime.now().isoformat()
                completed_at = item.get("completed_at")
                raw_json = self.dumps(item)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO manual_group_queue
                    (id, profile_id, group_url, content, state, created_at, completed_at, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (mid, pid, gurl, content, state, created_at, completed_at, raw_json),
                )
        return True
