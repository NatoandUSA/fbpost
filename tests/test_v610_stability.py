import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from db import connect_db, init_db
from repositories.group_catalog_repo import GroupCatalogRepository
from repositories.workflow_repo import WorkflowRepository
from services import profile_session_manager as psm
from services.default_catalog import load_default_group_rows
from services.group_candidate import canonicalize_group_url, group_token_from_url, make_candidate


class ProfileSessionManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_lock_dir = psm.LOCK_DIR
        psm.LOCK_DIR = Path(self.tmp.name) / "locks"
        psm._active_leases.clear()
        psm._runtime.clear()

    def tearDown(self):
        for key in list(psm._active_leases):
            psm.release_profile(key)
        psm.LOCK_DIR = self.old_lock_dir
        self.tmp.cleanup()

    def test_same_process_cannot_lease_profile_twice(self):
        psm.acquire_profile("M21", timeout=0.2)
        with self.assertRaises(psm.ProfileLeaseError):
            psm.acquire_profile("M21", timeout=0.2)

    def test_release_profile_allows_subsequent_acquisition(self):
        psm.acquire_profile("M20", timeout=0.2)
        psm.release_profile("M20")
        # Should succeed without error
        psm.acquire_profile("M20", timeout=0.2)
        psm.release_profile("M20")

    def test_cross_process_lease_blocks_second_owner(self):
        env = os.environ.copy()
        env["FB_PROFILE_LOCK_DIR"] = str(psm.LOCK_DIR)
        code = (
            "from services.profile_session_manager import acquire_profile,release_profile;"
            "import time; acquire_profile('M21',timeout=1); print('READY',flush=True);"
            "time.sleep(4); release_profile('M21')"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", code], cwd=str(Path(__file__).resolve().parents[1]),
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        try:
            self.assertEqual(proc.stdout.readline().strip(), "READY")
            with self.assertRaises(psm.ProfileLeaseError):
                psm.acquire_profile("M21", timeout=0.5)
        finally:
            proc.terminate()
            proc.communicate(timeout=5)


class GroupCandidateTests(unittest.TestCase):
    def test_canonicalize_group_url_formats(self):
        self.assertEqual(
            canonicalize_group_url("https://www.facebook.com/groups/homestayhue/permalink/123"),
            "https://facebook.com/groups/homestayhue"
        )
        self.assertEqual(
            canonicalize_group_url("m.facebook.com/groups/123456789/?ref=share"),
            "https://facebook.com/groups/123456789"
        )
        self.assertEqual(group_token_from_url("https://facebook.com/groups/my-hue-group"), "my-hue-group")

    def test_make_candidate(self):
        cand = make_candidate("https://facebook.com/groups/huegroup1", name="Hue Group", member_count=5000)
        self.assertEqual(cand.url, "https://facebook.com/groups/huegroup1")
        self.assertEqual(cand.group_id, "huegroup1")
        self.assertEqual(cand.name, "Hue Group")
        self.assertEqual(cand.member_count, 5000)


class WorkflowMigrationTests(unittest.TestCase):
    def test_workflow_schema_created_on_temp_db(self):
        with tempfile.TemporaryDirectory() as directory:
            db_file = Path(directory) / "app.db"
            init_db(db_file)
            conn = connect_db(db_file)
            try:
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                self.assertTrue({
                    "group_catalog",
                    "profile_presets",
                    "workflow_tasks",
                    "workflow_events",
                }.issubset(tables))
                columns = {
                    row[1]
                    for row in conn.execute("PRAGMA table_info(workflow_tasks)").fetchall()
                }
                self.assertTrue({
                    "phase",
                    "submission_status",
                    "verification_status",
                    "progress",
                    "error_code",
                    "evidence_dir",
                }.issubset(columns))

                # Check seed 007
                group_count = conn.execute("SELECT COUNT(*) FROM group_catalog").fetchone()[0]
                self.assertGreaterEqual(group_count, 50, "Migration 007 should seed Hue group catalog")

                preset_count = conn.execute("SELECT COUNT(*) FROM profile_presets").fetchone()[0]
                self.assertGreaterEqual(preset_count, 1, "Migration 007 should seed profile presets")

                self.assertEqual(
                    conn.execute("PRAGMA integrity_check").fetchone()[0],
                    "ok",
                )
                self.assertEqual(
                    conn.execute("PRAGMA foreign_key_check").fetchall(),
                    [],
                )
            finally:
                conn.close()


class WorkflowRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_file = Path(self.tmp.name) / "app.db"
        init_db(self.db_file)

    def tearDown(self):
        self.tmp.cleanup()

    def test_workflow_task_lifecycle(self):
        repo = WorkflowRepository(self.db_file)
        task = repo.create_task(job_id="job-1", action="join-group", profile_id="M21", target_url="https://facebook.com/groups/hue")
        self.assertIsNotNone(task)
        self.assertEqual(task["state"], "queued")
        self.assertEqual(task["phase"], "QUEUED")

        repo.add_event(task["id"], "RUNNING", "OPENING_BROWSER", "Opening browser for M21")
        updated = repo.update_task(task["id"], state="running", phase="OPENING_BROWSER", progress=20)
        self.assertEqual(updated["state"], "running")

        events = repo.list_events(task["id"])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "RUNNING")

        finished = repo.update_task(task["id"], state="finished", phase="TERMINAL", submission_status="SUBMITTED", verification_status="CONFIRMED")
        self.assertEqual(finished["state"], "finished")
        self.assertEqual(finished["submission_status"], "SUBMITTED")


if __name__ == "__main__":
    unittest.main()


class V610ProductionLinkageTests(unittest.TestCase):
    def test_rotation_pool_honors_explicit_preset_order(self):
        from services.job_executor import _select_rotation_pool
        accounts = [
            {"id": "x", "name": "Other"},
            {"id": "m20", "name": "M20"},
            {"id": "m21", "name": "M21"},
        ]
        pool = _select_rotation_pool(accounts, {"accountIds": ["m21", "m20"]})
        self.assertEqual([a["name"] for a in pool], ["M21", "M20"])

    def test_frontend_loads_default_catalog_and_preset(self):
        root = Path(__file__).resolve().parents[1]
        app = (root / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("/api/group-catalog/defaults", app)
        self.assertIn("/api/profile-presets/default", app)
        self.assertIn("accountIds: accId === '__rotate__'", app)
        self.assertIn("loadAccounts().then(loadDefaultProductionSetup)", app)

    def test_execution_manager_dom_and_css_linkage(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "static" / "index.html").read_text(encoding="utf-8")
        css = (root / "static" / "styles.css").read_text(encoding="utf-8")
        app = (root / "static" / "app.js").read_text(encoding="utf-8")
        for element_id in ["workflow-task-body", "workflow-filter", "workflow-event-panel", "workflow-event-list"]:
            self.assertIn(f'id="{element_id}"', html)
            self.assertIn(f"getElementById('{element_id}')", app)
        self.assertIn(".workflow-table", css)
        self.assertIn(".workflow-event-row", css)
        self.assertIn("queueSection.appendChild(logCard)", app)

    def test_evidence_first_state_mapping_contract(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "services" / "job_executor.py").read_text(encoding="utf-8")
        for marker in [
            'verification_status="MEMBERSHIP_CONFIRMED"',
            'verification_status="REQUEST_UNVERIFIED"',
            'verification_status="COMMENT_VERIFIED"',
            'verification_status="COMMENT_UNVERIFIED"',
            'verification_status="PERMALINK_FOUND"',
            'verification_status="PENDING_EVIDENCE"',
            'verification_status="NO_PERMALINK"',
            '"FAILED_BEFORE_SUBMIT"',
        ]:
            self.assertIn(marker, source)
        self.assertNotIn('verification_status="CONFIRMED" if', source)
    def test_join_click_has_trusted_force_fallback(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "fb_join_group.py").read_text(encoding="utf-8")
        self.assertIn("btn_to_click.click(timeout=3000, force=True)", source)
        self.assertIn("page.mouse.click", source)
        self.assertIn("Native DOM fallback", source)


class V610FinalLiveGuardTests(unittest.TestCase):
    def test_group_composer_has_viewport_fallback_chain(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "fb_group.py").read_text(encoding="utf-8")
        self.assertIn("composer_box.click(force=True", source)
        self.assertIn("page.mouse.click", source)
        self.assertIn('composer_box.evaluate("el => el.click()")', source)

    def test_close_browser_keeps_lease_when_teardown_incomplete(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "utils.py").read_text(encoding="utf-8")
        start = source.index("if cdp_closed and roots_closed:")
        block = source[start:source.index("# ---- Advanced Composer Features")]
        success_branch, failure_branch = block.split("else:", 1)
        self.assertIn("release_profile(profile_id)", success_branch)
        self.assertNotIn("release_profile(profile_id)", failure_branch)
        self.assertIn("Keeping lease to block profile reuse", failure_branch)


class V610ComposerSelectionTests(unittest.TestCase):
    def test_group_composer_prefers_viewport_intersection(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "fb_group.py").read_text(encoding="utf-8")
        self.assertIn("def _pick_interactable(locator):", source)
        self.assertIn('box["y"] < viewport["h"]', source)
        self.assertIn("composer_box = _pick_interactable(buttons)", source)


class V610ReconcileWiringTests(unittest.TestCase):
    def test_reconcile_post_does_not_receive_post_only_flags(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "services" / "job_executor.py").read_text(encoding="utf-8")
        self.assertIn('if cmd != "reconcile-post":', source)
        block = source[source.index('full_cmd = build_cmd_for_account(curr_acc_id) + [cmd, target, task_content]'):]
        guarded = block.split('structured_result = {}', 1)[0]
        self.assertIn('--no-anti-hash-text', guarded)
        self.assertIn('if cmd != "reconcile-post":', guarded)


class V610NativePermalinkResolverTests(unittest.TestCase):
    def test_share_sheet_permalink_resolver_is_wired(self):
        root = Path(__file__).resolve().parents[1]
        utils_src = (root / "utils.py").read_text(encoding="utf-8")
        reconcile_src = (root / "fb_reconcile.py").read_text(encoding="utf-8")
        self.assertIn("def _copy_post_permalink_via_share_sheet", utils_src)
        self.assertIn("Copy link", utils_src)
        self.assertIn("clipboard-read", utils_src)
        self.assertIn("(?:posts|permalink)", utils_src)
        self.assertIn("_copy_post_permalink_via_share_sheet", reconcile_src)


class V610FinalLaunchInvariantsTests(unittest.TestCase):
    def test_project_selection_requires_signature(self):
        from brand_profiles import apply_brand_signature, validate_brand_signature
        text = apply_brand_signature("Hello Hue", "lacasa", include_signature=True)
        ok, missing = validate_brand_signature(text, "lacasa")
        self.assertTrue(ok)
        self.assertEqual([], missing)
        ok2, missing2 = validate_brand_signature("Hello Hue", "lacasa")
        self.assertFalse(ok2)
        self.assertTrue(missing2)

    def test_executor_forces_signature_when_project_selected(self):
        root = Path(__file__).resolve().parents[1]
        src = (root / "services" / "job_executor.py").read_text(encoding="utf-8")
        self.assertIn("include_signature = bool(brand_key)", src)
        self.assertIn("FINAL_CONTENT_SIGNATURE_MISSING", src)

    def test_gpm_session_normalizes_to_single_page(self):
        root = Path(__file__).resolve().parents[1]
        src = (root / "utils.py").read_text(encoding="utf-8")
        self.assertIn("def _normalize_single_interactive_page", src)
        self.assertIn("settle_seconds=10.0", src)
        self.assertIn("GPM_PAGE_SINGLETON_FAILED", src)
        self.assertIn("keep.wait_for_timeout(250)", src)
        self.assertIn("Single-page invariant active", src)


class V610SignatureApiContractTests(unittest.TestCase):
    def test_ai_spin_api_requires_signature_for_selected_project(self):
        root = Path(__file__).resolve().parents[1]
        src = (root / "server.py").read_text(encoding="utf-8")
        self.assertIn("include_signature = bool(brand_key)", src)


class V610LaunchRepairTests(unittest.TestCase):
    def test_job_repo_preserves_business_keys(self):
        from repositories.job_repo import JobRepository
        repo = JobRepository()
        job_id = "test-brand-key-preserved"
        repo.create_job({"id": job_id, "state": "queued", "payload": {
            "brandKey": "lacasa", "groupKeywords": "homestay hue",
            "geminiApiKey": "secret-value", "pageAccessToken": "token-value",
        }})
        saved = repo.get_job(job_id)["payload"]
        self.assertEqual(saved["brandKey"], "lacasa")
        self.assertEqual(saved["groupKeywords"], "homestay hue")
        self.assertEqual(saved["geminiApiKey"], "***REDACTED***")
        self.assertEqual(saved["pageAccessToken"], "***REDACTED***")

    def test_invalid_brand_key_fails_signature_contract(self):
        from brand_profiles import validate_brand_signature
        ok, missing = validate_brand_signature("hello", "***REDACTED***")
        self.assertFalse(ok)
        self.assertIn("INVALID_BRAND_KEY", missing)

    def test_gpm_process_singleton_helpers_wired(self):
        import utils
        self.assertTrue(callable(utils._gpm_root_processes))
        self.assertTrue(callable(utils._ensure_clean_gpm_process_state))
        self.assertTrue(callable(utils._wait_gpm_roots_closed))
