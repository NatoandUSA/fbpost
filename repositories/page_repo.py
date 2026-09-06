"""Repository for Created Facebook Pages."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from repositories.base import BaseRepository


class PageRepository(BaseRepository):
    def list_created_pages(self, account_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        conn = self.get_conn()
        try:
            if account_id:
                rows = conn.execute(
                    """
                    SELECT id, page_name, category, page_url, account_id, state, created_at
                    FROM created_pages
                    WHERE account_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (account_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, page_name, category, page_url, account_id, state, created_at
                    FROM created_pages
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def add_created_page(
        self,
        page_name: str,
        category: str = "Blogger",
        page_url: str = "",
        account_id: str = "default",
        state: str = "created",
    ) -> str:
        page_id = f"{account_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO created_pages
                (id, page_name, category, page_url, account_id, state, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (page_id, page_name, category, page_url, account_id, state, now_str),
            )
        return page_id

    def count_recent_pages(self, account_id: Optional[str] = None, hours: int = 24) -> int:
        cutoff = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        conn = self.get_conn()
        try:
            if account_id:
                row = conn.execute(
                    "SELECT COUNT(*) as c FROM created_pages WHERE account_id = ? AND created_at > ?",
                    (account_id, cutoff),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) as c FROM created_pages WHERE created_at > ?",
                    (cutoff,),
                ).fetchone()
            return row["c"] if row else 0
        finally:
            conn.close()
