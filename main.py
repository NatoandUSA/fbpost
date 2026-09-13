import sys
import argparse
import os
import json


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
    group_parser.add_argument("--images", nargs="*", default=None, help="List of image paths")
    group_parser.add_argument("--photos-folder", default=None, help="Folder containing images to pick randomly")
    group_parser.add_argument("--photo-count", default="2-4", help="Number of photos to pick from folder (default: 2-4)")
    group_parser.add_argument("--feeling", action="store_true", help="Add a random feeling to the post")
    group_parser.add_argument("--checkin", action="store_true", help="Add a random check-in location to the post")
    group_parser.add_argument("--auto-spin", action="store_true", help="Automatically spin post content with AI")
    group_parser.add_argument("--gemini-key", default=None, help="Gemini API Key for AI rewriting")
    group_parser.add_argument("--skip-duplicate", action="store_true", help="Skip if posted within 24 hours")
    group_parser.add_argument("--anti-hash-text", action="store_true", default=False, help="Legacy compatibility option; disabled by default")
    group_parser.add_argument("--no-anti-hash-text", dest="anti_hash_text", action="store_false")
    group_parser.add_argument("--clean-exif", action="store_true", default=True, help="Create a metadata-sanitized image copy")
    group_parser.add_argument("--no-clean-exif", dest="clean_exif", action="store_false")
    group_parser.add_argument("--brand-key", default=None, help="Brand key: umee or lacasa")
    
    # Page command
    page_parser = subparsers.add_parser("page", help="Post to a Facebook Page you manage")
    page_parser.add_argument("url", help="The full URL of the Facebook Page")
    page_parser.add_argument("content", help="The text content of your post")
    page_parser.add_argument("--image", help="Absolute path to an image file", default=None)
    page_parser.add_argument("--images", nargs="*", default=None, help="List of image paths")
    page_parser.add_argument("--photos-folder", default=None, help="Folder containing images to pick randomly")
    page_parser.add_argument("--photo-count", default="2-4", help="Number of photos to pick from folder (default: 2-4)")
    page_parser.add_argument("--feeling", action="store_true", help="Add a random feeling to the post")
    page_parser.add_argument("--checkin", action="store_true", help="Add a random check-in location to the post")
    page_parser.add_argument("--auto-spin", action="store_true", help="Automatically spin post content with AI")
    page_parser.add_argument("--gemini-key", default=None, help="Gemini API Key for AI rewriting")
    page_parser.add_argument("--skip-duplicate", action="store_true", help="Skip if posted within 24 hours")
    page_parser.add_argument("--anti-hash-text", action="store_true", default=False, help="Legacy compatibility option; disabled by default")
    page_parser.add_argument("--no-anti-hash-text", dest="anti_hash_text", action="store_false")
    page_parser.add_argument("--clean-exif", action="store_true", default=True, help="Strip EXIF and randomize image pHash")
    page_parser.add_argument("--no-clean-exif", dest="clean_exif", action="store_false")
    page_parser.add_argument("--brand-key", default=None, help="Brand key: umee or lacasa")
    
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
    comment_parser.add_argument("--anti-hash-text", action="store_true", default=False, help="Legacy compatibility option; disabled by default")
    comment_parser.add_argument("--no-anti-hash-text", action="store_false", dest="anti_hash_text", help="Disable anti-hash text")

    # Join-group command
    join_group_parser = subparsers.add_parser("join-group", help="Search and automatically join Facebook groups by keywords")
    join_group_parser.add_argument("--keywords", default="Homestay Huế, Du lịch Huế", help="Comma-separated keywords")
    join_group_parser.add_argument("--limit", type=int, default=2, help="Max groups to join per run (Max 2 per profile)")
    join_group_parser.add_argument("--delay-min", type=int, default=60, help="Min delay between groups in seconds")
    join_group_parser.add_argument("--delay-max", type=int, default=180, help="Max delay between groups in seconds")
    join_group_parser.add_argument("--interact-feed", action="store_true", default=False, help="Optional: interact with group feed")
    join_group_parser.add_argument("--no-interact-feed", action="store_false", dest="interact_feed", help="Disable group feed interaction")
    join_group_parser.add_argument("--auto-rules", action="store_true", default=False, help="Optional: answer/accept group rules when a join dialog requires it")
    join_group_parser.add_argument("--gemini-key", default=None, help="Gemini API Key for AI comment generation")

    # Reconcile an already submitted post without posting again
    reconcile_parser = subparsers.add_parser("reconcile-post", help="Reconcile an existing submitted post without posting again")
    reconcile_parser.add_argument("url", help="Target Group/Page URL")
    reconcile_parser.add_argument("content", help="Original submitted content used for matching")

    # Create-page command
    create_page_parser = subparsers.add_parser("create-page", help="Create a personal Facebook Fanpage with avatar and cover")
    create_page_parser.add_argument("--name", required=True, help="Page name")
    create_page_parser.add_argument("--category", default="Blogger", help="Page category (e.g. Blogger, Khách sạn)")
    create_page_parser.add_argument("--bio", default=None, help="Page bio description")
    create_page_parser.add_argument("--avatar", default=None, help="Path to avatar image file")
    create_page_parser.add_argument("--cover", default=None, help="Path to cover photo image file")

    args = parser.parse_args()
    
    success = True
    if args.command == "auth":
        from fb_auth import login_account
        res = login_account(args.account_id, args.gpm_api)
        success = (res is not False)
    elif args.command == "group":
        from fb_group import post_to_group
        img_arg = args.images if args.images else args.image
        result = post_to_group(
            args.url, args.content, img_arg, args.account_id, args.gpm_api,
            args.feeling, args.checkin,
            photos_folder=args.photos_folder, photo_count=args.photo_count,
            auto_spin=args.auto_spin, gemini_key=args.gemini_key,
            skip_duplicate=args.skip_duplicate,
            anti_hash_text=args.anti_hash_text,
            clean_exif=args.clean_exif,
            brand_key=getattr(args, "brand_key", None)
        )
        if hasattr(result, "to_dict"):
            print("ACTION_RESULT:" + json.dumps(result.to_dict(), ensure_ascii=False))
        success = bool(result)
    elif args.command == "page":
        from fb_page import post_to_page
        img_arg = args.images if args.images else args.image
        result = post_to_page(
            args.url, args.content, img_arg, args.account_id, args.gpm_api,
            args.feeling, args.checkin,
            photos_folder=args.photos_folder, photo_count=args.photo_count,
            auto_spin=args.auto_spin, gemini_key=args.gemini_key,
            skip_duplicate=args.skip_duplicate,
            anti_hash_text=args.anti_hash_text,
            clean_exif=args.clean_exif,
            brand_key=getattr(args, "brand_key", None)
        )
        if hasattr(result, "to_dict"):
            print("ACTION_RESULT:" + json.dumps(result.to_dict(), ensure_ascii=False))
        success = bool(result)
    elif args.command == "thread":
        from fb_thread import send_message
        result = send_message(args.id, args.content, args.image, args.account_id, args.gpm_api)
        if hasattr(result, "to_dict"):
            print("ACTION_RESULT:" + json.dumps(result.to_dict(), ensure_ascii=False))
        success = bool(result)
    elif args.command == "interact":
        from fb_interact import interact_newsfeed
        res = interact_newsfeed(args.limit, args.comments, args.account_id, args.gpm_api)
        if hasattr(res, "to_dict"):
            print("ACTION_RESULT:" + json.dumps(res.to_dict(), ensure_ascii=False))
        success = bool(res)
    elif args.command == "scrape":
        from fb_scraper import scrape_comments
        res = scrape_comments(args.url, args.limit, args.account_id, args.gpm_api)
        if hasattr(res, "to_dict"):
            print("ACTION_RESULT:" + json.dumps(res.to_dict(), ensure_ascii=False))
        success = bool(res)
    elif args.command == "comment":
        from fb_comment import comment_on_post, comment_on_list
        if args.urls_file and os.path.exists(args.urls_file):
            with open(args.urls_file, "r", encoding="utf-8") as f:
                urls = [l.strip() for l in f if l.strip()]
            success = bool(comment_on_list(urls, args.content or "", args.account_id, args.gpm_api, args.like, args.min_delay, args.max_delay, anti_hash_text=args.anti_hash_text))
        elif args.url and args.content:
            result = comment_on_post(args.url, args.content, args.account_id, args.gpm_api, args.like, anti_hash_text=args.anti_hash_text)
            if hasattr(result, "to_dict"):
                print("ACTION_RESULT:" + json.dumps(result.to_dict(), ensure_ascii=False))
            success = bool(result)
        else:
            comment_parser.print_help()
            success = False
    elif args.command == "join-group":
        from fb_join_group import search_and_join_groups
        delay_min = getattr(args, "delay_min", 60)
        delay_max = getattr(args, "delay_max", 180)
        interact_feed = getattr(args, "interact_feed", False)
        gemini_key = getattr(args, "gemini_key", None)
        joined_count = search_and_join_groups(
            args.keywords,
            args.limit,
            args.account_id,
            args.gpm_api,
            delay_min=delay_min,
            delay_max=delay_max,
            interact_feed=interact_feed,
            gemini_key=gemini_key,
            auto_rules=getattr(args, "auto_rules", False)
        )
        success = (joined_count is not None and (joined_count > 0 or getattr(args, 'limit', 1) == 0))
    elif args.command == "reconcile-post":
        from fb_reconcile import reconcile_existing_post
        result = reconcile_existing_post(args.url, args.content, args.account_id, args.gpm_api)
        print("ACTION_RESULT:" + json.dumps(result.to_dict(), ensure_ascii=False))
        success = bool(result)
    elif args.command == "create-page":
        from fb_create_page import create_facebook_page
        result = create_facebook_page(args.name, args.category, args.bio, args.avatar, args.cover, args.account_id, args.gpm_api)
        if hasattr(result, "to_dict"):
            print("ACTION_RESULT:" + json.dumps(result.to_dict(), ensure_ascii=False))
        success = bool(result)
    else:
        parser.print_help()
        success = False

    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
