"""Transactional, fail-closed guards for Facebook composers."""
import re

PAGE_ENTITIES = {
    "umee": {"name": "UMEE Homestay", "handle": "umeehomestay", "url": "https://www.facebook.com/umeehomestay"},
    "lacasa": {"name": "Lacasa Homestay", "handle": "lacasahomestayinvietnam", "url": "https://www.facebook.com/lacasahomestayinvietnam"},
}
URL_RE = re.compile(r"(?i)\b(?:https?://|www\.|fb\.com/|zalo\.me/|maps\.app\.goo\.gl/)[^\s]+")
CTA_RE = re.compile(r"(?i)(?:inbox|nh[aậ]n|li[eê]n\s+h[eệ]|t[iì]m).{0,120}(?:umee|lacasa|homestay|facebook|page|ph[oò]ng)")
TAG_RE = re.compile(r"(?<!\w)#[^\s#]+", re.UNICODE)

def _norm(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()

def dedupe_content_blocks(content):
    """Return the same result on every call; never invent or rewrite prose."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", str(content or "").strip()) if b.strip()]
    seen, seen_tags, out = set(), set(), []
    for block in blocks:
        lines = []
        for line in block.splitlines():
            tags = TAG_RE.findall(line)
            residue = TAG_RE.sub("", line).strip()
            if tags and not residue:
                fresh = [t for t in tags if t.casefold() not in seen_tags]
                seen_tags.update(t.casefold() for t in fresh)
                if fresh:
                    lines.append(" ".join(fresh))
            else:
                lines.append(line.rstrip())
        block = "\n".join(lines).strip()
        key = _norm(block)
        if block and key not in seen:
            seen.add(key)
            out.append(block)
    return "\n\n".join(out).strip()

def audit_final_content(content, brand_key="", linkless=True):
    text = str(content or "").strip()
    clean = dedupe_content_blocks(text)
    issues = []
    if clean != text:
        issues.append("DUPLICATE_BLOCKS")
    if linkless and URL_RE.search(clean):
        issues.append("URL_IN_MAIN_POST")
    for tag in ("#UMEEHomestay", "#LacasaHomestay"):
        if len(re.findall(re.escape(tag), clean, re.I)) > 1:
            issues.append("DUPLICATE_TAG:" + tag)
    ctas = sum(1 for b in re.split(r"\n\s*\n", clean) if CTA_RE.search(b))
    key = str(brand_key or "").strip().casefold()
    entity = PAGE_ENTITIES.get(key)
    if key and entity and entity["name"].casefold() not in clean.casefold():
        issues.append("BRAND_NAME_MISSING")
    if key and ctas != 1:
        issues.append("CTA_COUNT:" + str(ctas))
    return {"pass": not issues, "content": clean, "issues": issues, "cta_count": ctas}

def page_entity(brand_key):
    return PAGE_ENTITIES.get(str(brand_key or "").strip().casefold())
def mention_entity_committed(locator, brand_key):
    entity = page_entity(brand_key)
    if not entity:
        return False
    try:
        if locator.locator(f"a[href*='{entity['handle']}' i]").count():
            return True
        semantic = locator.locator("[contenteditable='false']").filter(
            has_text=re.compile(re.escape(entity["name"]), re.I)
        )
        return bool(semantic.count())
    except Exception:
        return False
