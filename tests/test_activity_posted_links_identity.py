from pathlib import Path
import tempfile

from db import init_db
from repositories.activity_repo import ActivityRepository


def _repo(tmpdir):
    db = Path(tmpdir) / "app.db"
    init_db(db)
    return ActivityRepository(str(db))


def test_unresolved_group_evidence_is_scoped_by_account_and_content():
    with tempfile.TemporaryDirectory() as td:
        repo = _repo(td)
        target = "https://facebook.com/groups/123"

        repo.record_posted_link(
            target, target, "content A", "submitted", "acc-old",
            "submitted", "group", "submitted_unverified",
        )
        repo.record_posted_link(
            target, target, "content B", "submitted", "acc-new",
            "submitted", "group", "submitted_unverified",
        )

        rows = repo.list_posted_links(limit=10)
        assert len(rows) == 2
        identities = {(r["account_id"], r["content"], r["publish_state"]) for r in rows}
        assert ("acc-old", "content A", "submitted_unverified") in identities
        assert ("acc-new", "content B", "submitted_unverified") in identities


def test_same_unresolved_identity_updates_owner_and_surfaces_as_recent(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        repo = _repo(td)
        target = "https://facebook.com/groups/123"

        repo.record_posted_link(
            target, target, "same content", "submitted", "acc-1",
            "submitted", "group", "submitted_unverified",
        )
        repo.record_posted_link(
            "https://facebook.com/groups/other",
            "https://facebook.com/groups/other/posts/999",
            "published content", "published", "acc-other",
            "published", "post", "published",
        )
        repo.record_posted_link(
            target, target, "same content", "pending", "acc-1",
            "pending", "group", "pending",
        )

        rows = repo.list_posted_links(limit=10)
        matching = [r for r in rows if r["target"] == target and r["content"] == "same content"]
        assert len(matching) == 1
        assert matching[0]["account_id"] == "acc-1"
        assert matching[0]["publish_state"] == "pending"
        assert rows[0]["created_at"] >= rows[-1]["created_at"]


def test_published_permalink_can_upgrade_matching_unresolved_identity():
    with tempfile.TemporaryDirectory() as td:
        repo = _repo(td)
        target = "https://facebook.com/groups/123"
        content = "same content"
        account = "acc-1"

        repo.record_posted_link(
            target, target, content, "submitted", account,
            "submitted", "group", "submitted_unverified",
        )
        repo.record_posted_link(
            target, target + "/posts/456", content, "published", account,
            "published", "post", "published",
        )

        rows = [r for r in repo.list_posted_links(limit=10) if r["target"] == target]
        assert len(rows) == 1
        assert rows[0]["account_id"] == account
        assert rows[0]["publish_state"] == "published"
        assert rows[0]["url"].endswith("/posts/456")
