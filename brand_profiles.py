"""Deterministic brand/project signatures for generated Facebook posts."""

BRAND_SIGNATURES = {
    "umee": {
        "brandName": "Umee Homestay",
        "signatureText": "HOMESTAY\nUmee\nhttps://www.facebook.com/umeehomestay\nhttps://www.tiktok.com/@umee.homestay\nhttps://www.umeehomestay.com/Home\nhttps://maps.app.goo.gl/YvhzxAjYBoJ2QqUX6\n\nZalo: 0905555317",
    },
    "lacasa": {
        "brandName": "Lacasa Homestay",
        "signatureText": "Lacasa\n\nhttps://www.facebook.com/lacasahomestayinvietnam\nhttps://www.tiktok.com/@lacasahomestayhue\nhttps://www.lacasahomestay.com/\nhttps://maps.app.goo.gl/yatorSbnQBytZCEk9\nZalo: 0905555317",
    },
}

SIGNATURE_SEPARATOR = "-------------------"


def normalize_brand_key(value):
    key = str(value or "").strip().lower()
    return key if key in BRAND_SIGNATURES else ""


def brand_name(value):
    key = normalize_brand_key(value)
    return BRAND_SIGNATURES[key]["brandName"] if key else ""


def strip_known_signature(content):
    text = (content or "").strip()
    for profile in BRAND_SIGNATURES.values():
        signature = profile["signatureText"]
        for suffix in (f"{SIGNATURE_SEPARATOR}\n{signature}", signature):
            if text.endswith(suffix):
                text = text[:-len(suffix)].rstrip()
    return text


def apply_brand_signature(content, brand_key, include_signature=True):
    clean = strip_known_signature(content)
    key = normalize_brand_key(brand_key)
    if not include_signature or not key:
        return clean
    return f"{clean}\n\n{SIGNATURE_SEPARATOR}\n{BRAND_SIGNATURES[key]['signatureText']}".strip()
