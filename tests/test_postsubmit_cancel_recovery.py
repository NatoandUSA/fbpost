import json

import services.job_executor as executor
import brand_profiles
import composer_guard
import content_studio


class _Runner:
    def __init__(self):
        self.calls = []
        self.cancel_after_submit = False

    def is_cancelled(self, _job_id):
        return self.cancel_after_submit

    def run_command_sync(self, cmd, *, on_line=None, **kwargs):
        self.calls.append(cmd)
        if len(self.calls) == 1:
            if on_line:
                on_line("SUBMIT_TRIGGERED_MARKER:POST_BUTTON_ACTIVATED\n")
                on_line(
                    "ACTION_RESULT:"
                    + json.dumps({
                        "success": False,
                        "code": "POST_SUBMITTED_UNVERIFIED",
                        "message": "submitted but permalink not found",
                        "state": "submitted_unverified",
                        "target_url": "https://facebook.com/groups/123",
                        "result_url": "",
                        "url_type": "group",
                        "metadata": {},
                        "data": {},
                    })
                    + "\n"
                )
            self.cancel_after_submit = True
            return 1
        raise AssertionError("read-only reconcile child must not start after cancellation")


class _JobRepo:
    def __init__(self):
        self.updates = []

    def update_job(self, job_id, **updates):
        self.updates.append((job_id, updates))
        return True


class _ReconcileRepo:
    enqueued = []

    def __init__(self, *args, **kwargs):
        pass

    def enqueue(
        self,
        target_url,
        content,
        account_id=None,
        queue_item_id=None,
        delay_seconds=30,
        reconcile_kind="uncertain",
        origin_job_id=None,
    ):
        self.__class__.enqueued.append({
            "target_url": target_url,
            "content": content,
            "account_id": account_id,
            "queue_item_id": queue_item_id,
            "delay_seconds": delay_seconds,
            "reconcile_kind": reconcile_kind,
            "origin_job_id": origin_job_id,
        })
        return "reconcile-id-1234567890"


class _ModerationRepo:
    def requires_approval(self, _target):
        return True


def test_cancel_after_submit_keeps_durable_reconcile_before_cancellable_wait(monkeypatch):
    _ReconcileRepo.enqueued.clear()
    runner = _Runner()
    repo = _JobRepo()
    logs = []

    monkeypatch.setattr(executor, "load_config", lambda: {})
    monkeypatch.setattr(executor, "_published_content_history", lambda limit=200: [])
    monkeypatch.setattr(executor, "is_recently_posted", lambda target, hours: (False, None, None))
    monkeypatch.setattr(executor, "record_profile_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr(executor, "workflow_start_task", lambda **kwargs: "wf-1")
    monkeypatch.setattr(executor, "workflow_finish_task", lambda *args, **kwargs: None)
    monkeypatch.setattr(executor, "ReconcileRepository", _ReconcileRepo)
    monkeypatch.setattr(executor, "ModerationRepository", _ModerationRepo)

    monkeypatch.setattr(brand_profiles, "apply_brand_signature", lambda content, *args, **kwargs: content)
    monkeypatch.setattr(brand_profiles, "validate_brand_signature", lambda *args, **kwargs: (True, []))
    monkeypatch.setattr(brand_profiles, "prepare_linkless_post", lambda value: value)
    monkeypatch.setattr(composer_guard, "normalize_single_cta", lambda content, brand_key: content)
    monkeypatch.setattr(composer_guard, "dedupe_content_blocks", lambda content: content)
    monkeypatch.setattr(composer_guard, "audit_final_content", lambda *args, **kwargs: {"pass": True, "issues": []})
    monkeypatch.setattr(content_studio, "similarity_gate", lambda *args, **kwargs: {"pass": True, "max_similarity": 0.0, "threshold": 0.82})

    ok = executor.execute_automation_task(
        job_id="postsubmit-cancel",
        cmd="group",
        data={
            "accountId": "acc-1",
            "rotateAccounts": False,
            "autoSpin": False,
            "skipDuplicate24h": True,
            "skipDuplicateHours": 3,
            "brandKey": "",
            "tasks": [{
                "target": "https://facebook.com/groups/123",
                "content": "Unique factual post content for post-submit cancellation recovery.",
                "image": None,
            }],
        },
        on_line=logs.append,
        process_runner=runner,
        job_repo=repo,
    )

    assert ok is False
    assert len(runner.calls) == 1
    assert len(_ReconcileRepo.enqueued) == 1
    recovery = _ReconcileRepo.enqueued[0]
    assert recovery["origin_job_id"] == "postsubmit-cancel"
    assert recovery["target_url"] == "https://facebook.com/groups/123"
    assert recovery["delay_seconds"] == 30
    assert any("READ_ONLY / NO REPOST" in line for line in logs)
