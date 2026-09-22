"""E6 publication-authority rollout modes and shadow evaluation."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import os
from typing import Any, Dict, Optional

from certification.publication_authority import validate_publication_authority

ROLLOUT_ENV = "FB_GROUP_AUTHORITY_ROLLOUT_MODE"


class RolloutMode(str, Enum):
    LEGACY = "LEGACY"
    SHADOW = "SHADOW"
    ENFORCE = "ENFORCE"


def resolve_rollout_mode(value: Optional[str] = None) -> RolloutMode:
    """Resolve rollout mode. Missing/invalid config safely preserves legacy behavior."""
    raw = os.getenv(ROLLOUT_ENV, "") if value is None else value
    normalized = str(raw or "").strip().upper()
    if normalized == RolloutMode.SHADOW.value:
        return RolloutMode.SHADOW
    if normalized == RolloutMode.ENFORCE.value:
        return RolloutMode.ENFORCE
    return RolloutMode.LEGACY


@dataclass(frozen=True)
class ShadowEvaluation:
    mode: str
    queue_item_id: str
    target: str
    e5_decision: str
    would_allow: bool
    reason: str
    evaluated_at: str
    authority_ref: str
    publication_blocked: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_shadow(queue_item_id: str, target: str, authority: object) -> ShadowEvaluation:
    """Read-only E5 evaluation. It never decides or mutates publication state."""
    ok, reason = validate_publication_authority(target, authority)
    decision = "ZERO_CONFIRMED" if ok else str((authority or {}).get("decision", "UNKNOWN")) if isinstance(authority, dict) else "UNKNOWN"
    authority_ref = str((authority or {}).get("receipt_ref", "")) if isinstance(authority, dict) else ""
    return ShadowEvaluation(
        mode=RolloutMode.SHADOW.value,
        queue_item_id=str(queue_item_id or ""),
        target=str(target or ""),
        e5_decision=decision or "UNKNOWN",
        would_allow=bool(ok),
        reason=reason,
        evaluated_at=datetime.now(timezone.utc).isoformat(),
        authority_ref=authority_ref,
        publication_blocked=False,
    )
