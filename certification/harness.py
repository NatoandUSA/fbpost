"""Offline-only E4 certification harness."""
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, Sequence, Tuple
from certification.pending_resolver import NavigationBudget, PendingObservation, PendingState, resolve_pending_read_only, validate_candidate

@dataclass(frozen=True)
class SurfaceSpec:
    source_id: str
    selector: str
    authority: str = "pending_control"

@dataclass(frozen=True)
class CorrelationReceipt:
    candidate_id: str
    source_ids: Tuple[str, ...]
    selectors: Tuple[str, ...]
    navigation_count: int
    pending_state: PendingState
    pending_count: int | None
    eligible: bool
    reason: str

class CertificationHarness:
    def __init__(self, locked_pool: Iterable[str], excluded: Iterable[str], navigation_limit: int, surface_specs: Sequence[SurfaceSpec]):
        self.locked_pool = tuple(str(x).strip() for x in locked_pool)
        self.excluded = tuple(str(x).strip() for x in excluded)
        self.budget = NavigationBudget(navigation_limit)
        self._authorization_counts = defaultdict(int)
        self._navigation_counts = defaultdict(int)
        self.surface_specs = tuple(surface_specs)
        self._validate_specs()

    def _validate_specs(self) -> None:
        if not self.surface_specs:
            raise ValueError("authoritative_surface_specs_required")
        source_ids, selectors = set(), set()
        for spec in self.surface_specs:
            if spec.authority != "pending_control":
                raise ValueError("unsupported_surface_authority")
            if not spec.source_id or not spec.selector:
                raise ValueError("surface_provenance_required")
            if spec.selector.strip().casefold() in {"body", "html", "*"}:
                raise ValueError("broad_surface_selector_forbidden")
            if spec.source_id in source_ids or spec.selector in selectors:
                raise ValueError("duplicate_surface_spec")
            source_ids.add(spec.source_id); selectors.add(spec.selector)

    def authorize_navigation(self, candidate_id: str) -> str:
        value = self.budget.authorize(candidate_id, self.locked_pool, self.excluded)
        self._authorization_counts[value] += 1
        return value

    def record_navigation(self, candidate_id: str) -> str:
        value = validate_candidate(candidate_id, self.locked_pool, self.excluded)
        authorized = self._authorization_counts.get(value, 0)
        navigated = self._navigation_counts.get(value, 0)
        if navigated >= authorized:
            raise RuntimeError("navigation_not_authorized")
        self._navigation_counts[value] = navigated + 1
        return value

    def evaluate_after_navigation(self, candidate_id: str, located_surfaces: Dict[str, object]) -> CorrelationReceipt:
        value = validate_candidate(candidate_id, self.locked_pool, self.excluded)
        navigation_count = self._navigation_counts.get(value, 0)
        if navigation_count < 1:
            raise RuntimeError("candidate_not_navigated")
        surfaces, used_specs = [], []
        for spec in self.surface_specs:
            surface = located_surfaces.get(spec.source_id)
            if surface is not None:
                surfaces.append(surface); used_specs.append(spec)
        observation: PendingObservation = resolve_pending_read_only(surfaces)
        return CorrelationReceipt(value, tuple(x.source_id for x in used_specs), tuple(x.selector for x in used_specs), navigation_count, observation.state, observation.count, observation.eligible, observation.reason)
