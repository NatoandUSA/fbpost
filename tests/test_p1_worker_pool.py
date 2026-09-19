import threading
import time
import unittest

from services.job_manager import JobManager


class _Repo:
    pass


class _Runner:
    pass


class WorkerPoolTests(unittest.TestCase):
    def _manager(self, workers=3):
        jm = object.__new__(JobManager)
        jm._initialized = False
        JobManager.__init__(jm, job_repo=_Repo(), process_runner=_Runner(), max_workers=workers)
        return jm

    def test_capacity_snapshot_and_worker_bound(self):
        jm = self._manager(3)
        snap = jm.capacity_snapshot()
        self.assertEqual(snap['worker_max'], 3)
        self.assertEqual(snap['worker_active'], 0)
        self.assertEqual(snap['worker_available'], 3)

    def test_three_jobs_can_be_active_concurrently(self):
        jm = self._manager(3)
        release = threading.Event()
        entered = []
        lock = threading.Lock()
        def fake_execute(job_id):
            with lock:
                entered.append(job_id)
            release.wait(2)
        jm._execute_job = fake_execute
        for job_id in ('a','b','c'):
            jm._work_queue.put(job_id)
        deadline = time.time() + 2
        while time.time() < deadline and len(jm.get_active_job_ids()) < 3:
            time.sleep(0.01)
        self.assertEqual(len(jm.get_active_job_ids()), 3)
        self.assertEqual(jm.capacity_snapshot()['worker_available'], 0)
        release.set()
        jm._work_queue.join()

    def test_worker_count_is_clamped(self):
        self.assertEqual(self._manager(0).max_workers, 1)
        self.assertEqual(self._manager(999).max_workers, 32)


if __name__ == '__main__':
    unittest.main()
