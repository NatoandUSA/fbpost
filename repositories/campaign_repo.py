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
