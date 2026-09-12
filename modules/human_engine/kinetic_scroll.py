"""Kinetic & Impulse Scrolling Engine.

Simulates human mouse-wheel and trackpad scrolling with inertia, deceleration curves,
reading pauses, and micro-backscrolls. Supports both discrete notched wheels and continuous trackpads.
"""

import math
import random
import time
from typing import Optional, Any
from .behavioral_profile import BehavioralProfile


class KineticScroll:
    """Simulates physical inertia scrolling and natural reading pauses."""

    def __init__(self, profile: Optional[BehavioralProfile] = None):
        self.profile = profile or BehavioralProfile.from_seed("default")

    def _scroll_discrete_wheel(self, page: Any, target_dy: int) -> bool:
        """Simulate notched desktop mouse wheel (discrete steps of 100-120px with ticks)."""
        sign = 1 if target_dy > 0 else -1
        total_abs = abs(target_dy)
        step_size = 100
        steps = max(1, int(round(total_abs / step_size)))

        for i in range(steps):
            try:
                page.mouse.wheel(0, sign * step_size)
            except Exception:
                break
            # Physical notched wheel tick interval: 40ms to 90ms with micro-variance
            time.sleep(random.uniform(0.045, 0.095))
        return True

    def _scroll_smooth_touchpad(self, page: Any, target_dy: int, steps: int = 14) -> bool:
        """Simulate smooth inertial trackpad scroll with exponential decay."""
        sign = 1 if target_dy > 0 else -1
        total_abs = abs(target_dy)
        steps = max(8, min(24, steps))

        decay_factor = 0.84
        weights = [decay_factor ** i for i in range(steps)]
        sum_weights = sum(weights)

        for w in weights:
            step_dy = int(round(sign * (total_abs * (w / sum_weights))))
            if step_dy != 0:
                try:
                    page.mouse.wheel(0, step_dy)
                except Exception:
                    break
            time.sleep(random.uniform(0.016, 0.032))
        return True

    def scroll_smooth(
        self,
        page: Any,
        target_dy: int,
        steps: int = 14,
        with_reading_pause: bool = True
    ) -> bool:
        """
        Scroll the page smoothly according to the persona's input device profile.
        """
        if not page or target_dy == 0:
            return False

        try:
            if hasattr(page, "is_closed") and page.is_closed() is True:
                return False

            # Check device type from profile
            if self.profile.mouse_wheel_type == "discrete_wheel":
                self._scroll_discrete_wheel(page, target_dy)
            else:
                self._scroll_smooth_touchpad(page, target_dy, steps=steps)

            # Natural post-scroll reading pause (eyes scanning feed)
            if with_reading_pause:
                dwell = random.uniform(1.2, 3.2)
                time.sleep(dwell)

            # 18% probability of micro-backscroll (user scrolled past something interesting)
            if random.random() < 0.18 and abs(target_dy) > 200:
                sign = 1 if target_dy > 0 else -1
                back_dy = -int(sign * random.randint(50, 140))
                self._scroll_smooth_touchpad(page, back_dy, steps=6)
                time.sleep(random.uniform(0.7, 1.5))

            return True
        except Exception:
            return False

    def browse_feed(self, page: Any, rounds: int = 2) -> bool:
        """Simulate browsing a social feed naturally (scrolls, pauses, occasional look-backs)."""
        if not page:
            return False
        for _ in range(max(1, rounds)):
            scroll_dist = int(random.randint(280, 680) * self.profile.scroll_impulse_factor)
            self.scroll_smooth(page, scroll_dist, with_reading_pause=True)
        return True
