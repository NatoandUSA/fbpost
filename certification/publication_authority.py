"""Fail-closed E5 publication authority for Group Facebook mutation.

Human/content approval and certification authority are deliberately separate.
Only a current, target-bound ZERO_CONFIRMED receipt authorizes Group publication.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, Optional
from urllib.parse import urlsplit, urlunsplit

AUTHORITY_VERSION = "E5.v1"
ZERO_CONFIRMED = "ZERO_CONFIRMED"


def _canonical_target(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        host = parts.netloc.casefold().removeprefix("www.")
        path = parts.path.rstrip("/")
        return urlunsplit((parts.scheme.casefold() or "https", host, path, "", ""))
    except Exception:
        return raw.rstrip("/").casefold()


def is_group_target(target: str) -> bool:
    return "/groups/" in _canonical_target(target).casefold()


def _parse_utc(value: object) -> Optional[datetime]:
    try:
        text = str(value or "").strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _receipt_material(receipt: Dict[str, Any]) -> Dict[str, str]:
    return {
        "version": str(receipt.get("version") or ""),
        "candidate_id": str(receipt.get("candidate_id") or "").strip(),
        "target": _canonical_target(receipt.get("target") or ""),
        "decision": str(receipt.get("decision") or ""),
        "observed_at": str(receipt.get("observed_at") or ""),
        "valid_until": str(receipt.get("valid_until") or ""),
        "evidence_ref": str(receipt.get("evidence_ref") or "").strip(),
    }


def compute_receipt_ref(receipt: Dict[str, Any]) -> str:
    payload = json.dumps(_receipt_material(receipt), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_publication_authority(
    target: str,
    receipt: object,
    *,
    now: Optional[datetime] = None,
) -> tuple[bool, str]:
    """Validate Group publication authority. Non-Group targets remain unchanged."""
    if not is_group_target(target):
        return True, "non_group_not_gated"
    if not isinstance(receipt, dict):
        return False, "certification_missing"
    material = _receipt_material(receipt)
    if material["version"] != AUTHORITY_VERSION:
        return False, "certification_version_invalid"
    if material["decision"] != ZERO_CONFIRMED:
        return False, "certification_not_eligible"
    if not material["candidate_id"].isdigit():
        return False, "certification_candidate_invalid"
    canonical_target = _canonical_target(target)
    target_parts = [part for part in urlsplit(canonical_target).path.split("/") if part]
    target_group_id = target_parts[1] if len(target_parts) >= 2 and target_parts[0].casefold() == "groups" else ""
    if target_group_id and material["candidate_id"] != target_group_id:
        return False, "certification_candidate_target_mismatch"
    if not material["evidence_ref"]:
        return False, "certification_evidence_missing"
    if material["target"] != _canonical_target(target):
        return False, "certification_target_mismatch"
    observed_at = _parse_utc(material["observed_at"])
    valid_until = _parse_utc(material["valid_until"])
    if not observed_at or not valid_until or valid_until <= observed_at:
        return False, "certification_time_invalid"
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    if current > valid_until:
        return False, "certification_stale"
    expected = compute_receipt_ref(receipt)
    if str(receipt.get("receipt_ref") or "").strip() != expected:
        return False, "certification_reference_mismatch"
    return True, "certification_zero_confirmed"
