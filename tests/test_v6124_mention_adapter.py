"""Focused tests for isolated Facebook mention adapter."""
import unittest
from unittest.mock import patch
from adapters.facebook_mention import _rank_candidate, MentionResult

class FakeHandle: pass
class FakeEditor:
    def element_handle(self): return FakeHandle()
class FakeLinks:
    def __init__(self, hrefs): self.hrefs=hrefs
    def count(self): return len(self.hrefs)
    def nth(self,i): return FakeLink(self.hrefs[i])
class FakeLink:
    def __init__(self, href): self.href=href
    def get_attribute(self,k): return self.href
class FakeRow:
    def __init__(self,text,hrefs=(),inside=False): self.text=text; self.hrefs=list(hrefs); self.inside=inside
    def is_visible(self,timeout=0): return True
    def evaluate(self,script,handle): return self.inside
    def inner_text(self,timeout=0): return self.text
    def locator(self,sel): return FakeLinks(self.hrefs)

class MentionAdapterTests(unittest.TestCase):
    def setUp(self):
        self.entity={"name":"UMEE Homestay","handle":"umeehomestay"}
        self.editor=FakeEditor()
    def test_editor_echo_is_never_candidate(self):
        self.assertIsNone(_rank_candidate(FakeRow('@UMEE Homestay', inside=True), self.entity, self.editor))
    def test_plain_exact_name_without_page_semantics_is_rejected(self):
        self.assertIsNone(_rank_candidate(FakeRow('@UMEE Homestay'), self.entity, self.editor))
    @patch('adapters.facebook_mention._visible', return_value=True)
    def test_page_metadata_candidate_is_accepted(self, _):
        info=_rank_candidate(FakeRow('UMEE Homestay' + chr(10) + 'Page - 973 followers'), self.entity, self.editor)
        self.assertIsNotNone(info); self.assertIn('page_type', info['evidence'])
    @patch('adapters.facebook_mention._visible', return_value=True)
    def test_canonical_href_is_strongest(self, _):
        info=_rank_candidate(FakeRow('UMEE Homestay', ['https://facebook.com/umeehomestay']), self.entity, self.editor)
        self.assertGreaterEqual(info['score'], 200)

if __name__ == '__main__': unittest.main()
