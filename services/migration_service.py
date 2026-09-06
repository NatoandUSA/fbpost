"""Automated Migration Service.
Migrates legacy scattered JSON data to SQLite upon first startup,
preserves legacy JSON files in data/backups/legacy/, and generates
a structured migration report.
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from db import init_db
from paths import BASE_DIR, DATA_DIR, BACKUP_DIR
from repositories.account_repo import AccountRepository
from repositories.activity_repo import ActivityRepository
from repositories.campaign_repo import CampaignRepository
from repositories.group_repo import GroupRepository
from repositories.settings_repo import SettingsRepository
from repositories.vault_repo import VaultRepository


def load_legacy_json(file_path: Path, default_val: Any = None) -> Any:
    if not file_path.exists():
        return default_val
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default_val


def run_migration_if_needed(base_dir: Path = BASE_DIR) -> Dict[str, Any]:
    init_db()

    settings_repo = SettingsRepository()
    already_migrated = settings_repo.get_setting("migration_legacy_done", False)

    report: Dict[str, Any] = {
        "migrated_at": datetime.now().isoformat(),
        "already_migrated": bool(already_migrated),
        "counts": {},
        "errors": [],
    }

    if already_migrated:
        return report

    legacy_backup_dir = BACKUP_DIR / "legacy"
    legacy_backup_dir.mkdir(parents=True, exist_ok=True)

    # 1. Accounts
    accounts_file = base_dir / "accounts.json"
    accounts = load_legacy_json(accounts_file, [])
    if isinstance(accounts, list) and accounts:
        AccountRepository().save_accounts(accounts)
        report["counts"]["accounts"] = len(accounts)
        shutil.copy2(accounts_file, legacy_backup_dir / "accounts.json")

    # 2. Config / Settings
    config_file = base_dir / "config.json"
    config = load_legacy_json(config_file, {})
    if isinstance(config, dict) and config:
        settings_repo.save_config(config)
        report["counts"]["settings"] = len(config)
        shutil.copy2(config_file, legacy_backup_dir / "config.json")

    # 3. Groups Registry
    groups_file = base_dir / "group_registry.json"
    groups = load_legacy_json(groups_file, [])
    if isinstance(groups, list) and groups:
        GroupRepository().save_groups(groups)
        report["counts"]["groups"] = len(groups)
        shutil.copy2(groups_file, legacy_backup_dir / "group_registry.json")

    # 4. Joined Groups
    joined_file = base_dir / "joined_groups.json"
    joined = load_legacy_json(joined_file, [])
    if isinstance(joined, list) and joined:
        GroupRepository().save_joined_groups(joined)
        report["counts"]["joined_groups"] = len(joined)
        shutil.copy2(joined_file, legacy_backup_dir / "joined_groups.json")

    # 5. Campaigns
    campaigns_file = base_dir / "campaigns.json"
    campaigns = load_legacy_json(campaigns_file, [])
    if isinstance(campaigns, list) and campaigns:
        CampaignRepository().save_campaigns(campaigns)
        report["counts"]["campaigns"] = len(campaigns)
        shutil.copy2(campaigns_file, legacy_backup_dir / "campaigns.json")

    # 6. Publication Queue
    queue_file = base_dir / "publication_queue.json"
    queue = load_legacy_json(queue_file, [])
    if isinstance(queue, list) and queue:
        CampaignRepository().save_queue(queue)
        report["counts"]["publication_queue"] = len(queue)
        shutil.copy2(queue_file, legacy_backup_dir / "publication_queue.json")

    # 7. Manual Group Queue
    manual_queue_file = base_dir / "manual_group_queue.json"
    manual_queue = load_legacy_json(manual_queue_file, [])
    if isinstance(manual_queue, list) and manual_queue:
        CampaignRepository().save_manual_group_queue(manual_queue)
        report["counts"]["manual_group_queue"] = len(manual_queue)
        shutil.copy2(manual_queue_file, legacy_backup_dir / "manual_group_queue.json")

    # 8. Profile Activity
    activity_file = base_dir / "profile_activity.json"
    activities = load_legacy_json(activity_file, [])
    if isinstance(activities, list) and activities:
        ActivityRepository().save_activities(activities)
        report["counts"]["activity_log"] = len(activities)
        shutil.copy2(activity_file, legacy_backup_dir / "profile_activity.json")

    # 9. Posted Links
    posted_file = base_dir / "posted_links.json"
    posted_links = load_legacy_json(posted_file, [])
    if isinstance(posted_links, list) and posted_links:
        ActivityRepository().save_posted_links(posted_links)
        report["counts"]["posted_links"] = len(posted_links)
        shutil.copy2(posted_file, legacy_backup_dir / "posted_links.json")

    # 10. Vault Entries
    vault_file = base_dir / "account_vault.json"
    vault = load_legacy_json(vault_file, [])
    if isinstance(vault, list) and vault:
        VaultRepository().save_entries(vault)
        report["counts"]["vault_entries"] = len(vault)
        shutil.copy2(vault_file, legacy_backup_dir / "account_vault.json")

    settings_repo.set_setting("migration_legacy_done", True)

    report_path = DATA_DIR / "migration-report.json"
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    except Exception as e:
        report["errors"].append(str(e))

    return report
