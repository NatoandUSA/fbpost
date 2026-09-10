import sys
import time
import random
import re
import os
from playwright.sync_api import sync_playwright
from utils import process_spintax, human_type, resolve_account, launch_browser, close_browser, safe_mouse_wheel, ActionResult
from paths import DATA_DIR

STATE_FILE = str(DATA_DIR / "state.json")

def interact_newsfeed(limit=5, comment_pool_str="", account_id=None, gpm_api_url=None):
    print(f"Bắt đầu tương tác Newsfeed (Giới hạn: {limit} bài viết)")
    
    if comment_pool_str:
        comment_pool = [c.strip() for c in comment_pool_str.split(";") if c.strip()]
    else:
        # v6: không tự tạo bình luận ngẫu nhiên nếu người dùng không cung cấp nội dung.
        comment_pool = []
        
    # Load account if provided
    account = None
    if account_id:
        account = resolve_account(account_id, gpm_api_url)
        if not account:
            print(f"❌ Error: Account ID '{account_id}' not found in accounts.json or GPM.")
            return ActionResult(False, "ACCOUNT_NOT_FOUND", f"Account ID '{account_id}' not found.", state="failed")

    browser_obj = None
    context = None
    with sync_playwright() as p:
        try:
            if account:
                browser_obj, context, page = launch_browser(account, p, gpm_api_url)
            else:
                print("No account specified, fallback to default state.json.")
                browser_obj = p.chromium.launch(headless=False)
                state_arg = STATE_FILE if os.path.exists(STATE_FILE) else None
                context = browser_obj.new_context(storage_state=state_arg)
                page = context.new_page()

            page.set_default_timeout(45000)
            page.mouse.move(random.randint(100, 500), random.randint(100, 500))
            print("Đang mở trang chủ Facebook...")
            try:
                page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=45000)
            except Exception as nav_err:
                print(f"⚠️ Cảnh báo tải trang: {nav_err}. Tiếp tục xử lý giao diện...")
            time.sleep(random.uniform(3.0, 5.0))
            
            interacted_count = 0
            like_count = 0
            comment_count = 0
            articles_seen = 0
            like_candidates_seen = 0
            visited_articles = set()
            
            for scroll_step in range(limit * 3):
                if interacted_count >= limit:
                    break
                    
                scroll_y = random.randint(300, 700)
                safe_mouse_wheel(page, 0, scroll_y)
                if scroll_step == 0 or (scroll_step + 1) % 3 == 0:
                    print(f"Đang quét Newsfeed... bước {scroll_step + 1}/{limit * 3}")
                time.sleep(random.uniform(2.5, 4.5))
                
                articles = page.locator("div[role='article']").all()
                if not articles:
                    continue
                articles_seen = max(articles_seen, len(articles))
                    
                # Never interact with the same post twice in one run.
                article = None
                for candidate in articles:
                    try:
                        href = candidate.locator("a[href*='/posts/'], a[href*='/permalink/']").first.get_attribute("href") or ""
                    except Exception:
                        href = ""
                    try:
                        txt = (candidate.inner_text() or "").strip()[:100]
                    except Exception:
                        txt = ""
                    key = href.split("?", 1)[0] or txt
                    if key and key not in visited_articles:
                        visited_articles.add(key); article = candidate; break
                if article is None:
                    continue

                try:
                    article.scroll_into_view_if_needed()
                    time.sleep(random.uniform(1.0, 2.0))
                    
                    if random.random() < 0.6:
                        like_btn = article.locator("div[role='button'], button").filter(
                            has_text=re.compile(r"^\s*(Thích|Like)(\s+\d+)?\s*$", re.IGNORECASE)
                        ).or_(article.locator("[aria-label*='Thích' i], [aria-label*='Like' i]")).first
                        try:
                            if like_btn.count() > 0:
                                like_candidates_seen += 1
                        except Exception:
                            pass
                        
                        if like_btn.is_visible() and like_btn.is_enabled():
                            print("👉 Thả biểu cảm thích (Like) bài viết...")
                            before_pressed = like_btn.get_attribute("aria-pressed")
                            before_label = ((like_btn.get_attribute("aria-label") or "") + " " + (like_btn.inner_text() or "")).lower()
                            # Do not toggle an already-active reaction off.
                            if before_pressed == "true" or any(x in before_label for x in ("bỏ thích", "unlike")):
                                continue
                            like_btn.click()
                            time.sleep(random.uniform(1.5, 3.0))
                            after_pressed = like_btn.get_attribute("aria-pressed")
                            after_label = ((like_btn.get_attribute("aria-label") or "") + " " + (like_btn.inner_text() or "")).lower()
                            if after_pressed == "true" or after_label != before_label:
                                like_count += 1
                                interacted_count += 1
                        
                    if random.random() < 0.3 and comment_pool:
                        comment_input = article.locator("div[role='textbox']").first
                        if not comment_input.is_visible():
                            comment_btn = article.locator("div[role='button']").filter(
                                has_text=re.compile("^(Bình luận|Comment)$", re.IGNORECASE)
                            ).first
                            if comment_btn.is_visible():
                                comment_btn.click()
                                time.sleep(random.uniform(1.5, 2.5))
                                comment_input = article.locator("div[role='textbox']").first
                                
                        if comment_input.is_visible() and comment_input.is_enabled():
                            raw_comment = random.choice(comment_pool)
                            comment_text = process_spintax(raw_comment)
                            print(f"👉 Viết bình luận: \"{comment_text}\"")
                            human_type(page, comment_input, comment_text)
                            time.sleep(random.uniform(1.0, 2.0))
                            page.keyboard.press("Enter")
                            time.sleep(random.uniform(3.0, 5.0))
                            snippet = re.sub(r"\s+", " ", comment_text).strip()[:30]
                            try:
                                matches = article.locator("div[role='article']").filter(has_text=snippet)
                                verified = any(matches.nth(ci).is_visible(timeout=300) for ci in range(min(matches.count(), 8)))
                            except Exception:
                                verified = False
                            if verified:
                                comment_count += 1
                                interacted_count += 1
                            
                except Exception:
                    continue
                    
            print(f"✅ Hoàn thành tương tác Newsfeed. Đã tương tác: {interacted_count}/{limit} bài viết.")
            print(f"📊 Feed diagnostics: articles_seen={articles_seen}, unique_seen={len(visited_articles)}, likes_verified={like_count}, comments_verified={comment_count}, like_candidates={like_candidates_seen}")
            if interacted_count >= limit:
                return ActionResult(True, "INTERACT_CONFIRMED", f"Đạt mục tiêu {interacted_count}/{limit} tương tác.", state="completed", metadata={"interacted": interacted_count, "limit": limit, "articles_seen": articles_seen, "unique_seen": len(visited_articles), "likes_verified": like_count, "comments_verified": comment_count, "like_candidates": like_candidates_seen})
            if interacted_count > 0:
                return ActionResult(True, "INTERACT_PARTIAL", f"Tương tác một phần {interacted_count}/{limit}.", state="partial", metadata={"interacted": interacted_count, "limit": limit, "articles_seen": articles_seen, "unique_seen": len(visited_articles), "likes_verified": like_count, "comments_verified": comment_count, "like_candidates": like_candidates_seen})
            return ActionResult(False, "INTERACT_NO_ACTION", f"Không thực hiện được tương tác nào (0/{limit}).", state="no_action", metadata={"interacted": 0, "limit": limit, "articles_seen": articles_seen, "unique_seen": len(visited_articles), "likes_verified": like_count, "comments_verified": comment_count, "like_candidates": like_candidates_seen})
            
        except Exception as e:
            print(f"❌ Có lỗi xảy ra khi nuôi nick: {e}")
            raise
        finally:
            if account:
                close_browser(browser_obj if browser_obj else context, account, gpm_api_url)
            else:
                if 'browser_obj' in locals() and browser_obj:
                    browser_obj.close()

if __name__ == "__main__":
    import argparse
    import sys
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--comments", default="")
    parser.add_argument("--account-id", default=None)
    parser.add_argument("--gpm-api", default=None)
    args = parser.parse_args()
    
    try:
        ok = interact_newsfeed(args.limit, args.comments, args.account_id, args.gpm_api)
        sys.exit(0 if ok is not False else 1)
    except Exception:
        sys.exit(1)
