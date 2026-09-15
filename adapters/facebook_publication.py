"""Stable boundary for Facebook publication/permalink evidence."""
from utils import (
    _scan_post_permalink_once as _legacy_scan,
    _copy_post_permalink_via_share_sheet as _legacy_copy,
    _has_pending_post_notice as _legacy_pending,
)


def scan_post_permalink(page, target="", content="", max_articles=10):
    return _legacy_scan(page, target=target, content=content, max_articles=max_articles)


def copy_post_permalink(page, target="", content=""):
    return _legacy_copy(page, target=target, content=content)


def has_pending_notice(page):
    return _legacy_pending(page)
