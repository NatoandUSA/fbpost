"""Process Runner Service.
Handles subprocess execution, output capturing, per-job file logging,
and Windows process-tree termination.
"""

import os
import sys
import re
import subprocess
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional
from paths import JOBS_LOG_DIR


class ProcessRunner:
    def __init__(self):
        self._active_processes: Dict[str, subprocess.Popen] = {}
        self._listeners: Dict[str, List[Callable[[str], None]]] = {}
        self._cancellation_requested: Dict[str, bool] = {}
        self._lock = threading.Lock()

    def get_log_path(self, job_id: str) -> Path:
        if not re.match(r"^[0-9a-zA-Z_\-]+$", job_id) or ".." in job_id:
            raise ValueError(f"Invalid job_id format: {job_id}")
        JOBS_LOG_DIR.mkdir(parents=True, exist_ok=True)
        resolved = (JOBS_LOG_DIR / f"{job_id}.log").resolve()
        if resolved.parent != JOBS_LOG_DIR.resolve():
            raise ValueError(f"Path traversal detected in job_id: {job_id}")
        return resolved

    def prepare_job(self, job_id: str) -> None:
        """Initialize job state before enqueueing or starting."""
        with self._lock:
            self._cancellation_requested[job_id] = False

    def is_running(self, job_id: str) -> bool:
        with self._lock:
            proc = self._active_processes.get(job_id)
            if proc is None:
                return False
            return proc.poll() is None

    def get_pid(self, job_id: str) -> Optional[int]:
        with self._lock:
            proc = self._active_processes.get(job_id)
            return proc.pid if proc else None

    def add_listener(self, job_id: str, callback: Callable[[str], None]):
        with self._lock:
            if job_id not in self._listeners:
                self._listeners[job_id] = []
            self._listeners[job_id].append(callback)

    def remove_listener(self, job_id: str, callback: Callable[[str], None]):
        with self._lock:
            if job_id in self._listeners:
                try:
                    self._listeners[job_id].remove(callback)
                except ValueError:
                    pass

    def cleanup_job(self, job_id: str) -> None:
        """Release listeners, active process handles, and cancellation flags."""
        with self._lock:
            self._active_processes.pop(job_id, None)
            self._listeners.pop(job_id, None)
            self._cancellation_requested.pop(job_id, None)

    def run_command_sync(
        self,
        cmd_args: List[str],
        job_id: str,
        on_line: Optional[Callable[[str], None]] = None,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: Optional[float] = None,
    ) -> int:
        """Run a command synchronously in the calling thread, streaming output line by line."""
        if self.is_cancelled(job_id):
            return -1

        log_path = self.get_log_path(job_id)
        process_env = {
            **os.environ,
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            **(env or {}),
        }

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        log_file = open(log_path, "a", encoding="utf-8", errors="replace")
        marker = f"JOB_LOG_IDENTITY:{job_id}|path={log_path.resolve()}\n"
        log_file.write(marker)
        log_file.flush()
        if on_line:
            try:
                on_line(marker)
            except Exception:
                pass
        proc = None
        timeout_hit = threading.Event()
        process_done = threading.Event()
        try:
            proc = subprocess.Popen(
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=process_env,
                cwd=cwd,
                creationflags=creationflags,
            )

            with self._lock:
                self._active_processes[job_id] = proc
                if self._cancellation_requested.get(job_id, False):
                    # Job was cancelled before/during process creation
                    proc.kill()
                    return -1
                if job_id not in self._cancellation_requested:
                    self._cancellation_requested[job_id] = False

            if timeout_seconds:
                def _watchdog():
                    if process_done.wait(max(1.0, float(timeout_seconds))):
                        return
                    timeout_hit.set()
                    if sys.platform == "win32" and proc and proc.pid:
                        try:
                            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=5)
                        except Exception:
                            pass
                    try:
                        if proc and proc.poll() is None:
                            proc.kill()
                    except Exception:
                        pass
                threading.Thread(target=_watchdog, daemon=True).start()

            if proc.stdout:
                for raw_line in iter(proc.stdout.readline, ""):
                    if not raw_line:
                        break
                    line = raw_line
                    log_file.write(line)
                    log_file.flush()

                    if on_line:
                        try:
                            on_line(line)
                        except Exception:
                            pass

                    with self._lock:
                        subs = list(self._listeners.get(job_id, []))
                    for sub in subs:
                        try:
                            sub(line)
                        except Exception:
                            pass

            returncode = proc.wait()
            process_done.set()
            if timeout_hit.is_set():
                msg = f"❌ [TARGET_TIMEOUT] Tiến trình vượt quá {int(float(timeout_seconds))}s; đã dừng process tree để chuyển target tiếp theo.\n"
                log_file.write(msg); log_file.flush()
                if on_line:
                    on_line(msg)
                return -2
            return returncode

        except Exception as err:
            err_msg = f"❌ [ProcessRunner] Lỗi thực thi tiến trình: {err}\n"
            log_file.write(err_msg)
            log_file.flush()
            if on_line:
                on_line(err_msg)
            return -1
        finally:
            process_done.set()
            log_file.close()
            with self._lock:
                self._active_processes.pop(job_id, None)

    def cancel(self, job_id: str, timeout: float = 5.0) -> bool:
        """Terminate process and all child processes (process tree)."""
        with self._lock:
            self._cancellation_requested[job_id] = True
            proc = self._active_processes.get(job_id)

        if not proc:
            return True

        pid = proc.pid
        if proc.poll() is not None:
            return True

        # On Windows, kill entire process tree using taskkill
        if sys.platform == "win32" and pid:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    timeout=timeout,
                )
            except Exception:
                pass

        try:
            proc.terminate()
            proc.wait(timeout=1.0)
        except Exception:
            try:
                proc.kill()
                proc.wait(timeout=1.0)
            except Exception:
                pass

        return proc.poll() is not None

    def is_cancelled(self, job_id: str) -> bool:
        with self._lock:
            return self._cancellation_requested.get(job_id, False)
