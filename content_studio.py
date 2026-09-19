"""v6.1.22 Content Studio: intent-led, truth-gated Facebook content generation."""
import json, re, hashlib
from difflib import SequenceMatcher
from ai_spinner import (content_reference_context, load_content_reference, parse_gemini_keys,
                        _ordered_available_keys, _cooldown_key, _urlopen_json,
                        GEMINI_MODEL, GEMINI_FALLBACK_MODELS, clean_ai_output,
                        _preserves_core_info)
import urllib.request, urllib.error

TOPICS = {
    "room_sale": "Bán phòng",
    "hourly": "Bán phòng theo giờ",
    "event": "Bán phòng theo sự kiện",
    "rain": "Bán phòng mùa mưa",
    "hue_info": "Thông tin / du lịch Huế",
    "food": "Ẩm thực Huế",
    "place": "Địa điểm Huế",
    "custom": "Chủ đề tùy chỉnh",
}

def normalize_text(text):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", str(text or "").casefold())).strip()

def similarity(a, b):
    return round(SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio(), 4)

def similarity_projection(text):
    """Project a post to its variable semantic body for duplicate-content comparison.

    Canonical signatures, CTA blocks and hashtags are intentionally excluded because they are
    required/controlled boilerplate. This keeps the existing similarity threshold meaningful
    without allowing identical bodies through merely by changing a footer.
    """
    from brand_profiles import prepare_linkless_post
    from composer_guard import CTA_RE, TAG_RE

    clean = prepare_linkless_post(text or "")
    blocks = [b.strip() for b in re.split(r"\n\s*\n", clean) if b.strip()]
    variable_blocks = []
    for block in blocks:
        if CTA_RE.search(block):
            continue
        stripped = TAG_RE.sub("", block).strip()
        if stripped:
            variable_blocks.append(stripped)
    projected = "\n\n".join(variable_blocks)
    projected = re.sub(r"[ \t]+\n", "\n", projected)
    projected = re.sub(r"\n{3,}", "\n\n", projected)
    return projected.strip()


def similarity_gate(candidate, history, threshold=0.82):
    scores = [similarity(candidate, old) for old in (history or []) if old]
    peak = max(scores, default=0.0)
    return {"pass": peak < threshold, "max_similarity": peak, "threshold": threshold}

def score_content(text, keyword, truth_ok=True):
    low = str(text or "").casefold(); kw = str(keyword or "").strip().casefold()
    intent = 25 if kw and kw in low else (18 if kw else 20)
    readability = 15 if 250 <= len(text) <= 1800 else 10
    local = 15 if "huế" in low else 8
    conversion = 15 if any(x in low for x in ("inbox", "nhắn", "đặt", "liên hệ")) else 8
    semantic = 20 if len(set(normalize_text(text).split())) >= 45 else 14
    truth = 10 if truth_ok else 0
    return min(100, intent + readability + local + conversion + semantic + truth)

def _prompt(brand, topic, keyword, audience, angle, user_facts, seed):
    truth = content_reference_context(brand)
    return f"""Bạn là Facebook content writer tại Huế. Viết MỘT bài hoàn chỉnh, tự nhiên, hữu ích.
PROJECT: {brand}; TOPIC: {TOPICS.get(topic, TOPICS['custom'])}; KEYWORD/SEARCH INTENT: {keyword}
AUDIENCE: {audience or 'khách đang tìm lưu trú tại Huế'}; ANGLE: {angle or 'tự nhiên, hữu ích'}; VARIANT SEED: {seed}
USER VERIFIED LIVE FACTS (chỉ dùng nếu có): {user_facts or 'NONE'}
{truth}
QUY TẮC TRUTH GATE: chỉ dùng facts ở trên hoặc USER VERIFIED LIVE FACTS. Không tự bịa giá, phòng trống,
khuyến mãi, thời tiết, lịch/giờ/địa điểm sự kiện, khoảng cách, tiện nghi. Không claim tốt nhất/rẻ nhất.
Không đặt URL trong thân bài. Keyword dùng tự nhiên, không nhồi. Có hook khác biệt, đoạn ngắn dễ đọc, CTA phù hợp.
Không lặp nguyên một đoạn. Chỉ trả nội dung bài Facebook, không markdown giải thích."""

def _local_master(brand, topic, keyword, audience="", angle="", user_facts="", tone="natural", length="medium", cta="message"):
    """Human-readable truth-safe fallback; no synthetic labels or filler prose."""
    ref = load_content_reference(); facts = list((ref.get(brand) or {}).get("facts") or [])
    limit = 1 if length == "short" else (3 if length == "long" else 2)
    chosen = facts[:limit]
    leads = {"hourly":"Cần một khoảng nghỉ linh hoạt tại Huế?", "event":"Có lịch trình hoặc sự kiện ở Huế và cần chỗ nghỉ phù hợp?", "rain":"Những ngày Huế có mưa, một chỗ nghỉ thuận tiện giúp lịch trình nhẹ nhàng hơn.", "hue_info":"Đang lên lịch khám phá Huế và muốn thông tin rõ ràng trước chuyến đi?"}
    lead = leads.get(topic, "Đang tìm một homestay Huế với thông tin rõ ràng, dễ cân nhắc?")
    if audience:
        lead = f"{lead} Gợi ý này dành cho {audience.strip()}."
    fact_lines = "\n".join(f"• {x}" for x in chosen)
    live = f"\n• {user_facts.strip()}" if user_facts.strip() else ""
    name = "UMEE Homestay" if brand == "umee" else "Lacasa Homestay"
    ctas = {"question":"Bạn đang ưu tiên điều gì nhất cho chuyến đi Huế lần này?", "save":"Bạn có thể lưu lại để đối chiếu khi lên lịch Huế.", "soft":"Nếu thấy phù hợp, bạn có thể nhắn để kiểm tra thông tin thực tế.", "message":"Nếu cần kiểm tra thông tin phù hợp với lịch trình thực tế, hãy nhắn để được xác nhận."}
    return f"{lead}\n\n{name} gửi bạn vài thông tin đã được xác nhận:\n{fact_lines}{live}\n\n{ctas.get(cta, ctas['message'])}"

def generate_master(brand, topic, keyword, api_keys, audience="", angle="", user_facts="", seed="", tone="natural", length="medium", cta="message"):
    brand = str(brand or "").strip().lower()
    if brand not in ("umee", "lacasa"):
        raise ValueError("Project phải là UMEE hoặc Lacasa")
    if topic not in TOPICS:
        raise ValueError("Chủ đề không hợp lệ")
    if not str(keyword or "").strip():
        raise ValueError("Keyword/search intent là bắt buộc")
    prompt = _prompt(brand, topic, keyword, audience, angle, user_facts, seed) + f"\nWRITING OPTIONS: tone={tone}; length={length}; cta={cta}. Follow these options unless they conflict with Truth Gate."
    keys = _ordered_available_keys(api_keys)
    errors = []
    for slot, key in enumerate(keys, 1):
        for model in (GEMINI_MODEL,) + GEMINI_FALLBACK_MODELS:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                payload = {"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"maxOutputTokens":1200,"temperature":0.9}}
                req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type":"application/json","x-goog-api-key":key})
                raw = _urlopen_json(req, timeout=25, attempts=1)
                text = clean_ai_output(raw["candidates"][0]["content"]["parts"][0]["text"])
                truth = content_reference_context(brand) + "\n" + str(user_facts or "")
                if not text or not _preserves_core_info("", text, brand_key=brand, truth_context=truth):
                    raise ValueError("Truth Gate rejected generated content")
                return {"content":text,"mode":"gemini","model":model,"key_slot":slot,"truth_pass":True}
            except urllib.error.HTTPError as exc:
                errors.append(f"key#{slot}/{model}: HTTP {exc.code}")
                if exc.code in (429,403): _cooldown_key(key, 120 if exc.code == 429 else 300)
                break
            except Exception as exc:
                errors.append(f"key#{slot}/{model}: {exc}")
    fallback = _local_master(brand, topic, keyword, audience, angle, user_facts, tone, length, cta)
    return {"content": fallback, "mode": "content_hub_fallback", "model": "local-truth-template", "key_slot": 0, "truth_pass": True, "error": "; ".join(errors[-6:])}

def generate_with_quality(brand, topic, keyword, api_keys, history=None, audience="", angle="", user_facts="", attempts=4, tone="natural", length="medium", cta="message"):
    """Generate until Truth + similarity gates pass. Never weakens the gate to force a result."""
    history = list(history or [])[-200:]
    rejected = []
    for attempt in range(max(1, min(int(attempts), 8))):
        seed = hashlib.sha256(f"{brand}|{topic}|{keyword}|{len(history)}|{attempt}".encode()).hexdigest()[:12]
        result = generate_master(brand, topic, keyword, api_keys, audience, angle, user_facts, seed, tone, length, cta)
        gate = similarity_gate(result["content"], history)
        result["similarity"] = gate
        result["score"] = score_content(result["content"], keyword, result.get("truth_pass", False))
        if gate["pass"]:
            return result
        rejected.append(gate["max_similarity"])
    raise RuntimeError(f"Similarity Gate từ chối {len(rejected)} candidate; max={max(rejected, default=0):.2f}")

def topic_catalog():
    return [{"id": key, "label": value} for key, value in TOPICS.items()]

def writing_option_catalog():
    return {
        "tone": [{"id":"natural","label":"Tự nhiên"},{"id":"friendly","label":"Thân thiện"},{"id":"concise","label":"Ngắn gọn"},{"id":"story","label":"Kể chuyện"}],
        "length": [{"id":"short","label":"Ngắn"},{"id":"medium","label":"Vừa"},{"id":"long","label":"Dài"}],
        "cta": [{"id":"message","label":"Nhắn tin tư vấn"},{"id":"question","label":"Đặt câu hỏi"},{"id":"save","label":"Gợi ý lưu bài"},{"id":"soft","label":"CTA nhẹ"}],
    }
