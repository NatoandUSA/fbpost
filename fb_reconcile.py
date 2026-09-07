import time
from playwright.sync_api import sync_playwright

from utils import (
    ActionResult,
    _has_pending_post_notice,
    _scan_post_permalink_once,
    close_browser,
    launch_browser,
    record_posted_link,
    resolve_account,
)


def reconcile_existing_post(target_url, content, account_id=None, gpm_api_url=None):
    """Read-only reconciliation: never opens composer and never submits a post."""
    if not target_url or not content:
        return ActionResult(False, "RECONCILE_INVALID_INPUT", "Thiếu target/content để đối soát.", target_url=target_url)

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

            for attempt in range(2):
                permalink = _scan_post_permalink_once(page, target=target_url, content=content, max_articles=15)
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
                if attempt == 0:
                    page.reload(wait_until="domcontentloaded", timeout=15000)
                    time.sleep(2.5)

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
