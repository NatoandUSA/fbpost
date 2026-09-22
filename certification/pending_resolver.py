"""Read-only, fail-closed helpers for E4 certification.

This module is intentionally isolated from the production posting path.
It must not join groups, open composers, enqueue jobs, post, or comment.
"""
from dataclasses import dataclass
from enum import Enum
import re
from typing import Iterable, Optional, Set


class PendingState(str, Enum):
    ZERO_CONFIRMED = "ZERO_CONFIRMED"
    COUNT_CONFIRMED = "COUNT_CONFIRMED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class PendingObservation:
    state: PendingState
    count: Optional[int] = None
    reason: str = ""

    @property
    def eligible(self) -> bool:
        return self.state is PendingState.ZERO_CONFIRMED


_PENDING_PATTERNS = (
    re.compile(r"(?:Đang\s+chờ\s+quản\s+trị\s+viên\s+phê\s+duyệt|pending\s+admin\s+approval)[\s\S]{0,100}?(\d+)\s+(?:bài\s+viết|posts?)", re.I),
    re.compile(r"(\d+)\s+(?:bài\s+viết|posts?)[\s\S]{0,70}?(?:chờ\s+(?:quản\s+trị\s+viên\s+)?phê\s+duyệt|pending\s+approval)", re.I),
)
_ZERO_PATTERNS = (
    re.compile(r"(?:Đang\s+chờ\s+quản\s+trị\s+viên\s+phê\s+duyệt|pending\s+admin\s+approval)[\s\S]{0,100}?0\s+(?:bài\s+viết|posts?)", re.I),
    re.compile(r"0\s+(?:bài\s+viết|posts?)[\s\S]{0,70}?(?:chờ\s+(?:quản\s+trị\s+viên\s+)?phê\s+duyệt|pending\s+approval)", re.I),
)


def resolve_pending_read_only(page) -> PendingObservation:
    try:
        text = page.locator("body").inner_text(timeout=2500)
    except Exception as exc:
        return PendingObservation(PendingState.UNKNOWN, reason=f"body_read_failure:{type(exc).__name__}")
    if not isinstance(text, str):
        return PendingObservation(PendingState.UNKNOWN, reason="non_string_body")
    for pattern in _PENDING_PATTERNS:
        match = pattern.search(text)
        if match:
            try:
                count = max(0, int(match.group(1)))
            except (TypeError, ValueError):
                return PendingObservation(PendingState.UNKNOWN, reason="parse_failure")
            state = PendingState.ZERO_CONFIRMED if count == 0 else PendingState.COUNT_CONFIRMED
            return PendingObservation(state, count=count, reason="observed_pending_surface")
    for pattern in _ZERO_PATTERNS:
        if pattern.search(text):
            return PendingObservation(PendingState.ZERO_CONFIRMED, count=0, reason="observed_zero_surface")
    return PendingObservation(PendingState.UNKNOWN, reason="pending_surface_not_observed")


_NUMERIC_ID = re.compile(r"^[0-9]+$")


def validate_candidate(candidate_id: str, locked_pool: Iterable[str], excluded: Iterable[str] = ()) -> str:
    value = str(candidate_id or "").strip()
    if not _NUMERIC_ID.fullmatch(value):
        raise ValueError("candidate_id_not_numeric")
    locked: Set[str] = {str(x).strip() for x in locked_pool}
    blocked: Set[str] = {str(x).strip() for x in excluded}
    if value not in locked:
        raise ValueError("candidate_id_not_in_locked_pool")
    if value in blocked:
        raise ValueError("candidate_id_excluded")
    return value


class NavigationBudget:
    def __init__(self, maximum: int):
        if maximum < 0:
            raise ValueError("navigation_budget_negative")
        self.maximum = maximum
        self.used = 0

    def authorize(self, candidate_id: str) -> None:
        if self.used >= self.maximum:
            raise RuntimeError("navigation_budget_exhausted")
        self.used += 1
