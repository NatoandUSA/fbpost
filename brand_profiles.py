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
        "signatureText": "🏡 UMEE HOMESTAY × LACASA HOMESTAY\n📞 Hotline / Zalo: 0905 555 317\n📘 Fanpage: fb.com/umeehomestay\n📩 Inbox Fanpage hoặc Zalo để nhận thông tin chi tiết.\n━━━━━━━━━━━━━━━━━━━━",
    },
    "lacasa": {
        "brandName": "Lacasa Homestay",
        "signatureText": "🏡 LACASA HOMESTAY × UMEE HOMESTAY\n📞 Hotline / Zalo: 0905 555 317\n📘 Fanpage: fb.com/lacasahomestayinvietnam\n📩 Inbox Fanpage hoặc Zalo để nhận thông tin chi tiết.\n━━━━━━━━━━━━━━━━━━━━",
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
        "👉 Quý khách inbox trực tiếp Fanpage hoặc kết bạn Zalo để nhận hình ảnh và thông tin phòng."
    ),
    "lacasa": (
        "🌸 THÔNG TIN LIÊN HỆ & ĐẶT PHÒNG LACASA × UMEE HOMESTAY 🌸\n"
        "📘 Fanpage Lacasa: https://www.facebook.com/lacasahomestayinvietnam\n"
        "📘 Fanpage Umee: https://www.facebook.com/umeehomestay\n"
        "🌐 Website: https://www.lacasahomestay.com/\n"
        "🎵 TikTok: https://www.tiktok.com/@lacasahomestayhue\n"
        "📞 Hotline / Zalo: 0905 555 317 (https://zalo.me/0905555317)\n"
        "📍 Chỉ đường Maps: https://maps.app.goo.gl/yatorSbnQBytZCEk9\n"
        "👉 Quý khách inbox trực tiếp Fanpage hoặc kết bạn Zalo để nhận hình ảnh và thông tin phòng."
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
