# Exact-head Windows regression coverage.\nimport json
import threading


def test_prebrowser_action_result_is_persisted(tmp_path, monkeypatch):
    import services.job_manager as job_manager_mod
    import services.job_executor as job_executor_mod

    job_id = "prebrowser123"

    class FakeRepo:
        def __init__(self):
            self.finished = None

        def get_job(self, wanted):
            assert wanted == job_id
            return {
                "id": job_id,
                "command": "group",
                "state": "queued",
                "payload": {"tasks": [{"target": "https://facebook.com/groups/example", "content": "x"}]},
                "account_id": "acc-1",
            }

        def mark_running(self, wanted):
            assert wanted == job_id
            return True

        def mark_finished(self, wanted, state, error_message=None):
            self.finished = (wanted, state, error_message)
            return True

    class FakeRunner:
        def __init__(self):
            self.log_path = tmp_path / f"{job_id}.log"

        def get_log_path(self, wanted):
            assert wanted == job_id
            return self.log_path

        def is_cancelled(self, wanted):
            assert wanted == job_id
            return False

        def cleanup_job(self, wanted):
            assert wanted == job_id

    class FakeReconcileRepo:
        def count_active(self, origin_job_id=None):
            return 0

    def fake_execute_automation_task(*, job_id, cmd, data, on_line, process_runner, job_repo):
        assert cmd == "group"
        on_line(
            "ACTION_RESULT:"
            + json.dumps(
                {
                    "success": False,
                    "code": "SKIPPED_DUPLICATE",
                    "state": "skipped_duplicate",
                    "message": "No submit attempted.",
                }
            )
            + "\n"
        )
        on_line("RUN_RESULT:finished\n")
        return True

    monkeypatch.setattr(job_executor_mod, "execute_automation_task", fake_execute_automation_task)
    monkeypatch.setattr(job_manager_mod, "ReconcileRepository", lambda: FakeReconcileRepo())

    manager = object.__new__(job_manager_mod.JobManager)
    manager.job_repo = FakeRepo()
    manager.process_runner = FakeRunner()
    manager._raw_payloads = {}
    manager._job_queues = {}
    manager._lock = threading.Lock()

    manager._execute_job(job_id)

    assert manager.job_repo.finished == (job_id, "success", None)
    assert manager.process_runner.log_path.exists()
    log = manager.process_runner.log_path.read_text(encoding="utf-8")
    assert f"JOB_LOG_IDENTITY:{job_id}|" in log
    assert '"code": "SKIPPED_DUPLICATE"' in log
    assert '"state": "skipped_duplicate"' in log
    assert "RUN_RESULT:finished" in log
