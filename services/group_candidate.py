"""Canonical Facebook Group candidate model shared by import, search and execution."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import urlparse, urlunparse


@dataclass(frozen=True)
class GroupCandidate:
    url: str
    group_id: str = ""
    name: str = ""
    source: str = "manual"
    privacy: str = ""
    member_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def canonicalize_group_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw.lstrip("/")
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if host in {"www.facebook.com", "m.facebook.com", "web.facebook.com"}:
        host = "facebook.com"
    if host != "facebook.com":
        return ""
    path_parts = [p for p in parsed.path.split("/") if p]
    if len(path_parts) < 2 or path_parts[0].lower() != "groups":
        return ""
    group_token = path_parts[1]
    clean_path = f"/groups/{group_token}"
    return urlunparse(("https", "facebook.com", clean_path, "", "", ""))
def group_token_from_url(value: str) -> str:
    canonical = canonicalize_group_url(value)
    if not canonical:
        return ""
    parts = [p for p in urlparse(canonical).path.split("/") if p]
    return parts[1] if len(parts) >= 2 else ""


def make_candidate(url: str, **kwargs) -> GroupCandidate:
    canonical = canonicalize_group_url(url)
    if not canonical:
        raise ValueError(f"Invalid group URL: {url}")
    return GroupCandidate(
        url=canonical,
        group_id=group_token_from_url(canonical),
        **kwargs,
    )
