"""Backward-Compatibility Adapter with Fail-Safe Fallbacks.

Provides drop-in replacements matching existing utility function signatures in `utils.py`
so that integrating the Human Behavior Engine requires zero refactoring of business logic
and guarantees 100% fail-safe behavior under all operating conditions.
"""

from typing import Any, Optional
from .engine import HumanEngine

# Module-level cached engines keyed by account_id
_ENGINES = {}


def _get_engine(account_id: Optional[str] = None) -> HumanEngine:
    key = str(account_id or "default")
    if key not in _ENGINES:
        _ENGINES[key] = HumanEngine(key)
    return _ENGINES[key]


def human_type_advanced(page: Any, locator: Any, text: str, multiline_key: str = "Enter", account_id: Optional[str] = None) -> bool:
    """
    Drop-in upgrade for `utils.human_type` with biometric keystroke cadence.
    If any unexpected exception occurs, gracefully falls back to legacy typing without crashing.
    """
    if not page or not locator or text is None:
        return False

    try:
        engine = _get_engine(account_id)
        if engine.type_into(page, locator, text, multiline_key=multiline_key, click_first=False):
            return True
    except Exception:
        pass

    # Legacy safe fallback
    try:
        locator.fill(str(text))
        return True
    except Exception:
        try:
            lines = str(text).split("\n")
            for idx, line in enumerate(lines):
                if line:
                    page.keyboard.insert_text(line)
                if idx < len(lines) - 1:
                    page.keyboard.press("Shift+Enter" if multiline_key == "Shift+Enter" else "Enter")
            return True
        except Exception:
            return False


def human_click(page: Any, locator: Any, account_id: Optional[str] = None) -> bool:
    """Execute natural Bézier cursor movement and human-paced click with fallback."""
    if not page or not locator:
        return False
    try:
        engine = _get_engine(account_id)
        if engine.click(page, locator):
            return True
    except Exception:
        pass

    try:
        locator.click(timeout=3000)
        return True
    except Exception:
        try:
            locator.click(force=True, timeout=3000)
            return True
        except Exception:
            return False


def kinetic_mouse_wheel(page: Any, dx: int, dy: int, account_id: Optional[str] = None) -> bool:
    """Drop-in upgrade for `utils.safe_mouse_wheel` with inertia deceleration and fallback."""
    if not page:
        return False
    try:
        engine = _get_engine(account_id)
        if engine.natural_scroll(page, dy, reading_pause=False):
            return True
    except Exception:
        pass

    try:
        if hasattr(page, "is_closed") and page.is_closed() is True:
            return False
        page.mouse.wheel(dx, dy)
        return True
    except Exception:
        return False


def warm_up_surface(page: Any, account_id: Optional[str] = None, rounds: int = 2) -> bool:
    """Simulate human warm-up browsing on the active surface before sensitive actions."""
    try:
        engine = _get_engine(account_id)
        return engine.warm_up(page, rounds=rounds)
    except Exception:
        return False
