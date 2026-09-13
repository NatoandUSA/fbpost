import re
import uuid
from datetime import datetime, timezone
from repositories.base import BaseRepository

def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def canonical_group_url(value):
    text = str(value or "").strip()
    match = re.search(r"(?:facebook\.com/)?groups/([^/?#]+)", text, re.I)
    return f"https://www.facebook.com/groups/{match.group(1)}" if match else text.rstrip("/")

class ModerationRepository(BaseRepository):
    def mark_requires_approval(self, group_url, evidence, profile_id=None):
        target = canonical_group_url(group_url)
        now = _now()
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO group_moderation_registry
                (group_url, requires_approval, evidence, confirmed_count, last_confirmed_at, last_profile_id)
                VALUES (?,1,?,1,?,?)
                ON CONFLICT(group_url) DO UPDATE SET
                    requires_approval=1, evidence=excluded.evidence,
                    confirmed_count=confirmed_count+1,
                    last_confirmed_at=excluded.last_confirmed_at,
                    last_profile_id=excluded.last_profile_id
            """, (target, evidence, now, profile_id))
        return target

    def requires_approval(self, group_url):
        conn = self.get_conn()
        try:
            row = conn.execute(
                "SELECT requires_approval FROM group_moderation_registry WHERE group_url=?",
                (canonical_group_url(group_url),)
            ).fetchone()
            return bool(row and row["requires_approval"])
        finally:
            conn.close()

    def defer_first_comment(self, group_url, content, account_id, brand_key, comment_text):
        now = _now()
        rid = uuid.uuid4().hex
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO deferred_first_comments
                (id,group_url,content,account_id,brand_key,comment_text,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,'pending',?,?)
                ON CONFLICT(group_url,content,account_id) DO UPDATE SET
                    brand_key=excluded.brand_key, comment_text=excluded.comment_text,
                    status='pending', updated_at=excluded.updated_at
            """, (rid, canonical_group_url(group_url), content, account_id, brand_key, comment_text, now, now))
        return rid

    def get_deferred(self, group_url, content, account_id=None):
        conn = self.get_conn()
        try:
            row = conn.execute("""
                SELECT * FROM deferred_first_comments
                WHERE group_url=? AND content=? AND COALESCE(account_id,'')=COALESCE(?,'')
                  AND status='pending' LIMIT 1
            """, (canonical_group_url(group_url), content, account_id)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def resolve_deferred(self, rid, post_url, success):
        with self.transaction() as conn:
            conn.execute(
                "UPDATE deferred_first_comments SET status=?,post_url=?,updated_at=? WHERE id=?",
                ("commented" if success else "manual_review", post_url or None, _now(), rid)
            )