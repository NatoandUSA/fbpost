import json
import time
from playwright.sync_api import sync_playwright

STATE_FILE = "state.json"

def login():
    """
    Opens an interactive browser window for the user to log in manually.
    Saves the session state (cookies, etc.) to state.json.
    """
    print("Starting Playwright...")
    with sync_playwright() as p:
        # Launch headed browser so the user can see and interact
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("Navigating to Facebook...")
        page.goto("https://www.facebook.com/")
        
        print("\n" + "="*50)
        print("*** ACTION REQUIRED ***")
        print("1. Please log into Facebook in the opened browser window.")
        print("2. If you have 2-Factor Authentication (2FA) enabled, please complete it.")
        print("3. Wait until you are fully logged in and see your News Feed.")
        print("="*50 + "\n")
        
        input("Press Enter in this terminal ONLY AFTER you have successfully logged in...")
        
        # Save state
        context.storage_state(path=STATE_FILE)
        print(f"Session state saved to '{STATE_FILE}'. You can now run the automation scripts.")
        
        browser.close()

if __name__ == "__main__":
    login()
