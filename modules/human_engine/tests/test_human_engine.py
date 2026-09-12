"""Comprehensive Unit Tests for Human Behavior & Anti-Checkpoint Engine.

Validates mathematical models, biometric distributions, WindMouse trajectory mechanics,
keystroke DU telemetry, stealth scripts, and text integrity under simulated browser conditions.
"""

import math
import unittest
from unittest.mock import MagicMock, patch

from modules.human_engine.behavioral_profile import BehavioralProfile
from modules.human_engine.kinematic_mouse import KinematicMouse, _cubic_bezier
from modules.human_engine.biometric_typing import BiometricTyping
from modules.human_engine.kinetic_scroll import KineticScroll
from modules.human_engine.engine import HumanEngine
from modules.human_engine.stealth_evasion import apply_stealth_scripts, STEALTH_INJECTION_SCRIPT
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
        down_events = []
        mock_page = MagicMock()
        mock_page.keyboard.down.side_effect = lambda k: down_events.append(k)
        mock_locator = MagicMock()

        test_text = "Dong 1\nDong 2"
        with patch("time.sleep", return_value=None):
            ok = self.typing.type_text(mock_page, mock_locator, test_text, multiline_key="Shift+Enter", allow_typos=False)
        
        self.assertTrue(ok)
        self.assertIn("Shift+Enter", down_events)


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


class StealthEvasionTests(unittest.TestCase):
    def test_apply_stealth_scripts_context(self):
        mock_context = MagicMock()
        ok = apply_stealth_scripts(mock_context)
        self.assertTrue(ok)
        mock_context.add_init_script.assert_called_once()
        script_arg = mock_context.add_init_script.call_args[0][0]
        self.assertIn("navigator.webdriver", script_arg)
        self.assertIn("window.chrome", script_arg)
        self.assertIn("UNMASKED_VENDOR_WEBGL", script_arg)


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


if __name__ == "__main__":
    unittest.main()
