import sys
import time
import random
import re
from playwright.sync_api import sync_playwright
from utils import process_spintax, human_type

STATE_FILE = "state.json"

def interact_newsfeed(limit=5, comment_pool_str=""):
    print(f"Bắt đầu tương tác Newsfeed (Giới hạn: {limit} bài viết)")
    
    # Chuẩn bị danh sách bình luận
    if comment_pool_str:
        comment_pool = [c.strip() for c in comment_pool_str.split(";") if c.strip()]
    else:
        comment_pool = ["Tuyệt vời quá!", "Bài viết rất hay.", "Chúc bạn ngày mới tốt lành!", "Like mạnh nhé!", "Quá xuất sắc!"]
        
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(storage_state=STATE_FILE)
            page = context.new_page()

            # Giả lập di chuyển chuột trước khi vào trang chủ
            page.mouse.move(random.randint(100, 500), random.randint(100, 500))
            print("Đang mở trang chủ Facebook...")
            page.goto("https://www.facebook.com/")
            page.wait_for_load_state("networkidle")
            time.sleep(random.uniform(3.0, 5.0))
            
            interacted_count = 0
            
            # Cuộn trang và tìm bài viết
            for scroll_step in range(limit * 3):
                if interacted_count >= limit:
                    break
                    
                # Cuộn trang xuống ngẫu nhiên
                scroll_y = random.randint(300, 700)
                page.mouse.wheel(0, scroll_y)
                print(f"Đang lướt Newsfeed... (Cuộn xuống {scroll_y}px)")
                time.sleep(random.uniform(2.5, 4.5))
                
                # Tìm các bài viết đang hiển thị trên màn hình
                articles = page.locator("div[role='article']").all()
                if not articles:
                    continue
                    
                # Chọn một bài viết ngẫu nhiên trong danh sách tìm thấy
                article = random.choice(articles)
                
                try:
                    # Cuộn bài viết này vào giữa màn hình
                    article.scroll_into_view_if_needed()
                    time.sleep(random.uniform(1.0, 2.0))
                    
                    # 1. Thả Like/Thích (Tỉ lệ 60%)
                    if random.random() < 0.6:
                        # Tìm nút Like
                        like_btn = article.locator("div[role='button']").filter(
                            has_text=re.compile("^(Thích|Like)$", re.IGNORECASE)
                        ).first
                        
                        if like_btn.is_visible() and like_btn.is_enabled():
                            print("👉 Thả biểu cảm thích (Like) bài viết...")
                            like_btn.click()
                            time.sleep(random.uniform(1.5, 3.0))
                            interacted_count += 1
                        
                    # 2. Bình luận bài viết (Tỉ lệ 30%)
                    if random.random() < 0.3 and comment_pool:
                        # Thử bấm vào ô Bình luận nếu không thấy ô nhập trực tiếp
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
                            
                except Exception as ex:
                    # Bỏ qua lỗi nhỏ trên từng bài viết đơn lẻ
                    continue
                    
            print(f"✅ Hoàn thành tương tác Newsfeed. Đã tương tác: {interacted_count}/{limit} bài viết.")
            
        except Exception as e:
            print(f"❌ Có lỗi xảy ra khi nuôi nick: {e}")
        finally:
            if 'browser' in locals():
                browser.close()

if __name__ == "__main__":
    limit = 5
    comments = ""
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            pass
    if len(sys.argv) > 2:
        comments = sys.argv[2]
        
    interact_newsfeed(limit, comments)
