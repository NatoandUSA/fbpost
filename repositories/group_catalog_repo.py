"""Read/write access to the canonical Group catalog metadata."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from repositories.base import BaseRepository
from services.group_candidate import canonicalize_group_url, group_token_from_url


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GroupCatalogRepository(BaseRepository):
    def get_group(self, row_id: str):
        conn = self.get_conn()
        try:
            row = conn.execute("SELECT * FROM group_catalog WHERE id=?", (row_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    def list_groups(self, enabled_only: bool = False, limit: int = 500):
        conn = self.get_conn()
        try:
            where = " WHERE enabled=1" if enabled_only else ""
            rows = conn.execute(
                f"SELECT * FROM group_catalog{where} ORDER BY member_count DESC, name ASC LIMIT ?",
                (int(limit),),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def count_groups(self) -> int:
        conn = self.get_conn()
        try:
            return int(conn.execute("SELECT COUNT(*) FROM group_catalog").fetchone()[0])
        finally:
            conn.close()

    def upsert_group(self, url: str, name: str = "", privacy: str = "", member_count: int = 0,
                     source: str = "manual", enabled: bool = True):
        canonical = canonicalize_group_url(url)
        if not canonical:
            return None
        token = group_token_from_url(canonical)
        row_id = f"fbgroup:{token.lower()}"
        now = _now()
        with self.transaction() as conn:
            existing = conn.execute(
                "SELECT * FROM group_catalog WHERE canonical_url=?", (canonical,)
            ).fetchone()
            if existing:
                best_members = max(int(existing["member_count"] or 0), int(member_count or 0))
                best_name = name or existing["name"] or token
                best_privacy = privacy or existing["privacy"] or ""
                conn.execute(
                    "UPDATE group_catalog SET name=?, privacy=?, member_count=?, enabled=?, updated_at=? WHERE canonical_url=?",
                    (best_name, best_privacy, best_members, 1 if enabled else 0, now, canonical),
                )
                return existing["id"]
            conn.execute(
                "INSERT INTO group_catalog(id,canonical_url,facebook_group_id,name,privacy,member_count,source,enabled,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (row_id, canonical, token, name or token, privacy, int(member_count or 0), source, 1 if enabled else 0, now, now),
            )
            return row_id
