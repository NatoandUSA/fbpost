import unittest
from fb_comment import _canonicalize_comment_url
from utils import canonical_facebook_post_url

class GateDPermalinkContractTests(unittest.TestCase):
    def test_group_root_is_never_post_identity(self):
        self.assertEqual(canonical_facebook_post_url("https://www.facebook.com/groups/123"), "")
        self.assertEqual(_canonicalize_comment_url("https://www.facebook.com/groups/123"), "")

    def test_group_post_is_canonical(self):
        url="https://www.facebook.com/groups/123/posts/456/?__cft__=tracking"
        self.assertEqual(canonical_facebook_post_url(url),"https://www.facebook.com/groups/123/posts/456")
        self.assertEqual(_canonicalize_comment_url(url),"https://www.facebook.com/groups/123/posts/456")

    def test_permalink_query_requires_post_id(self):
        self.assertEqual(canonical_facebook_post_url("https://www.facebook.com/permalink.php?id=12"), "")
        self.assertIn("story_fbid=456", canonical_facebook_post_url("https://www.facebook.com/permalink.php?story_fbid=456&id=12"))

    def test_share_and_reel_routes_are_specific(self):
        self.assertEqual(canonical_facebook_post_url("https://www.facebook.com/share/p/abc123/"),"https://www.facebook.com/share/p/abc123")
        self.assertEqual(canonical_facebook_post_url("https://www.facebook.com/reel/999/"),"https://www.facebook.com/reel/999")

    def test_non_facebook_url_rejected(self):
        self.assertEqual(canonical_facebook_post_url("https://example.com/groups/123/posts/456"), "")

if __name__=="__main__":
    unittest.main()
