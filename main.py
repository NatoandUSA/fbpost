import sys
import argparse
import os


def configure_unicode_output():
    """Keep a Windows legacy console from crashing when a log contains Vietnamese."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


configure_unicode_output()

def check_state():
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
    group_parser.add_argument("--feeling", action="store_true", help="Add a random feeling to the post")
    group_parser.add_argument("--checkin", action="store_true", help="Add a random check-in location to the post")
    
    # Page command
    page_parser = subparsers.add_parser("page", help="Post to a Facebook Page you manage")
    page_parser.add_argument("url", help="The full URL of the Facebook Page")
    page_parser.add_argument("content", help="The text content of your post")
    page_parser.add_argument("--image", help="Absolute path to an image file", default=None)
    page_parser.add_argument("--feeling", action="store_true", help="Add a random feeling to the post")
    page_parser.add_argument("--checkin", action="store_true", help="Add a random check-in location to the post")
    
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
    
    # Comment command (Comment vào danh sách bài viết chỉ định)
    comment_parser = subparsers.add_parser("comment", help="Comment on specific Facebook posts (Group or Page)")
    comment_parser.add_argument("url", nargs="?", help="The full URL of the Facebook post")
    comment_parser.add_argument("content", nargs="?", help="The text content of your comment")
    comment_parser.add_argument("--urls-file", default=None, help="Path to text file containing list of post URLs")
    comment_parser.add_argument("--like", action="store_true", default=False, help="Like the post before commenting")
    comment_parser.add_argument("--min-delay", type=int, default=25, help="Min delay between comments in seconds")
    comment_parser.add_argument("--max-delay", type=int, default=45, help="Max delay between comments in seconds")
    
    args = parser.parse_args()
    
    if args.command == "auth":
        from fb_auth import login_account
        login_account(args.account_id, args.gpm_api)
    elif args.command == "group":
        from fb_group import post_to_group
        post_to_group(args.url, args.content, args.image, args.account_id, args.gpm_api, args.feeling, args.checkin)
    elif args.command == "page":
        from fb_page import post_to_page
        post_to_page(args.url, args.content, args.image, args.account_id, args.gpm_api, args.feeling, args.checkin)
    elif args.command == "thread":
        from fb_thread import send_message
        send_message(args.id, args.content, args.image, args.account_id, args.gpm_api)
    elif args.command == "interact":
        from fb_interact import interact_newsfeed
        interact_newsfeed(args.limit, args.comments, args.account_id, args.gpm_api)
    elif args.command == "scrape":
        from fb_scraper import scrape_comments
        scrape_comments(args.url, args.limit, args.account_id, args.gpm_api)
    elif args.command == "comment":
        from fb_comment import comment_on_post, comment_on_list
        if args.urls_file and os.path.exists(args.urls_file):
            with open(args.urls_file, "r", encoding="utf-8") as f:
                urls = [l.strip() for l in f if l.strip()]
            comment_on_list(urls, args.content or "", args.account_id, args.gpm_api, args.like, args.min_delay, args.max_delay)
        elif args.url and args.content:
            comment_on_post(args.url, args.content, args.account_id, args.gpm_api, args.like)
        else:
            comment_parser.print_help()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
