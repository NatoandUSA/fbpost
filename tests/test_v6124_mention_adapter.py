"""Focused tests for isolated Facebook mention adapter."""
import unittest
from unittest.mock import patch
from adapters.facebook_mention import _rank_candidate, type_with_page_mention, MentionResult

class FakeHandle: pass
class FakeEditor:
    def __init__(self, events=None): self.events=events if events is not None else []
    def element_handle(self): return FakeHandle()
    def fill(self, value): self.events.append(("fill", value))
    def focus(self, timeout=0): self.events.append(("focus", timeout))
    def evaluate(self, script): self.events.append(("caret_end", script))
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

class FakeCandidate:
    def __init__(self, events): self.events=events
    def click(self, force=False, timeout=0): self.events.append(("candidate_click", None))
class FakeRows:
    def __init__(self, events): self.row=FakeCandidate(events)
    def count(self): return 1
    def nth(self, i): return self.row
class FakeKeyboard:
    def __init__(self, events): self.events=events
    def insert_text(self, value): self.events.append(("insert_text", value))
    def type(self, value, delay=0): self.events.append(("type", value))
class FakePage:
    def __init__(self, events): self.keyboard=FakeKeyboard(events)

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
    @patch('adapters.facebook_mention._semantic_commit_evidence', side_effect=[{"kind":"structured_mention"},{"kind":"structured_mention"}])
    @patch('adapters.facebook_mention._rank_candidate', return_value={"score":200,"evidence":["canonical_href"]})
    @patch('adapters.facebook_mention._candidate_rows')
    @patch('adapters.facebook_mention.page_entity')
    def test_suffix_is_appended_only_after_editor_focus_and_caret_restore(self, page_entity_mock, rows_mock, _rank, _evidence, _sleep):
        events=[]
        editor=FakeEditor(events)
        page=FakePage(events)
        page_entity_mock.return_value=self.entity
        rows_mock.return_value=FakeRows(events)
        result=type_with_page_mention(page,editor,'Hello UMEE Homestay — full caption suffix',brand_key='umee')
        self.assertTrue(result.verified)
        click_i=events.index(("candidate_click",None))
        caret_i=next(i for i,e in enumerate(events) if e[0]=="caret_end")
        suffix_i=events.index(("insert_text",' — full caption suffix'))
        self.assertLess(click_i,caret_i)
        self.assertLess(caret_i,suffix_i)
        self.assertEqual(events[suffix_i],("insert_text",' — full caption suffix'))

if __name__ == '__main__': unittest.main()
