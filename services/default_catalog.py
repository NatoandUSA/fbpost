from __future__ import annotations

import csv
from pathlib import Path

from paths import BASE_DIR
from services.group_candidate import canonicalize_group_url, group_token_from_url

DEFAULT_GROUP_SEED = BASE_DIR / "seeds" / "group_catalog_hue.tsv"
DEFAULT_PROFILE_NAMES = ["M21", "M20", "M19", "M18", "M17", "M4", "M6", "M14"]


def load_default_group_rows(seed_file: Path | None = None):
    path = Path(seed_file or DEFAULT_GROUP_SEED)
    if not path.exists():
        return []
    merged = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            canonical = canonicalize_group_url((row.get("url") or "").strip())
            if not canonical:
                continue
            item = {
                "url": canonical,
                "group_id": group_token_from_url(canonical),
                "name": (row.get("name") or "").strip(),
                "privacy": (row.get("privacy") or "").strip(),
                "member_count": int(row.get("member_count") or 0),
            }
            current = merged.get(canonical)
            if not current or item["member_count"] > current["member_count"]:
                merged[canonical] = item
    return sorted(merged.values(), key=lambda x: (-x["member_count"], x["name"]))
