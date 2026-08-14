import sys
import argparse
import os

def check_state():
    if not os.path.exists("state.json"):
        print("❌ Error: state.json not found.")
        print("Please run 'python main.py auth' first to log in and save your session state.")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Facebook Automation Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Auth command
    subparsers.add_parser("auth", help="Log into Facebook and save session state")
    
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
        from fb_auth import login
        login()
    elif args.command == "group":
        check_state()
        from fb_group import post_to_group
        post_to_group(args.url, args.content, args.image)
    elif args.command == "page":
        check_state()
        from fb_page import post_to_page
        post_to_page(args.url, args.content, args.image)
    elif args.command == "thread":
        check_state()
        from fb_thread import send_message
        send_message(args.id, args.content, args.image)
    elif args.command == "interact":
        check_state()
        from fb_interact import interact_newsfeed
        interact_newsfeed(args.limit, args.comments)
    elif args.command == "scrape":
        check_state()
        from fb_scraper import scrape_comments
        scrape_comments(args.url, args.limit)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
