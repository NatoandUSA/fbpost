import sys
import time
import random
import re
import json
import os
from playwright.sync_api import sync_playwright
from utils import load_accounts, launch_browser, close_browser

STATE_FILE = "state.json"

def extract_phone(text):
    pattern = re.compile(r'\b(0[35789]\d{8}|0[35789]\d{2}[.\s-]?\d{3}[.\s-]?\d{3})\b')
    match = pattern.search(text)
    if match:
        num = re.sub(r'\D', '', match.group(1))
        return num
    return None

def scrape_comments(post_url, max_comments=50, account_id=None, gpm_api_url=None):
    print(f"Bắt đầu quét bình luận từ bài viết: {post_url}")
    
    # Load account if provided
    account = None
    if account_id:
        accounts = load_accounts()
        account = next((a for a in accounts if a["id"] == account_id), None)
        if not account:
            print(f"❌ Error: Account ID '{account_id}' not found in accounts.json.")
            return

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

            page.mouse.move(random.randint(100, 500), random.randint(100, 500))
            print("Đang mở link bài viết...")
            page.goto(post_url)
            page.wait_for_load_state("networkidle")
            time.sleep(random.uniform(3.0, 5.0))
            
            print("Đang tải thêm bình luận...")
            for click_idx in range(5):
                try:
                    more_btn = page.locator("span").filter(
                        has_text=re.compile("View more comments|Xem thêm bình luận|Xem thêm phản hồi|Xem tất cả bình luận", re.IGNORECASE)
                    ).first
                    
                    if more_btn.is_visible() and more_btn.is_enabled():
                        print(f"Nhấp nút xem thêm bình luận lần {click_idx + 1}...")
                        more_btn.click()
                        time.sleep(random.uniform(2.5, 4.0))
                    else:
                        break
                except Exception:
                    break
            
            raw_comments = page.evaluate("""() => {
                const results = [];
                const articles = document.querySelectorAll('div[role="article"]');
                articles.forEach(art => {
                    const links = art.querySelectorAll('a[role="link"], a');
                    let name = '';
                    let profileUrl = '';
                    
                    for (let link of links) {
                        if (link.innerText && link.href && !link.href.includes('/posts/') && !link.href.includes('/groups/')) {
                            name = link.innerText;
                            profileUrl = link.href;
                            break;
                        }
                    }
                    
                    const textElems = art.querySelectorAll('div[dir="auto"], span[dir="auto"]');
                    let text = '';
                    textElems.forEach(el => {
                        if (el.innerText && el.innerText !== name) {
                            text = el.innerText;
                        }
                    });
                    
                    if (name && text) {
                        results.push({ name, profileUrl, text });
                    }
                });
                return results;
            }""")
            
            scraped_data = []
            for item in raw_comments:
                text = item.get('text', '')
                phone = extract_phone(text)
                
                profile = item.get('profileUrl', '')
                if '?' in profile:
                    profile = profile.split('?')[0]
                    
                scraped_data.append({
                    "name": item.get('name', ''),
                    "profile": profile,
                    "comment": text,
                    "phone": phone if phone else "Không có"
                })
                
            print(f"✅ Đã quét được {len(scraped_data)} bình luận.")
            print("JSON_DATA:" + json.dumps(scraped_data, ensure_ascii=False))
            
        except Exception as e:
            print(f"❌ Có lỗi xảy ra khi quét bình luận: {e}")
        finally:
            if account:
                close_browser(browser_obj if browser_obj else context, account, gpm_api_url)
            else:
                if 'browser_obj' in locals() and browser_obj:
                    browser_obj.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--account-id", default=None)
    parser.add_argument("--gpm-api", default=None)
    args = parser.parse_args()
    
    scrape_comments(args.url, args.limit, args.account_id, args.gpm_api)
