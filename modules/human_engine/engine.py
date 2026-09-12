"""HumanEngine Facade.

Integrates KinematicMouse, BiometricTyping, KineticScroll, and BehavioralProfile
into a single, high-level API for seamless browser automation.
"""

import random
import time
from typing import Optional, Any
from .behavioral_profile import BehavioralProfile
from .kinematic_mouse import KinematicMouse
from .biometric_typing import BiometricTyping
from .kinetic_scroll import KineticScroll


class HumanEngine:
    """Complete Human Simulation & Anti-Bot Evasion Engine."""

    def __init__(self, account_id: Optional[str] = None):
        self.account_id = str(account_id or "default")
        self.profile = BehavioralProfile.from_seed(self.account_id)
        self.mouse = KinematicMouse(self.profile)
        self.typing = BiometricTyping(self.profile)
        self.scroll = KineticScroll(self.profile)

    def click(self, page: Any, locator: Any, hover_dwell: bool = True) -> bool:
        """
        Move naturally to the target element using Bézier kinematics,
        optionally hover, and execute a human-timed click.
        """
        if not page or not locator:
            return False
        try:
            # 1. Kinematic trajectory to target element
            self.mouse.move_to_locator(page, locator)
            
            # 2. Brief hover dwell (human eye-hand coordination latency: 80ms - 220ms)
            if hover_dwell:
                time.sleep(random.uniform(0.08, 0.22))

            # 3. Click with slight mouse down-up dwell
            box = locator.bounding_box()
            if box:
                # Slight micro-jitter on click
                click_x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
                click_y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
                page.mouse.move(click_x, click_y)
                page.mouse.down()
                time.sleep(random.uniform(0.04, 0.09))
                page.mouse.up()
            else:
                locator.click(timeout=3000)
            
            # Post-click reaction settle
            time.sleep(random.uniform(0.15, 0.35))
            return True
        except Exception:
            try:
                locator.click(force=True, timeout=3000)
                return True
            except Exception:
                return False

    def type_into(
        self,
        page: Any,
        locator: Any,
        text: str,
        multiline_key: str = "Enter",
        click_first: bool = True
    ) -> bool:
        """
        Focus the element naturally and type content with biometric cadence.
        """
        if not page or not locator or not text:
            return False
        try:
            if click_first:
                self.click(page, locator, hover_dwell=False)
            else:
                try:
                    locator.focus(timeout=2000)
                except Exception:
                    pass

            time.sleep(random.uniform(0.2, 0.5))
            return self.typing.type_text(page, locator, text, multiline_key=multiline_key)
        except Exception:
            return False

    def natural_scroll(self, page: Any, dy: int, reading_pause: bool = True) -> bool:
        """Execute physical kinetic scrolling."""
        return self.scroll.scroll_smooth(page, dy, with_reading_pause=reading_pause)

    def warm_up(self, page: Any, rounds: int = 2) -> bool:
        """
        Browse and establish natural session entropy (scrolling, looking at posts, random cursor drift)
        prior to executing sensitive actions like posting or joining groups.
        """
        if not page:
            return False
        try:
            # 1. Random cursor drift across viewport
            vp = {"w": 1280, "h": 800}
            try:
                vp = page.evaluate("() => ({w: window.innerWidth, h: window.innerHeight})")
            except Exception:
                pass

            for _ in range(random.randint(1, 3)):
                rx = random.uniform(150, vp["w"] - 150)
                ry = random.uniform(150, vp["h"] - 150)
                self.mouse.move(page, rx, ry)
                time.sleep(random.uniform(0.3, 0.8))

            # 2. Browse feed naturally
            return self.scroll.browse_feed(page, rounds=rounds)
        except Exception:
            return False
