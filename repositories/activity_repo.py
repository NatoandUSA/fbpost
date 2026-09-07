"""Repository for Profile Activity Log and Posted Links."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from repositories.base import BaseRepository


class ActivityRepository(BaseRepository):
    # Profile Activity
    def list_activities(self, limit: int = 500) -> List[Dict[str, Any]]:
        conn = self.get_conn()
        try:
            rows = conn.execute(
                """
                SELECT timestamp, profile_id, action, target, content, outcome
                FROM activity_log
                ORDER BY id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def record_activity(
        self,
        profile_id: str,
        action: str,
        target: str = "",
        content: str = "",
        outcome: str = "finished",
    ) -> None:
        now_str = datetime.now().isoformat()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO activity_log (timestamp, profile_id, action, target, content, outcome)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (now_str, profile_id, action, target, content, outcome),
            )

    def save_activities(self, activities: List[Dict[str, Any]]) -> bool:
        with self.transaction() as conn:
            conn.execute("DELETE FROM activity_log")
            for a in activities:
                conn.execute(
                    """
                    INSERT INTO activity_log (timestamp, profile_id, action, target, content, outcome)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        a.get("timestamp", datetime.now().isoformat()),
                        a.get("profile_id", ""),
                        a.get("action", ""),
                        a.get("target", ""),
                        a.get("content", ""),
                        a.get("outcome", "finished"),
                    ),
                )
        return True

    def clear_activities(self) -> bool:
        with self.transaction() as conn:
            conn.execute("DELETE FROM activity_log")
        return True

    # Posted Links
    def list_posted_links(self, limit: int = 200) -> List[Dict[str, Any]]:
        conn = self.get_conn()
        try:
            rows = conn.execute(
                """
                SELECT id, url, target, content, note, account_id, status, created_at, url_type, publish_state
                FROM posted_links
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def record_posted_link(
        self,
        target: str,
        post_url: str,
        content: str = "",
        note: str = "",
        account_id: str = "",
        status: str = "",
        url_type: str = "unknown",
        publish_state: str = "unknown",
    ) -> None:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.transaction() as conn:
            existing = conn.execute(
                "SELECT id FROM posted_links WHERE target = ? AND url = ? ORDER BY id DESC LIMIT 1",
                (target, post_url),
            ).fetchone()
            if not existing and publish_state == "published" and url_type == "post":
                existing = conn.execute(
                    """
                    SELECT id FROM posted_links
                    WHERE target = ? AND account_id = ? AND content = ?
                      AND publish_state IN ('submitted_unverified','pending')
                    ORDER BY id DESC LIMIT 1
                    """,
                    (target, account_id, content),
                ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE posted_links SET url = ?, content = ?, note = ?, status = ?, url_type = ?, publish_state = ?, created_at = ? WHERE id = ?",
                    (post_url, content, note, status, url_type, publish_state, now_str, existing["id"]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO posted_links (url, target, content, note, account_id, status, url_type, publish_state, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (post_url, target, content, note, account_id, status, url_type, publish_state, now_str),
                )

    def save_posted_links(self, links: List[Dict[str, Any]]) -> bool:
        with self.transaction() as conn:
            conn.execute("DELETE FROM posted_links")
            for l in links:
                conn.execute(
                    """
                    INSERT INTO posted_links (url, target, content, note, account_id, status, url_type, publish_state, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        l.get("url", ""),
                        l.get("target", ""),
                        l.get("content", ""),
                        l.get("note", ""),
                        l.get("account_id", ""),
                        l.get("status", ""),
                        l.get("url_type", "unknown"),
                        l.get("publish_state", "unknown"),
                        l.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    ),
                )
        return True

    def clear_posted_links(self) -> bool:
        with self.transaction() as conn:
            conn.execute("DELETE FROM posted_links")
        return True
