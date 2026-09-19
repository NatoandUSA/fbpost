import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import services.profile_session_manager as psm


class TerminalLifecycleTests(unittest.TestCase):
    def test_terminal_worker_exit_ignores_non_daemon_thread(self):
        code = (
            "import threading,time,main; "
            "threading.Thread(target=lambda: time.sleep(60), daemon=False).start(); "
            "print('BEFORE_EXIT', flush=True); main._terminal_worker_exit(True)"
        )
        started = time.time()
        proc = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=5)
        elapsed = time.time() - started
        self.assertEqual(proc.returncode, 0)
        self.assertIn('BEFORE_EXIT', proc.stdout)
        self.assertLess(elapsed, 3.0)

    def test_terminal_worker_exit_preserves_failure_code(self):
        proc = subprocess.run(
            [sys.executable, '-c', "import main; print('FAIL_EXIT', flush=True); main._terminal_worker_exit(False)"],
            capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn('FAIL_EXIT', proc.stdout)

    def test_release_profile_clears_persisted_endpoint_before_unlock(self):
        events = []
        class FakeLease:
            handle = object()
            def _write_meta(self, endpoint=''):
                events.append(('meta', endpoint))
            def release(self):
                events.append(('release', None))
        key = 'profile-test'
        fake = FakeLease()
        with psm._registry_lock:
            psm._active_leases[key] = fake
            psm._runtime[key] = {'cdp_endpoint':'http://127.0.0.1:5555'}
        try:
            psm.release_profile(key)
        finally:
            with psm._registry_lock:
                psm._active_leases.pop(key, None)
                psm._runtime.pop(key, None)
        self.assertEqual(events, [('meta', ''), ('release', None)])


if __name__ == '__main__':
    unittest.main()
