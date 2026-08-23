import requests
import json
from utils import process_spintax

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"

def validate_token(page_access_token):
    """Check if the token is valid and return page info."""
    try:
        resp = requests.get(
            f"{GRAPH_API_BASE}/me",
            params={"access_token": page_access_token, "fields": "id,name"},
            timeout=10
        )
        data = resp.json()
        if "error" in data:
            return False, data["error"].get("message", "Token không hợp lệ")
        return True, data
    except Exception as e:
        return False, str(e)

def exchange_long_lived_token(short_token, app_id, app_secret):
    """
    Exchange a short-lived token for a long-lived token (~60 days).
    Then use that to get a permanent Page Access Token.
    """
    try:
        # Step 1: Get long-lived user token
        resp = requests.get(
            f"{GRAPH_API_BASE}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": app_secret,
                "fb_exchange_token": short_token,
            },
            timeout=10
        )
        data = resp.json()
        if "error" in data:
            return False, data["error"].get("message", "Lỗi đổi token")
        
        long_lived_user_token = data.get("access_token")
        
        # Step 2: Get permanent Page Access Token from long-lived user token
        resp2 = requests.get(
            f"{GRAPH_API_BASE}/me/accounts",
            params={"access_token": long_lived_user_token},
            timeout=10
        )
        pages = resp2.json()
        if "error" in pages:
            return False, pages["error"].get("message", "Không lấy được Page token")
        
        return True, pages.get("data", [])
    except Exception as e:
        return False, str(e)

def post_to_page(page_id, page_access_token, content, image_url=None):
    """
    Post a message (with optional image) to a Facebook Page via Graph API.
    Returns (success: bool, response: dict)
    """
    # Process spintax before posting
    content = process_spintax(content)
    
    try:
        if image_url and image_url.strip():
            # Post with image (photo post)
            url = f"{GRAPH_API_BASE}/{page_id}/photos"
            payload = {
                "url": image_url.strip(),
                "caption": content,
                "access_token": page_access_token,
            }
        else:
            # Plain text post
            url = f"{GRAPH_API_BASE}/{page_id}/feed"
            payload = {
                "message": content,
                "access_token": page_access_token,
            }
        
        resp = requests.post(url, data=payload, timeout=30)
        data = resp.json()
        
        if "error" in data:
            return False, data["error"].get("message", "Lỗi không xác định từ Facebook API")
        
        post_id = data.get("id") or data.get("post_id")
        return True, {"post_id": post_id, "content_preview": content[:80]}
    
    except Exception as e:
        return False, str(e)
