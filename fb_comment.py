import sys
import os
import time
import random
import re
from playwright.sync_api import sync_playwright
from utils import process_spintax, human_type, load_accounts, resolve_account, launch_browser, close_browser, safe_mouse_wheel, ActionResult
from paths import DATA_DIR

STATE_FILE = str(DATA_DIR / "state.json")

def _canonicalize_comment_url(url):
    """Return a canonical Facebook post URL, or empty when the input is not a post identity."""
    value = (url or "").strip()
    m = re.search(r"facebook\.com/groups/([^/?#]+)/\?multi_permalinks=(\d+)", value, re.IGNORECASE)
    if m:
        return f"https://www.facebook.com/groups/{m.group(1)}/posts/{m.group(2)}"
    m = re.search(r"facebook\.com/groups/([^/?#]+)/(?:posts|permalink)/(\d+)", value, re.IGNORECASE)
    if m:
        return f"https://www.facebook.com/groups/{m.group(1)}/posts/{m.group(2)}"
    if re.search(r"facebook\.com/.+/(?:posts|videos)/\d+", value, re.IGNORECASE):
        return value.split("?", 1)[0]
    if re.search(r"facebook\.com/(?:story\.php|permalink\.php)\?.*(?:story_fbid|fbid)=\d+", value, re.IGNORECASE):
        return value
    return ""

def _post_identity(url):
    value = (url or "").strip()
    m = re.search(r"facebook\.com/groups/([^/?#]+)/(?:posts|permalink)/(\d+)", value, re.IGNORECASE)
    if m:
        return {"group_id": m.group(1), "post_id": m.group(2)}
    m = re.search(r"facebook\.com/.+/(?:posts|videos)/(\d+)", value, re.IGNORECASE)
    if m:
        return {"group_id": "", "post_id": m.group(1)}
    m = re.search(r"[?&](?:story_fbid|fbid)=(\d+)", value, re.IGNORECASE)
    return {"group_id": "", "post_id": m.group(1)} if m else {"group_id": "", "post_id": ""}

def _locate_target_post_article(page, canonical_url):
    """Resolve the exact target-post DOM scope and fail closed on ambiguity."""
    ident = _post_identity(canonical_url)
    post_id = (ident.get("post_id") or "").strip()
    if not post_id:
        return None

    selectors = [
        f"a[href*='/posts/{post_id}']",
        f"a[href*='/permalink/{post_id}']",
        f"a[href*='story_fbid={post_id}']",
        f"a[href*='fbid={post_id}']",
    ]
    for selector in selectors:
        locator = page.locator(selector)
        for idx in range(min(locator.count(), 12)):
            try:
                article = locator.nth(idx).locator("xpath=ancestor::div[@role='article'][1]")
                if article.count() and article.is_visible(timeout=800):
                    print(f"[Comment Resolver] post_identity={post_id} scope=identity-article")
                    return article
            except Exception:
                continue

    deadline = time.monotonic() + 12.0
    while time.monotonic() < deadline:
        try:
            current_url = page.url or ""
            if post_id not in current_url:
                break
            dialogs = page.locator("div[role='dialog']")
            visible_dialogs = []
            for idx in range(min(dialogs.count(), 8)):
                try:
                    dialog = dialogs.nth(idx)
                    if dialog.is_visible(timeout=300):
                        visible_dialogs.append(dialog)
                except Exception:
                    continue
            if len(visible_dialogs) == 1:
                print(f"[Comment Resolver] post_identity={post_id} scope=exact-permalink-dialog")
                return visible_dialogs[0]
            if len(visible_dialogs) > 1:
                print(f"[Comment Resolver] post_identity={post_id} scope=ambiguous-dialogs count={len(visible_dialogs)}")
                return None
        except Exception:
            pass
        time.sleep(0.35)

    print(f"[Comment Resolver] post_identity={post_id} scope=not-found")
    return None



def _comment_search_roots(page, post_scope, canonical_url):
    """Return exact-post-safe roots that may own Facebook's portalled comment editor."""
    roots = [post_scope]
    ident = _post_identity(canonical_url)
    post_id = (ident.get("post_id") or "").strip()
    if not post_id or post_id not in (page.url or ""):
        return roots
    try:
        dialogs = page.locator("div[role='dialog']")
        exact_dialogs = []
        for idx in range(min(dialogs.count(), 8)):
            dialog = dialogs.nth(idx)
            try:
                if not dialog.is_visible(timeout=250):
                    continue
                scope_handle = post_scope.element_handle()
                owns_scope = bool(scope_handle) and dialog.evaluate(
                    "(dialog, scope) => dialog.contains(scope)", scope_handle
                )
                owns_permalink = dialog.locator(f"a[href*='{post_id}']").count() > 0
                if owns_scope or owns_permalink:
                    exact_dialogs.append(dialog)
            except Exception:
                pass
        # Only an unambiguous dialog tied to this exact post may own a portalled editor.
        if len(exact_dialogs) == 1:
            roots.append(exact_dialogs[0])
    except Exception:
        pass
    return roots


def _find_comment_input(page, post_scope, canonical_url, wait_rounds=8):
    """Find a visible writable editor without escaping exact-post-safe roots."""
    selectors = [
        "div[role='textbox'][contenteditable='true'][data-lexical-editor='true']",
        "div[role='textbox'][contenteditable='true']",
        "[contenteditable='true'][data-lexical-editor='true']",
        "[contenteditable='true'][aria-label*='comment' i]",
        "[contenteditable='true'][aria-placeholder*='comment' i]",
        "[contenteditable='true'][aria-label*='bình luận' i]",
        "[contenteditable='true'][aria-placeholder*='bình luận' i]",
    ]
    for wait_round in range(1, max(1, int(wait_rounds)) + 1):
        roots = _comment_search_roots(page, post_scope, canonical_url)
        for root_idx, root in enumerate(roots):
            for selector in selectors:
                candidates = root.locator(selector)
                for idx in range(min(candidates.count(), 16)):
                    el = candidates.nth(idx)
                    try:
                        if not el.is_visible(timeout=250):
                            continue
                        editable = (el.get_attribute("contenteditable") or "").lower()
                        if editable != "true":
                            continue
                        print(f"[Comment Resolver] textbox=found root={root_idx} wait_round={wait_round}")
                        return el
                    except Exception:
                        pass
        if wait_round < wait_rounds:
            page.wait_for_timeout(800)
    return None


def _open_comment_surface(page, post_scope, canonical_url):
    """Activate comment UI inside the exact post and wait for a portalled/lazy editor."""
    open_comment_buttons = [
        "div[role='button'][aria-label='Write a comment']",
        "div[role='button'][aria-label*='comment' i]",
        "div[role='button'][aria-label*='bình luận' i]",
        "div[role='button']:has-text('Write a comment')",
        "div[role='button']:has-text('Comment')",
        "div[role='button']:has-text('Bình luận')",
    ]
    for selector in open_comment_buttons:
        candidates = post_scope.locator(selector)
        for idx in range(min(candidates.count(), 12)):
            btn = candidates.nth(idx)
            try:
                if not btn.is_visible(timeout=250):
                    continue
                try:
                    btn.scroll_into_view_if_needed(timeout=1200)
                except Exception:
                    pass
                try:
                    btn.click(timeout=1800)
                except Exception:
                    # Transparent overlays are common; DOM click stays within exact scope.
                    btn.evaluate("e => e.click()")
                page.wait_for_timeout(900)
                found = _find_comment_input(page, post_scope, canonical_url, wait_rounds=6)
                if found is not None:
                    return found
            except Exception:
                pass
    return _find_comment_input(page, post_scope, canonical_url, wait_rounds=4)

def _save_comment_evidence(page, code):
    try:
        from paths import LOG_DIR
        from datetime import datetime
        evidence_dir = LOG_DIR / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        safe_code = re.sub(r"[^A-Za-z0-9_-]+", "_", code or "comment")[:40]
        out = evidence_dir / f"comment_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{safe_code}.png"
        page.screenshot(path=str(out), full_page=False)
        return str(out)
    except Exception:
        return ""

def comment_on_post(post_url, comment_content, account_id=None, gpm_api_url=None, like_post=False, anti_hash_text=False):
    """
    Tự động mở một bài viết Facebook (trong Group public hoặc Fanpage public) và để lại bình luận.
    Hỗ trợ Spintax, human typing, like trước khi comment, và xử lý các loại giao diện Facebook.
    """
    canonical_url = _canonicalize_comment_url(post_url)
    if not canonical_url:
        print(f"❌ Link không phải permalink bài viết Facebook hợp lệ: {post_url}")
        return ActionResult(success=False, code="INVALID_POST_URL", message="Chỉ nhận permalink của một bài viết Facebook cụ thể.", target_url=post_url)
    print(f"🔗 Đang mở bài viết để bình luận: {canonical_url}")
    parsed_comment = process_spintax(comment_content, anti_hash=anti_hash_text)
    
    account = None
    if account_id:
        account = resolve_account(account_id, gpm_api_url)
        if not account:
            print(f"❌ Lỗi: Không thể khởi tạo cấu hình cho Account ID '{account_id}'.")
            return ActionResult(success=False, code="ACCOUNT_NOT_FOUND", message=f"Không thể khởi tạo cấu hình cho Account ID '{account_id}'.", target_url=post_url)
        print(f"👤 Khởi chạy profile: {account.get('name', account_id)} ({account.get('type', 'local')})")

    browser_obj = None
    context = None
    try:
        with sync_playwright() as p:
            if account:
                browser_obj, context, page = launch_browser(account, p, gpm_api_url)
            else:
                print("Dùng session mặc định (state.json).")
                browser_obj = p.chromium.launch(headless=False)
                state_arg = STATE_FILE if os.path.exists(STATE_FILE) else None
                context = browser_obj.new_context(storage_state=state_arg)
                page = context.new_page()

            page.set_default_timeout(25000)
            
            # Di chuyển chuột ngẫu nhiên
            page.mouse.move(random.randint(100, 500), random.randint(100, 500))
            print(f"🔗 Permalink canonical: {canonical_url}")
            try:
                page.goto(canonical_url, wait_until="domcontentloaded", timeout=35000)
            except Exception as nav_err:
                # Facebook có thể giữ connection mở quá lâu; chỉ coi là fatal khi
                # trang thực sự không đi tới Facebook hoặc không có DOM hữu dụng.
                current = (page.url or "").lower()
                try:
                    body_chars = len(page.locator("body").inner_text(timeout=3000).strip())
                except Exception:
                    body_chars = 0
                if "facebook.com" not in current or body_chars < 20:
                    raise
                print(f"⚠️ Navigation timeout nhưng Facebook DOM đã tải ({body_chars} chars); tiếp tục tìm comment box: {nav_err}")
            time.sleep(random.uniform(3.0, 5.0))

            # Cuộn trang nhẹ nhàng mô phỏng hành vi đọc bài viết
            safe_mouse_wheel(page, 0, random.randint(250, 550))
            time.sleep(random.uniform(1.5, 3.0))
            safe_mouse_wheel(page, 0, -random.randint(100, 250))
            time.sleep(random.uniform(1.0, 2.0))

            post_scope = _locate_target_post_article(page, canonical_url)
            if post_scope is None:
                evidence = _save_comment_evidence(page, "POST_IDENTITY_NOT_FOUND")
                return ActionResult(False, "POST_IDENTITY_NOT_FOUND", "Đã mở permalink nhưng không khóa được DOM vào đúng post ID.", state="unverified", target_url=canonical_url, metadata={"evidence_path": evidence})

            # 1. Tương tác Thích / Thả Tim nếu được yêu cầu
            if like_post:
                try:
                    like_btn = post_scope.locator("div[role='button']").filter(
                        has_text=re.compile(r"^\s*(Thích|Like)(\s+\d+)?\s*$", re.IGNORECASE)
                    ).or_(post_scope.locator("div[role='button'][aria-label*='Thích' i], div[role='button'][aria-label*='Like' i]")).first
                    if like_btn.is_visible(timeout=3500):
                        aria_pressed = like_btn.get_attribute("aria-pressed")
                        if aria_pressed != "true":
                            reacted = False
                            # Tỷ lệ 70% thả Tim (Love), 30% Thích (Like)
                            if random.random() < 0.70:
                                try:
                                    print("❤️ Đang hover để thả Tim (Love) bài viết...")
                                    like_btn.hover()
                                    time.sleep(random.uniform(0.8, 1.4))
                                    # Tìm icon Yêu thích trong popover reactions
                                    love_btn = page.locator("div[aria-label*='Yêu thích' i], div[aria-label*='Love' i], div[role='toolbar'] div[role='button']").nth(1)
                                    if love_btn.is_visible(timeout=2000):
                                        love_btn.click(force=True)
                                        reacted = True
                                        print("❤️ Đã thả Tim (Love) bài viết thành công!")
                                        time.sleep(random.uniform(2.0, 3.5))
                                except Exception:
                                    pass
                            
                            if not reacted:
                                print("👍 Đang bấm Thích (Like) bài viết...")
                                like_btn.click(force=True)
                                print("👍 Đã thả Like bài viết thành công!")
                                time.sleep(random.uniform(1.5, 3.0))
                except Exception as e:
                    print(f"⚠️ Bỏ qua bước tương tác cảm xúc: {e}")

            # 2. Resolve the Facebook 2026 comment surface. The editor may be
            # lazy-mounted or portalled to the single permalink dialog, so search
            # only exact-post-safe roots and never fall back to arbitrary page DOM.
            print("[Comment Resolver] locating comment surface...")
            comment_input = _find_comment_input(page, post_scope, canonical_url, wait_rounds=8)
            if comment_input is None:
                comment_input = _open_comment_surface(page, post_scope, canonical_url)

            if comment_input is None:
                evidence = _save_comment_evidence(page, "COMMENT_INPUT_NOT_FOUND")
                print("[Comment Resolver] textbox=not-found after exact-scope lazy/portal search")
                return ActionResult(
                    success=False, code="COMMENT_INPUT_NOT_FOUND",
                    message="Không tìm thấy ô bình luận trong exact-post scope.",
                    target_url=post_url, metadata={"evidence_path": evidence}
                )

            # 3. Focus và gõ nội dung bình luận (dùng Shift+Enter cho newline để không submit sớm)
            print(f"💬 Đang gõ nội dung bình luận: \"{parsed_comment}\"")
            comment_input.scroll_into_view_if_needed()
            time.sleep(random.uniform(0.8, 1.5))
            # Facebook 2026 may place a transparent overlay above a visible Lexical
            # editor. DOM focus/force fallback in human_type is safer than a normal
            # pointer click, which can wait the full page timeout on interception.
            try:
                comment_input.focus(timeout=2000)
            except Exception:
                pass
            time.sleep(random.uniform(0.3, 0.7))

            human_type(page, comment_input, parsed_comment, multiline_key="Shift+Enter")
            time.sleep(random.uniform(1.0, 2.0))

            # 4. Ưu tiên nút Gửi/Send rõ ràng; Enter chỉ là fallback.
            submitted_by_button = False
            for send_sel in [
                "div[role='button'][aria-label='Gửi' i]", "button[aria-label='Gửi' i]",
                "div[role='button'][aria-label='Send' i]", "button[aria-label='Send' i]"
            ]:
                try:
                    send_btn = post_scope.locator(send_sel).last
                    if send_btn.is_visible(timeout=500) and send_btn.is_enabled():
                        send_btn.click(timeout=2500)
                        submitted_by_button = True
                        print("🚀 Đã bấm nút Gửi bình luận.")
                        break
                except Exception:
                    continue
            if not submitted_by_button:
                print("🚀 Không thấy nút Gửi rõ ràng; dùng Enter fallback.")
                page.keyboard.press("Enter")
            time.sleep(random.uniform(3.0, 5.0))

            # Kiểm tra nhanh lỗi spam cảnh báo từ Facebook
            spam_warning = page.locator("text='Bạn tạm thời bị chặn', text='không thể bình luận', text='bị hạn chế', text='something went wrong'").first
            if spam_warning.is_visible():
                print("⚠️ Cảnh báo Facebook: Bạn tạm thời bị hạn chế tính năng bình luận.")
                evidence = _save_comment_evidence(page, "ACTION_BLOCKED")
                return ActionResult(success=False, code="ACTION_BLOCKED", message="Cảnh báo Facebook: Bạn tạm thời bị hạn chế tính năng bình luận.", target_url=post_url, metadata={"evidence_path": evidence})

            # Xác thực ô bình luận đã được dọn sạch (comment đã submit)
            try:
                remaining_text = comment_input.inner_text().strip()
                if remaining_text:
                    time.sleep(2.0)
                    remaining_text = comment_input.inner_text().strip()
                    if remaining_text:
                        print("⚠️ Ô bình luận vẫn còn chứa nội dung sau khi gửi, có thể chưa gửi thành công.")
                        return ActionResult(success=False, code="SUBMIT_UNVERIFIED", message="Ô bình luận vẫn còn chữ sau khi nhấn gửi.", target_url=post_url)
            except Exception:
                pass

            # Chỉ xác thực comment bên trong đúng post_scope; không quét Messenger/chat/toàn page.
            comment_verified = False
            check_snippet = re.sub(r'[\s\u200b\u200c\u200d]+', ' ', parsed_comment).strip()[:30]
            if check_snippet:
                deadline = time.time() + 10.0
                while time.time() < deadline and not comment_verified:
                    try:
                        matches = post_scope.locator("div[role='article']").filter(has_text=check_snippet)
                        for idx in range(min(matches.count(), 12)):
                            if matches.nth(idx).is_visible(timeout=500):
                                comment_verified = True
                                break
                    except Exception:
                        pass
                    if not comment_verified:
                        time.sleep(1.0)
                print(f"[Comment Resolver] verify_in_target_post={'1' if comment_verified else '0'} post_id={_post_identity(canonical_url).get('post_id')}")

            # Immediate DOM appearance is not enough: Facebook may echo editor text
            # before the comment is durably persisted. Reopen the permalink and require
            # the marker to exist again inside the exact post scope.
            persisted_verified = False
            if comment_verified and check_snippet:
                try:
                    page.goto(canonical_url, wait_until="domcontentloaded", timeout=35000)
                    page.wait_for_timeout(3500)
                    persisted_scope = _locate_target_post_article(page, canonical_url)
                    if persisted_scope is not None:
                        persisted_matches = persisted_scope.get_by_text(check_snippet, exact=False)
                        for idx in range(min(persisted_matches.count(), 12)):
                            if persisted_matches.nth(idx).is_visible(timeout=500):
                                persisted_verified = True
                                break
                except Exception:
                    persisted_verified = False
                print(f"[Comment Resolver] verify_after_reopen={'1' if persisted_verified else '0'} post_id={_post_identity(canonical_url).get('post_id')}")

            if not persisted_verified:
                print(f"⚠️ Bình luận chưa được xác thực bền vững sau khi mở lại bài viết: {post_url}")
                evidence = _save_comment_evidence(page, "COMMENT_UNVERIFIED")
                return ActionResult(
                    success=False, code="COMMENT_UNVERIFIED", state="unverified",
                    message="Đã thử gửi bình luận nhưng không xác thực được sau khi mở lại bài viết.",
                    target_url=post_url, metadata={"evidence_path": evidence}
                )

            evidence = _save_comment_evidence(page, "COMMENT_VERIFIED")
            print("✅ COMMENT_VERIFIED: bình luận tồn tại sau khi mở lại đúng permalink.")
            return ActionResult(
                success=True, code="COMMENT_VERIFIED", state="commented",
                message="Đã bình luận và xác thực bền vững trên đúng bài viết.", target_url=post_url, result_url=post_url,
                metadata={"evidence_path": evidence, "verification_status": "COMMENT_VERIFIED"}
            )

    except Exception as e:
        print(f"❌ Xảy ra lỗi khi bình luận vào bài viết: {e}")
        return ActionResult(success=False, code="ERROR", message=str(e), target_url=post_url)
    finally:
        if account:
            close_browser(browser_obj if browser_obj else context, account, gpm_api_url)
        else:
            if browser_obj:
                try:
                    browser_obj.close()
                except Exception:
                    pass

def comment_on_list(urls, comment_content, account_id=None, gpm_api_url=None, like_post=False, min_delay=25, max_delay=45, anti_hash_text=False):
    """
    Duyệt qua danh sách link bài viết và bình luận lần lượt.
    """
    total = len(urls)
    print(f"\n=======================================================")
    print(f"🚀 BẮT ĐẦU CHẠY BÌNH LUẬN VÀO {total} BÀI VIẾT ĐÃ CHỌN")
    print(f"=======================================================\n")

    success_count = 0
    fail_count = 0

    for idx, url in enumerate(urls, 1):
        url = url.strip()
        if not url:
            continue

        print(f"\n[{idx}/{total}] Đang xử lý: {url}")
        res = comment_on_post(
            post_url=url,
            comment_content=comment_content,
            account_id=account_id,
            gpm_api_url=gpm_api_url,
            like_post=like_post,
            anti_hash_text=anti_hash_text
        )

        if res and (getattr(res, 'success', False) or res is True):
            success_count += 1
        else:
            fail_count += 1

        if idx < total:
            delay = random.randint(min_delay, max_delay)
            print(f"\n⏳ [Anti-Spam] Nghỉ {delay} giây trước khi chuyển sang link tiếp theo...")
            for sec in range(delay, 0, -1):
                if sec % 10 == 0 or sec <= 5:
                    print(f"... còn {sec}s")
                time.sleep(1)

    print(f"\n🎉 HOÀN THÀNH TẤT CẢ! Tổng: {total} | Thành công: {success_count} | Thất bại: {fail_count}")
    all_success = (fail_count == 0 and success_count > 0) or (total == 0)
    stats = {"total": total, "success": success_count, "failed": fail_count}
    return ActionResult(
        success=all_success,
        code="COMMENT_LIST_COMPLETE" if all_success else "COMMENT_LIST_PARTIAL_FAIL",
        message=f"Bình luận danh sách: {success_count}/{total} thành công, {fail_count} thất bại.",
        metadata=stats,
        data=stats
    )

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Tự động bình luận vào bài viết Group / Fanpage Facebook")
    parser.add_argument("url", nargs="?", help="URL bài viết cần comment")
    parser.add_argument("content", nargs="?", help="Nội dung comment (hỗ trợ Spintax)")
    parser.add_argument("--urls-file", help="Đường dẫn file chứa danh sách link (mỗi dòng 1 link)")
    parser.add_argument("--account-id", default=None, help="ID tài khoản trong accounts.json")
    parser.add_argument("--gpm-api", default=None, help="URL GPM API")
    parser.add_argument("--like", action="store_true", default=False, help="Tùy chọn like trước khi comment; mặc định tắt")
    parser.add_argument("--min-delay", type=int, default=25, help="Thời gian nghỉ tối thiểu (giây)")
    parser.add_argument("--max-delay", type=int, default=45, help="Thời gian nghỉ tối đa (giây)")
    parser.add_argument("--anti-hash-text", action="store_true", default=False, help="Legacy compatibility option; disabled by default")
    parser.add_argument("--no-anti-hash-text", dest="anti_hash_text", action="store_false")
    args = parser.parse_args()

    if args.urls_file and os.path.exists(args.urls_file):
        with open(args.urls_file, "r", encoding="utf-8") as f:
            target_urls = [line.strip() for line in f if line.strip()]
        content = args.content or "Bài viết rất hữu ích!"
        res = comment_on_list(target_urls, content, args.account_id, args.gpm_api, args.like, args.min_delay, args.max_delay, anti_hash_text=args.anti_hash_text)
        is_ok = getattr(res, "success", False) if hasattr(res, "success") else bool(res)
        sys.exit(0 if is_ok else 1)
    elif args.url and args.content:
        res = comment_on_post(args.url, args.content, args.account_id, args.gpm_api, args.like, anti_hash_text=args.anti_hash_text)
        is_ok = getattr(res, "success", False) if hasattr(res, "success") else bool(res)
        sys.exit(0 if is_ok else 1)
    else:
        parser.print_help()
        sys.exit(1)
