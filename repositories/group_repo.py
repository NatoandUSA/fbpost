"""Repository for Facebook Group Registry and Joined Groups."""

from datetime import datetime
from typing import Any, Dict, List
from repositories.base import BaseRepository


class GroupRepository(BaseRepository):
    # Group Registry
    def list_groups(self) -> List[Dict[str, Any]]:
        conn = self.get_conn()
        try:
            rows = conn.execute("SELECT raw_json FROM groups ORDER BY created_at ASC").fetchall()
            return [self.loads(r["raw_json"]) for r in rows if r["raw_json"]]
        finally:
            conn.close()

    def save_groups(self, groups: List[Dict[str, Any]]) -> bool:
        with self.transaction() as conn:
            conn.execute("DELETE FROM groups")
            for g in groups:
                gid = str(g.get("id") or g.get("url") or "")
                if not gid:
                    continue
                name = g.get("name", "")
                url = g.get("url", "")
                category = g.get("category", "")
                notes = g.get("notes", "")
                created_at = g.get("created_at") or datetime.now().isoformat()
                updated_at = g.get("updated_at") or datetime.now().isoformat()
                raw_json = self.dumps(g)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO groups
                    (id, name, url, category, notes, created_at, updated_at, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (gid, name, url, category, notes, created_at, updated_at, raw_json),
                )
        return True

    # Joined Groups
    def list_joined_groups(self) -> List[Dict[str, Any]]:
        conn = self.get_conn()
        try:
            rows = conn.execute("SELECT id, group_name, keyword, url, account_id, joined_at, state FROM joined_groups ORDER BY joined_at DESC").fetchall()
            result = []
            for r in rows:
                item = dict(r)
                item["name"] = item.get("group_name", "")
                result.append(item)
            return result
        finally:
            conn.close()

    def replace_joined_groups_for_migration(self, groups: List[Dict[str, Any]]) -> bool:
        with self.transaction() as conn:
            conn.execute("DELETE FROM joined_groups")
            for idx, g in enumerate(groups):
                gid = str(g.get("id") or f"{g.get('account_id')}_{g.get('joined_at')}_{idx}")
                gname = g.get("group_name") or g.get("name", "")
                state = g.get("state", "joined")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO joined_groups
                    (id, group_name, keyword, url, account_id, joined_at, state)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        gid,
                        gname,
                        g.get("keyword", ""),
                        g.get("url", ""),
                        g.get("account_id", ""),
                        g.get("joined_at", ""),
                        state,
                    ),
                )
        return True

    def save_joined_groups(self, groups: List[Dict[str, Any]]) -> bool:
        """Deprecated alias for replace_joined_groups_for_migration."""
        return self.replace_joined_groups_for_migration(groups)

    def add_joined_group(self, g: Dict[str, Any]) -> bool:
        gname = g.get("group_name") or g.get("name", "")
        gid = str(g.get("id") or g.get("url") or f"{g.get('account_id')}_{g.get('joined_at')}_{gname}")
        state = g.get("state", "joined")
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO joined_groups
                (id, group_name, keyword, url, account_id, joined_at, state)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    gid,
                    gname,
                    g.get("keyword", ""),
                    g.get("url", ""),
                    g.get("account_id", ""),
                    g.get("joined_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    state,
                ),
            )
        return True

    def clear_joined_groups(self) -> bool:
        with self.transaction() as conn:
            conn.execute("DELETE FROM joined_groups")
        return True
