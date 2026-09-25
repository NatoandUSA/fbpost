"""Stable boundary for Facebook publication/permalink evidence."""
from utils import (
    _scan_post_permalink_once as _legacy_scan,
    _copy_post_permalink_via_share_sheet as _legacy_copy,
    _has_pending_post_notice as _legacy_pending,
    _search_group_post_by_content as _legacy_group_search,
    _search_group_my_posted_by_content as _legacy_my_posted,
    _search_group_pending_by_content as _legacy_pending_content,
    _resolve_share_reference_to_group_post as _legacy_share_resolve,
)


def scan_post_permalink(page, target="", content="", max_articles=10):
    return _legacy_scan(page, target=target, content=content, max_articles=max_articles)


def copy_post_permalink(page, target="", content=""):
    return _legacy_copy(page, target=target, content=content)


def has_pending_notice(page):
    return _legacy_pending(page)


def search_group_post(page, target="", content=""):
    return _legacy_group_search(page, target=target, content=content)


def resolve_share_reference(page, reference="", target="", content=""):
    return _legacy_share_resolve(page, reference=reference, target=target, content=content)

def search_my_posted(page, target="", content=""):
    return _legacy_my_posted(page, target=target, content=content)


def search_pending(page, target="", content=""):
    return _legacy_pending_content(page, target=target, content=content)
