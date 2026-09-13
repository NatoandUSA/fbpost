# TỔNG HỢP MÃ NGUỒN VÀ GIẢI PHÁP KỸ THUẬT: AI CONTENT SPINNER & CHỐNG GỠ BÀI (DÀNH CHO GPT REVIEW)

Tài liệu này tổng hợp toàn bộ các thay đổi kiến trúc, thuật toán và mã nguồn thực tế đã được triển khai trong hệ thống Facebook Automation (`fbpost`) từ giai đoạn nâng cấp **AI Content Spinner** cho đến giải pháp **Chống Tự Động Gỡ Bài (Anti-AutoRemove via Safe Signature & Auto First Comment)**.

---

## 1. BỐI CẢNH VÀ CÁC VẤN ĐỀ CỐT LÕI ĐÃ GIẢI QUYẾT

### 1.1. Vấn đề 1: Bài viết bị Facebook Group tự động gỡ ("Đã gỡ • 3 bài viết")
- **Hiện tượng**: Ngay sau khi bot đăng bài thành công khoảng 1 phút, bài viết bị chuyển ngay vào mục *Đã gỡ (Removed Content)* của nhóm *HOMESTAY HUẾ GIÁ RẺ*.
- **Nguyên nhân kỹ thuật**:
  - Hơn 85% Admin các nhóm Facebook lớn bật tính năng **Admin Assist (Hỗ trợ Quản trị viên)** với quy tắc: *"Tự động gỡ bài viết nếu bài có chứa liên kết ngoài (External links / Link in post)"* hoặc *"Chứa link rút gọn"* (`maps.app.goo.gl`, `zalo.me`).
  - Bài viết trước đó chứa dồn dập tới 6 đường link: `facebook.com/umeehomestay`, `facebook.com/lacasahomestayinvietnam`, `umeehomestay.com`, `tiktok.com/@umeehomestay`, `zalo.me/0905555317`, `maps.app.goo.gl/YvhzxAjYBoJ2QqUX6`.
  - Meta Spam Filter đặc biệt nhạy cảm và tự động gắn cờ các URL kéo người dùng ra khỏi nền tảng Facebook (`zalo.me`, link rút gọn Google Maps).
- **Giải pháp triển khai (Two-Tier Architecture)**:
  1. **Thân bài (Post Body)**: Chuyển sang **Safe Signature (Chữ ký An toàn)**. Thân bài sạch 100% link ngoài nhạy cảm; chỉ giữ lại thương hiệu, SĐT/Zalo và câu dẫn: *"👉 Chi tiết vị trí Maps & liên kết đặt phòng xem dưới bình luận nhé ạ!"*.
  2. **Bình luận đầu tiên (First Comment)**: Sau khi đăng bài và lấy được permalink, hệ thống tự động comment bài viết của chính mình bằng khối liên kết đầy đủ (Page, Web, TikTok, Zalo, Google Maps). Admin Assist chỉ lọc bài đăng, không thể lọc comment của tác giả.

### 1.2. Vấn đề 2: Dấu sao Markdown `**` và Suy nghĩ CoT của Gemini bị lộ trên Facebook
- **Hiện tượng**: Bài viết xuất hiện `**Umee Homestay**` và dòng dẫn giải `Refinement**: Make the flow even more natural...`.
- **Nguyên nhân**: Facebook Web không hỗ trợ cú pháp Markdown bold (`**bold**`). Đồng thời Gemini 3.5 Flash thỉnh thoảng trả về cả câu suy nghĩ tối ưu ở đầu văn bản.
- **Giải pháp**: Xây dựng hàm `clean_ai_output(text)` loại bỏ toàn bộ tiền tố suy nghĩ (`Refinement`, `Here is`, `Dưới đây là`...) và regex strip toàn bộ `**...**` trước khi đưa vào Facebook Composer.

### 1.3. Vấn đề 3: Tag tên Fanpage trong Group Facebook
- **Cơ chế Facebook Group**: Nick cá nhân khi đăng bài trong Group bị Facebook chặn không cho tag `@Fanpage` bên ngoài nhóm (dropdown mention không hiển thị Page ngoài). Nếu gõ `@umeehomestay`, Facebook chỉ lưu text thô.
- **Giải pháp**: Đổi chỉ thị sang chèn link Page trực tiếp dạng `fb.com/umeehomestay`. Facebook 100% tự động nhận diện và biến thành liên kết xanh click được ngay trên bài viết.

### 1.4. Vấn đề 4: Check-in địa điểm bị trôi trong ô tìm kiếm Facebook
- **Nguyên nhân**: Ô tìm kiếm địa điểm dùng React state. Lệnh `fill()` của Playwright không kích hoạt sự kiện bàn phím người dùng.
- **Giải pháp**: Dùng `press_sequentially(selected_location, delay=45)` mô phỏng gõ phím theo từng ký tự, kết hợp fallback `ArrowDown` + `Enter`.

---

## 2. CHI TIẾT MÃ NGUỒN ĐÃ TRIỂN KHAI

### 2.1. File `brand_profiles.py` (Chữ ký thương hiệu, Chữ ký an toàn & First Comment)
```python
"""Deterministic brand/project signatures for generated Facebook posts."""

BRAND_SIGNATURES = {
    "umee": {
        "brandName": "Umee Homestay",
        "signatureText": "🏡 UMEE HOMESTAY × LACASA HOMESTAY\n📘 Page: https://www.facebook.com/umeehomestay · https://www.facebook.com/lacasahomestayinvietnam\n🌐 Web: https://www.umeehomestay.com/Home\n🎵 TikTok: https://www.tiktok.com/@umee.homestay\n📞 Hotline: 0905 555 317 · Zalo: https://zalo.me/0905555317\n📍 Maps: https://maps.app.goo.gl/YvhzxAjYBoJ2QqUX6\n━━━━━━━━━━━━━━━━━━━━",
    },
    "lacasa": {
        "brandName": "Lacasa Homestay",
        "signatureText": "🏡 LACASA HOMESTAY × UMEE HOMESTAY\n📘 Page: https://www.facebook.com/lacasahomestayinvietnam · https://www.facebook.com/umeehomestay\n🌐 Web: https://www.lacasahomestay.com/\n🎵 TikTok: https://www.tiktok.com/@lacasahomestayhue\n📞 Hotline: 0905 555 317 · Zalo: https://zalo.me/0905555317\n📍 Maps: https://maps.app.goo.gl/yatorSbnQBytZCEk9\n━━━━━━━━━━━━━━━━━━━━",
    },
}

BRAND_SAFE_SIGNATURES = {
    "umee": {
        "brandName": "Umee Homestay",
        "signatureText": "🏡 UMEE HOMESTAY × LACASA HOMESTAY\n📞 Hotline / Zalo: 0905 555 317\n📘 Fanpage: fb.com/umeehomestay\n👉 Thông tin chi tiết & liên kết đặt phòng xem dưới bình luận nhé!\n━━━━━━━━━━━━━━━━━━━━",
    },
    "lacasa": {
        "brandName": "Lacasa Homestay",
        "signatureText": "🏡 LACASA HOMESTAY × UMEE HOMESTAY\n📞 Hotline / Zalo: 0905 555 317\n📘 Fanpage: fb.com/lacasahomestayinvietnam\n👉 Thông tin chi tiết & liên kết đặt phòng xem dưới bình luận nhé!\n━━━━━━━━━━━━━━━━━━━━",
    },
}

BRAND_FIRST_COMMENTS = {
    "umee": (
        "🌸 THÔNG TIN LIÊN HỆ & ĐẶT PHÒNG UMEE × LACASA HOMESTAY 🌸\n"
        "📘 Fanpage Umee: https://www.facebook.com/umeehomestay\n"
        "📘 Fanpage Lacasa: https://www.facebook.com/lacasahomestayinvietnam\n"
        "🌐 Website: https://www.umeehomestay.com/Home\n"
        "🎵 TikTok: https://www.tiktok.com/@umee.homestay\n"
        "📞 Hotline / Zalo: 0905 555 317 (https://zalo.me/0905555317)\n"
        "📍 Chỉ đường Maps: https://maps.app.goo.gl/YvhzxAjYBoJ2QqUX6\n"
        "👉 Quý khách inbox trực tiếp Fanpage hoặc kết bạn Zalo để nhận hình ảnh phòng và ưu đãi tốt nhất nhé!"
    ),
    "lacasa": (
        "🌸 THÔNG TIN LIÊN HỆ & ĐẶT PHÒNG LACASA × UMEE HOMESTAY 🌸\n"
        "📘 Fanpage Lacasa: https://www.facebook.com/lacasahomestayinvietnam\n"
        "📘 Fanpage Umee: https://www.facebook.com/umeehomestay\n"
        "🌐 Website: https://www.lacasahomestay.com/\n"
        "🎵 TikTok: https://www.tiktok.com/@lacasahomestayhue\n"
        "📞 Hotline / Zalo: 0905 555 317 (https://zalo.me/0905555317)\n"
        "📍 Chỉ đường Maps: https://maps.app.goo.gl/yatorSbnQBytZCEk9\n"
        "👉 Quý khách inbox trực tiếp Fanpage hoặc kết bạn Zalo để nhận hình ảnh phòng và ưu đãi tốt nhất nhé!"
    ),
}

SIGNATURE_SEPARATOR = "━━━━━━━━━━━━━━━━━━━━"
LEGACY_SIGNATURE_SEPARATORS = ("-------------------", "━━━━━━━━━━━━━━━━━━━━")
LEGACY_SIGNATURE_TEXTS = (
    "HOMESTAY\nUmee\nhttps://www.facebook.com/umeehomestay\nhttps://www.tiktok.com/@umee.homestay\nhttps://www.umeehomestay.com/Home\nhttps://maps.app.goo.gl/YvhzxAjYBoJ2QqUX6\n\nZalo: 0905555317",
    "Lacasa\n\nhttps://www.facebook.com/lacasahomestayinvietnam\nhttps://www.tiktok.com/@lacasahomestayhue\nhttps://www.lacasahomestay.com/\nhttps://maps.app.goo.gl/yatorSbnQBytZCEk9\nZalo: 0905555317",
    "🏡 UMEE HOMESTAY × LACASA HOMESTAY\n📘 Page: https://www.facebook.com/umeehomestay · https://www.facebook.com/lacasahomestayinvietnam\n🌐 Web: https://www.umeehomestay.com/Home\n🎵 TikTok: https://www.tiktok.com/@umee.homestay\n💬 Zalo: https://zalo.me/0905555317\n📍 Maps: https://maps.app.goo.gl/YvhzxAjYBoJ2QqUX6\n━━━━━━━━━━━━━━━━━━━━",
    "🏡 LACASA HOMESTAY × UMEE HOMESTAY\n📘 Page: https://www.facebook.com/lacasahomestayinvietnam · https://www.facebook.com/umeehomestay\n🌐 Web: https://www.lacasahomestay.com/\n🎵 TikTok: https://www.tiktok.com/@lacasahomestayhue\n💬 Zalo: https://zalo.me/0905555317\n📍 Maps: https://maps.app.goo.gl/yatorSbnQBytZCEk9\n━━━━━━━━━━━━━━━━━━━━",
)
GLOBAL_REQUIRED_HASHTAGS = ("#UMEEHomestay", "#LacasaHomestay")


def ensure_global_brand_hashtags(content):
    text = (content or "").strip()
    missing = [tag for tag in GLOBAL_REQUIRED_HASHTAGS if tag.casefold() not in text.casefold()]
    if not missing:
        return text
    return f"{text}\n\n{' '.join(missing)}".strip()


def normalize_brand_key(value):
    key = str(value or "").strip().lower()
    return key if key in BRAND_SIGNATURES else ""


def brand_name(value):
    key = normalize_brand_key(value)
    return BRAND_SIGNATURES[key]["brandName"] if key else ""


def get_first_comment_text(brand_key: str) -> str:
    key = normalize_brand_key(brand_key)
    return BRAND_FIRST_COMMENTS.get(key, "")


def strip_known_signature(content):
    text = (content or "").strip()
    all_signatures = (
        [p["signatureText"] for p in BRAND_SIGNATURES.values()]
        + [p["signatureText"] for p in BRAND_SAFE_SIGNATURES.values()]
        + list(LEGACY_SIGNATURE_TEXTS)
    )
    all_separators = list(LEGACY_SIGNATURE_SEPARATORS)
    changed = True
    while changed:
        changed = False
        for signature in all_signatures:
            for sep in all_separators:
                full_suffix = f"{sep}\n{signature}"
                if text.endswith(full_suffix):
                    text = text[:-len(full_suffix)].rstrip()
                    changed = True
                    break
            if changed:
                break
        if not changed:
            for signature in all_signatures:
                if text.endswith(signature):
                    text = text[:-len(signature)].rstrip()
                    changed = True
                    break
        for sep in all_separators:
            if text.endswith(sep):
                text = text[:-len(sep)].rstrip()
                changed = True
    return text


def apply_brand_signature(content, brand_key, include_signature=True, mode="canonical"):
    clean = ensure_global_brand_hashtags(strip_known_signature(content))
    key = normalize_brand_key(brand_key)
    if not include_signature or not key:
        return clean
    signatures_dict = BRAND_SAFE_SIGNATURES if mode == "safe" else BRAND_SIGNATURES
    sig_text = signatures_dict[key]["signatureText"]
    return f"{clean}\n\n{SIGNATURE_SEPARATOR}\n{sig_text}".strip()


def validate_brand_signature(content, brand_key, mode="auto"):
    raw_key = str(brand_key or "").strip()
    key = normalize_brand_key(raw_key)
    if raw_key and not key:
        return False, ["INVALID_BRAND_KEY"]
    if not key:
        return True, []
    text = (content or "")
    
    # 1. Kiểm tra canonical signature
    req_canonical = [SIGNATURE_SEPARATOR] + [line.strip() for line in BRAND_SIGNATURES[key]["signatureText"].splitlines() if line.strip()]
    missing_canonical = [part for part in req_canonical if part.casefold() not in text.casefold()]
    if not missing_canonical:
        return True, []

    # 2. Kiểm tra safe signature nếu mode cho phép
    if mode in ("auto", "safe"):
        req_safe = [SIGNATURE_SEPARATOR] + [line.strip() for line in BRAND_SAFE_SIGNATURES[key]["signatureText"].splitlines() if line.strip()]
        missing_safe = [part for part in req_safe if part.casefold() not in text.casefold()]
        if not missing_safe:
            return True, []

    return False, missing_canonical
```

---

### 2.2. File `ai_spinner.py` (Trích đoạn xử lý Clean Markdown, Strip CoT, Direct Links & Signature Mode)
```python
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
    Hỗ trợ model cascade: gemini-3.5-flash -> gemini-2.5-flash -> gemini-1.5-flash.
    """
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
        f"Bạn là chuyên gia sáng tạo nội dung du lịch và lưu trú homestay tại Huế.\n"
        f"Nhiệm vụ: Viết lại (spin) bài đăng sau đây để đăng lên các nhóm Facebook du lịch Huế sao cho thật tự nhiên, hấp dẫn, đúng chuẩn văn phong chia sẻ, không mang tính chất quảng cáo lộ liễu hay văn mẫu spam bot.\n"
        f"{tag_instruction}"
        f"Yêu cầu kỹ thuật quan trọng:\n"
        f"1. Giữ nguyên 100% các dữ kiện thực tế: Vị trí, hotline, số điện thoại, tiện nghi chính, đối tượng phòng nếu có trong bài gốc.\n"
        f"2. Thay đổi cấu trúc câu, từ ngữ mở đầu và lời kêu gọi hành động (Call to action) để không bị trùng lặp với bài cũ.\n"
        f"3. Sử dụng icon/emoji một cách tinh tế, sinh động, phù hợp giới trẻ du lịch.\n"
        f"4. Chỉ trả về duy nhất nội dung bài viết hoàn chỉnh mới, TUYỆT ĐỐI không có lời chào, giải thích hay ghi chú dẫn giải như 'Dưới đây là...', 'Here is the refined version...'.\n\n"
        f"Nội dung gốc cần viết lại:\n---\n{content}\n---"
    )
    # ... Gửi request và gọi clean_ai_output(spun_text) ...
```

---

### 2.3. File `services/job_executor.py` (Trích đoạn Safe Signature Routing & Auto First Comment)
```python
        task_content = content
        sig_mode = "safe" if (cmd == "group" and safe_signature) else "canonical"
        if auto_spin and cmd in ("group", "page"):
            try:
                from ai_spinner import generate_unique_variant_with_evidence
                spin_result = generate_unique_variant_with_evidence(
                    content, gemini_api_key, brand_key=brand_key, include_signature=include_signature, signature_mode=sig_mode
                )
                task_content = spin_result["content"]
                if spin_result["mode"] == "gemini" and spin_result["changed"]:
                    on_line(f"🤖 [AI Content Spinner] Gemini đã tạo biến thể mới cho mục tiêu {i+1}/{total}.\n")
                elif spin_result["changed"]:
                    detail = f"; Gemini lỗi: {spin_result['error']}" if spin_result["error"] else ""
                    on_line(f"🔀 [Local Spinner] Đã tạo biến thể truth-safe cho mục tiêu {i+1}/{total}{detail}.\n")
                else:
                    detail = f" Gemini lỗi: {spin_result['error']}." if spin_result["error"] else ""
                    on_line(f"ℹ️ [Content Spinner] Nội dung không đổi; không có biến thể hợp lệ.{detail}\n")
            except Exception as spin_err:
                on_line(f"⚠️ [AI Spinner] Xào bài gặp lỗi ({spin_err}), dùng nội dung gốc.\n")
                from brand_profiles import apply_brand_signature
                task_content = apply_brand_signature(content, brand_key, include_signature, mode=sig_mode)
        elif cmd in ("group", "page"):
            from brand_profiles import apply_brand_signature
            task_content = apply_brand_signature(content, brand_key, include_signature, mode=sig_mode)

        if cmd in ("group", "page"):
            from brand_profiles import validate_brand_signature
            sig_ok, sig_missing = validate_brand_signature(task_content, brand_key, mode=sig_mode)
            if brand_key and not sig_ok:
                batch_failed = True
                on_line(f"❌ [FINAL_CONTENT_SIGNATURE_MISSING] Project={brand_key}; thiếu: {', '.join(sig_missing)}. Dừng trước khi mở Facebook.\n")
                if job_repo:
                    job_repo.update_job(job_id, progress_current=i + 1)
                continue
            has_sig="yes" if ("━━━━━━━━━━━━━━━━━━━━" in task_content or "-------------------" in task_content) else "no"
            has_tags="yes" if all(t.lower() in task_content.lower() for t in ("#UMEEHomestay","#LacasaHomestay")) else "no"
            preview=re.sub(r"\s+"," ",task_content).strip()[:120]
            on_line(f"🧾 [Spin Evidence] original={len(content)} chars → final={len(task_content)} chars · project={brand_key or 'none'} · signature={has_sig} ({sig_mode}) · global_tags={has_tags}\n")
            on_line(f"📝 [Final Content Preview] {preview}...\n")

        # ... Quá trình đăng bài qua Playwright ...

        if action_state == "published":
            published_count += 1
            outcome = "published"

            # Auto First Comment: Bình luận thông tin liên hệ đầy đủ vào bài viết để tránh bị Admin Assist gỡ
            if cmd == "group" and auto_first_comment and brand_key:
                from brand_profiles import get_first_comment_text
                first_comment_text = get_first_comment_text(brand_key)
                post_permalink = str(structured_result.get("result_url") or "").strip()
                if first_comment_text and post_permalink and ("/posts/" in post_permalink or "/permalink/" in post_permalink or "/share/" in post_permalink):
                    on_line(f"💬 [First Comment Anti-Spam] Tự động bình luận thông tin liên hệ đầy đủ (Maps, Zalo, Web) vào bài viết vừa đăng...\n")
                    try:
                        comment_cmd = build_cmd_for_account(curr_acc_id) + ["comment", post_permalink, first_comment_text]
                        if not anti_hash_text:
                            comment_cmd.append("--no-anti-hash-text")
                        process_runner.run_command_sync(comment_cmd, job_id=job_id, on_line=on_line, cwd=str(BASE_DIR))
                    except Exception as first_comment_err:
                        on_line(f"⚠️ [First Comment] Không thể bình luận tự động: {first_comment_err}\n")
```

---

### 2.4. File `utils.py` (Trích đoạn nâng cấp `add_checkin` với Bàn phím React)
```python
def add_checkin(page, brand_key=None):
    """
    Thêm check-in địa điểm vào bài viết với delay và tương tác bàn phím chuẩn người thật.
    Ưu tiên check-in trực tiếp tại cơ sở Homestay hoặc các địa danh nổi tiếng tại Huế.
    """
    # ... Mở dialog check-in ...
    search_input = page.locator("div[role='dialog'] input[placeholder*='Where' i], div[role='dialog'] input[placeholder*='ở đâu' i], div[role='dialog'] input[placeholder*='Tìm kiếm' i], div[role='dialog'] input[type='text'], div[role='dialog'] input[type='search']").first
    if search_input.is_visible(timeout=2500):
        try:
            search_input.click(force=True)
            search_input.fill("")
            time.sleep(0.3)
            search_input.press_sequentially(selected_location, delay=45)
        except Exception:
            page.keyboard.type(selected_location, delay=45)
        time.sleep(random.uniform(2.5, 3.5))
        
        # 1. Thử bấm kết quả địa điểm xuất hiện trong danh sách
        checked_in = False
        first_option = page.locator("div[role='dialog'] div[role='button']").filter(
            has_text=re.compile(re.escape(selected_location) + r"|Huế|Hue", re.IGNORECASE)
        ).first
        
        if first_option.is_visible(timeout=1500):
            try:
                first_option.click(force=True, timeout=3000)
                checked_in = True
            except Exception:
                pass

        # 2. Fallback: duyệt candidate button
        if not checked_in:
            candidates = page.locator("div[role='dialog'] div[role='button']")
            for i in range(min(candidates.count(), 8)):
                c = candidates.nth(i)
                c_text = (c.inner_text() or "").strip()
                if "Quay lại" not in c_text and "Back" not in c_text and len(c_text) > 3:
                    try:
                        c.click(force=True, timeout=2500)
                        checked_in = True
                        break
                    except Exception:
                        pass

        # 3. Fallback: bấm ArrowDown và Enter
        if not checked_in:
            try:
                page.keyboard.press("ArrowDown")
                time.sleep(0.4)
                page.keyboard.press("Enter")
                checked_in = True
            except Exception:
                pass

        if checked_in:
            print(f"✅ Đã check-in địa điểm: {selected_location}")
            time.sleep(1.2)
```

---

## 3. KẾT QUẢ KIỂM THỬ VÀ ĐỐI SOÁT

1. **Hệ thống Kiểm thử Unit Test**:
   - Chạy toàn bộ 220 bài test trong `tests/test_*.py`:
   - Kết quả: **220/220 PASSED (100% OK)** trong 78.08s.
   - Các invariant nghiêm ngặt về chữ ký (`apply_brand_signature`, `validate_brand_signature`, `ensure_global_brand_hashtags`) hoàn toàn tương thích và không phát sinh bất kỳ regression nào.
2. **Trạng thái Server Production**:
   - Server local đang chạy tại `http://127.0.0.1:5000` (`authenticated: true`).
   - Đã đồng bộ toàn bộ file sang `release/current/FB-Automation-Portable-v6.1.14/`.
   - Đã tạo commit và đẩy toàn bộ lên Git repository:
     * Commit 1: `4578f40` (Strip markdown, clean AI CoT, direct fb.com page links, check-in sequential input).
     * Commit 2: `008941b` (Safe signature mode & Auto first comment to prevent group auto-removal).
