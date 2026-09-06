"""Repository for Account Vault entries."""

from datetime import datetime
from typing import Any, Dict, List
from repositories.base import BaseRepository


class VaultRepository(BaseRepository):
    def list_entries(self) -> List[Dict[str, Any]]:
        conn = self.get_conn()
        try:
            rows = conn.execute("SELECT raw_json FROM vault_entries ORDER BY date_added ASC").fetchall()
            return [self.loads(r["raw_json"]) for r in rows if r["raw_json"]]
        finally:
            conn.close()

    def save_entries(self, entries: List[Dict[str, Any]]) -> bool:
        now_str = datetime.now().isoformat()
        with self.transaction() as conn:
            conn.execute("DELETE FROM vault_entries")
            for e in entries:
                vid = e.get("id")
                if not vid:
                    continue
                platform = e.get("platform", "facebook")
                account_name = e.get("account_name", "")
                email = e.get("email", "")
                password = e.get("password", "")
                notes = e.get("notes", "")
                date_added = e.get("date_added", now_str)
                password_changed_at = e.get("password_changed_at")
                raw_json = self.dumps(e)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO vault_entries
                    (id, platform, account_name, email, password, notes, date_added, password_changed_at, created_at, updated_at, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (vid, platform, account_name, email, password, notes, date_added, password_changed_at, now_str, now_str, raw_json),
                )
        return True
