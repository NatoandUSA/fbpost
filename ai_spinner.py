# -*- coding: utf-8 -*-
"""
ai_spinner.py - Module Xào Bài Viết Tự Động (AI Content Spinner)
Hỗ trợ:
1. Gemini AI Online: Tận dụng Gemini 1.5 Flash / 2.5 Flash API để tạo bài viết độc nhất 100%.
2. Local Smart Spinner Offline: Tự động phân tích và sinh biến thể thông minh chuyên ngành Homestay Huế / Du lịch
   ngay cả khi không có mạng hoặc không có API Key.
"""

import os
import re
import random
import json
import urllib.request
import urllib.error

# Kho ngữ liệu thông minh Local Spinner cho Homestay Huế & Du lịch
HOOKS_HOMESTAY = [
    "🌿 Tìm một chốn dừng chân bình yên ngay trung tâm Cố Đô Huế? Đừng bỏ lỡ căn homestay cực xinh này nhé!",
    "✨ Trải nghiệm Huế thật dịu dàng và trọn vẹn cùng căn homestay không gian xanh mát, cực chill!",
    "🌸 Đi Huế chơi mà chưa biết ở đâu vừa ấm cúng, view đẹp lại gần các điểm check-in? Ghé ngay homestay nhà mình nhé!",
    "🏡 Góc nhỏ bình yên giữa lòng thành phố Huế mộng mơ — Nơi lý tưởng để nghỉ ngơi và nạp lại năng lượng!",
    "☀️ Đón nắng sớm Cố Đô tại không gian homestay thoáng đãng, phong cách mộc mạc và siêu ấm cúng!",
    "🍃 Du lịch Huế tự túc cùng gia đình hoặc nhóm bạn? Căn homestay siêu tiện nghi này sinh ra là dành cho bạn!",
    "🌟 Review một homestay Huế xinh ngất ngây, giá cực hạt dẻ mà dịch vụ thì 10/10!",
    "🛶 Sớm thức dậy bên tách trà nóng, nghe tiếng chim hót giữa không gian yên ả của xứ Huế...",
]

HIGHLIGHTS_HOMESTAY = [
    "✅ Phòng ốc sạch sẽ tinh tươm, đón gió và ánh sáng tự nhiên.",
    "✅ Vị trí đắc địa, chỉ mất vài phút di chuyển đến Đại Nội, Sông Hương, Cầu Tràng Tiền và phố đi bộ.",
    "✅ Đầy đủ tiện nghi: Điều hòa mát lạnh, máy nước nóng, máy giặt, bếp nấu ăn tự do như ở nhà.",
    "✅ Không gian sân vườn xanh mát, góc chill sống ảo lung linh từng centimet.",
    "✅ Chủ nhà thân thiện, nhiệt tình hỗ trợ thuê xe máy, tư vấn địa điểm ăn uống ngon chuẩn vị Huế.",
    "✅ Giá phòng hợp lý, hỗ trợ đặt phòng linh hoạt cho cả khách lẻ và gia đình.",
]

CALL_TO_ACTIONS = [
    "📲 Nhắn tin ngay cho homestay hoặc liên hệ hotline để nhận ưu đãi phòng tốt nhất hôm nay nhé!",
    "👉 Inbox trực tiếp cho page để được tư vấn phòng trống và nhận giá ưu đãi cho chuyến đi sắp tới!",
    "💌 Số lượng phòng có hạn vào cuối tuần, bạn hãy nhắn trước để giữ phòng đẹp nhất nha!",
    "📞 Liên hệ ngay hôm nay để nhận voucher giảm giá đặc biệt cho kỳ nghỉ tại Cố Đô Huế!",
    "🛎️ Chúc bạn có một chuyến đi khám phá Huế thật nhiều kỷ niệm đáng nhớ cùng người thân yêu!",
]

HASHTAG_POOLS = [
    "#homestayhue #dulichhue #huecity #checkinhue #khachsanhue #homestaygiarehue #phongchothuehue",
    "#huehomestay #reviewhue #amthuchue #codohue #dulichtutuc #homestayviewdep",
    "#homestay #hue #vietnamtravel #stayinhue #travelvietnam #huevietnam #visithue"
]


def extract_core_info(content: str) -> dict:
    """
    Trích xuất các thông tin cốt lõi quan trọng: SĐT, Zalo, Địa chỉ, Giá phòng, Link từ bài viết gốc
    để đảm bảo dù xào bài thế nào cũng không bị mất thông tin liên hệ.
    """
    phones = re.findall(r'(?:0|\+84)[1-9][0-9]{8,9}', content)
    prices = re.findall(r'\b\d+(?:[.,]\d+)?\s*(?:k|vnđ|vnd|đ|triệu|k/đêm|k/ngày)\b', content, re.IGNORECASE)
    links = re.findall(r'https?://[^\s]+', content)
    
    # Tìm dòng chứa địa chỉ
    addresses = []
    for line in content.split('\n'):
        if any(kw in line.lower() for kw in ['địa chỉ:', 'đc:', 'address:', 'tại:']):
            addresses.append(line.strip())
            
    return {
        "phones": list(set(phones)),
        "prices": list(set(prices)),
        "links": list(set(links)),
        "addresses": addresses
    }


def spin_content_local(content: str) -> str:
    """
    Xào bài thông minh bằng quy tắc ngữ nghĩa Local (Hoàn toàn Offline & Miễn phí).
    Tự động tái cấu trúc bài viết: Mở bài mới lạ + Thân bài giữ nguyên cốt lõi + Điểm nhấn + Lời kêu gọi + Hashtag.
    """
    if not content or not content.strip():
        return content

    core = extract_core_info(content)
    lines = [line.strip() for line in content.strip().split('\n') if line.strip()]
    
    # Lấy các dòng thân bài chính (bỏ các dòng hook hoặc hashtag cũ)
    body_lines = []
    for line in lines:
        if not line.startswith('#') and not any(h in line for h in ['#', 'Homestay Huế', 'Chào']):
            body_lines.append(line)
            
    # Tạo mở đầu ngẫu nhiên
    hook = random.choice(HOOKS_HOMESTAY)
    
    # Chọn ngẫu nhiên 2 - 3 điểm nhấn tiện ích
    selected_highlights = random.sample(HIGHLIGHTS_HOMESTAY, random.randint(2, 3))
    
    # Lời kêu gọi
    cta = random.choice(CALL_TO_ACTIONS)
    
    # Hashtag
    hashtags = random.choice(HASHTAG_POOLS)
    
    parts = [hook, ""]
    
    if body_lines:
        parts.append("\n".join(body_lines[:4]))
        parts.append("")
        
    parts.extend(selected_highlights)
    parts.append("")
    
    # Gắn lại thông tin liên hệ nếu có
    if core["phones"]:
        parts.append(f"☎️ Hotline / Zalo đặt phòng: {' - '.join(core['phones'])}")
    if core["addresses"]:
        parts.append(f"📍 {core['addresses'][0]}")
    if core["prices"]:
        parts.append(f"💵 Giá phòng chỉ từ: {core['prices'][0]}")
    if core["links"]:
        parts.append(f"🔗 Xem thêm tại: {core['links'][0]}")
        
    parts.append("")
    parts.append(cta)
    parts.append("")
    parts.append(hashtags)
    
    return "\n".join(parts).strip()


def spin_content_gemini(content: str, api_key: str, style: str = "tự nhiên") -> str:
    """
    Xào bài viết qua Google Gemini API (Online).
    Tạo ra bài viết độc nhất 100%, câu cú mượt mà, hấp dẫn và giữ nguyên dữ liệu gốc.
    """
    if not api_key:
        raise ValueError("Chưa cung cấp Gemini API Key.")
        
    prompt = (
        f"Bạn là một chuyên gia sáng tạo nội dung mạng xã hội (Facebook Copywriter) chuyên ngành Homestay, Du lịch và Bất động sản.\n"
        f"Hãy viết lại bài đăng Facebook sau đây thành một phiên bản hoàn toàn mới lạ, hấp dẫn, văn phong {style}, "
        f"sử dụng các biểu cảm emoji sinh động, bố cục thoáng đãng và có lời kêu gọi hành động thu hút.\n\n"
        f"YÊU CẦU BẮT BUỘC:\n"
        f"- Giữ nguyên toàn bộ số điện thoại, Zalo, địa chỉ, giá phòng hoặc link nếu có trong bài gốc.\n"
        f"- Viết bằng Tiếng Việt tự nhiên, phù hợp đăng nhóm cộng đồng hoặc fanpage.\n"
        f"- KHÔNG thêm bất kỳ lời dẫn giải nào như 'Dưới đây là bài viết...'. Chỉ trả về duy nhất nội dung bài đăng.\n\n"
        f"NỘI DUNG BÀI GỐC:\n{content}"
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.85,
            "topP": 0.95,
            "maxOutputTokens": 1024
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        res_data = json.loads(response.read().decode("utf-8"))
        
    candidates = res_data.get("candidates", [])
    if candidates and "content" in candidates[0] and "parts" in candidates[0]["content"]:
        spun_text = candidates[0]["content"]["parts"][0].get("text", "").strip()
        if spun_text:
            return spun_text
            
    raise Exception("Gemini không trả về nội dung hợp lệ.")


def generate_unique_variant(content: str, api_key: str = None) -> str:
    """
    Hàm giao tiếp tổng quát: Thử dùng Gemini API nếu có key hợp lệ,
    nếu lỗi hoặc không có key sẽ tự động chuyển sang Local Smart Spinner.
    Đảm bảo 100% luôn luôn có bài viết xào mới thành công!
    """
    if not content or not content.strip():
        return content
        
    if api_key and len(api_key.strip()) > 10:
        try:
            return spin_content_gemini(content, api_key.strip())
        except Exception as e:
            print(f"⚠️ [AI Spinner] Gemini API gặp lỗi ({e}), chuyển sang chế độ Local Smart Spinner.")
            
    return spin_content_local(content)


COMMENT_HOOKS = [
    "Chào bạn nha! ", "Hello bạn! ", "Chào ad ạ! ", "Bài viết tuyệt vời quá! ",
    "Cảm ơn bài chia sẻ rất hay của bạn! ", "Thích bài viết này quá nè! ", "Hello mọi người! "
]

COMMENT_BODIES = [
    "Bên mình có căn homestay Huế ấm cúng, không gian xanh cực chill ngay trung tâm, giá rất ưu đãi cho bạn ghé thăm nè.",
    "Bạn đi Huế cần tìm phòng homestay view đẹp, gần các điểm tham quan cứ nhắn tin cho mình tư vấn phòng đẹp nhé.",
    "Không gian homestay xinh xắn tại Cố Đô Huế, đầy đủ tiện nghi như ở nhà, bạn cần phòng nhắn mình giữ phòng nhé.",
    "Homestay nhà mình gần Sông Hương và Đại Nội, view thoáng mát, dịch vụ nhiệt tình chu đáo lắm nha."
]

COMMENT_CTAS = [
    " Cần thông tin phòng bạn cứ inbox mình nhé!",
    " Chúc bạn một ngày mới thật nhiều niềm vui!",
    " Chúc bài viết của bạn nhận được thật nhiều tương tác nha!",
    " Chúc bạn có kỳ nghỉ khám phá Huế thật tuyệt vời!"
]

def spin_comment(content: str, api_key: str = None) -> str:
    """
    Xào nội dung bình luận (Comment) bằng Gemini AI hoặc Local Smart Engine.
    Tạo câu bình luận tự nhiên, ngắn gọn (1-3 câu), giữ nguyên số điện thoại/link nếu có.
    """
    if not content or not content.strip():
        return content

    core = extract_core_info(content)

    if api_key and len(api_key.strip()) > 10:
        try:
            prompt = (
                "Bạn là một người dùng Facebook đang bình luận dưới bài viết trên Facebook (Group hoặc Fanpage).\n"
                "Hãy viết lại đoạn bình luận sau thành một phiên bản ngắn gọn (1 đến 3 câu), tự nhiên, thân thiện, có emoji phù hợp.\n"
                "YÊU CẦU: Giữ nguyên số điện thoại, Zalo, địa chỉ hoặc link nếu có trong nội dung gốc. "
                "Chỉ trả về nội dung bình luận, không thêm lời dẫn giải.\n\n"
                f"NỘI DUNG BÌNH LUẬN GỐC:\n{content}"
            )
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key.strip()}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.85, "maxOutputTokens": 300}
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            if candidates and "content" in candidates[0] and "parts" in candidates[0]["content"]:
                spun = candidates[0]["content"]["parts"][0].get("text", "").strip()
                if spun:
                    return spun
        except Exception as e:
            print(f"⚠️ [AI Comment Spinner] Gemini API gặp lỗi ({e}), chuyển sang Local Comment Spinner.")

    # Local comment spinning
    hook = random.choice(COMMENT_HOOKS)
    body = random.choice(COMMENT_BODIES)
    cta = random.choice(COMMENT_CTAS)
    
    # Nếu nội dung ban đầu có thông tin liên hệ, gắn vào
    extra = ""
    if core["phones"]:
        extra += f" (Zalo/Hotline: {core['phones'][0]})"
    if core["prices"]:
        extra += f" - Giá từ {core['prices'][0]}"

    return f"{hook}{body}{extra}{cta}".strip()


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


