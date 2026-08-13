import sys
import os
import time
import random
from playwright.sync_api import sync_playwright
from utils import process_spintax, human_type

STATE_FILE = "state.json"

def send_message(thread_id, content, image_path=None):
    thread_url = f"https://www.messenger.com/t/{thread_id}"
    print(f"Attempting to send message to thread: {thread_url}")
    content = process_spintax(content)
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(storage_state=STATE_FILE)
            page = context.new_page()

            page.mouse.move(random.randint(100, 500), random.randint(100, 500))
            page.goto(thread_url)
            page.wait_for_load_state("networkidle")
            time.sleep(random.uniform(2.0, 4.0))
            
            if image_path and os.path.exists(image_path):
                print(f"Attaching image: {image_path}")
                try:
                    file_input = page.locator("input[type='file'][accept*='image']").first
                    file_input.set_input_files(image_path)
                    print("Waiting for image to upload...")
                    time.sleep(random.uniform(3.0, 6.0))
                except Exception as e:
                    print(f"Warning: Could not attach image. Error: {e}")
            
            print("Looking for message input box...")
            textbox = page.get_by_role("textbox").first
            
            print("Typing message...")
            human_type(page, textbox, content)
            time.sleep(random.uniform(0.5, 1.5))
            
            print("Sending message...")
            page.keyboard.press("Enter")
            
            print("Waiting for message to send...")
            time.sleep(random.uniform(2.0, 4.0))
            print("✅ Successfully sent message to thread!")
            
        except Exception as e:
            print(f"❌ An error occurred: {e}")
        finally:
            if 'browser' in locals():
                browser.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python fb_thread.py <THREAD_ID> '<YOUR MESSAGE CONTENT>' [IMAGE_PATH]")
        print("Note: THREAD_ID can be a username or a numeric ID from the messenger.com URL.")
        sys.exit(1)
    
    thread_id = sys.argv[1]
    content = sys.argv[2]
    image_path = sys.argv[3] if len(sys.argv) > 3 else None
    send_message(thread_id, content, image_path)
