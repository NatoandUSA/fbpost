import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from services.process_runner import ProcessRunner


class ProcessRunnerLifecycleTests(unittest.TestCase):
    def test_worker_exit_is_authoritative_even_if_descendant_keeps_stdout_open(self):
        runner = ProcessRunner()
        lines = []
        # The worker spawns a descendant that inherits stdout and sleeps. The worker then
        # emits ACTION_RESULT and exits immediately. Old ProcessRunner blocked on pipe EOF.
        code = (
            "import os,sys,subprocess; "
            "subprocess.Popen([sys.executable,'-c','import time; time.sleep(6)']); "
            "print('ACTION_RESULT:{\\\"success\\\":true,\\\"state\\\":\\\"published\\\"}', flush=True); "
            "os._exit(0)"
        )
        started = time.monotonic()
        ret = runner.run_command_sync(
            [sys.executable, '-c', code],
            job_id='lifecycle_pipe_hold',
            on_line=lines.append,
            timeout_seconds=10,
        )
        elapsed = time.monotonic() - started
        self.assertEqual(ret, 0)
        self.assertLess(elapsed, 4.0, f'runner waited on inherited pipe for {elapsed:.2f}s')
        self.assertTrue(any(line.startswith('ACTION_RESULT:') for line in lines))

    def test_real_timeout_still_returns_minus_two(self):
        runner = ProcessRunner()
        started = time.monotonic()
        ret = runner.run_command_sync(
            [sys.executable, '-c', 'import time; time.sleep(4)'],
            job_id='lifecycle_real_timeout',
            timeout_seconds=1,
        )
        elapsed = time.monotonic() - started
        self.assertEqual(ret, -2)
        self.assertLess(elapsed, 4.0)


if __name__ == '__main__':
    unittest.main()
