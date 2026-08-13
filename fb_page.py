import sys
import os
import time
import random
from playwright.sync_api import sync_playwright
from utils import process_spintax, human_type

STATE_FILE = "state.json"

def post_to_page(page_url, content, image_path=None):
    print(f"Attempting to post to page: {page_url}")
    content = process_spintax(content)
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(storage_state=STATE_FILE)
            page = context.new_page()

            page.mouse.move(random.randint(100, 500), random.randint(100, 500))
            page.goto(page_url)
            page.wait_for_load_state("networkidle")
            time.sleep(random.uniform(2.0, 4.0))
            
            page.mouse.wheel(0, random.randint(200, 600))
            time.sleep(random.uniform(1.0, 2.0))
            page.mouse.wheel(0, -random.randint(100, 300))
            
            print("Looking for post input area...")
            
            try:
                write_box = page.locator("div[role='button']").filter(has_text="What's on your mind").first
                if not write_box.is_visible():
                    write_box = page.get_by_text("Write something...", exact=False).first
                write_box.click()
            except Exception:
                print("Could not find the initial post box. Ensure you are logged in and have admin rights to this page.")
                return
            
            time.sleep(random.uniform(1.5, 3.0))
            
            if image_path and os.path.exists(image_path):
                print(f"Attaching image: {image_path}")
                try:
                    file_input = page.locator("input[type='file'][accept*='image']").first
                    file_input.set_input_files(image_path)
                    print("Waiting for image to upload...")
                    time.sleep(random.uniform(4.0, 7.0))
                except Exception as e:
                    print(f"Warning: Could not attach image. Error: {e}")
            
            print("Typing content...")
            textbox = page.get_by_role("textbox").filter(has_text="").first
            human_type(page, textbox, content)
            
            time.sleep(random.uniform(1.0, 2.5))
            
            print("Clicking 'Post' button...")
            post_button = page.get_by_role("button", name="Post", exact=True)
            if post_button.is_visible():
                post_button.click()
            else:
                page.locator("div[aria-label='Post']").click()
            
            print("Waiting for post to process...")
            time.sleep(random.uniform(6.0, 8.0))
            print("✅ Successfully posted to page!")
            
        except Exception as e:
            print(f"❌ An error occurred: {e}")
        finally:
            if 'browser' in locals():
                browser.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python fb_page.py <PAGE_URL> '<YOUR POST CONTENT>' [IMAGE_PATH]")
        sys.exit(1)
    
    page_url = sys.argv[1]
    content = sys.argv[2]
    image_path = sys.argv[3] if len(sys.argv) > 3 else None
    post_to_page(page_url, content, image_path)
