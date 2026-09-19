"""Focused tests for isolated Facebook mention adapter."""
import unittest
from unittest.mock import patch
from adapters.facebook_mention import _rank_candidate, MentionResult, _insert_multiline_suffix

class FakeHandle: pass
class FakeEditor:
    def element_handle(self): return FakeHandle()
    def focus(self, timeout=0): return None
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
class FakeKeyboard:
    def __init__(self): self.events=[]
    def insert_text(self, text): self.events.append(('insert', text))
    def press(self, key): self.events.append(('press', key))
class FakePage:
    def __init__(self): self.keyboard=FakeKeyboard()

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
    @patch('adapters.facebook_mention.time.sleep', return_value=None)
    def test_multiline_suffix_preserves_line_boundaries_without_single_multiline_insert(self, _):
        page=FakePage()
        suffix=' first line\n\n#UMEEHomestay #LacasaHomestay\n' + ('x'*170)
        _insert_multiline_suffix(page, self.editor, suffix)
        inserts=[value for kind,value in page.keyboard.events if kind=='insert']
        presses=[value for kind,value in page.keyboard.events if kind=='press']
        self.assertTrue(inserts)
        self.assertTrue(all('\n' not in value for value in inserts))
        self.assertEqual(presses, ['Shift+Enter','Shift+Enter','Shift+Enter'])
        self.assertTrue(all(len(value) <= 80 for value in inserts))
        rebuilt=''.join(inserts)
        self.assertIn('#UMEEHomestay #LacasaHomestay', rebuilt)
        self.assertIn('x'*80, rebuilt)

if __name__ == '__main__': unittest.main()
