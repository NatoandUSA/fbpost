"""Kinematic Mouse Movement Engine.

Generates organic, curved mouse paths using Cubic Bézier curves, velocity bell curves,
Fitts's Law overshoot/correction, and physiological tremors to defeat bot telemetry.
"""

import math
import random
import time
from typing import List, Tuple, Optional, Any
from .behavioral_profile import BehavioralProfile


def _cubic_bezier(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    """Calculate single coordinate on a cubic Bézier curve at step t (0 <= t <= 1)."""
    return (
        (1 - t) ** 3 * p0
        + 3 * (1 - t) ** 2 * t * p1
        + 3 * (1 - t) * t ** 2 * p2
        + t ** 3 * p3
    )


class KinematicMouse:
    """Simulates organic human cursor trajectories."""

    def __init__(self, profile: Optional[BehavioralProfile] = None):
        self.profile = profile or BehavioralProfile.from_seed("default")
        self._current_pos: Tuple[float, float] = (100.0, 100.0)

    @property
    def current_position(self) -> Tuple[float, float]:
        return self._current_pos

    def generate_path(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        overshoot: bool = False
    ) -> List[Tuple[float, float, float]]:
        """
        Generate a list of (x, y, dt_seconds) waypoints simulating human arm/wrist motion.
        """
        x0, y0 = start
        x3, y3 = end
        dist = math.hypot(x3 - x0, y3 - y0)
        
        if dist < 4.0:
            return [(x3, y3, 0.02)]

        # Calculate number of intermediate steps proportional to distance
        # Scaled by profile speed factor
        base_steps = int(max(15, min(80, dist / 12.0)))
        steps = int(base_steps / self.profile.mouse_speed_factor)
        steps = max(10, steps)

        # Generate organic control points
        # Perpendicular deviation for natural curvature
        angle = math.atan2(y3 - y0, x3 - x0)
        perp_angle = angle + math.pi / 2.0
        deviation_scale = min(120.0, dist * 0.35)

        # Control point 1: closer to start
        d1 = dist * random.uniform(0.2, 0.45)
        dev1 = random.gauss(0, deviation_scale * 0.7)
        x1 = x0 + d1 * math.cos(angle) + dev1 * math.cos(perp_angle)
        y1 = y0 + d1 * math.sin(angle) + dev1 * math.sin(perp_angle)

        # Control point 2: closer to destination
        d2 = dist * random.uniform(0.55, 0.85)
        dev2 = random.gauss(0, deviation_scale * 0.5)
        x2 = x0 + d2 * math.cos(angle) + dev2 * math.cos(perp_angle)
        y2 = y0 + d2 * math.sin(angle) + dev2 * math.sin(perp_angle)

        # Handle overshoot if requested
        if overshoot:
            overshoot_dist = min(25.0, dist * 0.10)
            overshoot_angle = angle + random.uniform(-0.3, 0.3)
            ox3 = x3 + overshoot_dist * math.cos(overshoot_angle)
            oy3 = y3 + overshoot_dist * math.sin(overshoot_angle)
            # Generate primary path to overshoot target
            primary_path = self._render_curve(x0, y0, x1, y1, x2, y2, ox3, oy3, steps)
            # Generate corrective secondary path to actual destination
            correct_steps = max(6, int(steps * 0.3))
            cx1 = ox3 + (x3 - ox3) * 0.4 + random.gauss(0, 2)
            cy1 = oy3 + (y3 - oy3) * 0.4 + random.gauss(0, 2)
            correction_path = self._render_curve(ox3, oy3, cx1, cy1, cx1, cy1, x3, y3, correct_steps)
            return primary_path + correction_path[1:]

        return self._render_curve(x0, y0, x1, y1, x2, y2, x3, y3, steps)

    def _render_curve(
        self,
        x0: float, y0: float,
        x1: float, y1: float,
        x2: float, y2: float,
        x3: float, y3: float,
        steps: int
    ) -> List[Tuple[float, float, float]]:
        waypoints = []
        total_duration = 0.008 + (steps * 0.006)

        for i in range(steps + 1):
            # Sigmoidal velocity profile (Ease-in, Ease-out)
            raw_t = i / steps
            # Smoothstep easing: 3t^2 - 2t^3
            t = raw_t * raw_t * (3.0 - 2.0 * raw_t)

            bx = _cubic_bezier(x0, x1, x2, x3, t)
            by = _cubic_bezier(y0, y1, y2, y3, t)

            # Physiological tremor (8 - 12Hz physiological micro-oscillation)
            # Amplitude decays near endpoints
            tremor_damp = math.sin(raw_t * math.pi)
            tx = bx + random.gauss(0, 0.8) * tremor_damp
            ty = by + random.gauss(0, 0.8) * tremor_damp

            # Delta time per step (smaller in middle when moving fast, longer at start/end)
            speed_weight = 1.0 - 0.5 * tremor_damp
            dt = (total_duration / steps) * speed_weight
            waypoints.append((round(tx, 1), round(ty, 1), max(0.002, dt)))

        return waypoints

    def move(self, page: Any, target_x: float, target_y: float) -> bool:
        """Execute physical human mouse movement to the target coordinates."""
        if not page:
            return False
        try:
            start_pos = self._current_pos
            should_overshoot = random.random() < self.profile.mouse_overshoot_prob
            waypoints = self.generate_path(start_pos, (target_x, target_y), overshoot=should_overshoot)

            for x, y, dt in waypoints:
                try:
                    page.mouse.move(x, y)
                except Exception:
                    pass
                time.sleep(dt)

            self._current_pos = (target_x, target_y)
            return True
        except Exception:
            return False

    def move_to_locator(self, page: Any, locator: Any) -> bool:
        """Move naturally to a randomized inner coordinate of the target locator."""
        if not page or not locator:
            return False
        try:
            box = locator.bounding_box()
            if not box:
                return False
            # Target inner 60% of bounding box (avoids clicking outer borders)
            pad_x = box["width"] * 0.20
            pad_y = box["height"] * 0.20
            target_x = box["x"] + pad_x + random.uniform(0, box["width"] - 2 * pad_x)
            target_y = box["y"] + pad_y + random.uniform(0, box["height"] - 2 * pad_y)
            return self.move(page, target_x, target_y)
        except Exception:
            return False
