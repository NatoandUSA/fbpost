import fb_comment


URL = "https://www.facebook.com/groups/rivewdulichtphue/posts/1391877076350479"


class _Count:
    def __init__(self, n=0): self.n = n
    def count(self): return self.n
    def nth(self, i): raise AssertionError("no dialogs expected")


class _HydrationPage:
    def __init__(self, ready_after_wait=True, exact_route=True):
        self.ready = False
        self.ready_after_wait = ready_after_wait
        self.url = URL if exact_route else "https://www.facebook.com/"
    def locator(self, selector):
        if selector.startswith("a[href*='1391877076350479']"):
            return _Count(1 if self.ready else 0)
        if selector == "div[role='article']":
            return _Count(0)
        if selector == "div[role='dialog']":
            return _Count(0)
        raise AssertionError(selector)
    def wait_for_timeout(self, ms):
        if self.ready_after_wait:
            self.ready = True


def test_permalink_hydration_waits_for_concrete_exact_route_evidence():
    page = _HydrationPage()
    assert fb_comment._wait_for_permalink_hydration(page, URL, timeout_seconds=0.05) is True


def test_permalink_hydration_never_accepts_loading_shell_or_wrong_route():
    splash = _HydrationPage(ready_after_wait=False, exact_route=True)
    assert fb_comment._wait_for_permalink_hydration(splash, URL, timeout_seconds=0.01) is False
    wrong = _HydrationPage(ready_after_wait=True, exact_route=False)
    assert fb_comment._wait_for_permalink_hydration(wrong, URL, timeout_seconds=0.01) is False


class _Dialog:
    def __init__(self, name, contains=()):
        self.name = name
        self.contains = set(contains)
    def element_handle(self):
        return self
    def evaluate(self, script, inner):
        return inner.name in self.contains


def test_nested_dialog_wrappers_collapse_to_innermost_modal():
    outer = _Dialog("outer", contains={"inner"})
    inner = _Dialog("inner")
    assert fb_comment._innermost_visible_dialogs([outer, inner]) == [inner]


def test_true_sibling_dialogs_remain_ambiguous():
    left = _Dialog("left")
    right = _Dialog("right")
    assert fb_comment._innermost_visible_dialogs([left, right]) == [left, right]
