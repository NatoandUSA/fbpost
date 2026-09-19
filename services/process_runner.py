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
        """Run a child process with process-exit authority and file-backed log streaming.

        Browser descendants can inherit stdout handles. A PIPE therefore cannot be used as the
        completion boundary because EOF may arrive long after the CLI worker exits. Child output
        is written directly to the durable job log while a daemon tailer mirrors new lines to
        callbacks/listeners. The worker process itself is the only lifecycle authority.
        """
        if self.is_cancelled(job_id):
            return -1

        log_path = self.get_log_path(job_id)
        process_env = {
            **os.environ,
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUNBUFFERED": "1",
            **(env or {}),
        }
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        start_offset = log_path.stat().st_size if log_path.exists() else 0
        log_file = open(log_path, "a", encoding="utf-8", errors="replace", buffering=1)
        proc = None
        tailer_done = threading.Event()
        process_finished = threading.Event()
        try:
            proc = subprocess.Popen(
                cmd_args,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=process_env,
                cwd=cwd,
                creationflags=creationflags,
            )
            with self._lock:
                self._active_processes[job_id] = proc
                if self._cancellation_requested.get(job_id, False):
                    proc.kill()
                    return -1
                if job_id not in self._cancellation_requested:
                    self._cancellation_requested[job_id] = False

            def _emit(line: str) -> None:
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

            def _tail_log():
                try:
                    with open(log_path, "r", encoding="utf-8", errors="replace") as reader:
                        reader.seek(start_offset)
                        quiet_after_exit = 0
                        while True:
                            line = reader.readline()
                            if line:
                                quiet_after_exit = 0
                                _emit(line)
                                continue
                            if process_finished.is_set():
                                quiet_after_exit += 1
                                if quiet_after_exit >= 4:  # ~200 ms grace to drain final buffered line(s)
                                    break
                            time.sleep(0.05)
                finally:
                    tailer_done.set()

            # Local import avoids changing module API and keeps the tail loop cheap.
            import time
            threading.Thread(target=_tail_log, name=f"job-log-tail-{job_id}", daemon=True).start()

            timeout_hit = False
            try:
                returncode = proc.wait(timeout=max(1.0, float(timeout_seconds))) if timeout_seconds else proc.wait()
            except subprocess.TimeoutExpired:
                timeout_hit = True
                if sys.platform == "win32" and proc.pid:
                    try:
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=5)
                    except Exception:
                        pass
                try:
                    if proc.poll() is None:
                        proc.kill()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=5)
                except Exception:
                    pass
                returncode = -2

            process_finished.set()
            # Process exit is authoritative. Tailer is allowed only a short drain window.
            tailer_done.wait(1.0)
            if timeout_hit:
                msg = f"[TARGET_TIMEOUT] Process exceeded {int(float(timeout_seconds))}s; process tree terminated before advancing.\n"
                try:
                    log_file.write(msg); log_file.flush()
                except Exception:
                    pass
                _emit(msg)
                return -2
            return returncode

        except Exception as err:
            err_msg = f"[ProcessRunner] Execution error: {err}\n"
            try:
                log_file.write(err_msg); log_file.flush()
            except Exception:
                pass
            if on_line:
                try:
                    on_line(err_msg)
                except Exception:
                    pass
            return -1
        finally:
            process_finished.set()
            try:
                log_file.close()
            except Exception:
                pass
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
