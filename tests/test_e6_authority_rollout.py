import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from certification.publication_authority import AUTHORITY_VERSION, compute_receipt_ref
from certification.rollout import RolloutMode, evaluate_shadow, resolve_rollout_mode
from db import init_db
from repositories.campaign_repo import CampaignRepository

GROUP = "https://www.facebook.com/groups/752129859681671"
PAGE = "https://www.facebook.com/examplepage"


def authority():
    now = datetime.now(timezone.utc)
    value = {
        "version": AUTHORITY_VERSION,
        "candidate_id": "752129859681671",
        "target": GROUP,
        "decision": "ZERO_CONFIRMED",
        "observed_at": (now - timedelta(minutes=1)).isoformat(),
        "valid_until": (now + timedelta(minutes=5)).isoformat(),
        "evidence_ref": "e6-proof",
    }
    value["receipt_ref"] = compute_receipt_ref(value)
    return value


def item(auth=None, target=GROUP):
    value = {"id": "q-e6", "target": target, "content": "x", "state": "approved"}
    if auth is not None:
        value["certification_authority"] = auth
    return value


def repo_with(auth=None, target=GROUP):
    td = tempfile.TemporaryDirectory()
    db = Path(td.name) / "e6.db"; init_db(db)
    repo = CampaignRepository(db_file=str(db)); repo.insert_queue_item(item(auth, target))
    return td, repo


def test_mode_resolver_missing_and_invalid_preserve_legacy():
    assert resolve_rollout_mode("") is RolloutMode.LEGACY
    assert resolve_rollout_mode("garbage") is RolloutMode.LEGACY
    assert resolve_rollout_mode("shadow") is RolloutMode.SHADOW
    assert resolve_rollout_mode("ENFORCE") is RolloutMode.ENFORCE


def test_legacy_missing_authority_allows_existing_transition():
    td, repo = repo_with()
    try:
        with patch.dict("os.environ", {"FB_GROUP_AUTHORITY_ROLLOUT_MODE": "LEGACY"}):
            assert repo.transition_queue_item("q-e6", ("approved",), "processing")["state"] == "processing"
    finally: td.cleanup()


def test_shadow_missing_authority_would_reject_but_transition_unchanged():
    shadow = evaluate_shadow("q-e6", GROUP, None)
    assert shadow.would_allow is False and shadow.e5_decision == "UNKNOWN" and shadow.publication_blocked is False
    td, repo = repo_with()
    try:
        with patch.dict("os.environ", {"FB_GROUP_AUTHORITY_ROLLOUT_MODE": "SHADOW"}):
            assert repo.transition_queue_item("q-e6", ("approved",), "processing")["state"] == "processing"
    finally: td.cleanup()


def test_shadow_valid_zero_would_allow_without_blocking():
    shadow = evaluate_shadow("q-e6", GROUP, authority())
    assert shadow.would_allow is True and shadow.e5_decision == "ZERO_CONFIRMED" and shadow.publication_blocked is False


def test_shadow_stale_and_mismatch_would_reject_without_blocking():
    stale = authority(); stale["valid_until"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(); stale["receipt_ref"] = compute_receipt_ref(stale)
    mismatch = authority(); mismatch["target"] = "https://www.facebook.com/groups/999"; mismatch["receipt_ref"] = compute_receipt_ref(mismatch)
    for value in (stale, mismatch):
        shadow = evaluate_shadow("q-e6", GROUP, value)
        assert shadow.would_allow is False and shadow.publication_blocked is False


def test_enforce_valid_zero_allows_and_missing_rejects():
    td, repo = repo_with(authority())
    try:
        with patch.dict("os.environ", {"FB_GROUP_AUTHORITY_ROLLOUT_MODE": "ENFORCE"}):
            assert repo.transition_queue_item("q-e6", ("approved",), "processing")["state"] == "processing"
    finally: td.cleanup()
    td, repo = repo_with()
    try:
        with patch.dict("os.environ", {"FB_GROUP_AUTHORITY_ROLLOUT_MODE": "ENFORCE"}):
            assert repo.transition_queue_item("q-e6", ("approved",), "processing") is None
    finally: td.cleanup()


def test_non_group_unchanged_even_in_enforce():
    td, repo = repo_with(target=PAGE)
    try:
        with patch.dict("os.environ", {"FB_GROUP_AUTHORITY_ROLLOUT_MODE": "ENFORCE"}):
            assert repo.transition_queue_item("q-e6", ("approved",), "processing")["state"] == "processing"
    finally: td.cleanup()


def test_reconcile_unchanged_in_enforce():
    td, repo = repo_with()
    try:
        stored = repo.get_queue_item("q-e6"); stored["state"] = "unverified"; repo.save_queue([stored])
        with patch.dict("os.environ", {"FB_GROUP_AUTHORITY_ROLLOUT_MODE": "ENFORCE"}):
            assert repo.transition_queue_item("q-e6", ("unverified",), "reconciling")["state"] == "reconciling"
    finally: td.cleanup()

class ReachedRunner:
    def __init__(self): self.calls = 0
    def is_cancelled(self, job_id): return False
    def run_command_sync(self, *args, **kwargs):
        self.calls += 1
        return 1


def _executor_data(auth_marker="absent"):
    task = {"target": GROUP, "content": "Một nơi nghỉ tại Huế.\n\nKhông gian riêng tư.\n\nThuận tiện nghỉ ngơi.\n\nLiên hệ để biết thêm."}
    return {"accountId": "profile-1", "tasks": [task], "skipDuplicate24h": False}


def _run_executor(mode, persisted_authority, *, shadow_side_effect=None):
    from services.job_executor import execute_automation_task
    runner, lines = ReachedRunner(), []
    queue = {"id": "q-e6", "target": GROUP, "state": "approved", "certification_authority": persisted_authority}
    data = _executor_data()
    data["tasks"][0]["queueItemId"] = "q-e6"
    patches = [
        patch.dict("os.environ", {"FB_GROUP_AUTHORITY_ROLLOUT_MODE": mode}),
        patch("composer_guard.audit_final_content", return_value={"pass": True, "issues": []}),
        patch("content_studio.similarity_gate", return_value={"pass": True, "max_similarity": 0.0, "threshold": 0.82}),
        patch("repositories.campaign_repo.CampaignRepository.get_queue_item", return_value=queue),
        patch("repositories.campaign_repo.CampaignRepository.transition_queue_item", return_value=queue),
        patch("repositories.moderation_repo.ModerationRepository.requires_approval", return_value=False),
        patch("services.job_executor.workflow_start_task", return_value=None),
    ]
    if shadow_side_effect is not None:
        patches.append(patch("certification.rollout.evaluate_shadow", side_effect=shadow_side_effect))
    entered = []
    try:
        for ctx in patches: entered.append(ctx); ctx.start()
        result = execute_automation_task("e6-executor", "group", data, lines.append, runner)
    finally:
        for ctx in reversed(entered): ctx.stop()
    return result, runner, lines


def test_executor_shadow_missing_authority_would_reject_but_reaches_runner():
    _, runner, lines = _run_executor("SHADOW", None)
    assert runner.calls == 1
    assert any("[E6_SHADOW]" in line and '"would_allow": false' in line for line in lines)


def test_executor_shadow_stale_authority_would_reject_but_reaches_runner():
    stale = authority(); stale["valid_until"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(); stale["receipt_ref"] = compute_receipt_ref(stale)
    _, runner, lines = _run_executor("SHADOW", stale)
    assert runner.calls == 1
    assert any("[E6_SHADOW]" in line and '"would_allow": false' in line for line in lines)


def test_executor_shadow_evaluator_exception_records_error_and_reaches_runner():
    _, runner, lines = _run_executor("SHADOW", None, shadow_side_effect=RuntimeError("synthetic-shadow-failure"))
    assert runner.calls == 1
    assert any("[E6_SHADOW_ERROR]" in line and "publication unchanged" in line for line in lines)


def test_executor_shadow_valid_zero_would_allow_and_reaches_runner():
    _, runner, lines = _run_executor("SHADOW", authority())
    assert runner.calls == 1
    assert any("[E6_SHADOW]" in line and '"would_allow": true' in line for line in lines)


def test_executor_enforce_missing_authority_never_reaches_runner():
    _, runner, lines = _run_executor("ENFORCE", None)
    assert runner.calls == 0
    assert any("[E5_AUTHORITY_REJECT]" in line for line in lines)
