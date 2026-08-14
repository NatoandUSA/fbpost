import sys
import argparse
import os

def check_state():
    # If using local profile, state.json is not required globally, so we skip check_state for specific profiles.
    pass

def main():
    parser = argparse.ArgumentParser(description="Facebook Automation Tool")
    parser.add_argument("--account-id", default=None, help="The Account ID to use for running the automation")
    parser.add_argument("--gpm-api", default=None, help="GPM Login API URL (e.g. http://127.0.0.1:13926)")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Auth command
    auth_parser = subparsers.add_parser("auth", help="Log into Facebook and save session state")
    
    # Group command
    group_parser = subparsers.add_parser("group", help="Post to a Facebook Group")
    group_parser.add_argument("url", help="The full URL of the Facebook Group")
    group_parser.add_argument("content", help="The text content of your post")
    group_parser.add_argument("--image", help="Absolute path to an image file", default=None)
    
    # Page command
    page_parser = subparsers.add_parser("page", help="Post to a Facebook Page you manage")
    page_parser.add_argument("url", help="The full URL of the Facebook Page")
    page_parser.add_argument("content", help="The text content of your post")
    page_parser.add_argument("--image", help="Absolute path to an image file", default=None)
    
    # Thread command
    thread_parser = subparsers.add_parser("thread", help="Send a message to a Messenger Thread")
    thread_parser.add_argument("id", help="The Thread ID or username")
    thread_parser.add_argument("content", help="The text content of your message")
    thread_parser.add_argument("--image", help="Absolute path to an image file", default=None)

    # Interact command (Nuôi nick)
    interact_parser = subparsers.add_parser("interact", help="Interact with Facebook Newsfeed (Like/Comment)")
    interact_parser.add_argument("--limit", type=int, default=5, help="Number of articles to interact with")
    interact_parser.add_argument("--comments", help="Semicolon separated comments for random posting", default="")

    # Scrape command (Quét bình luận)
    scrape_parser = subparsers.add_parser("scrape", help="Scrape comments and phone numbers from a post")
    scrape_parser.add_argument("url", help="The full URL of the Facebook post")
    scrape_parser.add_argument("--limit", type=int, default=50, help="Maximum number of comments to scan")
    
    args = parser.parse_args()
    
    if args.command == "auth":
        # Launch headed auth for the specific account
        from fb_auth import login_account
        login_account(args.account_id, args.gpm_api)
    elif args.command == "group":
        from fb_group import post_to_group
        post_to_group(args.url, args.content, args.image, args.account_id, args.gpm_api)
    elif args.command == "page":
        from fb_page import post_to_page
        post_to_page(args.url, args.content, args.image, args.account_id, args.gpm_api)
    elif args.command == "thread":
        from fb_thread import send_message
        send_message(args.id, args.content, args.image, args.account_id, args.gpm_api)
    elif args.command == "interact":
        from fb_interact import interact_newsfeed
        interact_newsfeed(args.limit, args.comments, args.account_id, args.gpm_api)
    elif args.command == "scrape":
        from fb_scraper import scrape_comments
        scrape_comments(args.url, args.limit, args.account_id, args.gpm_api)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
