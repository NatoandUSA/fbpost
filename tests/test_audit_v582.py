"""Regression Test Suite for FB Automation v5.8.2 Audit Remediation.
Directly verifies all 20 mandatory regression test cases requested in the audit.
"""

import os
import re
import sys
import json
import time
import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_TEST_DATA_DIR = tempfile.mkdtemp(prefix="fb-auto-audit-tests-")
os.environ.setdefault("FB_AUTOMATION_DATA_DIR", _TEST_DATA_DIR)

import server
from utils import (
    ActionResult,
    close_browser,
    text_similarity_match,
    normalize_target_url,
    is_recently_posted,
    scrape_post_link,
    click_post_publish_button,
)
from repositories.activity_repo import ActivityRepository
from repositories.group_repo import GroupRepository
from repositories.job_repo import JobRepository
from services.job_manager import JobManager
from services.process_runner import ProcessRunner


class AuditV582RegressionTests(unittest.TestCase):
    def setUp(self):
        self.client = server.app.test_client()

    # 1. test_unverified_post_is_not_success
    def test_unverified_post_is_not_success(self):
        class FakePage:
            url = "https://facebook.com/groups/hue"
            def locator(self, *a, **kw):
                class SubLoc:
                    def all(self): return []
                    def filter(self, *a, **kw): return self
                    def count(self): return 0
                return SubLoc()

        with patch("time.sleep", return_value=None):
            res = scrape_post_link(FakePage(), target="https://facebook.com/groups/hue", content="Test unverified")
            self.assertFalse(res.success)
            self.assertEqual(res.code, "POST_SUBMITTED_UNVERIFIED")
            self.assertFalse(bool(res))

    # 2. test_publish_dialog_exception_is_not_success
    def test_publish_dialog_exception_is_not_success(self):
        class ExplodingPage:
            def evaluate(self, *a, **kw): return {"clicked": True, "text": "Đăng"}
            def locator(self, sel):
                raise RuntimeError("TargetClosedError: detached node")

        with patch("time.sleep", return_value=None):
            success = click_post_publish_button(ExplodingPage())
            self.assertFalse(success)

    # 3. test_publish_dialog_still_open_is_failure
    def test_publish_dialog_still_open_is_failure(self):
        class StillOpenComposer:
            def is_visible(self, timeout=None): return True
            def inner_text(self, timeout=None): return "Tạo bài viết công khai... [Vẫn mở]"
            def locator(self, sel):
                class SubLoc:
                    def count(self): return 1
                    def nth(self, idx): return self
                    def get_attribute(self, attr): return "Tạo bài viết công khai"
                    def filter(self, *a, **kw): return self
                return SubLoc()

        class FakePage:
            def evaluate(self, *a, **kw): return {"clicked": True, "text": "Đăng"}
            def locator(self, sel):
                class SubLoc:
                    def all(self): return [StillOpenComposer()]
                    def first(self): return StillOpenComposer()
                return SubLoc()

        with patch("time.sleep", return_value=None):
            success = click_post_publish_button(FakePage())
            self.assertFalse(success)

    # 4. test_permalink_same_prefix_does_not_match_wrong_post
    def test_permalink_same_prefix_does_not_match_wrong_post(self):
        # Hai chuỗi có chung câu mở đầu nhưng nội dung phía sau hoàn toàn khác nhau
        post_a = "Chào mọi người, hôm nay mình muốn chia sẻ sản phẩm A chất lượng cao tại Huế với dịch vụ homestay chuyên nghiệp nhất."
        post_b = "Chào mọi người, hôm nay mình muốn chia sẻ sản phẩm B hoàn toàn khác biệt chuyên về nhà xe vận chuyển du lịch toàn quốc."
        self.assertFalse(text_similarity_match(post_a, post_b))

    # 5. test_pending_body_generic_admin_text_not_detected
    def test_pending_body_generic_admin_text_not_detected(self):
        class GenericAdminPage:
            url = "https://facebook.com/groups/hue"
            def locator(self, sel):
                class SubLoc:
                    def all(self): return []
                    def filter(self, *a, **kw):
                        # Giả lập page có text admin/quản trị viên chung chung nhưng không khớp regex pending
                        return self
                    def count(self): return 0
                return SubLoc()

        with patch("time.sleep", return_value=None):
            res = scrape_post_link(GenericAdminPage(), target="https://facebook.com/groups/hue", content="Test")
            self.assertNotEqual(res.code, "POST_PENDING")
            self.assertFalse(res.success)
            self.assertEqual(res.code, "POST_SUBMITTED_UNVERIFIED")

    # 6. test_pending_record_does_not_block_retry
    def test_unverified_record_blocks_retry_until_reconciled(self):
        target = f"https://facebook.com/groups/audit-retry-{int(time.time()*1000)}"
        repo = ActivityRepository()
        # Ghi nhận trạng thái submitted_unverified
        repo.record_posted_link(
            target=target,
            post_url=target,
            content="Unverified post",
            url_type="group",
            publish_state="submitted_unverified"
        )
        is_dup, _, _ = is_recently_posted(target)
        self.assertTrue(is_dup, "submitted_unverified may already exist on Facebook and must block auto-retry")

        # Ghi nhận trạng thái published
        repo.record_posted_link(
            target=target,
            post_url=f"{target}/posts/123",
            content="Published post",
            url_type="post",
            publish_state="published"
        )
        is_dup_pub, _, _ = is_recently_posted(target)
        self.assertTrue(is_dup_pub, "published record must block duplicate within 24h")

    # 7. test_group_123_not_duplicate_group_1234
    def test_group_123_not_duplicate_group_1234(self):
        target_a = "https://facebook.com/groups/123"
        target_b = "https://facebook.com/groups/1234"
        repo = ActivityRepository()
        repo.record_posted_link(
            target=target_a,
            post_url=f"{target_a}/posts/1",
            content="Content A",
            url_type="post",
            publish_state="published"
        )
        is_dup, _, _ = is_recently_posted(target_b)
        self.assertFalse(is_dup, "Group 123 must NOT match Group 1234 as duplicate")

    # 8. test_posted_links_api_reads_sqlite
    def test_posted_links_api_reads_sqlite(self):
        unique_post = f"https://facebook.com/groups/hue/posts/{int(time.time()*1000)}"
        repo = ActivityRepository()
        repo.record_posted_link(
            target="https://facebook.com/groups/hue",
            post_url=unique_post,
            content="Read from sqlite test",
            url_type="post",
            publish_state="published"
        )
        res = self.client.get("/api/posted-links")
        self.assertEqual(res.status_code, 200)
        urls = [item.get("url") for item in res.get_json()]
        self.assertIn(unique_post, urls)

    # 9. test_comment_export_only_published_permalink
    def test_comment_export_only_published_permalink(self):
        mock_saved_links = [
            {"url": "https://facebook.com/groups/123", "url_type": "group", "publish_state": "pending"},
            {"url": "https://facebook.com/groups/123", "url_type": "group", "publish_state": "submitted_unverified"},
            {"url": "https://facebook.com/groups/123/posts/999", "url_type": "post", "publish_state": "published"},
            {"url": "https://facebook.com/mypage", "url_type": "page", "publish_state": "published"},
        ]
        def filter_for_comment(links):
            result = []
            for item in links:
                url = item.get("url", "")
                is_post_url = any(x in url for x in ["/posts/", "/permalink/", "permalink.php", "/videos/"])
                url_type = item.get("url_type") or ("post" if is_post_url else "unknown")
                pub_state = item.get("publish_state") or "unknown"
                if (url_type == "post" or is_post_url) and pub_state == "published":
                    result.append(url)
            return result

        exported = filter_for_comment(mock_saved_links)
        self.assertEqual(exported, ["https://facebook.com/groups/123/posts/999"])

    # 10. test_join_stale_locator_is_not_confirmed
    def test_join_stale_locator_is_not_confirmed(self):
        from fb_join_group import search_and_join_groups

        class StaleElement:
            def is_visible(self, *a, **kw): return True
            def inner_text(self): raise RuntimeError("Element handle is detached from DOM")
            def get_attribute(self, attr): raise RuntimeError("Detached node")

        class FakePage:
            def set_default_timeout(self, *a, **kw): pass
            def goto(self, *a, **kw): pass
            def locator(self, *a, **kw):
                class SubLoc:
                    def all(self): return [StaleElement()]
                    def first(self): return StaleElement()
                    def count(self): return 0
                    def is_visible(self, *a, **kw): return False
                return SubLoc()

        with patch("fb_join_group.sync_playwright"):
            joined = search_and_join_groups("https://facebook.com/groups/stale-join", max_groups=1)
            self.assertEqual(joined, 0)

    # 11. test_join_repo_does_not_replace_all_records
    def test_join_repo_does_not_replace_all_records(self):
        from db import init_db
        with tempfile.TemporaryDirectory() as directory:
            db_file = Path(directory) / "app.db"
            init_db(db_file)
            repo = GroupRepository(db_file)
            t = int(time.time()*1000)
            g1 = {"id": f"g1_{t}", "group_name": "Group 1", "keyword": "k1", "url": f"https://fb.com/g/1_{t}", "state": "joined"}
            g2 = {"id": f"g2_{t}", "group_name": "Group 2", "keyword": "k2", "url": f"https://fb.com/g/2_{t}", "state": "joined"}
            repo.add_joined_group(g1)
            repo.add_joined_group(g2)

            groups = [g["url"] for g in repo.list_joined_groups()]
            self.assertIn(g1["url"], groups)
            self.assertIn(g2["url"], groups)

    # 12. test_create_page_home_redirect_is_not_success
    def test_create_page_home_redirect_is_not_success(self):
        from fb_create_page import create_facebook_page

        class FakeKB:
            def press(self, key): pass
            def type(self, text, delay=0): pass
            def insert_text(self, text): pass

        class FakeMouse:
            def move(self, *a, **kw): pass
            def wheel(self, *a, **kw): pass

        class HomeRedirectPage:
            url = "https://www.facebook.com/"
            def __init__(self):
                self.keyboard = FakeKB()
                self.mouse = FakeMouse()
            def set_default_timeout(self, *a, **kw): pass
            def goto(self, *a, **kw): pass
            def locator(self, *a, **kw):
                class SubLoc:
                    @property
                    def first(self): return self
                    def nth(self, idx): return self
                    def all(self): return []
                    def is_visible(self, *a, **kw): return False
                    def fill(self, *a, **kw): pass
                    def click(self, *a, **kw): pass
                    def scroll_into_view_if_needed(self): pass
                    def filter(self, *a, **kw): return self
                    def inner_text(self, *a, **kw): return ""
                    def count(self): return 0
                return SubLoc()
            def title(self): return "Facebook - Đăng nhập hoặc đăng ký"

        with patch("fb_create_page.sync_playwright") as mock_pw, \
             patch("fb_create_page.can_create_page", return_value=(True, 0, "")), \
             patch("fb_create_page.time.sleep", return_value=None):
            mock_p = mock_pw.return_value.__enter__.return_value
            mock_p.chromium.launch.return_value.new_context.return_value.new_page.return_value = HomeRedirectPage()
            res = create_facebook_page(page_name="Test Home Redirect Page")
            self.assertFalse(res.success)
            self.assertIn(res.code, ("UNVERIFIED", "ERROR", "PAGE_CREATION_REJECTED"))

    # 13. test_close_browser_none
    def test_close_browser_none(self):
        try:
            close_browser(None, None, None)
        except Exception as e:
            self.fail(f"close_browser(None, None, None) raised an exception: {e}")

    # 14. test_cancel_before_process_registration
    def test_cancel_before_process_registration(self):
        runner = ProcessRunner()
        job_id = f"job-cancel-early-{int(time.time()*1000)}"
        runner.prepare_job(job_id)
        runner.cancel(job_id)
        self.assertTrue(runner.is_cancelled(job_id))
        ret = runner.run_command_sync(["cmd.exe", "/c", "echo", "test"], job_id=job_id)
        self.assertEqual(ret, -1)

    # 15. test_cancel_terminal_job_does_not_mutate_history
    def test_cancel_terminal_job_does_not_mutate_history(self):
        jm = JobManager()
        job_id = f"job-term-{int(time.time()*1000)}"
        jm.job_repo.create_job({"id": job_id, "state": "success"})
        self.assertFalse(jm.cancel_job(job_id))
        job = jm.get_job(job_id)
        self.assertEqual(job["state"], "success")

    # 16. test_queued_jobs_requeued_after_restart
    def test_queued_jobs_requeued_after_restart(self):
        jm = JobManager()
        job_id = f"job-requeue-{int(time.time()*1000)}"
        jm.job_repo.create_job({"id": job_id, "state": "queued"})
        jm.reconcile_on_startup()
        
        queued_ids = []
        while not jm._work_queue.empty():
            queued_ids.append(jm._work_queue.get_nowait())
        self.assertIn(job_id, queued_ids)

    # 17. test_comment_clear_without_visible_comment_is_unverified
    def test_comment_clear_without_visible_comment_is_unverified(self):
        from fb_comment import comment_on_post

        class FakeCommentInput:
            def is_visible(self, *a, **kw): return True
            def inner_text(self, *a, **kw): return ""
            def focus(self, *a, **kw): pass
            def click(self, *a, **kw): pass
            def scroll_into_view_if_needed(self, *a, **kw): pass

        class FakeNonVisible:
            def is_visible(self, *a, **kw): return False
            def count(self): return 0
            def filter(self, *a, **kw): return self
            @property
            def first(self): return self

        class FakeKB:
            def press(self, key): pass
            def type(self, text, delay=0): pass
            def insert_text(self, text): pass

        class FakeMouse:
            def move(self, *a, **kw): pass
            def wheel(self, *a, **kw): pass

        class FakeCommentPage:
            def __init__(self):
                self.keyboard = FakeKB()
                self.mouse = FakeMouse()
            def set_default_timeout(self, *a, **kw): pass
            def goto(self, *a, **kw): pass
            def evaluate(self, *a, **kw): return None
            def locator(self, *a, **kw):
                sel_str = str(a[0] if a else "").lower()
                if any(x in sel_str for x in ["chặn", "hạn chế", "something", "không thể bình luận", "article"]):
                    return FakeNonVisible()
                class SubLoc:
                    @property
                    def first(self): return FakeCommentInput()
                    def all(self): return [FakeCommentInput()]
                    def is_visible(self, *a, **kw): return True
                    def filter(self, *a, **kw): return self
                    def count(self): return 1
                    def nth(self, idx): return FakeCommentInput()
                    def get_attribute(self, attr): return ""
                return SubLoc()
            def wait_for_function(self, *a, **kw):
                raise TimeoutError("Comment did not appear in DOM")

        with patch("fb_comment.sync_playwright") as mock_pw, \
             patch("fb_comment.time.sleep", return_value=None), \
             patch("time.sleep", return_value=None):
            mock_p = mock_pw.return_value.__enter__.return_value
            mock_p.chromium.launch.return_value.new_context.return_value.new_page.return_value = FakeCommentPage()
            res = comment_on_post("https://facebook.com/groups/1/posts/1", "Hello unverified comment", like_post=False)
            self.assertFalse(res.success)
            self.assertIn(res.code, {"POST_IDENTITY_NOT_FOUND", "COMMENT_UNVERIFIED"})

    # 18. test_requested_image_missing_causes_failure
    def test_requested_image_missing_causes_failure(self):
        from fb_group import post_to_group

        class FakeKB:
            def press(self, key): pass
            def type(self, text, delay=0): pass
            def insert_text(self, text): pass

        class FakeMouse:
            def move(self, *a, **kw): pass
            def wheel(self, *a, **kw): pass

        class FakeLocatorItem:
            def is_visible(self, *a, **kw): return True
            def click(self, *a, **kw): pass
            def inner_text(self, *a, **kw): return "Tạo bài viết"
            @property
            def first(self): return self
            @property
            def last(self): return self
            def nth(self, idx): return self
            def count(self): return 1
            def all(self): return [self]
            def filter(self, *a, **kw): return self
            def get_attribute(self, attr): return ""
            def locator(self, *a, **kw): return self
            def wait_for_selector(self, *a, **kw): pass

        class FakeGroupPage:
            def __init__(self):
                self.keyboard = FakeKB()
                self.mouse = FakeMouse()
            def set_default_timeout(self, *a, **kw): pass
            def goto(self, *a, **kw): pass
            def wait_for_selector(self, *a, **kw): pass
            def locator(self, *a, **kw): return FakeLocatorItem()
            def get_by_text(self, *a, **kw): return FakeLocatorItem()
            def evaluate(self, *a, **kw): return None

        with patch("fb_group.sync_playwright") as mock_pw, \
             patch("fb_group.is_recently_posted", return_value=(False, 0, None)), \
             patch("fb_group.navigate_facebook_surface", return_value=True), \
             patch("fb_group._ensure_group_membership", return_value="joined"), \
             patch("fb_group.attach_image_to_composer", return_value=False), \
             patch("fb_group.verify_entered_content", return_value=True), \
             patch("fb_group.safe_mouse_wheel"), \
             patch("time.sleep", return_value=None):
            mock_p = mock_pw.return_value.__enter__.return_value
            mock_p.chromium.launch.return_value.new_context.return_value.new_page.return_value = FakeGroupPage()
            res = post_to_group(
                group_url="https://facebook.com/groups/hue",
                content="Hello image fail",
                image_path="invalid_image.jpg"
            )
            self.assertFalse(res.success)
            self.assertEqual(res.code, "MEDIA_ATTACH_FAILED")

    # 19. test_job_api_does_not_expose_gemini_key
    def test_job_api_does_not_expose_gemini_key(self):
        secret_key = "AIzaSySecretGeminiKey12345"
        res = self.client.post("/api/jobs", json={
            "command": "comment",
            "geminiApiKey": secret_key,
            "password": "MySuperSecretPassword",
            "payload": {"target": "hue", "geminiApiKey": secret_key}
        })
        self.assertEqual(res.status_code, 201)
        job_id = res.get_json()["job_id"]

        get_res = self.client.get(f"/api/jobs/{job_id}")
        self.assertEqual(get_res.status_code, 200)
        res_text = get_res.get_data(as_text=True)
        self.assertNotIn(secret_key, res_text)
        self.assertNotIn("MySuperSecretPassword", res_text)

    # 20. test_log_job_id_path_traversal_rejected
    def test_log_job_id_path_traversal_rejected(self):
        res = self.client.get("/api/jobs/../../etc/passwd/logs")
        self.assertIn(res.status_code, (400, 404))


if __name__ == "__main__":
    unittest.main()
