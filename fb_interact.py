import sys
import time
import random
import re
import os
from playwright.sync_api import sync_playwright
from utils import process_spintax, human_type, load_accounts, launch_browser, close_browser

STATE_FILE = "state.json"

def interact_newsfeed(limit=5, comment_pool_str="", account_id=None, gpm_api_url=None):
    print(f"Bắt đầu tương tác Newsfeed (Giới hạn: {limit} bài viết)")
    
    if comment_pool_str:
        comment_pool = [c.strip() for c in comment_pool_str.split(";") if c.strip()]
    else:
        comment_pool = ["Tuyệt vời quá!", "Bài viết rất hay.", "Chúc bạn ngày mới tốt lành!", "Like mạnh nhé!", "Quá xuất sắc!"]
        
    # Load account if provided
    account = None
    if account_id:
        accounts = load_accounts()
        account = next((a for a in accounts if a["id"] == account_id), None)
        if not account:
            print(f"❌ Error: Account ID '{account_id}' not found in accounts.json.")
            return

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
            
            for scroll_step in range(limit * 3):
                if interacted_count >= limit:
                    break
                    
                scroll_y = random.randint(300, 700)
                page.mouse.wheel(0, scroll_y)
                print(f"Đang lướt Newsfeed... (Cuộn xuống {scroll_y}px)")
                time.sleep(random.uniform(2.5, 4.5))
                
                articles = page.locator("div[role='article']").all()
                if not articles:
                    continue
                    
                article = random.choice(articles)
                
                try:
                    article.scroll_into_view_if_needed()
                    time.sleep(random.uniform(1.0, 2.0))
                    
                    if random.random() < 0.6:
                        like_btn = article.locator("div[role='button']").filter(
                            has_text=re.compile("^(Thích|Like)$", re.IGNORECASE)
                        ).first
                        
                        if like_btn.is_visible() and like_btn.is_enabled():
                            print("👉 Thả biểu cảm thích (Like) bài viết...")
                            like_btn.click()
                            time.sleep(random.uniform(1.5, 3.0))
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
                            
                except Exception:
                    continue
                    
            print(f"✅ Hoàn thành tương tác Newsfeed. Đã tương tác: {interacted_count}/{limit} bài viết.")
            
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--comments", default="")
    parser.add_argument("--account-id", default=None)
    parser.add_argument("--gpm-api", default=None)
    args = parser.parse_args()
    
    interact_newsfeed(args.limit, args.comments, args.account_id, args.gpm_api)
