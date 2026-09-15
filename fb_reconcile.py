import time
import re

from playwright.sync_api import sync_playwright

from adapters.facebook_publication import scan_post_permalink, copy_post_permalink, has_pending_notice
# Compatibility patch points retained for stable tests/callers; implementation lives in adapter.
_scan_post_permalink_once = scan_post_permalink
_copy_post_permalink_via_share_sheet = copy_post_permalink
_has_pending_post_notice = has_pending_notice

from utils import (
    ActionResult,
    close_browser,
    launch_browser,
    record_posted_link,
    resolve_account,
)


def _normalize_target(value):
    value=(value or "").strip().split("?",1)[0].rstrip("/")
    return re.sub(r"^https?://(?:www\.)?facebook\.com", "facebook://", value, flags=re.I).casefold()

def _normalize_content(value):
    return " ".join((value or "").split())


def reconcile_existing_post(target_url, content, account_id=None, gpm_api_url=None):
    """Read-only reconciliation: never opens composer and never submits a post."""
    if not target_url or not content:
        return ActionResult(False, "RECONCILE_INVALID_INPUT", "Thiếu target/content để đối soát.", target_url=target_url)

    # Durable history is authoritative when the exact target/account/content tuple
    # already has a published post permalink. Reconciliation must not depend on feed
    # ranking after we already persisted terminal evidence, and it must never repost.
    try:
        from repositories.activity_repo import ActivityRepository
        expected_account = account_id or "default"
        expected_target = _normalize_target(target_url)
        for row in ActivityRepository().list_posted_links(limit=500):
            if (row.get("publish_state") == "published" and row.get("url_type") == "post"
                    and (row.get("account_id") or "default") == expected_account
                    and _normalize_target(row.get("target")) == expected_target
                    and _normalize_content(row.get("content")) == _normalize_content(content)
                    and row.get("url")):
                return ActionResult(True, "RECONCILE_PUBLISHED", "?? x?c nh?n t? durable publication history.",
                                    state="published", target_url=target_url, result_url=row["url"],
                                    url_type="post", metadata={"evidence_source": "sqlite_posted_links"})
    except Exception as history_err:
        print(f"?? Durable reconcile lookup failed; ti?p t?c live resolver: {history_err}")

    account = resolve_account(account_id, gpm_api_url) if account_id else None
    browser_obj = None
    context = None
    try:
        with sync_playwright() as p:
            if account:
                browser_obj, context, page = launch_browser(account, p, gpm_api_url)
            else:
                browser_obj = p.chromium.launch(headless=False)
                context = browser_obj.new_context()
                page = context.new_page()
            page.set_default_timeout(20000)
            page.goto(target_url, wait_until="domcontentloaded")
            time.sleep(2.5)

            # Facebook may rank the just-submitted post below pinned content and may
            # expose only a share URL at first. Scan a larger window and try the
            # native Share -> Copy link path on both later passes.
            for attempt in range(3):
                permalink = _scan_post_permalink_once(page, target=target_url, content=content, max_articles=30)
                if not permalink and attempt >= 1:
                    permalink = _copy_post_permalink_via_share_sheet(page, target=target_url, content=content)
                if permalink:
                    record_posted_link(
                        target_url, permalink, content, note="Đã xuất bản (đối soát)",
                        account_id=account_id or "default", url_type="post", publish_state="published"
                    )
                    return ActionResult(True, "RECONCILE_PUBLISHED", "Đã tìm thấy permalink của bài đã gửi.",
                                        state="published", target_url=target_url, result_url=permalink, url_type="post")
                if _has_pending_post_notice(page):
                    record_posted_link(
                        target_url, target_url, content, note="Đang chờ admin duyệt (đối soát)",
                        account_id=account_id or "default", url_type="group" if "/groups/" in target_url else "page",
                        publish_state="pending"
                    )
                    return ActionResult(True, "RECONCILE_PENDING", "Bài đang chờ duyệt.", state="pending", target_url=target_url)
                if attempt < 2:
                    try:
                        page.reload(wait_until="domcontentloaded", timeout=20000)
                    except Exception as reload_err:
                        current = (page.url or "").lower()
                        try:
                            body_chars = len(page.locator("body").inner_text(timeout=3000).strip())
                        except Exception:
                            body_chars = 0
                        if "facebook.com" not in current or body_chars < 20:
                            raise
                        print(f"⚠️ Reload timeout nhưng Facebook DOM vẫn còn ({body_chars} chars); tiếp tục native permalink resolver: {reload_err}")
                    time.sleep(2.5 + attempt * 2)

            return ActionResult(False, "RECONCILE_NOT_FOUND", "Chưa tìm thấy bài hoặc permalink; giữ trạng thái chưa xác minh.",
                                state="unverified", target_url=target_url)
    except Exception as exc:
        return ActionResult(False, "RECONCILE_ERROR", str(exc), state="unverified", target_url=target_url)
    finally:
        if account:
            close_browser(browser_obj if browser_obj else context, account, gpm_api_url)
        elif browser_obj:
            try:
                browser_obj.close()
            except Exception:
                pass
