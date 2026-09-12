"""Kinetic & Impulse Scrolling Engine.

Simulates human mouse-wheel and trackpad scrolling with inertia, deceleration curves,
reading pauses, and micro-backscrolls.
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

    def scroll_smooth(
        self,
        page: Any,
        target_dy: int,
        steps: int = 12,
        with_reading_pause: bool = True
    ) -> bool:
        """
        Scroll the page smoothly over several deceleration frames.
        """
        if not page or target_dy == 0:
            return False

        try:
            if hasattr(page, "is_closed") and page.is_closed() is True:
                return False

            sign = 1 if target_dy > 0 else -1
            total_abs = abs(target_dy)
            steps = max(6, min(24, steps))

            # Exponential decay impulse curve
            decay_factor = 0.82
            weights = [decay_factor ** i for i in range(steps)]
            sum_weights = sum(weights)

            for w in weights:
                step_dy = int(round(sign * (total_abs * (w / sum_weights))))
                if step_dy != 0:
                    try:
                        page.mouse.wheel(0, step_dy)
                    except Exception:
                        break
                # Frame interval: 16ms - 32ms (approx 30-60 FPS)
                time.sleep(random.uniform(0.016, 0.032))

            # Natural post-scroll reading pause (eyes scanning content)
            if with_reading_pause:
                dwell = random.uniform(1.2, 3.2)
                time.sleep(dwell)

            # 15% probability of micro-backscroll (user scrolled too fast and checks back)
            if random.random() < 0.18 and abs(target_dy) > 200:
                back_dy = -int(sign * random.randint(40, 120))
                back_steps = 5
                b_weights = [0.8 ** i for i in range(back_steps)]
                b_sum = sum(b_weights)
                for bw in b_weights:
                    b_step = int(round(back_dy * (bw / b_sum)))
                    try:
                        page.mouse.wheel(0, b_step)
                    except Exception:
                        break
                    time.sleep(0.02)
                time.sleep(random.uniform(0.6, 1.4))

            return True
        except Exception:
            return False

    def browse_feed(self, page: Any, rounds: int = 2) -> bool:
        """Simulate browsing a social feed naturally (scrolls, pauses, occasional look-backs)."""
        if not page:
            return False
        for _ in range(max(1, rounds)):
            scroll_dist = int(random.randint(250, 650) * self.profile.scroll_impulse_factor)
            self.scroll_smooth(page, scroll_dist, with_reading_pause=True)
        return True
