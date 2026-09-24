"""Job Manager Service.
Decouples automation execution lifecycle from HTTP connection lifecycle.
Manages job queue, state transitions, log streaming, and cancellation.
"""

import os
import sys
import time
import queue
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional

from paths import JOBS_LOG_DIR, BASE_DIR
from repositories.job_repo import JobRepository
from repositories.reconcile_repo import ReconcileRepository
from services.process_runner import ProcessRunner


class JobManager:
    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super(JobManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, job_repo: Optional[JobRepository] = None, process_runner: Optional[ProcessRunner] = None):
        if getattr(self, "_initialized", False):
            return
        self.job_repo = job_repo or JobRepository()
        self.process_runner = process_runner or ProcessRunner()
        self._job_queues: Dict[str, queue.Queue] = {}
        self._raw_payloads: Dict[str, Dict[str, Any]] = {}
        self._active_job_id: Optional[str] = None
        self._lock = threading.Lock()
        self._work_queue: queue.Queue = queue.Queue()
        self._worker_thread = threading.Thread(target=self._queue_worker, daemon=True)
        self._worker_thread.start()
        self._initialized = True

    def get_active_job_id(self) -> Optional[str]:
        with self._lock:
            return self._active_job_id

    def reconcile_on_startup(self) -> int:
        """Mark abandoned running jobs as interrupted, and requeue queued jobs."""
        interrupted = self.job_repo.reconcile_running_jobs()
        try:
            ReconcileRepository().recover_running()
        except Exception as exc:
            print(f"[ReconcileQueue] startup recovery warning: {exc}")
        queued = self.job_repo.list_jobs(limit=1000, state="queued")
        for job in reversed(queued):
            job_id = job["id"]
            with self._lock:
                self._job_queues.setdefault(job_id, queue.Queue())
            self.process_runner.prepare_job(job_id)
            self._work_queue.put(job_id)
        return interrupted

    def create_job(self, command: str, payload: Dict[str, Any], account_id: Optional[str] = None) -> str:
        job_id = uuid.uuid4().hex[:16]
        log_file = str(self.process_runner.get_log_path(job_id))
        self.job_repo.create_job({
            "id": job_id,
            "command": command,
            "account_id": account_id,
            "state": "queued",
            "payload": payload,
            "log_file": log_file,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return job_id

    def submit_job(self, command: str, payload: Dict[str, Any], account_id: Optional[str] = None) -> str:
        job_id = self.create_job(command, payload, account_id)
        self.process_runner.prepare_job(job_id)
        with self._lock:
            self._raw_payloads[job_id] = payload
            self._job_queues[job_id] = queue.Queue()
        self._work_queue.put(job_id)
        return job_id

    def cancel_job(self, job_id: str) -> bool:
        job = self.get_job(job_id)
        if not job:
            return False
        if job.get("state") in ("success", "failed", "cancelled", "interrupted"):
            return False

        with self._lock:
            self._raw_payloads.pop(job_id, None)
            is_active = (self._active_job_id == job_id)

        self.process_runner.cancel(job_id)
        self.job_repo.mark_finished(
            job_id,
            state="cancelled",
            error_message="Người dùng đã yêu cầu dừng tiến trình.",
        )
        self._emit_line(job_id, "⚠️ [JobManager] Tiến trình đã được yêu cầu hủy bỏ.\n")
        self._emit_line(job_id, "RUN_RESULT:cancelled\n")

        # Cleanup GPM browser profile if associated
        try:
            acc_id = job.get("account_id") or (job.get("payload") or {}).get("accountId")
            gpm_api = (job.get("payload") or {}).get("gpmApiUrl")
            if acc_id:
                from utils import resolve_account, close_browser
                acc = resolve_account(acc_id, gpm_api)
                if acc and acc.get("type") == "gpm":
                    close_browser(None, acc, gpm_api)
        except Exception:
            pass

        return True

    def cancel_active_job(self) -> bool:
        active_id = self.get_active_job_id()
        if active_id:
            return self.cancel_job(active_id)
        return False

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self.job_repo.get_job(job_id)

    def list_jobs(self, limit: int = 50, state: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.job_repo.list_jobs(limit=limit, state=state)

    def get_job_logs(self, job_id: str, offset: int = 0) -> str:
        log_path = self.process_runner.get_log_path(job_id)
        if not log_path.exists():
            return ""
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                if offset > 0:
                    f.seek(offset)
                return f.read()
        except OSError:
            return ""

    def _emit_line(self, job_id: str, line: Optional[str]):
        with self._lock:
            q = self._job_queues.get(job_id)
        if q:
            q.put(line)

    def subscribe_logs(self, job_id: str) -> Generator[str, None, None]:
        """Generator yielding lines in real-time as they arrive for job_id."""
        with self._lock:
            if job_id not in self._job_queues:
                self._job_queues[job_id] = queue.Queue()
            q = self._job_queues[job_id]

        while True:
            try:
                line = q.get(timeout=1.0)
                if line is None:
                    break
                yield line
            except queue.Empty:
                job = self.get_job(job_id)
                if job and job.get("state") in ("success", "failed", "cancelled", "interrupted"):
                    while not q.empty():
                        try:
                            rem = q.get_nowait()
                            if rem is not None:
                                yield rem
                        except queue.Empty:
                            break
                    break

    def _enqueue_due_reconciles(self):
        """Claim durable read-only reconcile records and enqueue them as normal jobs."""
        try:
            rows = ReconcileRepository().claim_due(limit=5)
        except Exception:
            return 0
        for row in rows:
            payload = {
                "command": "reconcile-post",
                "accountId": row.get("account_id"),
                "reconcileRecordId": row.get("id"),
                "originJobId": row.get("origin_job_id"),
                "tasks": [{"target": row.get("target_url"), "content": row.get("content")}],
            }
            job_id = self.create_job("reconcile-post", payload, account_id=row.get("account_id"))
            self.process_runner.prepare_job(job_id)
            with self._lock:
                self._job_queues.setdefault(job_id, queue.Queue())
            origin = str(row.get("origin_job_id") or "").strip()
            print(f"[Background Reconcile] origin={origin or '-'} reconcile={str(row.get('id') or '')[:10]} child_job={job_id} profile={row.get('account_id') or '-'} attempt={int(row.get('attempt') or 0)+1} READ_ONLY_NO_REPOST")
            self._work_queue.put(job_id)
        return len(rows)

    def _queue_worker(self):
        while True:
            job_id = None
            try:
                try:
                    job_id = self._work_queue.get(timeout=5.0)
                except queue.Empty:
                    self._enqueue_due_reconciles()
                    continue
                if job_id is None:
                    break
                with self._lock:
                    self._active_job_id = job_id
                self._execute_job(job_id)
            except Exception as e:
                import traceback
                error = traceback.format_exc()
                try:
                    if job_id:
                        self.job_repo.mark_finished(job_id, state="failed", error_message=str(e))
                        self._emit_line(job_id, error + "\n")
                except Exception:
                    pass
            finally:
                if job_id:
                    with self._lock:
                        if self._active_job_id == job_id:
                            self._active_job_id = None
                    self._emit_line(job_id, None)
                    self._work_queue.task_done()

    def _execute_job(self, job_id: str):
        job = self.job_repo.get_job(job_id)
        if not job:
            return

        # Kiểm tra nếu job đã bị hủy bỏ khi còn trong hàng đợi
        if job.get("state") == "cancelled" or self.process_runner.is_cancelled(job_id):
            self._emit_line(job_id, f"⚠️ [JobManager] Job ID: {job_id} đã được hủy bỏ trước khi chạy.\n")
            return

        command = job.get("command", "")
        with self._lock:
            raw_payload = self._raw_payloads.pop(job_id, None)
        payload = raw_payload if raw_payload is not None else (job.get("payload") or {})
        account_id = job.get("account_id")

        if not self.job_repo.mark_running(job_id):
            self._emit_line(job_id, f"⚠️ [JobManager] Không thể kích hoạt Job ID: {job_id} (trạng thái hiện tại không phải 'queued').\n")
            return

        self._emit_line(job_id, f"▶ [JobManager] Bắt đầu thực thi Job ID: {job_id} (Command: {command})\n")

        def on_line(line: str):
            # Persist typed terminal evidence emitted by pre-browser branches.
            # Child-process output is already persisted by ProcessRunner; this
            # fallback only creates a durable log when no child log exists yet.
            if line and ("ACTION_RESULT:" in line or "RUN_RESULT:" in line):
                try:
                    log_path = self.process_runner.get_log_path(job_id)
                    if not log_path.exists():
                        log_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(log_path, "a", encoding="utf-8", errors="replace") as handle:
                            handle.write(f"JOB_LOG_IDENTITY:{job_id}|path={log_path.resolve()}\n")
                            handle.write(line)
                except Exception:
                    pass
            self._emit_line(job_id, line)

        try:
            from services.job_executor import execute_automation_task
            success = execute_automation_task(
                job_id=job_id,
                cmd=command,
                data=payload,
                on_line=on_line,
                process_runner=self.process_runner,
                job_repo=self.job_repo,
            )
            final_state = "success" if success else "failed"
            if self.process_runner.is_cancelled(job_id):
                final_state = "cancelled"
            if command != "reconcile-post":
                try:
                    bg_count = ReconcileRepository().count_active(origin_job_id=job_id)
                except Exception:
                    bg_count = 0
                if bg_count:
                    self._emit_line(job_id, f"[Lifecycle] Posting finished; {bg_count} background reconcile item(s) remain active. READ-ONLY / NO REPOST.\n")
            self.job_repo.mark_finished(job_id, state=final_state)
            self._emit_line(job_id, f"[JobManager] Hoàn tất tiến trình với trạng thái: {final_state}\n")
        except Exception as ex:
            err_str = str(ex)
            self.job_repo.mark_finished(job_id, state="failed", error_message=err_str)
            self._emit_line(job_id, f"❌ [JobManager] Lỗi nghiêm trọng: {err_str}\n")
        finally:
            self.process_runner.cleanup_job(job_id)
