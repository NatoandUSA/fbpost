import os
import re
import time
from datetime import datetime
from playwright.sync_api import sync_playwright
from paths import DATA_DIR, LOG_DIR
from utils import ActionResult, human_type, process_spintax, resolve_account, launch_browser, close_browser

STATE_FILE = str(DATA_DIR / "state.json")

def _save_evidence(page, code):
    try:
        out_dir = LOG_DIR / "evidence"; out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"thread_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{code}.png"
        page.screenshot(path=str(out), full_page=False); return str(out)
    except Exception: return ""

def _thread_url(value):
    value = str(value or "").strip()
    if not value: return ""
    if value.startswith("http"):
        m = re.search(r"(?:messenger\.com|facebook\.com)/(?:t|messages/t)/([^/?#]+)", value, re.I)
        return f"https://www.messenger.com/t/{m.group(1)}" if m else ""
    if re.fullmatch(r"[A-Za-z0-9._-]{2,120}", value):
        return f"https://www.messenger.com/t/{value}"
    return ""

def _find_message_box(page):
    try: scope = page.locator("div[role='main']")
    except Exception: return None
    selectors = ["div[role='textbox'][contenteditable='true']", "div[contenteditable='true'][data-lexical-editor='true']"]
    rejects = ("tìm kiếm", "search", "bình luận", "comment")
    for _ in range(10):
        for sel in selectors:
            try:
                items = scope.locator(sel)
                for i in range(min(items.count(), 12)):
                    el=items.nth(i)
                    if not el.is_visible(timeout=250): continue
                    label=((el.get_attribute("aria-label") or "")+" "+(el.get_attribute("aria-placeholder") or "")).lower()
                    if not any(x in label for x in rejects): return el
            except Exception: pass
        try: page.wait_for_timeout(600)
        except Exception: time.sleep(.6)
    return None

def send_message(thread_id, content, image_path=None, account_id=None, gpm_api_url=None):
    url=_thread_url(thread_id)
    if not url: return ActionResult(False,"INVALID_THREAD","Thread ID/URL không hợp lệ.",target_url=str(thread_id or ""))
    content=process_spintax(content)
    if not content and not image_path: return ActionResult(False,"EMPTY_MESSAGE","Tin nhắn trống.",target_url=url)
    account=resolve_account(account_id,gpm_api_url) if account_id else None
    if account_id and not account: return ActionResult(False,"ACCOUNT_NOT_FOUND",f"Không tìm thấy profile {account_id}.",target_url=url)
    browser_obj=context=None; submitted=False
    try:
        with sync_playwright() as p:
            if account: browser_obj,context,page=launch_browser(account,p,gpm_api_url)
            else:
                browser_obj=p.chromium.launch(headless=False); context=browser_obj.new_context(storage_state=STATE_FILE if os.path.exists(STATE_FILE) else None); page=context.new_page()
            page.set_default_timeout(30000); page.goto(url,wait_until="domcontentloaded",timeout=45000)
            time.sleep(2)
            if "/t/" not in (page.url or "") and "/messages/t/" not in (page.url or ""):
                return ActionResult(False,"THREAD_IDENTITY_NOT_FOUND","Không khóa được đúng cuộc trò chuyện.",target_url=url)
            box=_find_message_box(page)
            if box is None: return ActionResult(False,"MESSAGE_INPUT_NOT_FOUND","Không tìm thấy ô nhập tin nhắn trong conversation scope.",target_url=url)
            if image_path:
                if not os.path.exists(image_path): return ActionResult(False,"MESSAGE_ATTACH_FAILED","File ảnh không tồn tại.",target_url=url)
                try:
                    fi=page.locator("div[role='main'] input[type='file'][accept*='image']").first
                    fi.set_input_files(image_path); page.wait_for_timeout(1500)
                except Exception as exc: return ActionResult(False,"MESSAGE_ATTACH_FAILED",str(exc),target_url=url)
            if content:
                human_type(page,box,content)
                try:
                    typed=(box.inner_text() or "").strip()
                    if content[:30] not in typed and typed not in content: return ActionResult(False,"MESSAGE_ENTRY_INCOMPLETE","Nội dung trong composer không khớp.",target_url=url)
                except Exception: pass
            page.keyboard.press("Enter"); submitted=True
            deadline=time.time()+12; verified=False
            snippet=re.sub(r"\s+"," ",content).strip()[:45]
            while time.time()<deadline:
                try:
                    main=page.locator("div[role='main']")
                    if snippet and main.get_by_text(snippet, exact=False).count()>0:
                        candidates=main.get_by_text(snippet,exact=False)
                        if any(candidates.nth(i).is_visible(timeout=250) for i in range(min(candidates.count(),10))): verified=True; break
                except Exception: pass
                time.sleep(.7)
            evidence=_save_evidence(page,"MESSAGE_VERIFIED" if verified else "MESSAGE_UNVERIFIED")
            if verified: return ActionResult(True,"MESSAGE_VERIFIED","Tin nhắn đã gửi và xác minh trong đúng conversation.",state="messaged",target_url=url,result_url=page.url,metadata={"evidence_path":evidence})
            return ActionResult(False,"MESSAGE_UNVERIFIED","Đã trigger gửi nhưng chưa xác minh được tin nhắn trong conversation.",state="unverified",target_url=url,result_url=page.url,metadata={"evidence_path":evidence})
    except Exception as exc:
        return ActionResult(False,"MESSAGE_UNVERIFIED" if submitted else "ERROR",str(exc),state="unverified" if submitted else "failed",target_url=url)
    finally:
        if account: close_browser(browser_obj if browser_obj else context,account,gpm_api_url)
        elif browser_obj:
            try: browser_obj.close()
            except Exception: pass

if __name__ == "__main__":
    import argparse,sys,json
    ap=argparse.ArgumentParser(); ap.add_argument("id"); ap.add_argument("content"); ap.add_argument("--image"); ap.add_argument("--account-id"); ap.add_argument("--gpm-api")
    a=ap.parse_args(); r=send_message(a.id,a.content,a.image,a.account_id,a.gpm_api); print("ACTION_RESULT:"+json.dumps(r.to_dict(),ensure_ascii=False)); sys.exit(0 if r else 1)
