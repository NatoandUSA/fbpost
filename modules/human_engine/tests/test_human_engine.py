"""Unit tests for the optional interaction pacing engine.

Validates mathematical models, biometric distributions, WindMouse trajectory mechanics,
keystroke timing, scrolling, and text integrity under simulated browser conditions.
"""

import math
import unittest
from unittest.mock import MagicMock, patch

from modules.human_engine.behavioral_profile import BehavioralProfile
from modules.human_engine.kinematic_mouse import KinematicMouse, _cubic_bezier
from modules.human_engine.biometric_typing import BiometricTyping
from modules.human_engine.kinetic_scroll import KineticScroll
from modules.human_engine.engine import HumanEngine
from modules.human_engine import adapter


class BehavioralProfileTests(unittest.TestCase):
    def test_deterministic_profile_generation(self):
        p1 = BehavioralProfile.from_seed("account_123")
        p2 = BehavioralProfile.from_seed("account_123")
        self.assertEqual(p1.wpm, p2.wpm)
        self.assertEqual(p1.iki_mean_ms, p2.iki_mean_ms)
        self.assertEqual(p1.mouse_speed_factor, p2.mouse_speed_factor)
        self.assertEqual(p1.typo_probability, p2.typo_probability)
        self.assertEqual(p1.device_type, p2.device_type)
        self.assertEqual(p1.double_tap_factor, p2.double_tap_factor)

    def test_divergent_profiles_for_different_accounts(self):
        p1 = BehavioralProfile.from_seed("profile_alex")
        p2 = BehavioralProfile.from_seed("profile_bob")
        self.assertNotEqual(p1.wpm, p2.wpm)
        self.assertNotEqual(p1.iki_mean_ms, p2.iki_mean_ms)

    def test_parameters_within_realistic_human_bounds(self):
        for seed in ["test1", "m14", "m21", "default", "profile_xyz"]:
            p = BehavioralProfile.from_seed(seed)
            self.assertTrue(45.0 <= p.wpm <= 85.0)
            self.assertTrue(80.0 <= p.iki_mean_ms <= 300.0)
            self.assertTrue(0.70 <= p.mouse_speed_factor <= 1.40)
            self.assertTrue(0.005 <= p.typo_probability <= 0.025)
            self.assertIn(p.device_type, {"desktop_mouse", "trackpad"})
            self.assertIn(p.mouse_wheel_type, {"discrete_wheel", "smooth_touchpad"})


class KinematicMouseTests(unittest.TestCase):
    def setUp(self):
        self.mouse = KinematicMouse(BehavioralProfile.from_seed("test_mouse"))

    def test_cubic_bezier_endpoints(self):
        self.assertAlmostEqual(_cubic_bezier(10.0, 30.0, 70.0, 100.0, 0.0), 10.0)
        self.assertAlmostEqual(_cubic_bezier(10.0, 30.0, 70.0, 100.0, 1.0), 100.0)
        mid = _cubic_bezier(0.0, 50.0, 50.0, 100.0, 0.5)
        self.assertAlmostEqual(mid, 50.0)

    def test_bezier_path_generation_starts_and_ends_correctly(self):
        start = (50.0, 50.0)
        end = (500.0, 300.0)
        path = self.mouse.generate_bezier_path(start, end, overshoot=False)
        self.assertGreater(len(path), 5)
        self.assertAlmostEqual(path[0][0], start[0], delta=3.0)
        self.assertAlmostEqual(path[0][1], start[1], delta=3.0)
        self.assertAlmostEqual(path[-1][0], end[0], delta=2.0)
        self.assertAlmostEqual(path[-1][1], end[1], delta=2.0)

    def test_windmouse_physics_path_generation(self):
        start = (100.0, 100.0)
        end = (300.0, 250.0)
        path = self.mouse.generate_windmouse_path(start, end)
        self.assertGreater(len(path), 8)
        # Verify landing at destination
        self.assertAlmostEqual(path[-1][0], end[0], delta=3.0)
        self.assertAlmostEqual(path[-1][1], end[1], delta=3.0)
        for _, _, dt in path:
            self.assertGreater(dt, 0.0)

    def test_overshoot_produces_extended_path(self):
        start = (100.0, 100.0)
        end = (600.0, 600.0)
        direct_path = self.mouse.generate_bezier_path(start, end, overshoot=False)
        overshoot_path = self.mouse.generate_bezier_path(start, end, overshoot=True)
        self.assertGreater(len(overshoot_path), len(direct_path))
        self.assertAlmostEqual(overshoot_path[-1][0], end[0], delta=2.0)

    def test_mouse_move_mock_execution(self):
        mock_page = MagicMock()
        ok = self.mouse.move(mock_page, 250.0, 350.0)
        self.assertTrue(ok)
        self.assertGreater(mock_page.mouse.move.call_count, 5)
        self.assertEqual(self.mouse.current_position, (250.0, 350.0))


class BiometricTypingTests(unittest.TestCase):
    def setUp(self):
        self.typing = BiometricTyping(BehavioralProfile.from_seed("test_typing"))

    def test_iki_sampling_within_bounds(self):
        for _ in range(50):
            iki_space = self.typing._sample_iki(' ')
            iki_char = self.typing._sample_iki('a')
            iki_upper = self.typing._sample_iki('A')
            self.assertTrue(0.030 <= iki_space <= 0.400)
            self.assertTrue(0.030 <= iki_char <= 0.650)
            self.assertTrue(0.030 <= iki_upper <= 0.650)

    def test_double_letter_acceleration(self):
        # 'o' after 'o' must be sampled faster than 'o' after 'x'
        iki_normal = self.typing._sample_iki('o', prev_char='x')
        iki_double = self.typing._sample_iki('o', prev_char='o')
        # Average expectation is double_tap_factor (~0.65)
        self.assertLess(self.typing.profile.double_tap_factor, 1.0)

    def test_type_text_fidelity_with_down_up_events(self):
        typed_chars = []
        mock_page = MagicMock()
        mock_page.keyboard.down.side_effect = lambda c: typed_chars.append(c) if c != "Shift" else None
        mock_locator = MagicMock()

        test_text = "hello world"
        with patch("time.sleep", return_value=None):
            ok = self.typing.type_text(mock_page, mock_locator, test_text, allow_typos=False)
        
        self.assertTrue(ok)
        # Check all characters were received via down events
        self.assertEqual("".join(typed_chars), test_text)

    def test_multiline_typing_fidelity(self):
        pressed_events = []
        mock_page = MagicMock()
        mock_page.keyboard.press.side_effect = lambda k: pressed_events.append(k)
        mock_locator = MagicMock()

        test_text = "Dong 1\nDong 2"
        with patch("time.sleep", return_value=None):
            ok = self.typing.type_text(mock_page, mock_locator, test_text, multiline_key="Shift+Enter", allow_typos=False)
        
        self.assertTrue(ok)
        self.assertIn("Shift+Enter", pressed_events)


class KineticScrollTests(unittest.TestCase):
    def setUp(self):
        self.scroller = KineticScroll(BehavioralProfile.from_seed("test_scroll"))

    def test_smooth_scroll_physics(self):
        mock_page = MagicMock()
        wheel_deltas = []
        mock_page.mouse.wheel.side_effect = lambda dx, dy: wheel_deltas.append(dy)

        with patch("time.sleep", return_value=None):
            ok = self.scroller.scroll_smooth(mock_page, 600, steps=10, with_reading_pause=False)
        
        self.assertTrue(ok)
        self.assertGreater(len(wheel_deltas), 3)
        self.assertAlmostEqual(sum(wheel_deltas), 600, delta=25)



class EngineFacadeAndAdapterTests(unittest.TestCase):
    def test_facade_initialization(self):
        engine = HumanEngine("profile_m14")
        self.assertEqual(engine.account_id, "profile_m14")
        self.assertIsNotNone(engine.mouse)
        self.assertIsNotNone(engine.typing)
        self.assertIsNotNone(engine.scroll)

    def test_adapter_delegation(self):
        mock_page = MagicMock()
        mock_locator = MagicMock()

        with patch("time.sleep", return_value=None):
            ok = adapter.human_type_advanced(mock_page, mock_locator, "Noi dung", account_id="m14")
            self.assertTrue(ok)

            ok_scroll = adapter.kinetic_mouse_wheel(mock_page, 0, 400, account_id="m14")
            self.assertTrue(ok_scroll)


class UtilsBridgeAccountTests(unittest.TestCase):
    def test_utils_bridge_propagates_page_account_identity(self):
        import utils
        page = MagicMock()
        page._fb_automation_account_id = "profile-real-123"
        locator = MagicMock()
        old = utils.ENABLE_ADVANCED_HUMAN_ENGINE
        utils.ENABLE_ADVANCED_HUMAN_ENGINE = True
        try:
            with patch("modules.human_engine.adapter.human_type_advanced", return_value=True) as typed:
                utils.human_type(page, locator, "hello")
                self.assertEqual(typed.call_args.kwargs["account_id"], "profile-real-123")
            with patch("modules.human_engine.adapter.kinetic_mouse_wheel", return_value=True) as scrolled:
                self.assertTrue(utils.safe_mouse_wheel(page, 0, 240))
                self.assertEqual(scrolled.call_args.kwargs["account_id"], "profile-real-123")
        finally:
            utils.ENABLE_ADVANCED_HUMAN_ENGINE = old


class PlaywrightTextFidelityIntegrationTests(unittest.TestCase):
    """Real headless Playwright integration tests verifying exact-text fidelity and multiline pacing."""

    def test_playwright_textarea_exact_fidelity_and_multiline(self):
        from playwright.sync_api import sync_playwright
        import utils

        test_text = (
            "Chào mừng đến với UMEE & Lacasa 2026!\n"
            "Dòng 2: Ký tự đặc biệt @#$% & số 0905555317.\n"
            "Dòng 3: Tiếng Việt có dấu: Huế, Đà Nẵng, Hà Nội.\n"
            "#UMEEHomestay #LacasaHomestay"
        )

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.set_content('<textarea id="editor" rows="10" cols="60"></textarea>')
                locator = page.locator('#editor')
                page._fb_automation_account_id = "acc_test_playwright"

                old_flag = utils.ENABLE_ADVANCED_HUMAN_ENGINE
                utils.ENABLE_ADVANCED_HUMAN_ENGINE = True
                try:
                    with patch("time.sleep", return_value=None):
                        utils.human_type(page, locator, test_text, multiline_key="Enter")
                    
                    actual_value = locator.input_value()
                    self.assertEqual(actual_value, test_text)
                    self.assertTrue(utils.verify_entered_content(locator, test_text))
                finally:
                    utils.ENABLE_ADVANCED_HUMAN_ENGINE = old_flag
            finally:
                page.close()
                browser.close()

    def test_playwright_contenteditable_shift_enter_multiline(self):
        from playwright.sync_api import sync_playwright
        import utils

        test_text = "Dòng 1 trong editor\nDòng 2 với Shift+Enter\n#LacasaHomestay"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.set_content('<div id="composer" contenteditable="true" style="min-height:50px"></div>')
                locator = page.locator('#composer')
                page._fb_automation_account_id = "acc_contenteditable"

                old_flag = utils.ENABLE_ADVANCED_HUMAN_ENGINE
                utils.ENABLE_ADVANCED_HUMAN_ENGINE = True
                try:
                    with patch("time.sleep", return_value=None):
                        utils.human_type(page, locator, test_text, multiline_key="Shift+Enter")
                    
                    text_content = locator.inner_text()
                    self.assertIn("#LacasaHomestay", text_content)
                    self.assertTrue(utils.verify_entered_content(locator, test_text))
                finally:
                    utils.ENABLE_ADVANCED_HUMAN_ENGINE = old_flag
            finally:
                page.close()
                browser.close()


if __name__ == "__main__":
    unittest.main()
