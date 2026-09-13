# -*- coding: utf-8 -*-
"""
ai_spinner.py - Module Xào Bài Viết Tự Động (AI Content Spinner)
Hỗ trợ:
1. Gemini AI Online: dùng model được cấu hình để viết lại nội dung theo truth contract.
2. Local fallback: chuẩn hóa an toàn và resolve spintax mà không tự thêm facts.
"""

import os
import re
import random
import json
import urllib.request
import urllib.error
import time as _time

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip() or "gemini-3.5-flash"
GEMINI_FALLBACK_MODELS = tuple(
    model.strip() for model in os.getenv(
        "GEMINI_FALLBACK_MODELS", "gemini-3.1-flash-lite"
    ).split(",") if model.strip()
)
CONTENT_REFERENCE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content_reference.json")

PHONE_RE = re.compile(r"(?<!\d)(?:\+?84|0)(?:[ .-]*\d){9,10}(?!\d)")


def _phone_digits(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    return "0" + digits[2:] if digits.startswith("84") else digits


def _without_phone_spans(value: str) -> str:
    return PHONE_RE.sub(" ", value or "")


def load_content_reference() -> dict:
    """Load the audited Content Hub facts. Missing/invalid data fails closed to an empty reference."""
    try:
        with open(CONTENT_REFERENCE_FILE, "r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def content_reference_context(brand_key: str = "") -> str:
    reference = load_content_reference()
    common = reference.get("global") or {}
    brand = reference.get((brand_key or "").strip().lower()) or {}
    facts = list(common.get("stable_facts") or []) + list(brand.get("facts") or [])
    rules = list(common.get("dynamic_rules") or []) + list(brand.get("rules") or [])
    if not facts and not rules:
        return ""
    source = reference.get("source") or {}
    return (
        f"CONTENT HUB REFERENCE [{source.get('knowledge_updated', 'unknown')} | {source.get('sha256', 'no-hash')}]:\n"
        + "\n".join(f"- FACT: {item}" for item in facts)
        + "\n"
        + "\n".join(f"- RULE: {item}" for item in rules)
    )


def _content_hub_numbers(brand_key: str = None) -> set:
    reference = load_content_reference()
    common = reference.get("global") or {}
    facts = list(common.get("stable_facts") or [])
    if brand_key:
        brand = reference.get(str(brand_key).strip().lower()) or {}
        facts.extend(brand.get("facts") or [])
    else:
        for key in ("lacasa", "umee"):
            facts.extend(reference.get(key, {}).get("facts") or [])
    text = " ".join(facts)
    return set(re.findall(r"\b\d+(?:[.,]\d+)?\b", _without_phone_spans(text)))


def _preserves_core_info(original: str, generated: str, brand_key: str = None) -> bool:
    """Reject AI output that drops phone/price/link/address invariants from the source."""
    src = extract_core_info(original)
    dst = generated or ""
    required = src["prices"] + src["links"]
    if any(value not in dst for value in required):
        return False
    dst_phones = {_phone_digits(value) for value in PHONE_RE.findall(dst)}
    if any(_phone_digits(value) not in dst_phones for value in src["phones"]):
        return False
    for address in src["addresses"]:
        key = address.split(":", 1)[-1].strip()
        if key and key not in dst:
            return False
    # AI is allowed to rephrase, never to manufacture dynamic facts.
    src_numbers = set(re.findall(r"\b\d+(?:[.,]\d+)?\b", _without_phone_spans(original)))
    dst_numbers = set(re.findall(r"\b\d+(?:[.,]\d+)?\b", _without_phone_spans(dst)))
    allowed_numbers = src_numbers | _content_hub_numbers(brand_key)
    if not dst_numbers.issubset(allowed_numbers):
        return False
    risky = ("rẻ nhất", "tốt nhất hôm nay", "phòng có hạn", "voucher", "giảm giá đặc biệt", "chỉ mất vài phút")
    src_low, dst_low = (original or "").casefold(), dst.casefold()
    if any(term in dst_low and term not in src_low for term in risky):
        return False
    return True

def _urlopen_json(req, timeout=20, attempts=3):
    last = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt + 1 < attempts:
                _time.sleep(1.5 * (attempt + 1))
    raise last or RuntimeError("Gemini request failed")

def extract_core_info(content: str) -> dict:
    """
    Trích xuất các thông tin cốt lõi quan trọng: SĐT, Zalo, Địa chỉ, Giá phòng, Link từ bài viết gốc
    để đảm bảo dù xào bài thế nào cũng không bị mất thông tin liên hệ.
    """
    phones = []
    seen_phones = set()
    for match in PHONE_RE.findall(content or ""):
        normalized = _phone_digits(match)
        if normalized not in seen_phones:
            phones.append(match.strip())
            seen_phones.add(normalized)
    prices = re.findall(r'\b\d+(?:[.,]\d+)?\s*(?:k|vnđ|vnd|đ|triệu|k/đêm|k/ngày)\b', content, re.IGNORECASE)
    links = re.findall(r'https?://[^\s]+', content)
    
    # Tìm dòng chứa địa chỉ
    addresses = []
    for line in content.split('\n'):
        if any(kw in line.lower() for kw in ['địa chỉ:', 'đc:', 'address:', 'tại:']):
            addresses.append(line.strip())
            
    return {
        "phones": phones,
        "prices": list(set(prices)),
        "links": list(set(links)),
        "addresses": addresses
    }


def spin_content_local(content: str) -> str:
    """Truth-preserving offline fallback: never invent facts absent from source."""
    if not content or not content.strip():
        return content
    # Resolve explicit {choice A|choice B} syntax without inventing facts.
    resolved = content
    choice_re = re.compile(r"\{([^{}]*\|[^{}]*)\}")
    def choose_existing_option(match):
        options = [part.strip() for part in match.group(1).split("|") if part.strip()]
        return random.choice(options) if options else match.group(0)

    for _ in range(8):
        resolved, count = choice_re.subn(choose_existing_option, resolved)
        if not count:
            break
    lines=[line.rstrip() for line in resolved.strip().splitlines()]
    out=[]; blank=False
    for line in lines:
        if not line.strip():
            if out and not blank: out.append("")
            blank=True
        else:
            out.append(line.strip()); blank=False
    # Styling-only variation is allowed; hashtags below make no new factual claim.
    lowered = (resolved or "").casefold()
    tags = []
    if "huế" in lowered: tags.append("#Hue")
    if "homestay" in lowered and "huế" in lowered: tags.append("#HomestayHue")
    if tags and not any("#" in line for line in out):
        out.extend(["", " ".join(tags)])
    return "\n".join(out).strip()


def _gemini_models():
    return tuple(dict.fromkeys((GEMINI_MODEL,) + GEMINI_FALLBACK_MODELS))


def _resolve_gemini_api_key(api_key: str = None) -> str:
    key = (api_key or "").strip()
    if not key or key.startswith("***REDACTED") or key.endswith("***"):
        try:
            from server import load_config
            key = str(load_config().get("gemini_api_key") or "").strip()
        except Exception:
            try:
                from repositories.settings_repo import SettingsRepository
                key = str(SettingsRepository().get_config().get("gemini_api_key") or "").strip()
            except Exception:
                key = ""
    return key


def clean_ai_output(text: str) -> str:
    """Lọc sạch lời mở đầu/suy nghĩ của Gemini và bỏ dấu markdown ** để hiển thị sạch trên Facebook."""
    if not text:
        return text
    # 1. Bỏ toàn bộ dòng mở đầu/suy nghĩ/dẫn giải của Gemini (Refinement, Here is, Dưới đây là, v.v.)
    cleaned = re.sub(
        r'^(?:\*{0,2}(?:Refinement|Refined|Version|Phiên bản|Dưới đây là|Here is|Note)[^\n]*\n+)+',
        '', text.strip(), flags=re.IGNORECASE
    )
    # 2. Xóa bỏ dấu sao kép markdown **bold** để không bị lộ dấu ** trên Facebook
    cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned)
    return cleaned.strip()


def spin_content_gemini_with_model(content: str, api_key: str, style: str = "tự nhiên", brand_name: str = "", truth_context: str = "", brand_key: str = None) -> tuple:
    """
    Xào bài viết qua Google Gemini API (Online).
    Tạo ra bài viết độc nhất 100%, câu cú mượt mà, hấp dẫn và giữ nguyên dữ liệu gốc.
    """
    api_key = _resolve_gemini_api_key(api_key)
    if not api_key:
        raise ValueError("Chưa cung cấp Gemini API Key.")
        
    brand_fb_links = {
        "lacasa": "fb.com/lacasahomestayinvietnam",
        "umee": "fb.com/umeehomestay"
    }
    fb_link = brand_fb_links.get(str(brand_key or "").strip().lower(), "")
    tag_instruction = ""
    if brand_name:
        link_str = f" kèm link Page trực tiếp ({fb_link})" if fb_link else ""
        tag_instruction = (
            f"Thương hiệu/Project lưu trú là: {brand_name}. "
            f"BẮT BUỘC phải nhắc đến tên {brand_name}{link_str} tự nhiên và nổi bật ngay trong lời mở đầu và lời kêu gọi đặt phòng ở thân bài.\n"
            f"- KHÔNG dùng dấu sao đôi ** để in đậm (Facebook không hỗ trợ markdown **, sẽ bị lộ dấu ** trên bài). Hãy viết hoa hoặc dùng emoji tự nhiên.\n"
        )

    prompt = (
        f"Bạn là một chuyên gia sáng tạo nội dung mạng xã hội (Facebook Copywriter) chuyên ngành Homestay, Du lịch và Bất động sản tại Huế.\n"
        + tag_instruction
        + f"Hãy viết lại bài đăng Facebook sau đây với văn phong {style}, nhưng chỉ diễn đạt lại dữ liệu đã có, "
        f"sử dụng các biểu cảm emoji sinh động, bố cục thoáng đãng và có lời kêu gọi hành động thu hút.\n\n"
        f"YÊU CẦU BẮT BUỘC — CONTENT HUB TRUTH CONTRACT:\n"
        f"- KHÔNG thêm tiện nghi, khoảng cách, thời gian di chuyển, giá, số phòng trống, khuyến mãi, voucher, sự kiện hoặc lời hứa không có trong bài gốc.\n"
        f"- Giữ nguyên toàn bộ số điện thoại, Zalo, địa chỉ, giá phòng hoặc link nếu có trong bài gốc.\n"
        f"- Không dùng claim rẻ nhất/tốt nhất hôm nay/phòng có hạn/chỉ vài phút nếu bài gốc không có dữ liệu đó.\n"
        f"- Được đổi câu chữ và thứ tự đoạn; KHÔNG thay đổi nghĩa của facts.\n"
        f"- Viết bằng Tiếng Việt tự nhiên, phù hợp đăng nhóm cộng đồng hoặc fanpage.\n"
        f"- KHÔNG thêm bất kỳ lời dẫn giải nào như 'Dưới đây là bài viết...'. Chỉ trả về duy nhất nội dung bài đăng.\n\n"
        + (f"{truth_context}\n\nChỉ dùng FACT phù hợp với nội dung bài gốc; RULE luôn bắt buộc. Không tự thêm fact chỉ để làm bài dài hơn.\n\n" if truth_context else "")
        + f"NỘI DUNG BÀI GỐC:\n{content}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 2048
        }
    }

    for model in _gemini_models():
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key.strip()}
        )
        try:
            res_data = _urlopen_json(req, timeout=20, attempts=3)
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 404):
                continue
            raise
        candidates = res_data.get("candidates", [])
        if candidates and "content" in candidates[0] and "parts" in candidates[0]["content"]:
            spun_text = candidates[0]["content"]["parts"][0].get("text", "").strip()
            spun_text = clean_ai_output(spun_text)
            if spun_text and _preserves_core_info(content, spun_text, brand_key=brand_key):
                return spun_text, model
            if spun_text:
                raise ValueError("Gemini output làm mất hoặc thêm dữ liệu ngoài bài gốc")
    raise RuntimeError("Không có Gemini model được cấu hình nào trả về nội dung hợp lệ.")


def spin_content_gemini(content: str, api_key: str, style: str = "tự nhiên", brand_name: str = "", truth_context: str = "", brand_key: str = None) -> str:
    """Compatibility API returning only the generated text."""
    return spin_content_gemini_with_model(content, api_key, style, brand_name, truth_context, brand_key=brand_key)[0]


def generate_unique_variant(content: str, api_key: str = None, brand_key: str = None, include_signature: bool = False) -> str:
    """
    API tương thích cũ: thử Gemini khi có key, nếu không thì dùng fallback
    truth-safe. Hàm này không cam kết nội dung luôn thay đổi.
    """
    if not content or not content.strip():
        return content

    from brand_profiles import apply_brand_signature, brand_name, strip_known_signature
    source_content = strip_known_signature(content)
    api_key = _resolve_gemini_api_key(api_key)
    selected_brand_name = brand_name(brand_key)

    if api_key and len(api_key.strip()) > 10:
        try:
            spun = spin_content_gemini(
                source_content,
                api_key.strip(),
                brand_name=selected_brand_name,
                truth_context=content_reference_context(brand_key),
                brand_key=brand_key,
            )
            return apply_brand_signature(spun, brand_key, include_signature)
        except Exception as e:
            print(f"⚠️ [AI Spinner] Gemini API gặp lỗi ({e}), chuyển sang chế độ Local Smart Spinner.")
            
    spun = spin_content_local(source_content)
    return apply_brand_signature(spun, brand_key, include_signature)


def generate_unique_variant_with_evidence(content: str, api_key: str = None, brand_key: str = None,
                                          include_signature: bool = False) -> dict:
    """Generate content and expose real provenance/change evidence for truthful logs."""
    from brand_profiles import apply_brand_signature, brand_name, strip_known_signature

    if not content or not content.strip():
        return {"content": content, "mode": "unchanged", "changed": False, "error": "empty_content"}

    api_key = _resolve_gemini_api_key(api_key)
    source = strip_known_signature(content)
    spun = None
    mode = "local_fallback"
    error = ""
    if api_key and len(api_key.strip()) > 10:
        try:
            spun, used_model = spin_content_gemini_with_model(
                source, api_key.strip(), brand_name=brand_name(brand_key),
                truth_context=content_reference_context(brand_key),
                brand_key=brand_key,
            )
            mode = "gemini"
        except Exception as exc:
            error = str(exc)
    if spun is None:
        spun = spin_content_local(source)
    else:
        spun = clean_ai_output(spun)

    final = apply_brand_signature(spun, brand_key, include_signature)
    comparable_source = re.sub(r"\s+", " ", source).strip()
    comparable_spun = re.sub(r"\s+", " ", spun).strip()
    changed = comparable_source != comparable_spun
    if not changed:
        mode = "unchanged"
    result = {"content": final, "mode": mode, "changed": changed, "error": error}
    if mode == "gemini":
        result["model"] = used_model
    return result


def spin_comment(content: str, api_key: str = None) -> str:
    """
    Xào nội dung bình luận (Comment) bằng Gemini AI hoặc Local Smart Engine.
    Tạo câu bình luận tự nhiên, ngắn gọn (1-3 câu), giữ nguyên số điện thoại/link nếu có.
    """
    if not content or not content.strip():
        return content

    api_key = _resolve_gemini_api_key(api_key)
    if api_key and len(api_key.strip()) > 10:
        try:
            prompt = (
                "Bạn là một người dùng Facebook đang bình luận dưới bài viết trên Facebook (Group hoặc Fanpage).\n"
                "Hãy viết lại đoạn bình luận sau thành một phiên bản ngắn gọn (1 đến 3 câu), tự nhiên, thân thiện, có emoji phù hợp.\n"
                "YÊU CẦU: Giữ nguyên số điện thoại, Zalo, địa chỉ hoặc link nếu có trong nội dung gốc. "
                "Chỉ trả về nội dung bình luận, không thêm lời dẫn giải.\n\n"
                f"NỘI DUNG BÌNH LUẬN GỐC:\n{content}"
            )
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": 512}
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", "x-goog-api-key": api_key.strip()})
            data = _urlopen_json(req, timeout=15, attempts=3)
            candidates = data.get("candidates", [])
            if candidates and "content" in candidates[0] and "parts" in candidates[0]["content"]:
                spun = candidates[0]["content"]["parts"][0].get("text", "").strip()
                if spun and _preserves_core_info(content, spun):
                    return spun
                if spun:
                    raise ValueError("Gemini output làm mất dữ liệu bắt buộc từ bình luận gốc")
        except Exception as e:
            print(f"⚠️ [AI Comment Spinner] Gemini API gặp lỗi ({e}), chuyển sang Local Comment Spinner.")

    # Offline mode must fail closed: normalize/spintax only, never replace the
    # user's comment with unaudited promotional claims.
    return spin_content_local(content)


def generate_interact_comments(base_comments: str = "", api_key: str = None) -> str:
    """
    Tạo hoặc xào danh sách các bình luận nuôi nick (tương tác Newsfeed),
    phân tách bằng dấu ';'.
    """
    default_pool = [
        "Bài viết tuyệt vời quá bạn ơi!",
        "Rất ý nghĩa và hữu ích, cảm ơn bạn đã chia sẻ!",
        "Like mạnh cho bài viết này nhé!",
        "Ảnh chụp góc này đẹp xuất sắc luôn!",
        "Tuyệt vời quá, chúc bạn ngày mới thật nhiều năng lượng!",
        "Nội dung rất hay và truyền cảm hứng!",
        "Thả tim cho bài viết chất lượng này nha ❤️",
        "Đúng thông tin mình đang quan tâm, cảm ơn bạn nhiều!",
        "Chúc bạn và gia đình một ngày an lành, may mắn!",
        "Quá xịn sò luôn ạ!"
    ]

    if not base_comments or len(base_comments.strip()) < 5:
        # Xáo trộn và chọn ngẫu nhiên 6-8 câu
        random.shuffle(default_pool)
        return ";".join(default_pool[:7])

    # Nếu người dùng có nhập một số câu gốc, xào các câu đó
    user_items = [c.strip() for c in base_comments.split(";") if c.strip()]
    if not user_items:
        return ";".join(default_pool[:7])

    spun_items = []
    for item in user_items:
        spun_items.append(spin_comment(item, api_key))

    # Nếu ít hơn 5 câu, bổ sung thêm từ default pool
    while len(spun_items) < 6:
        candidate = random.choice(default_pool)
        if candidate not in spun_items:
            spun_items.append(candidate)

    return ";".join(spun_items)


# =========================================================================
# ANTI-HASH TEXT SPINNER (ZERO-WIDTH SPACE INJECTION)
# =========================================================================

ZERO_WIDTH_CHARS = [
    '\u200B',  # Zero-Width Space
    '\u200C',  # Zero-Width Non-Joiner
    '\u200D',  # Zero-Width Joiner
    '\uFEFF',  # Zero-Width No-Break Space
]


def inject_zero_width_chars(text: str, frequency: float = 0.35) -> str:
    """
    Chèn các ký tự tàng hình (Zero-Width Characters) vào văn bản ngẫu nhiên.
    Mục đích:
    - Mắt người đọc hoàn toàn không thấy gì khác biệt, nội dung đọc tự nhiên 100%.
    - Thuật toán băm chuỗi (MD5/SHA-256/String Hash) của Facebook nhận diện đây là chuỗi văn bản mới,
      triệt tiêu nguy cơ bị gắn cờ trùng lặp (Duplicate Spam Hash).
    - Bảo vệ các URL và số điện thoại không bị ngắt quãng.
    """
    if not text:
        return text

    lines = text.split('\n')
    processed_lines = []

    url_pattern = re.compile(r'https?://[^\s]+')
    phone_pattern = re.compile(r'\b(?:\+84|0)[1-9]\d{8,9}\b')

    for line in lines:
        if not line.strip():
            processed_lines.append(line)
            continue

        words = line.split(' ')
        new_words = []
        for word in words:
            # Giữ nguyên link và số điện thoại
            if url_pattern.search(word) or phone_pattern.search(word):
                new_words.append(word)
                continue

            if random.random() < frequency:
                char = random.choice(ZERO_WIDTH_CHARS)
                if len(word) > 4 and random.random() < 0.5:
                    split_idx = random.randint(2, len(word) - 2)
                    word = word[:split_idx] + char + word[split_idx:]
                else:
                    word = word + char
            new_words.append(word)
        processed_lines.append(' '.join(new_words))

    res = '\n'.join(processed_lines)
    # Đảm bảo ít nhất 1 ký tự tàng hình được chèn nếu có từ hợp lệ
    if not any(c in res for c in ZERO_WIDTH_CHARS):
        for i, line in enumerate(processed_lines):
            words = line.split(' ')
            for j, w in enumerate(words):
                if not (url_pattern.search(w) or phone_pattern.search(w)) and len(w) > 0:
                    char = random.choice(ZERO_WIDTH_CHARS)
                    words[j] = w + char
                    processed_lines[i] = ' '.join(words)
                    return '\n'.join(processed_lines)

    return res


def spin_two_tier(text: str, frequency: float = 0.35) -> str:
    """
    Quy trình Spintax 2 lớp theo kinh nghiệm dịch ngược MKT Software:
    Lớp 1: Xử lý Spintax ngữ nghĩa ({Chào bạn|Hello}).
    Lớp 2: Chèn ký tự tàng hình Anti-Hash (Zero-Width Characters) để đổi mã băm chuỗi.
    """
    if not text:
        return ""
    # Lớp 1: Spintax thông thường
    pattern = re.compile(r'\{([^{}]*)\}')
    current = text
    while True:
        match = pattern.search(current)
        if not match:
            break
        options = match.group(1).split('|')
        choice = random.choice(options)
        current = current[:match.start()] + choice + current[match.end():]

    # Lớp 2: Anti-Hash Zero-Width Characters
    return inject_zero_width_chars(current, frequency=frequency)
