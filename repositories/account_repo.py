"""Repository for Facebook accounts and GPM profiles."""

from typing import Any, Dict, List, Optional
from repositories.base import BaseRepository


class AccountRepository(BaseRepository):
    def list_accounts(self) -> List[Dict[str, Any]]:
        conn = self.get_conn()
        try:
            rows = conn.execute("SELECT raw_json FROM accounts ORDER BY created_at ASC").fetchall()
            accounts = []
            for r in rows:
                acc = self.loads(r["raw_json"])
                if acc:
                    accounts.append(acc)
            return accounts
        finally:
            conn.close()

    def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_conn()
        try:
            row = conn.execute("SELECT raw_json FROM accounts WHERE id = ?", (account_id,)).fetchone()
            if row:
                return self.loads(row["raw_json"])
            return None
        finally:
            conn.close()

    def save_accounts(self, accounts: List[Dict[str, Any]]) -> bool:
        with self.transaction() as conn:
            conn.execute("DELETE FROM accounts")
            for acc in accounts:
                acc_id = acc.get("id")
                if not acc_id:
                    continue
                name = acc.get("name", "")
                acc_type = acc.get("type", "gpm")
                profile_path_or_id = acc.get("profile_path_or_id", acc_id)
                proxy = acc.get("proxy", "")
                status = acc.get("status", "")
                created_at = acc.get("created_at", "")
                raw_json = self.dumps(acc)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO accounts
                    (id, name, type, profile_path_or_id, proxy, status, created_at, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (acc_id, name, acc_type, profile_path_or_id, proxy, status, created_at, raw_json),
                )
        return True

    def save_account(self, acc: Dict[str, Any]) -> bool:
        acc_id = acc.get("id")
        if not acc_id:
            return False
        with self.transaction() as conn:
            name = acc.get("name", "")
            acc_type = acc.get("type", "gpm")
            profile_path_or_id = acc.get("profile_path_or_id", acc_id)
            proxy = acc.get("proxy", "")
            status = acc.get("status", "")
            created_at = acc.get("created_at", "")
            raw_json = self.dumps(acc)
            conn.execute(
                """
                INSERT OR REPLACE INTO accounts
                (id, name, type, profile_path_or_id, proxy, status, created_at, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (acc_id, name, acc_type, profile_path_or_id, proxy, status, created_at, raw_json),
            )
        return True

    def delete_account(self, account_id: str) -> bool:
        with self.transaction() as conn:
            conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        return True
