import sys
import os
import time
import random
import re
from playwright.sync_api import sync_playwright
from utils import process_spintax, human_type, load_accounts, resolve_account, launch_browser, close_browser, safe_mouse_wheel, ActionResult

STATE_FILE = "state.json"

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
    ident = _post_identity(canonical_url)
    post_id = ident.get("post_id") or ""
    if not post_id:
        return None
    selectors = [
        f"a[href*='/posts/{post_id}']", f"a[href*='/permalink/{post_id}']",
        f"a[href*='story_fbid={post_id}']", f"a[href*='fbid={post_id}']"
    ]
    for selector in selectors:
        for idx in range(min(page.locator(selector).count(), 12)):
            try:
                article = page.locator(selector).nth(idx).locator("xpath=ancestor::div[@role='article'][1]")
                if article.count() and article.is_visible(timeout=800):
                    print(f"[Comment Resolver] post_identity={post_id} article=matched")
                    return article
            except Exception:
                continue
    # Facebook 2026 thường render permalink trong modal "Bài viết của ..." và để feed phía sau.
    # Nếu URL hiện tại vẫn khóa đúng post_id, modal visible là scope an toàn hơn các article nền.
    try:
        current_url = page.url or ""
        if post_id in current_url:
            dialogs = page.locator("div[role='dialog']")
            for idx in range(min(dialogs.count(), 8)):
                dlg = dialogs.nth(idx)
                if not dlg.is_visible(timeout=400):
                    continue
                aria = (dlg.get_attribute("aria-label") or "").strip().lower()
                text = (dlg.inner_text() or "").strip().lower()[:160]
                if ("bài viết của" in text or "post by" in text or not aria):
                    print(f"[Comment Resolver] post_identity={post_id} scope=permalink-dialog")
                    return dlg
    except Exception:
        pass
    visible = []
    for idx in range(min(page.locator("div[role='article']").count(), 8)):
        try:
            art = page.locator("div[role='article']").nth(idx)
            if art.is_visible(timeout=400) and not art.locator("[data-visualcompletion='loading-state']").count():
                visible.append(art)
        except Exception:
            pass
    if len(visible) == 1:
        print(f"[Comment Resolver] post_identity={post_id} article=single-visible-fallback")
        return visible[0]
    print(f"[Comment Resolver] post_identity={post_id} article=not-found visible_articles={len(visible)}")
    return None

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

            # 2. Tìm ô nhập bình luận
            print("🔍 Đang tìm ô bình luận...")
            comment_input = None

            # Danh sách các bộ chọn tìm ô comment linh hoạt cho FB 2026
            selectors = [
                "div[role='textbox'][contenteditable='true'][data-lexical-editor='true']",
                "div[role='textbox'][contenteditable='true']",
                "div[role='textbox'][aria-label*='bình luận']",
                "div[role='textbox'][aria-label*='comment' i]",
                "div[role='textbox'][aria-placeholder*='bình luận']",
                "div[role='textbox'][aria-placeholder*='comment' i]"
            ]

            # Facebook có thể mount Lexical editor trễ vài giây sau khi modal permalink hiện ra.
            for wait_round in range(1, 9):
                for selector in selectors:
                    candidates = post_scope.locator(selector)
                    count = candidates.count()
                    for i in range(count):
                        el = candidates.nth(i)
                        try:
                            if el.is_visible(timeout=300):
                                comment_input = el
                                break
                        except Exception:
                            pass
                    if comment_input:
                        break
                if comment_input:
                    print(f"[Comment Resolver] textbox=found wait_round={wait_round}")
                    break
                page.wait_for_timeout(900)

            # Nếu chưa thấy ô textbox, có thể cần click nút "Viết bình luận" hoặc "Bình luận"
            if not comment_input:
                open_comment_buttons = [
                    "div[role='button'][aria-label='Viết bình luận']",
                    "div[role='button'][aria-label='Write a comment']",
                    "div[role='button']:has-text('Viết bình luận')",
                    "div[role='button']:has-text('Write a comment')",
                    "div[role='button']:has-text('Bình luận')",
                    "div[role='button']:has-text('Comment')",
                    "div[aria-label*='bình luận' i][role='button']",
                    "div[aria-label*='comment' i][role='button']"
                ]
                for btn_sel in open_comment_buttons:
                    btn = post_scope.locator(btn_sel).first
                    if btn.is_visible():
                        print("👉 Click mở ô bình luận...")
                        btn.click()
                        time.sleep(random.uniform(1.5, 3.0))
                        break

                # Thử tìm lại ô textbox sau khi click; chờ editor mount trong đúng post_scope.
                for wait_round in range(1, 7):
                    for selector in selectors:
                        el = post_scope.locator(selector).first
                        try:
                            if el.is_visible(timeout=300):
                                comment_input = el
                                break
                        except Exception:
                            pass
                    if comment_input:
                        print(f"[Comment Resolver] textbox=found-after-open wait_round={wait_round}")
                        break
                    page.wait_for_timeout(800)

            if not comment_input or not comment_input.is_visible():
                print("❌ Không tìm thấy ô bình luận trên bài viết này (Bài viết có thể bị tắt tính năng bình luận hoặc yêu cầu phê duyệt).")
                return ActionResult(success=False, code="COMMENT_INPUT_NOT_FOUND", message="Không tìm thấy ô bình luận trên bài viết này.", target_url=post_url)

            # 3. Focus và gõ nội dung bình luận (dùng Shift+Enter cho newline để không submit sớm)
            print(f"💬 Đang gõ nội dung bình luận: \"{parsed_comment}\"")
            comment_input.scroll_into_view_if_needed()
            time.sleep(random.uniform(0.8, 1.5))
            comment_input.click()
            time.sleep(random.uniform(0.5, 1.0))
            
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

            if not comment_verified:
                print(f"⚠️ Bình luận đã nhấn gửi nhưng không thể xác thực hiển thị trên bài viết: {post_url}")
                evidence = _save_comment_evidence(page, "COMMENT_UNVERIFIED")
                return ActionResult(
                    success=False, code="COMMENT_UNVERIFIED", state="unverified",
                    message="Bình luận đã gửi nhưng không tìm thấy hiển thị trên bài viết.",
                    target_url=post_url, metadata={"evidence_path": evidence}
                )

            evidence = _save_comment_evidence(page, "COMMENT_VERIFIED")
            print("✅ Đã bình luận bài viết thành công và xác thực hiển thị!")
            return ActionResult(
                success=True, code="SUCCESS", state="commented",
                message="Đã bình luận bài viết thành công!", target_url=post_url, result_url=post_url,
                metadata={"evidence_path": evidence}
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
