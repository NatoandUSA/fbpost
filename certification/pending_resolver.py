"""Read-only, fail-closed helpers for E4 certification.

Certification observes only caller-supplied authoritative pending surfaces.
It never scans arbitrary page body text and performs no Facebook mutation.
"""
from dataclasses import dataclass
from enum import Enum
import re
from typing import Iterable, Optional, Sequence, Set


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


_COUNT_PATTERN = re.compile(r"(?<!\d)(\d+)(?!\d)")
_NUMERIC_ID = re.compile(r"^[0-9]+$")


def resolve_pending_read_only(authoritative_surfaces: Sequence[object]) -> PendingObservation:
    """Resolve already-identified authoritative pending surfaces, fail closed."""
    if not isinstance(authoritative_surfaces, (list, tuple)):
        return PendingObservation(PendingState.UNKNOWN, reason="unsupported_surface_collection")
    if not authoritative_surfaces:
        return PendingObservation(PendingState.UNKNOWN, reason="authoritative_surface_not_observed")

    counts = []
    for surface in authoritative_surfaces:
        try:
            text = surface.inner_text(timeout=2500)
        except Exception as exc:
            return PendingObservation(
                PendingState.UNKNOWN,
                reason=f"surface_read_failure:{type(exc).__name__}",
            )
        if not isinstance(text, str):
            return PendingObservation(PendingState.UNKNOWN, reason="non_string_surface")
        matches = _COUNT_PATTERN.findall(text)
        if len(matches) != 1:
            return PendingObservation(PendingState.UNKNOWN, reason="ambiguous_surface_count")
        try:
            counts.append(int(matches[0]))
        except (TypeError, ValueError):
            return PendingObservation(PendingState.UNKNOWN, reason="parse_failure")

    unique_counts = set(counts)
    if len(unique_counts) != 1:
        return PendingObservation(PendingState.UNKNOWN, reason="conflicting_authoritative_counts")

    count = counts[0]
    state = PendingState.ZERO_CONFIRMED if count == 0 else PendingState.COUNT_CONFIRMED
    return PendingObservation(state, count=count, reason="consistent_authoritative_surfaces")


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

    def authorize(self, candidate_id: str, locked_pool: Iterable[str], excluded: Iterable[str] = ()) -> str:
        value = validate_candidate(candidate_id, locked_pool, excluded)
        if self.used >= self.maximum:
            raise RuntimeError("navigation_budget_exhausted")
        self.used += 1
        return value
