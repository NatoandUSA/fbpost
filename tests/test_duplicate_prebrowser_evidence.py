import json

import services.job_executor as executor


class _FakeRunner:
    def is_cancelled(self, job_id):
        return False

    def run_command_sync(self, *args, **kwargs):
        raise AssertionError("duplicate pre-browser path must not open ProcessRunner/browser")


class _FakeJobRepo:
    def __init__(self):
        self.updates = []

    def update_job(self, job_id, **updates):
        self.updates.append((job_id, updates))
        return True


class _FakeActivityRepo:
    def list_posted_links(self, limit=300):
        return [{
            "target": "https://facebook.com/groups/rivewdulichtphue",
            "publish_state": "published",
            "posted_at": "2026-09-25 12:28:23",
            "url": "https://www.facebook.com/groups/rivewdulichtphue/posts/1391877076350479",
            "content": "unrelated recent post",
        }]


def test_duplicate_prebrowser_emits_typed_no_mutation_evidence(monkeypatch):
    lines = []
    monkeypatch.setattr(executor, "load_config", lambda: {})
    monkeypatch.setattr(executor, "is_recently_posted", lambda target, hours: (True, 1.1, "2026-09-25 12:28:23"))
    monkeypatch.setattr(executor, "ActivityRepository", _FakeActivityRepo)
    monkeypatch.setattr(executor, "workflow_start_task", lambda **kwargs: (_ for _ in ()).throw(AssertionError("workflow task must not be created before duplicate gate")))

    repo = _FakeJobRepo()
    ok = executor.execute_automation_task(
        job_id="duplicate-prebrowser",
        cmd="group",
        data={
            "accountId": "81812b97-7d4a-4135-a82c-6aa0b5eed0fe",
            "rotateAccounts": False,
            "autoSpin": False,
            "skipDuplicate24h": True,
            "skipDuplicateHours": 3,
            "brandKey": "umee",
            "tasks": [{
                "target": "https://facebook.com/groups/rivewdulichtphue",
                "content": "immutable commercial content",
                "image": None,
            }],
        },
        on_line=lines.append,
        process_runner=_FakeRunner(),
        job_repo=repo,
    )

    assert ok is True
    action_lines = [line for line in lines if line.startswith("ACTION_RESULT:")]
    assert len(action_lines) == 1
    result = json.loads(action_lines[0].split(":", 1)[1])
    assert result["code"] == "SKIPPED_DUPLICATE"
    assert result["state"] == "skipped_duplicate"
    assert result["metadata"]["prebrowser_noop"] is True
    assert result["metadata"]["external_mutation"] is False
    assert result["metadata"]["recent_state"] == "published"
    assert result["metadata"]["recent_url"].endswith("/1391877076350479")
    # V31 contract is intentionally unchanged: unsupported 3h resolves fail-closed to 24h.
    assert result["metadata"]["retry_window_hours"] == 24
    assert "RUN_RESULT:finished\n" in lines