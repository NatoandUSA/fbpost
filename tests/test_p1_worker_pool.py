import threading
import time
import unittest

from services.job_manager import JobManager


class _Repo:
    def __init__(self):
        self.jobs = {}
    def get_job(self, job_id):
        return self.jobs.get(job_id)


class _Runner:
    pass


class WorkerPoolTests(unittest.TestCase):
    def _manager(self, workers=3):
        repo = _Repo()
        jm = object.__new__(JobManager)
        jm._initialized = False
        JobManager.__init__(jm, job_repo=repo, process_runner=_Runner(), max_workers=workers)
        jm.profile_capacity._account_loader = lambda: [
            {'id':'P1'}, {'id':'P2'}, {'id':'P3'}, {'id':'P4'}
        ]
        return jm

    def _queue(self, jm, job_id, profile_id):
        jm.job_repo.jobs[job_id] = {
            'id': job_id, 'command': 'group', 'state': 'queued',
            'payload': {'accountId': profile_id},
        }
        jm._work_queue.put(job_id)

    def test_capacity_snapshot_and_worker_bound(self):
        jm = self._manager(3)
        snap = jm.capacity_snapshot()
        self.assertEqual(snap['worker_max'], 3)
        self.assertEqual(snap['worker_active'], 0)
        self.assertEqual(snap['worker_available'], 3)
        self.assertEqual(snap['profiles_total'], 4)

    def test_three_disjoint_jobs_can_be_active_concurrently(self):
        jm = self._manager(3)
        release = threading.Event()
        def fake_execute(job_id):
            release.wait(2)
        jm._execute_job = fake_execute
        self._queue(jm, 'a', 'P1')
        self._queue(jm, 'b', 'P2')
        self._queue(jm, 'c', 'P3')
        deadline = time.time() + 2
        while time.time() < deadline and len(jm.get_active_job_ids()) < 3:
            time.sleep(0.01)
        self.assertEqual(len(jm.get_active_job_ids()), 3)
        self.assertEqual(jm.capacity_snapshot()['profiles_reserved'], 3)
        release.set()
        jm._work_queue.join()

    def test_same_profile_jobs_are_serialized(self):
        jm = self._manager(2)
        release = threading.Event()
        jm._execute_job = lambda job_id: release.wait(2)
        self._queue(jm, 'a', 'P1')
        self._queue(jm, 'b', 'P1')
        deadline = time.time() + 1
        while time.time() < deadline and not jm.get_active_job_ids():
            time.sleep(0.01)
        self.assertEqual(len(jm.get_active_job_ids()), 1)
        self.assertGreaterEqual(jm.capacity_snapshot()['queue_depth'], 1)
        release.set()
        deadline = time.time() + 2
        while time.time() < deadline and jm._work_queue.unfinished_tasks:
            time.sleep(0.01)
        self.assertEqual(jm._work_queue.unfinished_tasks, 0)

    def test_worker_count_is_clamped(self):
        self.assertEqual(self._manager(0).max_workers, 1)
        self.assertEqual(self._manager(999).max_workers, 32)


if __name__ == '__main__':
    unittest.main()
