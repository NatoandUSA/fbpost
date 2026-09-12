"""Optional interaction pacing adapter.

Provides drop-in replacements matching existing utility function signatures in `utils.py`
so that integrating the Human Behavior Engine requires zero refactoring of business logic
while leaving the authoritative legacy fallback in utils.py.
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


def human_type_advanced(
    page: Any, locator: Any, text: str, multiline_key: str = "Enter",
    account_id: Optional[str] = None, allow_typos: bool = False
) -> bool:
    """Run only the optional paced typing path; utils.py owns fallback."""
    if not page or not locator or text is None:
        return False
    try:
        engine = _get_engine(account_id)
        return bool(engine.type_into(page, locator, text, multiline_key=multiline_key, click_first=False, allow_typos=allow_typos))
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
    """Run only optional kinetic scrolling; utils.py owns the direct wheel fallback."""
    if not page or dx != 0 or dy == 0:
        return False
    try:
        engine = _get_engine(account_id)
        return bool(engine.natural_scroll(page, dy, reading_pause=False))
    except Exception:
        return False


def warm_up_surface(page: Any, account_id: Optional[str] = None, rounds: int = 2) -> bool:
    """Simulate human warm-up browsing on the active surface before sensitive actions."""
    try:
        engine = _get_engine(account_id)
        return engine.warm_up(page, rounds=rounds)
    except Exception:
        return False
