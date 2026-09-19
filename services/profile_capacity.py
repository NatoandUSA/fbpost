"""Profile resource admission for concurrent automation jobs."""
from __future__ import annotations

from threading import RLock
from typing import Callable, Dict, Iterable, List, Set


PROFILE_FREE_COMMANDS = frozenset()


class ProfileCapacityManager:
    """Reserve profile identities before a job reaches browser execution."""
    def __init__(self, account_loader: Callable[[], List[dict]]):
        self._account_loader = account_loader
        self._lock = RLock()
        self._reserved_by_job: Dict[str, Set[str]] = {}

    def _all_profile_ids(self) -> List[str]:
        try:
            accounts = self._account_loader() or []
        except Exception:
            accounts = []
        return [str(a.get("id") or a.get("profile_path_or_id") or "").strip()
                for a in accounts
                if str(a.get("id") or a.get("profile_path_or_id") or "").strip()]

    def required_profiles(self, command: str, payload: dict) -> Set[str]:
        if command in PROFILE_FREE_COMMANDS:
            return set()
        account_id = str(payload.get("accountId") or "").strip()
        if account_id and account_id != "__rotate__":
            return {account_id}
        explicit = {str(x).strip() for x in (payload.get("accountIds") or []) if str(x).strip()}
        if explicit:
            return explicit
        if payload.get("rotateAccounts") or account_id == "__rotate__":
            return set(self._all_profile_ids())
        return set()

    def try_reserve(self, job_id: str, command: str, payload: dict) -> bool:
        wanted = self.required_profiles(command, payload)
        with self._lock:
            if job_id in self._reserved_by_job:
                return True
            busy = set().union(*self._reserved_by_job.values()) if self._reserved_by_job else set()
            if wanted & busy:
                return False
            self._reserved_by_job[job_id] = wanted
            return True

    def release(self, job_id: str) -> None:
        with self._lock:
            self._reserved_by_job.pop(job_id, None)

    def snapshot(self) -> dict:
        all_ids = set(self._all_profile_ids())
        with self._lock:
            reservations = {job: sorted(ids) for job, ids in self._reserved_by_job.items()}
            busy = set().union(*self._reserved_by_job.values()) if self._reserved_by_job else set()
        return {
            "profiles_total": len(all_ids),
            "profiles_reserved": len(busy),
            "profiles_ready": max(0, len(all_ids - busy)),
            "reserved_profile_ids": sorted(busy),
            "profile_reservations": reservations,
        }
