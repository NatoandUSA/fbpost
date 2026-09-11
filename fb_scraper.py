import os
import re
import json
import time
from playwright.sync_api import sync_playwright
from paths import DATA_DIR
from utils import ActionResult, resolve_account, launch_browser, close_browser
from fb_comment import _canonicalize_comment_url, _locate_target_post_article, _comment_search_roots

STATE_FILE = str(DATA_DIR / 'state.json')

def extract_phone(text):
    m=re.search(r'\b(0[35789]\d{8}|0[35789]\d{2}[.\s-]?\d{3}[.\s-]?\d{3})\b',text or '')
    return re.sub(r'\D','',m.group(1)) if m else None

def _extract_comment_rows(scope, limit):
    script = r'''(root, maxRows) => {
      const out=[]; const seen=new Set();
      const arts=[...root.querySelectorAll('div[role="article"]')];
      for (const art of arts) {
        if (out.length>=maxRows) break;
        const text=(art.innerText||'').trim(); if(!text||text.length<2) continue;
        const links=[...art.querySelectorAll('a[role="link"],a')]; let name='',profileUrl='';
        const isComment=links.some(a=>(a.href||'').includes('comment_id=')); if(!isComment) continue;
        for(const a of links){const href=a.href||'',t=(a.innerText||'').trim(); if(!t||!href||href.includes('/posts/')||href.includes('/permalink/'))continue; if(href.includes('facebook.com/')){name=t;profileUrl=href;break;}}
        if(!name)continue; const key=name+'|'+text.slice(0,120); if(seen.has(key))continue; seen.add(key); out.push({name,profileUrl,text});
      } return out;
    }'''
    try: return scope.evaluate(script, int(limit)) or []
    except Exception: return []

def scrape_comments(post_url, max_comments=50, account_id=None, gpm_api_url=None):
    canonical=_canonicalize_comment_url(post_url)
    if not canonical: return ActionResult(False,'INVALID_POST_URL','Chỉ quét từ permalink bài viết cụ thể.',target_url=post_url)
    limit=max(1,min(int(max_comments),200)); account=resolve_account(account_id,gpm_api_url) if account_id else None
    if account_id and not account: return ActionResult(False,'ACCOUNT_NOT_FOUND',f'Không tìm thấy profile {account_id}.',target_url=canonical)
    browser_obj=context=None
    try:
      with sync_playwright() as p:
        if account: browser_obj,context,page=launch_browser(account,p,gpm_api_url)
        else:
          browser_obj=p.chromium.launch(headless=False); context=browser_obj.new_context(storage_state=STATE_FILE if os.path.exists(STATE_FILE) else None); page=context.new_page()
        page.set_default_timeout(30000); page.goto(canonical,wait_until='domcontentloaded',timeout=45000); time.sleep(3)
        scope=_locate_target_post_article(page,canonical)
        if scope is None: return ActionResult(False,'POST_IDENTITY_NOT_FOUND','Không khóa được DOM vào đúng bài viết.',state='unverified',target_url=canonical)
        for _ in range(6):
          try:
            roots=_comment_search_roots(page,scope,canonical)
            comment_scope=roots[-1]
            b=comment_scope.locator("span,div[role='button']").filter(has_text=re.compile(r'View more comments|Xem thêm bình luận|Xem thêm phản hồi|Xem tất cả bình luận',re.I)).first
            if not b.is_visible(timeout=600): break
            b.click(); time.sleep(1)
          except Exception: break
        roots=_comment_search_roots(page,scope,canonical)
        comment_scope=roots[-1]
        rows=_extract_comment_rows(comment_scope,limit)[:limit]; data=[]
        for item in rows:
          profile=(item.get('profileUrl') or '').split('?',1)[0]; text=item.get('text','')
          data.append({'name':item.get('name',''),'profile':profile,'comment':text,'phone':extract_phone(text) or 'Không có'})
        print(f'✅ SCRAPE_VERIFIED: {len(data)}/{limit} comment rows trong đúng post scope.'); print('JSON_DATA:'+json.dumps(data,ensure_ascii=False))
        return ActionResult(True,'SCRAPE_VERIFIED',f'Đã quét {len(data)} bình luận trong đúng bài viết.',state='scraped',target_url=canonical,result_url=canonical,metadata={'rows':data,'count':len(data),'limit':limit})
    except Exception as exc: return ActionResult(False,'SCRAPE_ERROR',str(exc),state='failed',target_url=canonical)
    finally:
      if account: close_browser(browser_obj if browser_obj else context,account,gpm_api_url)
      elif browser_obj:
        try: browser_obj.close()
        except Exception: pass

if __name__=='__main__':
 import argparse,sys
 ap=argparse.ArgumentParser(); ap.add_argument('url'); ap.add_argument('--limit',type=int,default=50); ap.add_argument('--account-id'); ap.add_argument('--gpm-api'); a=ap.parse_args(); r=scrape_comments(a.url,a.limit,a.account_id,a.gpm_api); print('ACTION_RESULT:'+json.dumps(r.to_dict(),ensure_ascii=False)); sys.exit(0 if r else 1)
