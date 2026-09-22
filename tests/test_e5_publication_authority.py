import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.usefixtures("e5_enforce_mode")

@pytest.fixture
def e5_enforce_mode():
    with patch.dict("os.environ", {"FB_GROUP_AUTHORITY_ROLLOUT_MODE": "ENFORCE"}):
        yield

from certification.publication_authority import (
    AUTHORITY_VERSION,
    compute_receipt_ref,
    validate_publication_authority,
)
from db import init_db
from repositories.campaign_repo import CampaignRepository


GROUP = "https://www.facebook.com/groups/123456789"
PAGE = "https://www.facebook.com/examplepage"


def receipt(target=GROUP, decision="ZERO_CONFIRMED", *, stale=False, candidate_id="123456789"):
    now = datetime.now(timezone.utc)
    observed = now - (timedelta(hours=2) if stale else timedelta(minutes=1))
    valid_until = now - timedelta(minutes=1) if stale else now + timedelta(minutes=10)
    value = {
        "version": AUTHORITY_VERSION,
        "candidate_id": candidate_id,
        "target": target,
        "decision": decision,
        "observed_at": observed.isoformat(),
        "valid_until": valid_until.isoformat(),
        "evidence_ref": "e4-evidence-001",
    }
    value["receipt_ref"] = compute_receipt_ref(value)
    return value


def queue_item(authority=None, target=GROUP):
    return {
        "id": "q-e5-1",
        "target": target,
        "content": "E5 authority test",
        "state": "approved",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "certification_authority": authority,
    }


@pytest.mark.parametrize("authority", [
    None,
    {"version": AUTHORITY_VERSION, "decision": "UNKNOWN"},
])
def test_approved_missing_or_unknown_certification_rejects_processing(authority):
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "e5.db"; init_db(db)
        repo = CampaignRepository(db_file=str(db))
        repo.insert_queue_item(queue_item(authority))
        assert repo.transition_queue_item("q-e5-1", ("approved",), "processing") is None
        assert repo.get_queue_item("q-e5-1")["state"] == "approved"


@pytest.mark.parametrize("decision", ["NO_ELIGIBLE_TARGET", "COUNT_CONFIRMED"])
def test_noneligible_decisions_reject_processing(decision):
    authority = receipt(decision=decision)
    if decision == "COUNT_CONFIRMED":
        authority["pending_count"] = 2
        authority["receipt_ref"] = compute_receipt_ref(authority)
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "e5.db"; init_db(db)
        repo = CampaignRepository(db_file=str(db))
        repo.insert_queue_item(queue_item(authority))
        assert repo.transition_queue_item("q-e5-1", ("approved",), "processing") is None


def test_target_mismatched_receipt_rejects_processing():
    authority = receipt(target="https://www.facebook.com/groups/999999999")
    ok, reason = validate_publication_authority(GROUP, authority)
    assert not ok and reason == "certification_target_mismatch"


def test_stale_receipt_rejects_processing():
    ok, reason = validate_publication_authority(GROUP, receipt(stale=True))
    assert not ok and reason == "certification_stale"


def test_candidate_id_must_match_group_target():
    authority = receipt(candidate_id="999999999")
    ok, reason = validate_publication_authority(GROUP, authority)
    assert not ok and reason == "certification_candidate_target_mismatch"


def test_reference_mismatch_rejects_processing():
    authority = receipt()
    authority["evidence_ref"] = "tampered"
    ok, reason = validate_publication_authority(GROUP, authority)
    assert not ok and reason == "certification_reference_mismatch"


def test_valid_zero_confirmed_allows_processing():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "e5.db"; init_db(db)
        repo = CampaignRepository(db_file=str(db))
        repo.insert_queue_item(queue_item(receipt()))
        claimed = repo.transition_queue_item("q-e5-1", ("approved",), "processing")
        assert claimed and claimed["state"] == "processing"


def test_non_group_processing_path_is_unchanged():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "e5.db"; init_db(db)
        repo = CampaignRepository(db_file=str(db))
        repo.insert_queue_item(queue_item(None, target=PAGE))
        claimed = repo.transition_queue_item("q-e5-1", ("approved",), "processing")
        assert claimed and claimed["state"] == "processing"


def test_authority_is_bound_once_by_repository_and_then_immutable():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "e5.db"; init_db(db)
        repo = CampaignRepository(db_file=str(db))
        item = queue_item(None); item["state"] = "draft"
        repo.insert_queue_item(item)
        authority = receipt()
        bound = repo.bind_certification_authority("q-e5-1", authority)
        assert bound and bound["certification_authority"]["receipt_ref"] == authority["receipt_ref"]
        assert repo.bind_certification_authority("q-e5-1", authority) is None
        assert repo.transition_queue_item("q-e5-1", ("draft",), "approved", {"certification_authority": receipt()}) is None
        assert repo.get_queue_item("q-e5-1")["state"] == "draft"


class FakeRunner:
    def __init__(self):
        self.calls = 0
    def is_cancelled(self, job_id):
        return False
    def run_command_sync(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("Facebook/process execution must not be reached")


def test_direct_executor_group_payload_without_certification_rejects_before_execution():
    from services.job_executor import execute_automation_task
    runner = FakeRunner()
    lines = []
    data = {
        "accountId": "profile-1",
        "tasks": [{"target": GROUP, "content": "Một nơi nghỉ tại Huế.\n\nKhông gian riêng tư.\n\nThuận tiện nghỉ ngơi.\n\nLiên hệ để biết thêm."}],
        "skipDuplicate24h": False,
    }
    with patch("composer_guard.audit_final_content", return_value={"pass": True, "issues": []}), \
         patch("content_studio.similarity_gate", return_value={"pass": True, "max_similarity": 0.0, "threshold": 0.82}):
        result = execute_automation_task("e5-direct", "group", data, lines.append, runner)
    assert result is False
    assert runner.calls == 0
    assert any("E5_AUTHORITY_REJECT" in line for line in lines)


def test_legacy_moderation_cannot_satisfy_pre_submit_authority():
    from services.job_executor import execute_automation_task
    runner = FakeRunner()
    lines = []
    data = {
        "accountId": "profile-1",
        "tasks": [{"target": GROUP, "content": "Một nơi nghỉ tại Huế.\n\nKhông gian riêng tư.\n\nThuận tiện nghỉ ngơi.\n\nLiên hệ để biết thêm."}],
        "skipDuplicate24h": False,
    }
    with patch("composer_guard.audit_final_content", return_value={"pass": True, "issues": []}), \
         patch("content_studio.similarity_gate", return_value={"pass": True, "max_similarity": 0.0, "threshold": 0.82}), \
         patch("repositories.moderation_repo.ModerationRepository.requires_approval", return_value=True):
        result = execute_automation_task("e5-moderation", "group", data, lines.append, runner)
    assert result is False
    assert runner.calls == 0
    assert any("certification_queue_identity_missing" in line for line in lines)


def test_direct_executor_cannot_self_assert_forged_valid_authority():
    from services.job_executor import execute_automation_task
    runner = FakeRunner()
    lines = []
    data = {
        "accountId": "profile-1",
        "tasks": [{"target": GROUP, "content": "Một nơi nghỉ tại Huế.\n\nKhông gian riêng tư.\n\nThuận tiện nghỉ ngơi.\n\nLiên hệ để biết thêm.", "certification_authority": receipt()}],
        "skipDuplicate24h": False,
    }
    with patch("composer_guard.audit_final_content", return_value={"pass": True, "issues": []}), \
         patch("content_studio.similarity_gate", return_value={"pass": True, "max_similarity": 0.0, "threshold": 0.82}):
        result = execute_automation_task("e5-forged", "group", data, lines.append, runner)
    assert result is False
    assert runner.calls == 0
    assert any("certification_queue_identity_missing" in line for line in lines)


def test_reconcile_transition_remains_unchanged_without_certification():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "e5.db"; init_db(db)
        repo = CampaignRepository(db_file=str(db))
        item = queue_item(None)
        item["state"] = "unverified"
        repo.insert_queue_item(item)
        claimed = repo.transition_queue_item("q-e5-1", ("unverified",), "reconciling")
        assert claimed and claimed["state"] == "reconciling"
