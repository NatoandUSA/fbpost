import sys
import os
import time
import random
from playwright.sync_api import sync_playwright
from utils import process_spintax, human_type, load_accounts, launch_browser, close_browser

STATE_FILE = "state.json"

def send_message(thread_id, content, image_path=None, account_id=None, gpm_api_url=None):
    thread_url = f"https://www.messenger.com/t/{thread_id}"
    print(f"Attempting to send message to thread: {thread_url}")
    content = process_spintax(content)
    
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
            if account:
                close_browser(browser_obj if browser_obj else context, account, gpm_api_url)
            else:
                if 'browser_obj' in locals() and browser_obj:
                    browser_obj.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("id")
    parser.add_argument("content")
    parser.add_argument("--image", default=None)
    parser.add_argument("--account-id", default=None)
    parser.add_argument("--gpm-api", default=None)
    args = parser.parse_args()
    
    send_message(args.id, args.content, args.image, args.account_id, args.gpm_api)
