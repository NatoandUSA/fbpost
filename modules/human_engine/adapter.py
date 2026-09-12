"""Backward-Compatibility Adapter.

Provides drop-in replacements matching existing utility function signatures in `utils.py`
so that integrating the Human Behavior Engine requires zero refactoring of business logic.
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
    """Drop-in upgrade for `utils.human_type` with biometric keystroke cadence."""
    engine = _get_engine(account_id)
    return engine.type_into(page, locator, text, multiline_key=multiline_key, click_first=False)


def human_click(page: Any, locator: Any, account_id: Optional[str] = None) -> bool:
    """Execute natural Bézier cursor movement and human-paced click."""
    engine = _get_engine(account_id)
    return engine.click(page, locator)


def kinetic_mouse_wheel(page: Any, dx: int, dy: int, account_id: Optional[str] = None) -> bool:
    """Drop-in upgrade for `utils.safe_mouse_wheel` with inertia deceleration."""
    engine = _get_engine(account_id)
    return engine.natural_scroll(page, dy, reading_pause=False)


def warm_up_surface(page: Any, account_id: Optional[str] = None, rounds: int = 2) -> bool:
    """Simulate human warm-up browsing on the active surface before sensitive actions."""
    engine = _get_engine(account_id)
    return engine.warm_up(page, rounds=rounds)
