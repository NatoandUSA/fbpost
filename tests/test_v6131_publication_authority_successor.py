from unittest.mock import patch

import fb_reconcile
import utils


CANONICAL = "https://www.facebook.com/groups/garahue/posts/123456789"
TARGET = "https://facebook.com/groups/garahue"
CONTENT = "Unique certification content long enough for matching."


class FakePage:
    url = TARGET
    def set_default_timeout(self, value): pass
    def goto(self, *args, **kwargs): return None
    def reload(self, *args, **kwargs): return None


class FakePlaywrightContext:
    def __enter__(self): return object()
    def __exit__(self, *args): return False


def test_scrape_prefers_my_posted_before_group_search():
    page = FakePage()
    with patch.object(utils.time, "sleep", return_value=None), \
         patch.object(utils, "_scan_post_permalink_once", return_value=""), \
         patch.object(utils, "_copy_post_permalink_via_share_sheet", return_value=""), \
         patch.object(utils, "_has_pending_post_notice", return_value=False), \
         patch.object(utils, "_has_published_toast", return_value=False), \
         patch.object(utils, "_search_group_my_posted_by_content", return_value=CANONICAL), \
         patch.object(utils, "_search_group_pending_by_content", return_value=False), \
         patch.object(utils, "_search_group_post_by_content") as group_search, \
         patch.object(utils, "record_posted_link"):
        result = utils.scrape_post_link(page, target=TARGET, content=CONTENT, account_id="acc")
    assert result.state == "published"
    assert result.result_url == CANONICAL
    group_search.assert_not_called()


def test_scrape_pending_is_terminal_without_permalink_authority():
    page = FakePage()
    with patch.object(utils.time, "sleep", return_value=None), \
         patch.object(utils, "_scan_post_permalink_once", return_value=""), \
         patch.object(utils, "_copy_post_permalink_via_share_sheet", return_value=""), \
         patch.object(utils, "_has_pending_post_notice", return_value=False), \
         patch.object(utils, "_has_published_toast", return_value=False), \
         patch.object(utils, "_search_group_my_posted_by_content", return_value=""), \
         patch.object(utils, "_search_group_pending_by_content", return_value=True), \
         patch.object(utils, "_search_group_post_by_content") as group_search, \
         patch.object(utils, "record_posted_link"):
        result = utils.scrape_post_link(page, target=TARGET, content=CONTENT, account_id="acc")
    assert result.code == "POST_PENDING"
    assert result.state == "pending"
    assert not result.result_url
    assert result.metadata["evidence_source"] == "facebook_my_pending_content"
    group_search.assert_not_called()


def _reconcile_patches(my_posted="", pending=False):
    return (
        patch.object(fb_reconcile, "sync_playwright", return_value=FakePlaywrightContext()),
        patch.object(fb_reconcile, "resolve_account", return_value={"id": "acc", "name": "M14"}),
        patch.object(fb_reconcile, "launch_browser", return_value=(object(), object(), FakePage())),
        patch.object(fb_reconcile, "close_browser"),
        patch.object(fb_reconcile, "_scan_post_permalink_once", return_value=""),
        patch.object(fb_reconcile, "_copy_post_permalink_via_share_sheet", return_value=""),
        patch.object(fb_reconcile, "_has_pending_post_notice", return_value=False),
        patch.object(fb_reconcile, "search_my_posted", return_value=my_posted),
        patch.object(fb_reconcile, "search_pending", return_value=pending),
        patch.object(fb_reconcile, "search_group_post"),
        patch.object(fb_reconcile, "record_posted_link"),
        patch("repositories.activity_repo.ActivityRepository.list_posted_links", return_value=[]),
        patch.object(fb_reconcile.time, "sleep", return_value=None),
    )


def test_reconcile_prefers_my_posted_authority():
    patches = _reconcile_patches(my_posted=CANONICAL)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], \
         patches[7] as my_posted, patches[8] as pending, patches[9] as group_search, \
         patches[10], patches[11], patches[12]:
        result = fb_reconcile.reconcile_existing_post(TARGET, CONTENT, "acc", "http://127.0.0.1:19995")
    assert result.code == "RECONCILE_PUBLISHED"
    assert result.state == "published"
    assert result.result_url == CANONICAL
    assert result.metadata["evidence_source"] == "facebook_my_posted_content"
    my_posted.assert_called_once()
    pending.assert_not_called()
    group_search.assert_not_called()


def test_reconcile_pending_never_grants_permalink_authority():
    patches = _reconcile_patches(my_posted="", pending=True)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], \
         patches[7], patches[8] as pending, patches[9] as group_search, \
         patches[10], patches[11], patches[12]:
        result = fb_reconcile.reconcile_existing_post(TARGET, CONTENT, "acc", "http://127.0.0.1:19995")
    assert result.code == "RECONCILE_PENDING"
    assert result.state == "pending"
    assert result.result_url == ""
    assert result.metadata["evidence_source"] == "facebook_my_pending_content"
    pending.assert_called_once()
    group_search.assert_not_called()


class _EmptyArticles:
    def count(self): return 0
    def nth(self, idx): raise AssertionError("no articles expected")


class _Mouse:
    def wheel(self, x, y): return None


class _Anchor:
    def __init__(self, href): self.href = href
    def get_attribute(self, name): return self.href if name == "href" else ""


class _AnchorList:
    def __init__(self, href): self.href = href
    def all(self): return [_Anchor(self.href)]


class _Body:
    def __init__(self, text): self.text = text
    def inner_text(self, timeout=None): return self.text


class _Probe:
    def __init__(self, text): self.text = text
    def goto(self, *args, **kwargs): return None
    def locator(self, selector):
        assert selector == "body"
        return _Body(self.text)
    def close(self): return None


class _Context:
    def __init__(self, text): self.text = text
    def new_page(self): return _Probe(self.text)


class _GroupSearchPage:
    def __init__(self, candidate, candidate_text):
        self.candidate = candidate
        self.goto_url = ""
        self.mouse = _Mouse()
        self.context = _Context(candidate_text)
    def goto(self, url, **kwargs): self.goto_url = url
    def locator(self, selector):
        if selector == "div[role='article']":
            return _EmptyArticles()
        if "a[href*='/groups/']" in selector:
            return _AnchorList(self.candidate)
        raise AssertionError(selector)


def test_group_search_uses_short_fingerprint_query():
    page = _GroupSearchPage(CANONICAL, CONTENT)
    with patch.object(utils.time, "sleep", return_value=None), \
         patch.object(utils, "_scan_post_permalink_once", return_value=CANONICAL):
        result = utils._search_group_post_by_content(page, TARGET, CONTENT)
    assert result == CANONICAL
    assert "q=Unique%20certification%20content%20long%20enough" in page.goto_url


def test_group_search_verifies_canonical_candidate_when_article_layout_missing():
    page = _GroupSearchPage(CANONICAL, CONTENT)
    with patch.object(utils.time, "sleep", return_value=None), \
         patch.object(utils, "_scan_post_permalink_once", return_value=""):
        result = utils._search_group_post_by_content(page, TARGET, CONTENT)
    assert result == CANONICAL
