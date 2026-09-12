"""Google Sheets Group Synchronization & Deduplication Service.

Fetches, parses, deduplicates, and synchronizes Facebook group target lists
from live Google Sheets (public or shared CSV export) into the FB Automation registry.
"""

import csv
import io
import re
import urllib.parse
import uuid
from typing import Any, Dict, List, Optional, Tuple

import requests
from paths import DATA_DIR
from utils import normalize_target_url


DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/10kZe1_oYgdUWPua16jN59xaPBwR2WsK86bjNFHpGz2k/edit?gid=0#gid=0"


def to_csv_export_url(sheet_url: str) -> str:
    """
    Convert standard Google Sheets web URL (view/edit/share) into a public CSV export endpoint.
    
    Examples:
        https://docs.google.com/spreadsheets/d/10kZe1.../edit?gid=0#gid=0
        -> https://docs.google.com/spreadsheets/d/10kZe1.../export?format=csv&gid=0
    """
    if not sheet_url or not isinstance(sheet_url, str):
        return ""

    url = sheet_url.strip()
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "docs.google.com":
        raise ValueError("Chỉ chấp nhận liên kết HTTPS từ docs.google.com.")
    match = re.search(r"^/spreadsheets/d/([a-zA-Z0-9_-]+)", parsed.path)
    if not match:
        raise ValueError("Liên kết Google Sheets không hợp lệ.")

    doc_id = match.group(1)

    # Extract gid (worksheet id) if present, defaulting to '0' (first sheet)
    gid = "0"
    gid_match = re.search(r"[?&#]gid=([0-9]+)", url)
    if gid_match:
        gid = gid_match.group(1)

    return f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid}"


def fetch_sheet_csv(csv_url: str, timeout: float = 15.0) -> str:
    """Fetch raw CSV text from the given URL."""
    if not csv_url:
        raise ValueError("URL Google Sheet không được để trống.")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        )
    }
    response = requests.get(csv_url, headers=headers, timeout=timeout, stream=True)
    if response.status_code != 200:
        raise RuntimeError(
            f"Không thể tải dữ liệu từ Google Sheet (HTTP {response.status_code}). "
            "Vui lòng kiểm tra quyền chia sẻ (Bất kỳ ai có đường liên kết đều có thể xem)."
        )

    max_csv_bytes = 5 * 1024 * 1024
    chunks = []
    received = 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        received += len(chunk)
        if received > max_csv_bytes:
            raise ValueError("Google Sheet vượt giới hạn 5 MB.")
        chunks.append(chunk)
    raw = b"".join(chunks)
    encoding = response.encoding or "utf-8"
    return raw.decode(encoding, errors="replace")


def parse_member_count(raw_val: Any) -> Optional[int]:
    """Parse various member count formats into an integer."""
    if raw_val is None:
        return None
    val_str = str(raw_val).strip()
    if not val_str:
        return None

    # Handle compact suffixes such as '76k', '1.2m', '1,2 nghìn', or '2 triệu'.
    val_lower = val_str.lower().replace(" ", "")
    k_match = re.fullmatch(r"([0-9]+(?:[.,][0-9]+)?)(?:k|nghìn)", val_lower)
    if k_match:
        num = float(k_match.group(1).replace(",", "."))
        return int(round(num * 1_000))

    m_match = re.fullmatch(r"([0-9]+(?:[.,][0-9]+)?)(?:m|tr|triệu)", val_lower)
    if m_match:
        num = float(m_match.group(1).replace(",", "."))
        return int(round(num * 1_000_000))

    # Clean punctuation: '76,000' or '76.000' -> '76000'
    cleaned = re.sub(r"[^\d]", "", val_str)
    if not cleaned:
        return None
    try:
        count = int(cleaned)
        return count if 0 <= count <= 2_000_000_000 else None
    except ValueError:
        return None


def parse_privacy_type(raw_val: Any) -> str:
    """Classify group privacy as 'public', 'private', or 'unknown'."""
    if not raw_val:
        return "unknown"
    val = str(raw_val).lower().strip()
    if any(token in val for token in ("công khai", "public", "mở")):
        return "public"
    if any(token in val for token in ("riêng tư", "private", "kín", "đóng")):
        return "private"
    return "unknown"


def is_active_flag(raw_val: Any) -> bool:
    """Evaluate whether posting flag represents an active/enabled state."""
    if not raw_val:
        return False
    val = str(raw_val).strip().lower()
    return val in ("y", "yes", "có", "co", "1", "true", "x", "ok", "được", "duoc", "bật", "bat")


def _detect_header_indices(header: List[str]) -> Dict[str, int]:
    """Dynamically map column indices based on header names."""
    mapping = {
        "url_idx": -1,
        "name_idx": -1,
        "privacy_idx": -1,
        "members_idx": -1,
        "active_idx": -1,
    }

    for idx, col in enumerate(header):
        c = col.lower().strip()
        if mapping["url_idx"] == -1 and any(k in c for k in ("link", "url", "đường dẫn", "nhóm link")):
            mapping["url_idx"] = idx
        elif mapping["name_idx"] == -1 and any(k in c for k in ("group name", "tên nhóm", "name")):
            mapping["name_idx"] = idx
        elif mapping["privacy_idx"] == -1 and any(k in c for k in ("public", "private", "công khai", "riêng tư", "quyền")):
            mapping["privacy_idx"] = idx
        elif mapping["members_idx"] == -1 and any(k in c for k in ("thành viên", "member", "số lượng")):
            mapping["members_idx"] = idx
        elif mapping["active_idx"] == -1 and any(k in c for k in ("tự động", "auto", "đăng bài", "(y/n)", "active")):
            mapping["active_idx"] = idx

    # Fallback if URL column was not matched by keywords (e.g. index 1 standard)
    if mapping["url_idx"] == -1 and len(header) >= 2:
        mapping["url_idx"] = 1

    return mapping


def parse_group_sheet(
    csv_text: str,
    filter_active_only: bool = False,
    default_active_if_empty: bool = True
) -> Dict[str, Any]:
    """
    Parse CSV data from Google Sheets, extract metadata, deduplicate URLs, and classify groups.
    
    Returns structured summary with clean unique groups and duplicate breakdown.
    """
    if not csv_text or not csv_text.strip():
        return {
            "success": False,
            "error": "Nội dung CSV trống.",
            "total_rows": 0,
            "unique_count": 0,
            "duplicates_count": 0,
            "groups": []
        }

    reader = csv.reader(io.StringIO(csv_text))
    rows = [r for r in reader if r and any(cell.strip() for cell in r)]
    if not rows:
        return {
            "success": False,
            "error": "Không tìm thấy dữ liệu dòng nào trong CSV.",
            "total_rows": 0,
            "unique_count": 0,
            "duplicates_count": 0,
            "groups": []
        }

    header = rows[0]
    indices = _detect_header_indices(header)
    url_idx = indices["url_idx"]
    name_idx = indices["name_idx"]
    privacy_idx = indices["privacy_idx"]
    members_idx = indices["members_idx"]
    active_idx = indices["active_idx"]

    data_rows = rows[1:]
    
    # Check if the active column has any values at all across the sheet
    has_any_active_flags = False
    if active_idx != -1:
        has_any_active_flags = any(
            len(r) > active_idx and bool(r[active_idx].strip())
            for r in data_rows
        )

    unique_groups: List[Dict[str, Any]] = []
    seen_urls: Dict[str, Dict[str, Any]] = {}
    duplicates: List[Dict[str, Any]] = []

    for row_idx, row in enumerate(data_rows, start=2):
        if url_idx >= len(row):
            continue

        raw_url = row[url_idx].strip()
        if not raw_url or "facebook.com" not in raw_url.lower():
            continue

        canonical_url = normalize_target_url(raw_url).lower()
        if not canonical_url:
            continue

        # Extract metadata
        name = row[name_idx].strip() if 0 <= name_idx < len(row) else ""
        privacy_raw = row[privacy_idx].strip() if 0 <= privacy_idx < len(row) else ""
        members_raw = row[members_idx].strip() if 0 <= members_idx < len(row) else ""
        active_raw = row[active_idx].strip() if 0 <= active_idx < len(row) else ""

        privacy = parse_privacy_type(privacy_raw)
        members = parse_member_count(members_raw)

        # Active flag determination
        if has_any_active_flags:
            is_active = is_active_flag(active_raw)
        else:
            is_active = True if default_active_if_empty else False

        group_item = {
            "id": uuid.uuid4().hex[:12],
            "url": canonical_url,
            "raw_url": raw_url,
            "name": name or canonical_url,
            "group_type": privacy,
            "member_count": members,
            "is_active": is_active,
            "sheet_row": row_idx,
            "status": "approved" if is_active else "not_requested",
            "notes": f"Google Sheet row {row_idx} · {members_raw or '0'} members",
        }

        # Deduplication check
        if canonical_url in seen_urls:
            existing = seen_urls[canonical_url]
            duplicates.append({
                "duplicate_url": canonical_url,
                "first_row": existing["sheet_row"],
                "duplicate_row": row_idx,
                "name": name or existing["name"]
            })
            # If the current row has more complete metadata (e.g. member count), update it
            if members and not existing.get("member_count"):
                existing["member_count"] = members
            if name and (existing["name"] == canonical_url or not existing.get("name")):
                existing["name"] = name
        else:
            seen_urls[canonical_url] = group_item
            unique_groups.append(group_item)

    # Filter by active flag if requested
    if filter_active_only:
        selected_groups = [g for g in unique_groups if g["is_active"]]
    else:
        selected_groups = unique_groups

    return {
        "success": True,
        "total_rows": len(data_rows),
        "rows_with_urls": len(unique_groups) + len(duplicates),
        "unique_count": len(unique_groups),
        "duplicates_count": len(duplicates),
        "active_count": sum(1 for g in unique_groups if g["is_active"]),
        "selected_count": len(selected_groups),
        "duplicates_details": duplicates,
        "groups": selected_groups,
        "header_mapping": indices,
    }


def sync_to_group_registry(groups: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Save the parsed unique groups into the application's persistent group registry.
    Integrates with both SQLite GroupRepository and DATA_DIR/groups.json.
    """
    import json
    from repositories.group_repo import GroupRepository

    if not groups:
        return {"saved_count": 0, "status": "no_groups"}

    groups_file = DATA_DIR / "group_registry.json"
    existing_list: List[Dict[str, Any]] = []
    try:
        if groups_file.exists():
            with open(groups_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, list):
                    existing_list = loaded
    except (OSError, ValueError):
        existing_list = []

    try:
        repo = GroupRepository()
        for item in repo.list_groups():
            url = normalize_target_url(item.get("url") or "").lower()
            if url and not any(normalize_target_url(g.get("url") or "").lower() == url for g in existing_list):
                existing_list.append(item)
    except Exception as sqle:
        print(f"Warning: GroupRepository read error: {sqle}")
        repo = None

    merged_list = [item.copy() for item in existing_list]
    by_url = {
        normalize_target_url(item.get("url") or "").lower(): item
        for item in merged_list if item.get("url")
    }
    imported_count = 0
    updated_count = 0
    for group in groups:
        url = normalize_target_url(group.get("url") or "").lower()
        if not url:
            continue
        existing = by_url.get(url)
        if existing is None:
            item = group.copy()
            item["url"] = url
            item.setdefault("id", uuid.uuid4().hex[:12])
            item.setdefault("category", "homestay_hue")
            merged_list.append(item)
            by_url[url] = item
            imported_count += 1
        else:
            existing.update({
                "name": group.get("name") or existing.get("name", url),
                "member_count": group.get("member_count") or existing.get("member_count"),
                "group_type": group.get("group_type") or existing.get("group_type", "unknown"),
                "notes": group.get("notes") or existing.get("notes", ""),
            })
            updated_count += 1

    if repo is not None:
        repo.save_groups(merged_list)

    temp_file = groups_file.with_suffix(".json.tmp")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(merged_list, f, ensure_ascii=False, indent=2)
        temp_file.replace(groups_file)
    finally:
        if temp_file.exists():
            temp_file.unlink()

    return {
        "saved_count": len(groups),
        "imported_count": imported_count,
        "updated_count": updated_count,
        "registry_count": len(merged_list),
        "status": "success"
    }
