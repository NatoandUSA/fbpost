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

def _local_master(brand, topic, keyword, audience="", user_facts=""):
    ref = load_content_reference(); facts = list((ref.get(brand) or {}).get("facts") or [])
    chosen = facts[:2]
    lead = {"hourly":"C\u1ea7n m\u1ed9t kho\u1ea3ng ngh\u1ec9 linh ho\u1ea1t t\u1ea1i Hu\u1ebf?", "event":"C\u00f3 l\u1ecbch tr\u00ecnh ho\u1eb7c s\u1ef1 ki\u1ec7n \u1edf Hu\u1ebf v\u00e0 c\u1ea7n ch\u1ed7 ngh\u1ec9 ph\u00f9 h\u1ee3p?", "rain":"Nh\u1eefng ng\u00e0y Hu\u1ebf c\u00f3 m\u01b0a, m\u1ed9t ch\u1ed7 ngh\u1ec9 thu\u1eadn ti\u1ec7n gi\u00fap l\u1ecbch tr\u00ecnh nh\u1eb9 nh\u00e0ng h\u01a1n.", "hue_info":"\u0110ang l\u00ean l\u1ecbch kh\u00e1m ph\u00e1 Hu\u1ebf v\u00e0 mu\u1ed1n th\u00f4ng tin r\u00f5 r\u00e0ng tr\u01b0\u1edbc chuy\u1ebfn \u0111i?"}.get(topic, "\u0110ang t\u00ecm m\u1ed9t homestay Hu\u1ebf v\u1edbi th\u00f4ng tin r\u00f5 r\u00e0ng, d\u1ec5 c\u00e2n nh\u1eafc?")
    fact_lines = "\n".join(f"\u2022 {x}" for x in chosen)
    live = f"\n\u2022 {user_facts.strip()}" if user_facts.strip() else ""
    name = "UMEE Homestay" if brand == "umee" else "Lacasa Homestay"
    return f"{lead}\n\n{name} g\u1eedi b\u1ea1n v\u00e0i th\u00f4ng tin \u0111\u00e3 \u0111\u01b0\u1ee3c x\u00e1c nh\u1eadn:\n{fact_lines}{live}\n\nN\u1ebfu b\u1ea1n \u0111ang t\u00ecm theo nhu c\u1ea7u '{keyword}', h\u00e3y nh\u1eafn \u0111\u1ec3 \u0111\u01b0\u1ee3c ki\u1ec3m tra th\u00f4ng tin ph\u00f9 h\u1ee3p v\u1edbi l\u1ecbch tr\u00ecnh th\u1ef1c t\u1ebf c\u1ee7a b\u1ea1n."

def generate_master(brand, topic, keyword, api_keys, audience="", angle="", user_facts="", seed=""):
    brand = str(brand or "").strip().lower()
    if brand not in ("umee", "lacasa"):
        raise ValueError("Project phải là UMEE hoặc Lacasa")
    if topic not in TOPICS:
        raise ValueError("Chủ đề không hợp lệ")
    if not str(keyword or "").strip():
        raise ValueError("Keyword/search intent là bắt buộc")
    prompt = _prompt(brand, topic, keyword, audience, angle, user_facts, seed)
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
    fallback = _local_master(brand, topic, keyword, audience, user_facts)
    return {"content": fallback, "mode": "content_hub_fallback", "model": "local-truth-template", "key_slot": 0, "truth_pass": True, "error": "; ".join(errors[-6:])}

def generate_with_quality(brand, topic, keyword, api_keys, history=None, audience="", angle="", user_facts="", attempts=4):
    """Generate until Truth + similarity gates pass. Never weakens the gate to force a result."""
    history = list(history or [])[-200:]
    rejected = []
    for attempt in range(max(1, min(int(attempts), 8))):
        seed = hashlib.sha256(f"{brand}|{topic}|{keyword}|{len(history)}|{attempt}".encode()).hexdigest()[:12]
        result = generate_master(brand, topic, keyword, api_keys, audience, angle, user_facts, seed)
        gate = similarity_gate(result["content"], history)
        result["similarity"] = gate
        result["score"] = score_content(result["content"], keyword, result.get("truth_pass", False))
        if gate["pass"]:
            return result
        rejected.append(gate["max_similarity"])
    raise RuntimeError(f"Similarity Gate từ chối {len(rejected)} candidate; max={max(rejected, default=0):.2f}")

def topic_catalog():
    return [{"id": key, "label": value} for key, value in TOPICS.items()]
