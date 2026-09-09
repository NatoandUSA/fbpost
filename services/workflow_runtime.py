"""Thin runtime bridge from executors to persisted workflow task evidence."""
from __future__ import annotations

from datetime import datetime, timezone
from repositories.workflow_repo import WorkflowRepository


def _now():
    return datetime.now(timezone.utc).isoformat()


def start_task(job_id, action, profile_id, target_url, metadata=None):
    try:
        repo = WorkflowRepository()
        task = repo.create_task(job_id=job_id, action=action, profile_id=profile_id,
                                target_url=target_url, metadata=metadata or {})
        repo.update_task(task["id"], phase="RUNNING", state="running", progress=5,
                         started_at=_now())
        repo.add_event(task["id"], "TASK_STARTED", "RUNNING", "Task started")
        return task["id"]
    except Exception:
        return ""

def add_event(task_id, event_type, phase="", message="", payload=None):
    if not task_id:
        return
    try:
        WorkflowRepository().add_event(task_id, event_type, phase, message, payload or {})
    except Exception:
        pass


def finish_task(task_id, *, state, phase="TERMINAL", submission_status="NOT_SUBMITTED",
                verification_status="NOT_STARTED", result_url="", error_code="", error_message=""):
    if not task_id:
        return
    try:
        repo = WorkflowRepository()
        repo.update_task(task_id, phase=phase, state=state, progress=100,
                         submission_status=submission_status,
                         verification_status=verification_status,
                         result_url=result_url or "", error_code=error_code or None,
                         error_message=error_message or None, finished_at=_now())
        repo.add_event(task_id, "TASK_FINISHED", phase, state,
                       {"submission_status": submission_status,
                        "verification_status": verification_status,
                        "result_url": result_url or "", "error_code": error_code or ""})
    except Exception:
        pass
