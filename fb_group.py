import sys
import os
import time
import random
from playwright.sync_api import sync_playwright
from utils import process_spintax, human_type, load_accounts, launch_browser, close_browser

STATE_FILE = "state.json"

def post_to_group(group_url, content, image_path=None, account_id=None, gpm_api_url=None):
    print(f"Attempting to post to group: {group_url}")
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
            page.goto(group_url)
            page.wait_for_load_state("networkidle")
            time.sleep(random.uniform(2.0, 4.0))
            
            page.mouse.wheel(0, random.randint(200, 600))
            time.sleep(random.uniform(1.0, 2.0))
            page.mouse.wheel(0, -random.randint(100, 300))
            
            print("Looking for 'Write something...' box...")
            write_box = page.get_by_text("Write something...", exact=False).first
            write_box.click()
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
            print("✅ Successfully posted to group!")
            
        except Exception as e:
            print(f"❌ An error occurred: {e}")
        finally:
            if account:
                close_browser(browser_obj if browser_obj else context, account, gpm_api_url)
            else:
                if 'browser_obj' in locals() and browser_obj:
                    browser_obj.close()

if __name__ == "__main__":
    # Parsing command-line args for direct execution
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("content")
    parser.add_argument("--image", default=None)
    parser.add_argument("--account-id", default=None)
    parser.add_argument("--gpm-api", default=None)
    args = parser.parse_args()
    
    post_to_group(args.url, args.content, args.image, args.account_id, args.gpm_api)
