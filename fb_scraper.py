import sys
import time
import random
import re
import json
from playwright.sync_api import sync_playwright

STATE_FILE = "state.json"

def extract_phone(text):
    # Regex tìm số điện thoại Việt Nam (10 chữ số, có thể cách nhau bởi dấu chấm, khoảng trắng, gạch ngang)
    pattern = re.compile(r'\b(0[35789]\d{8}|0[35789]\d{2}[.\s-]?\d{3}[.\s-]?\d{3})\b')
    match = pattern.search(text)
    if match:
        # Làm sạch, chỉ giữ lại số
        num = re.sub(r'\D', '', match.group(1))
        return num
    return None

def scrape_comments(post_url, max_comments=50):
    print(f"Bắt đầu quét bình luận từ bài viết: {post_url}")
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(storage_state=STATE_FILE)
            page = context.new_page()

            page.mouse.move(random.randint(100, 500), random.randint(100, 500))
            print("Đang mở link bài viết...")
            page.goto(post_url)
            page.wait_for_load_state("networkidle")
            time.sleep(random.uniform(3.0, 5.0))
            
            # Click nút "Xem thêm bình luận" / "Xem thêm phản hồi"
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
            
            # Sử dụng Javascript chạy trên trình duyệt để trích xuất dữ liệu bình luận cực kỳ chính xác và nhanh chóng
            raw_comments = page.evaluate("""() => {
                const results = [];
                // Chọn tất cả các khối có thuộc tính role="article" (cấu trúc của bình luận trên FB)
                const articles = document.querySelectorAll('div[role="article"]');
                articles.forEach(art => {
                    const links = art.querySelectorAll('a[role="link"], a');
                    let name = '';
                    let profileUrl = '';
                    
                    // Tìm thẻ a chứa tên và link profile của người bình luận
                    for (let link of links) {
                        if (link.innerText && link.href && !link.href.includes('/posts/') && !link.href.includes('/groups/')) {
                            name = link.innerText;
                            profileUrl = link.href;
                            break;
                        }
                    }
                    
                    // Tìm nội dung bình luận
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
            
            # Xử lý và trích xuất số điện thoại từ các bình luận thu thập được
            scraped_data = []
            for item in raw_comments:
                text = item.get('text', '')
                phone = extract_phone(text)
                
                # Làm sạch link profile (bỏ phần query string để lấy link sạch hoặc UID)
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
            
            # In ra dạng JSON_DATA để frontend bắt và hiển thị dạng bảng
            print("JSON_DATA:" + json.dumps(scraped_data, ensure_ascii=False))
            
        except Exception as e:
            print(f"❌ Có lỗi xảy ra khi quét bình luận: {e}")
        finally:
            if 'browser' in locals():
                browser.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fb_scraper.py <POST_URL> [MAX_COMMENTS]")
        sys.exit(1)
        
    post_url = sys.argv[1]
    max_comments = 50
    if len(sys.argv) > 2:
        try:
            max_comments = int(sys.argv[2])
        except ValueError:
            pass
            
    scrape_comments(post_url, max_comments)
