import re
import uuid
from datetime import datetime, timezone, timedelta
from repositories.base import BaseRepository

def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def canonical_group_url(value):
    text = str(value or "").strip()
    match = re.search(r"(?:facebook\.com/)?groups/([^/?#]+)", text, re.I)
    return f"https://www.facebook.com/groups/{match.group(1)}" if match else text.rstrip("/")

class ModerationRepository(BaseRepository):
    def comment_cooldown(self, group_url):
        conn = self.get_conn()
        try:
            row = conn.execute("SELECT * FROM group_comment_policy WHERE group_url=?", (canonical_group_url(group_url),)).fetchone()
            if not row or not row["cooldown_until"]:
                return None
            return dict(row) if row["cooldown_until"] > _now() else None
        finally:
            conn.close()

    def record_comment_delivery(self, group_url, post_url, profile_id, brand_key, status, comment_text="", evidence=""):
        now = _now()
        event_id = uuid.uuid4().hex
        url_count = len(re.findall(r"https?://[^\s]+", comment_text or "", re.I))
        target = canonical_group_url(group_url)
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO comment_delivery_events
                (id,group_url,post_url,profile_id,brand_key,status,url_count,evidence,created_at)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (event_id, target, post_url or "", profile_id, brand_key or "", status, url_count, evidence or "", now))
            if status == "rejected":
                cooldown = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(timespec="seconds")
                conn.execute("""
                    INSERT INTO group_comment_policy
                    (group_url,rejected_count,cooldown_until,last_status,last_profile_id,updated_at)
                    VALUES (?,1,?,'rejected',?,?)
                    ON CONFLICT(group_url) DO UPDATE SET
                        rejected_count=rejected_count+1,
                        cooldown_until=excluded.cooldown_until,
                        last_status='rejected', last_profile_id=excluded.last_profile_id,
                        updated_at=excluded.updated_at
                """, (target, cooldown, profile_id, now))
        return event_id
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

    def record_pending_count(self, group_url, pending_count, profile_id=None, evidence="group_pending_counter"):
        target = canonical_group_url(group_url)
        now = _now()
        count = max(0, int(pending_count or 0))
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO group_moderation_registry
                (group_url,requires_approval,evidence,confirmed_count,last_confirmed_at,last_profile_id,pending_count,last_pending_checked_at,skip_threshold)
                VALUES (?,1,?,1,?,?,?, ?,2)
                ON CONFLICT(group_url) DO UPDATE SET
                    requires_approval=1,evidence=excluded.evidence,last_profile_id=excluded.last_profile_id,
                    pending_count=excluded.pending_count,last_pending_checked_at=excluded.last_pending_checked_at
            """, (target,evidence,now,profile_id,count,now))
        return count

    def moderation_info(self, group_url):
        conn = self.get_conn()
        try:
            row = conn.execute("SELECT * FROM group_moderation_registry WHERE group_url=?", (canonical_group_url(group_url),)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

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
