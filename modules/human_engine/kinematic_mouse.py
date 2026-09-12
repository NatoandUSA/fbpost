"""Kinematic & WindMouse Movement Engine.

Combines Cubic Bézier kinematics, Benjamin J. Land's WindMouse physics,
Fitts's Law target selection, physiological tremors, and optical mouse micro-slips.
"""

import math
import random
import time
from typing import List, Tuple, Optional, Any
from .behavioral_profile import BehavioralProfile


def _cubic_bezier(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    """Calculate coordinate on a cubic Bézier curve at step t (0 <= t <= 1)."""
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

    def generate_windmouse_path(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        gravity: float = 9.0,
        wind: float = 3.0,
        min_wait: float = 0.005,
        max_wait: float = 0.012,
        target_area: float = 8.0
    ) -> List[Tuple[float, float, float]]:
        """
        WindMouse algorithm (Benjamin J. Land physics model).
        Simulates cursor movement with gravitational pull, wind perturbations, and dynamic dampening.
        """
        xs, ys = start
        xe, ye = end
        velo_x = 0.0
        velo_y = 0.0
        wind_x = 0.0
        wind_y = 0.0
        points = []

        dist = math.hypot(xe - xs, ye - ys)
        if dist < target_area:
            return [(xe, ye, min_wait)]

        sqrt2 = math.sqrt(2.0)
        sqrt3 = math.sqrt(3.0)
        sqrt5 = math.sqrt(5.0)

        max_step = min(22.0, max(8.0, dist / 15.0)) * self.profile.mouse_speed_factor

        while dist > 1.5:
            # Random wind perturbation
            wind_x = wind_x / sqrt3 + (random.random() * (wind * 2.0 + 1.0) - wind) / sqrt5
            wind_y = wind_y / sqrt3 + (random.random() * (wind * 2.0 + 1.0) - wind) / sqrt5

            # Gravitational pull towards destination
            velo_x += wind_x + gravity * (xe - xs) / dist
            velo_y += wind_y + gravity * (ye - ys) / dist

            # Clamp velocity to max_step
            velo_mag = math.hypot(velo_x, velo_y)
            if velo_mag > max_step:
                random_dist = max_step / 2.0 + random.random() * (max_step / 2.0)
                velo_x = (velo_x / velo_mag) * random_dist
                velo_y = (velo_y / velo_mag) * random_dist

            xs += velo_x
            ys += velo_y

            # Tremor (8 - 12 Hz physiological tremor)
            tx = xs + random.gauss(0, 0.45)
            ty = ys + random.gauss(0, 0.45)

            # Polling delay: varies between 6ms and 15ms (125 Hz mouse polling rate)
            step_wait = min_wait + random.random() * (max_wait - min_wait)
            points.append((round(tx, 1), round(ty, 1), step_wait))

            dist = math.hypot(xe - xs, ye - ys)
            if dist < target_area * 1.5:
                # Decelerate near target
                max_step = max(2.5, max_step * 0.75)

        points.append((xe, ye, min_wait))
        return points

    def generate_bezier_path(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        overshoot: bool = False
    ) -> List[Tuple[float, float, float]]:
        """Generate smooth Cubic Bézier trajectory with Sigmoid velocity and overshoot."""
        x0, y0 = start
        x3, y3 = end
        dist = math.hypot(x3 - x0, y3 - y0)
        
        if dist < 4.0:
            return [(x3, y3, 0.02)]

        base_steps = int(max(15, min(80, dist / 12.0)))
        steps = int(base_steps / self.profile.mouse_speed_factor)
        steps = max(10, steps)

        angle = math.atan2(y3 - y0, x3 - x0)
        perp_angle = angle + math.pi / 2.0
        deviation_scale = min(120.0, dist * 0.35)

        d1 = dist * random.uniform(0.2, 0.45)
        dev1 = random.gauss(0, deviation_scale * 0.7)
        x1 = x0 + d1 * math.cos(angle) + dev1 * math.cos(perp_angle)
        y1 = y0 + d1 * math.sin(angle) + dev1 * math.sin(perp_angle)

        d2 = dist * random.uniform(0.55, 0.85)
        dev2 = random.gauss(0, deviation_scale * 0.5)
        x2 = x0 + d2 * math.cos(angle) + dev2 * math.cos(perp_angle)
        y2 = y0 + d2 * math.sin(angle) + dev2 * math.sin(perp_angle)

        if overshoot:
            overshoot_dist = min(25.0, dist * 0.10)
            overshoot_angle = angle + random.uniform(-0.3, 0.3)
            ox3 = x3 + overshoot_dist * math.cos(overshoot_angle)
            oy3 = y3 + overshoot_dist * math.sin(overshoot_angle)
            primary_path = self._render_curve(x0, y0, x1, y1, x2, y2, ox3, oy3, steps)
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
            raw_t = i / steps
            t = raw_t * raw_t * (3.0 - 2.0 * raw_t)

            bx = _cubic_bezier(x0, x1, x2, x3, t)
            by = _cubic_bezier(y0, y1, y2, y3, t)

            tremor_damp = math.sin(raw_t * math.pi)
            tx = bx + random.gauss(0, 0.8) * tremor_damp
            ty = by + random.gauss(0, 0.8) * tremor_damp

            speed_weight = 1.0 - 0.5 * tremor_damp
            dt = (total_duration / steps) * speed_weight
            # Mouse polling interval micro-jitter (6ms - 14ms)
            jittered_dt = max(0.004, dt + random.gauss(0, 0.001))
            waypoints.append((round(tx, 1), round(ty, 1), jittered_dt))

        return waypoints

    def generate_path(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        overshoot: bool = False
    ) -> List[Tuple[float, float, float]]:
        """Adaptive generator: chooses between WindMouse and Bézier based on profile and distance."""
        dist = math.hypot(end[0] - start[0], end[1] - start[1])
        # Short-to-medium distances: WindMouse excels at organic micro-corrections
        # Long distances: Bézier with overshoot provides realistic arc acceleration
        if dist < 220.0 and random.random() < 0.65:
            return self.generate_windmouse_path(start, end)
        return self.generate_bezier_path(start, end, overshoot=overshoot)

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
        """Move naturally using Fitts's Law 2D Gaussian distribution within the locator bounds."""
        if not page or not locator:
            return False
        try:
            box = locator.bounding_box()
            if not box:
                return False
            # Fitts's Law 2D Gaussian centered around 0.5 with sigma=0.12, clamped to [0.15, 0.85]
            gx = max(0.15, min(0.85, random.gauss(0.5, 0.12)))
            gy = max(0.15, min(0.85, random.gauss(0.5, 0.12)))
            target_x = box["x"] + box["width"] * gx
            target_y = box["y"] + box["height"] * gy
            return self.move(page, target_x, target_y)
        except Exception:
            return False
