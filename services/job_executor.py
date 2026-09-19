"""Job Executor Service.
Contains execution logic for all automation commands:
auth, interact, scrape, join-group, create-page, comment, group, page, thread.
Integrates with ProcessRunner for process tree execution and cancellation.
"""

import os
import json
import sys
import re
import time
import random
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from paths import BASE_DIR, DATA_DIR, UPLOAD_DIR, get_version
from utils import (
    load_accounts as utils_load_accounts,
    is_recently_posted,
    normalize_target_url,
    pick_random_photos,
)
from services.process_runner import ProcessRunner
from repositories.job_repo import JobRepository
from repositories.settings_repo import SettingsRepository
from repositories.activity_repo import ActivityRepository
from repositories.reconcile_repo import ReconcileRepository
from repositories.moderation_repo import ModerationRepository
from services.workflow_runtime import start_task as workflow_start_task, finish_task as workflow_finish_task, add_event as workflow_add_event

DUPLICATE_WINDOW_HOURS = (4, 8, 12, 16, 24)
SUBMIT_UNCERTAIN_CODES = frozenset(("POST_SUBMITTED_UNVERIFIED", "SUBMIT_TRIGGERED_UNVERIFIED"))
POST_PENDING_CODES = frozenset(("POST_PENDING", "RECONCILE_PENDING"))


def is_submit_uncertain(result: Dict[str, Any]) -> bool:
    """True only when Facebook submit was triggered but evidence is incomplete."""
    return (
        str((result or {}).get("state") or "") == "submitted_unverified"
        or str((result or {}).get("code") or "") in SUBMIT_UNCERTAIN_CODES
    )


def is_post_pending(result: Dict[str, Any]) -> bool:
    """Exclude group-membership pending from the post pending lifecycle."""
    return (
        str((result or {}).get("state") or "") == "pending"
        and str((result or {}).get("code") or "") in POST_PENDING_CODES
    )


def resolve_duplicate_window_hours(value) -> int:
    try:
        hours = int(value)
    except (TypeError, ValueError):
        return 24
    return hours if hours in DUPLICATE_WINDOW_HOURS else 24


def load_config():
    try:
        cfg = SettingsRepository().get_config()
        if cfg:
            return cfg
    except Exception:
        pass
    config_file = DATA_DIR / "config.json"
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            value = json.load(f)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}

def load_accounts():
    return utils_load_accounts()

def record_profile_activity(profile_id, action, target="", content="", outcome="finished"):
    try:
        ActivityRepository().record_activity(profile_id or "default-session", action, target, content, outcome)
    except Exception:
        pass

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def is_uploaded_image(value: str) -> bool:
    try:
        return Path(value).resolve().is_relative_to(UPLOAD_DIR)
    except (OSError, ValueError):
        return False


def _select_rotation_pool(all_accs, data):
    """Resolve an explicit profile preset in caller order, else all saved accounts."""
    requested = [str(x) for x in (data.get("accountIds") or []) if str(x).strip()]
    if requested:
        by_id = {str(a.get("id")): a for a in all_accs if a.get("id")}
        return [by_id[profile_id] for profile_id in requested if profile_id in by_id]
    supplied = data.get("accounts") or []
    if supplied:
        return [a for a in supplied if isinstance(a, dict) and a.get("id")]
    return [a for a in all_accs if a.get("id")]


def _resume_rotation_after_last_post(accounts_pool):
    """Persist fair round-robin implicitly from the last profile that actually posted."""
    if len(accounts_pool) < 2:
        return accounts_pool
    try:
        rows = ActivityRepository().list_posted_links(limit=100)
        last_id = next((str(r.get("account_id")) for r in rows if r.get("account_id")), "")
        ids = [str(a.get("id")) for a in accounts_pool]
        if last_id in ids:
            start = (ids.index(last_id) + 1) % len(accounts_pool)
            return accounts_pool[start:] + accounts_pool[:start]
    except Exception:
        pass
    return accounts_pool


def execute_automation_task(
    job_id: str,
    cmd: str,
    data: Dict[str, Any],
    on_line: Callable[[str], None],
    process_runner: ProcessRunner,
    job_repo: Optional[JobRepository] = None,
) -> bool:
    """Execute an automation command and return True if successful, False otherwise."""
    cfg = load_config()
    on_line(f"RUNTIME_IDENTITY:v{get_version()}|root={BASE_DIR.resolve()}|main={(BASE_DIR / 'main.py').resolve()}\n")
    account_id = data.get("accountId")
    reconcile_record_id = str(data.get("reconcileRecordId") or "").strip()
    gpm_api = data.get("gpmApiUrl") or cfg.get("gpm_api_url", "http://127.0.0.1:19995")

    rotate_accounts = data.get("rotateAccounts", False)
    if account_id == "__rotate__":
        rotate_accounts = True
        account_id = None

    delay_min = max(5, int(data.get("delayMin") or cfg.get("delay_min", 300)))
    delay_max = max(delay_min, int(data.get("delayMax") or cfg.get("delay_max", 600)))

    feeling = data.get("feeling", False)
    checkin = data.get("checkin", False)
    auto_spin = data.get("autoSpin", False)
    raw_gemini_key = data.get("geminiApiKeys") or data.get("geminiApiKey") or data.get("gemini_api_key") or ""
    if isinstance(raw_gemini_key, list):
        raw_gemini_key = "\n".join(str(item) for item in raw_gemini_key)
    raw_gemini_key = str(raw_gemini_key).strip()
    if not raw_gemini_key or raw_gemini_key.startswith("***REDACTED") or raw_gemini_key.endswith("***"):
        gemini_api_key = cfg.get("gemini_api_keys") or cfg.get("gemini_api_key") or ""
    else:
        gemini_api_key = raw_gemini_key
    raw_photo_folder = data.get("photoFolder", "")
    # Older/newer clients may send a single folder or a list. Normalize at the
    # executor boundary so UI payload shape can never crash a job with .strip().
    if isinstance(raw_photo_folder, (list, tuple, set)):
        legacy_photo_folders = [str(p).strip() for p in raw_photo_folder if str(p).strip()]
        photo_folder = legacy_photo_folders[0] if legacy_photo_folders else ""
    else:
        photo_folder = str(raw_photo_folder or "").strip()
        legacy_photo_folders = []
    photo_folders = [str(p).strip() for p in (data.get("photoFolders") or []) if str(p).strip()]
    if not photo_folders and legacy_photo_folders:
        photo_folders = legacy_photo_folders
    if not photo_folders and photo_folder:
        photo_folders = [photo_folder]
    photo_count_mode = data.get("photoCountMode", "2-4")
    skip_duplicate = data.get("skipDuplicate24h", True)  # Legacy key retained for older clients.
    skip_duplicate_hours = resolve_duplicate_window_hours(data.get("skipDuplicateHours", 24))
    clean_exif = data.get("cleanExif", True)
    anti_hash_text = data.get("antiHashText", False)
    brand_key = str(data.get("brandKey") or "").strip().lower()
    # Final-content contract: selecting a Project always requires its canonical signature.
    include_signature = bool(brand_key)
    safe_signature = bool(data.get("safeSignature", cfg.get("safe_signature", True)))
    auto_first_comment = bool(data.get("autoFirstComment", cfg.get("auto_first_comment", False)))

    auto_join_groups = data.get("autoJoinGroups", cfg.get("auto_join_groups", False))
    group_keywords = str(data.get("groupKeywords") or cfg.get("group_keywords", "Homestay Huế, Du lịch Huế")).strip()

    def build_cmd_for_account(acc_id):
        cmd_list = [sys.executable, str((BASE_DIR / "main.py").resolve())]
        if acc_id and str(acc_id).strip() not in ("__rotate__", "None", ""):
            cmd_list.extend(["--account-id", str(acc_id)])
        if gpm_api:
            cmd_list.extend(["--gpm-api", gpm_api])
        return cmd_list

    def check_cancel() -> bool:
        return process_runner.is_cancelled(job_id)

    def sleep_with_cancel(seconds: int) -> bool:
        for sec in range(seconds, 0, -1):
            if check_cancel():
                return False
            if sec == seconds or sec % 15 == 0 or sec <= 5:
                s_m = sec // 60
                s_s = sec % 60
                on_line(f"... còn {s_m}p {s_s}s ({sec}s)\n")
            time.sleep(1)
        return True

    # Load accounts pool for round-robin rotation
    accounts_pool = []
    if rotate_accounts and cmd != "auth":
        try:
            all_accs = load_accounts()
            accounts_pool = _resume_rotation_after_last_post(_select_rotation_pool(all_accs, data))
        except Exception:
            accounts_pool = []

        if not accounts_pool:
            on_line("⚠️ [Cảnh báo vận hành] Bạn đã bật chế độ Luân phiên nhưng chưa có tài khoản Facebook nào trong danh sách 'Tài khoản đã lưu'.\n")
            on_line("💡 Vui lòng nhấn nút '📥 Nhập Nick FB từ GPM' để chọn lọc các nick Facebook mong muốn trước khi bật luân phiên.\n")
            on_line("RUN_RESULT:failed\n")
            return False

    # 1. AUTH COMMAND
    if cmd == "auth":
        target_auth_id = account_id
        if not target_auth_id or str(target_auth_id).strip() in ("__rotate__", "None", ""):
            all_accs = load_accounts()
            target_auth_id = all_accs[0].get("id") if all_accs else None
        full_cmd = build_cmd_for_account(target_auth_id) + ["auth"]
        ret = process_runner.run_command_sync(full_cmd, job_id=job_id, on_line=on_line, cwd=str(BASE_DIR))
        outcome = "finished" if ret == 0 else "failed"
        on_line(f"RUN_RESULT:{outcome}\n")
        record_profile_activity(target_auth_id, "auth", outcome=outcome)
        return ret == 0

    # 2. INTERACT COMMAND
    if cmd == "interact":
        limit = max(1, min(int(data.get("limit", 5)), 50))
        comments = data.get("comments", "")
        target_accs = accounts_pool if (rotate_accounts and accounts_pool) else ([{"id": account_id}] if account_id else [{"id": None}])
        total_accs = len(target_accs)
        interact_failed = False
        interact_success_count = 0
        interact_partial_count = 0
        interact_no_action_count = 0
        interact_fail_count = 0

        if job_repo:
            job_repo.update_job(job_id, progress_total=total_accs)

        for acc_idx, acc_item in enumerate(target_accs):
            if check_cancel():
                on_line("⚠️ [JobExecutor] Tiến trình bị hủy bỏ bởi người dùng.\n")
                return False

            cur_id = acc_item.get("id") if isinstance(acc_item, dict) else acc_item
            acc_name = acc_item.get("name", cur_id) if isinstance(acc_item, dict) else cur_id

            if total_accs > 1:
                on_line(f"\n🔄 [Luân phiên Nuôi nick] Khởi chạy Profile {acc_idx+1}/{total_accs}: {acc_name}\n")

            cur_comments = comments
            if auto_spin and comments:
                try:
                    from ai_spinner import generate_interact_comments
                    cur_comments = generate_interact_comments(comments, gemini_api_key)
                    on_line(f"🤖 [AI Spin] Đã tạo danh sách bình luận nuôi nick mới cho {acc_name}!\n")
                except Exception:
                    cur_comments = comments

            full_cmd = build_cmd_for_account(cur_id) + ["interact", "--limit", str(limit)]
            if cur_comments:
                full_cmd.extend(["--comments", cur_comments])

            interact_result = {}
            def _capture_interact_line(line):
                on_line(line)
                clean = (line or "").strip()
                if clean.startswith("ACTION_RESULT:"):
                    try:
                        interact_result.update(json.loads(clean[len("ACTION_RESULT:"):]))
                    except Exception:
                        pass

            ret = process_runner.run_command_sync(full_cmd, job_id=job_id, on_line=_capture_interact_line, cwd=str(BASE_DIR))
            state = str(interact_result.get("state") or "")
            code = str(interact_result.get("code") or "")
            if state == "completed" or code == "INTERACT_CONFIRMED":
                interact_success_count += 1
                outcome = "completed"
            elif state == "partial" or code == "INTERACT_PARTIAL":
                interact_partial_count += 1
                outcome = "partial"
            elif state == "no_action" or code == "INTERACT_NO_ACTION":
                interact_no_action_count += 1
                interact_failed = True
                outcome = "no_action"
            else:
                interact_fail_count += 1
                interact_failed = True
                outcome = "failed"
            record_profile_activity(cur_id, "interact", target="newsfeed", content=cur_comments, outcome=outcome)

            if job_repo:
                job_repo.update_job(job_id, progress_current=acc_idx + 1)

            if acc_idx < total_accs - 1:
                delay = 5 if ret != 0 else random.randint(delay_min, delay_max)
                mins = delay // 60
                secs = delay % 60
                if ret != 0:
                    on_line(f"\n⚠️ Profile {acc_name} lỗi hạ tầng/thực thi. Nghỉ nhanh {delay}s trước profile tiếp theo...\n")
                else:
                    on_line(f"\n⏳ [Giãn cách] Nghỉ {delay}s ({mins}p {secs}s) trước khi đổi sang Profile tiếp theo...\n")
                if not sleep_with_cancel(delay):
                    return False

        on_line(f"📊 [Interact Summary] Đạt mục tiêu: {interact_success_count} · Một phần: {interact_partial_count} · 0 hành động: {interact_no_action_count} · Lỗi runtime: {interact_fail_count} · Tổng: {total_accs}.\n")
        on_line(f"RUN_RESULT:{'failed' if interact_failed else 'finished'}\n")
        return not interact_failed

    # 3. SCRAPE COMMAND
    if cmd == "scrape":
        target_url = data.get("target", "").strip()
        limit = max(1, min(int(data.get("limit", 50)), 200))
        if not target_url:
            on_line("Error: No target URL provided for scraping.\n")
            return False
        full_cmd = build_cmd_for_account(account_id) + ["scrape", target_url, "--limit", str(limit)]
        ret = process_runner.run_command_sync(full_cmd, job_id=job_id, on_line=on_line, cwd=str(BASE_DIR))
        outcome = "finished" if ret == 0 else "failed"
        on_line(f"RUN_RESULT:{outcome}\n")
        record_profile_activity(account_id, "scrape", target=target_url, outcome=outcome)
        return ret == 0

    # 4. JOIN-GROUP COMMAND
    if cmd == "join-group":
        mode = data.get("mode", "keywords")
        urls = data.get("urls", "").strip()
        raw_keywords = data.get("keywords") or data.get("groupKeywords") or group_keywords or "Homestay Huế, Du lịch Huế"
        limit = min(max(1, int(data.get("limit", 2))), 2)
        profile_delay_min = max(0, int(data.get("profileDelayMin", 60) or 60))
        profile_delay_max = max(profile_delay_min, int(data.get("profileDelayMax", 180) or 180))
        try: max_profiles=max(0,int(data.get("maxProfiles",0) or 0))
        except (TypeError,ValueError): max_profiles=0

        # Chế độ tương tác feed & delay
        interact_feed = data.get("interactFeed", False)
        feed_flag = ["--interact-feed"] if interact_feed else ["--no-interact-feed"]
        rules_flag = ["--auto-rules"] if data.get("autoRules", False) else []
        delay_args = ["--delay-min", "60", "--delay-max", "180"]
        if gemini_api_key:
            delay_args.extend(["--gemini-key", str(gemini_api_key)])

        # URL Mode: mỗi profile nhận toàn bộ danh sách và dừng sau tối đa limit nhóm mới.
        if mode == "urls" and urls:
            urls_list = [u.strip() for u in re.split(r"[\r\n,;]+", urls) if u.strip()]
            if not urls_list:
                on_line("Error: Danh sách URL nhóm đang trống.\n")
                on_line("RUN_RESULT:failed\n")
                return False
            on_line(f"🔗 Bắt đầu xử lý {len(urls_list)} link nhóm cho từng profile; mục tiêu {limit} JOINED đã xác minh/profile.\n")
            active_pool = accounts_pool if (rotate_accounts and accounts_pool) else []
            if not active_pool:
                target_id = account_id
                if not target_id or str(target_id).strip() in ("__rotate__", "None", ""):
                    all_accs = load_accounts()
                    target_id = all_accs[0].get("id") if all_accs else None
                active_pool = [{"id": target_id, "name": target_id or "default"}]
            if max_profiles > 0: active_pool=active_pool[:max_profiles]
            total_profiles=len(active_pool)
            on_line(f"👥 Phạm vi Join: {total_profiles} profile · mục tiêu {limit} JOINED/profile.\n")
            join_failed=False
            join_success = 0
            if job_repo:
                job_repo.update_job(job_id, progress_total=total_profiles)
            shared_targets = ",".join(urls_list)
            for idx, acc in enumerate(active_pool):
                if check_cancel():
                    return False
                acc_id = acc.get("id")
                acc_name = acc.get("name", acc_id)
                wf_task_id = workflow_start_task(
                    job_id=job_id,
                    action="join-group",
                    profile_id=acc_id,
                    target_url=shared_targets[:300],
                    metadata={"mode": "urls", "target_joined": limit, "profile_name": acc_name}
                )
                on_line(f"\n========== [Profile {idx + 1}/{total_profiles}: {acc_name} | mục tiêu JOINED {limit}] ==========\n")
                full_cmd = (
                    build_cmd_for_account(acc_id)
                    + ["join-group", "--keywords", shared_targets, "--limit", str(limit)]
                    + feed_flag + rules_flag + delay_args
                )
                join_summary_res = {}
                def _capture_join_line(line):
                    on_line(line)
                    clean = (line or "").strip()
                    if clean.startswith("JOIN_RESULT:"):
                        try:
                            join_summary_res.update(json.loads(clean[len("JOIN_RESULT:"):]))
                        except Exception:
                            pass
                ret = process_runner.run_command_sync(full_cmd, job_id=job_id, on_line=_capture_join_line, cwd=str(BASE_DIR))
                outcome = "finished" if ret == 0 else "failed"
                if ret == 0:
                    join_success += 1
                else:
                    join_failed = True
                confirmed = int(join_summary_res.get("joined_confirmed", 0))
                pending = int(join_summary_res.get("pending_confirmed", 0))
                uncertain = int(join_summary_res.get("unverified_attempts", 0))
                quota_met = bool(join_summary_res.get("quota_met")) or confirmed >= limit
                if quota_met:
                    workflow_finish_task(wf_task_id, state="completed", verification_status="JOIN_QUOTA_CONFIRMED", result_url=shared_targets[:300])
                elif pending > 0 and uncertain == 0:
                    workflow_finish_task(wf_task_id, state="pending", phase="VERIFYING", verification_status="REQUEST_PENDING", result_url=shared_targets[:300], error_code="JOIN_QUOTA_PARTIAL", error_message=f"Confirmed JOINED {confirmed}/{limit}; {pending} request(s) pending approval.")
                elif uncertain > 0:
                    workflow_finish_task(wf_task_id, state="unverified", phase="VERIFYING", verification_status="REQUEST_UNVERIFIED", result_url=shared_targets[:300], error_code="JOIN_CLICKED_UNVERIFIED", error_message=f"Confirmed JOINED {confirmed}/{limit}; some join actions remain unverified.")
                else:
                    workflow_finish_task(wf_task_id, state="failed", verification_status="JOIN_QUOTA_PARTIAL", error_code="JOIN_QUOTA_PARTIAL", error_message=f"Confirmed JOINED {confirmed}/{limit}; no eligible candidate remained.")
                record_profile_activity(acc_id, "join-group", target=shared_targets[:100], outcome=outcome)
                if job_repo:
                    job_repo.update_job(job_id, progress_current=idx + 1)
                if idx < total_profiles - 1:
                    next_name = active_pool[idx + 1].get("name", "profile tiếp theo")
                    rot_delay = 5 if ret != 0 else random.randint(profile_delay_min, profile_delay_max)
                    if ret != 0:
                        on_line(f"\n⚠️ Profile {acc_name} chưa xác nhận được nhóm mới. Nghỉ {rot_delay}s trước {next_name}.\n")
                    else:
                        on_line(f"\n⏳ [Giãn cách] Hoàn tất {acc_name}. Nghỉ {rot_delay}s trước {next_name}.\n")
                    if not sleep_with_cancel(rot_delay):
                        return False
            on_line(f"📊 [Join Summary] Profiles hoàn tất: {join_success}/{total_profiles} · Có lỗi: {total_profiles - join_success}/{total_profiles}.\n")
            on_line(f"RUN_RESULT:{'failed' if join_failed else 'finished'}\n")
            return not join_failed

        # Keyword Mode
        else:
            kw_list = [k.strip() for k in re.split(r"[\r\n,;]+", str(raw_keywords)) if k.strip() and k.strip() != "None"]
            input_targets = ", ".join(kw_list) if kw_list else "Homestay Huế, Du lịch Huế"
            on_line(f"🔍 Bắt đầu tìm kiếm & tự động xin gia nhập nhóm Facebook theo từ khóa: '{input_targets}'...\n")
            on_line(f"🛡️ [Quota] Mỗi profile tiếp tục xử lý cho đến khi đạt {limit} JOINED đã xác minh hoặc hết candidate.\n")

            if rotate_accounts and accounts_pool:
                scoped_pool=accounts_pool[:max_profiles] if max_profiles > 0 else accounts_pool
                total_acc=len(scoped_pool)
                on_line(f"👥 Phạm vi Join: {total_acc} profile · mục tiêu {limit} JOINED/profile.\n")
                join_failed=False
                if job_repo:
                    job_repo.update_job(job_id, progress_total=total_acc)
                for idx, acc in enumerate(scoped_pool):
                    if check_cancel():
                        return False
                    acc_id = acc.get("id")
                    acc_name = acc.get("name", acc_id)
                    wf_task_id = workflow_start_task(
                        job_id=job_id,
                        action="join-group",
                        profile_id=acc_id,
                        target_url=str(input_targets)[:300],
                        metadata={"mode": "keywords", "target_joined": limit, "profile_name": acc_name}
                    )
                    on_line(f"\n========== [Profile {idx+1}/{total_acc}: {acc_name} | mục tiêu JOINED {limit}] ==========\n")
                    full_cmd = (
                        build_cmd_for_account(acc_id)
                        + ["join-group", "--keywords", str(input_targets), "--limit", str(limit)]
                        + feed_flag
                        + rules_flag
                        + delay_args
                    )
                    join_kw_res = {}
                    def _capture_kw_join_line(line):
                        on_line(line)
                        clean = (line or "").strip()
                        if clean.startswith("JOIN_RESULT:"):
                            try:
                                join_kw_res.update(json.loads(clean[len("JOIN_RESULT:"):]))
                            except Exception:
                                pass
                    ret = process_runner.run_command_sync(full_cmd, job_id=job_id, on_line=_capture_kw_join_line, cwd=str(BASE_DIR))
                    outcome = "finished" if ret == 0 else "failed"
                    if ret != 0:
                        join_failed = True
                    confirmed = int(join_kw_res.get("joined_confirmed", 0))
                    pending = int(join_kw_res.get("pending_confirmed", 0))
                    uncertain = int(join_kw_res.get("unverified_attempts", 0))
                    quota_met = bool(join_kw_res.get("quota_met")) or confirmed >= limit
                    if quota_met:
                        workflow_finish_task(wf_task_id, state="completed", verification_status="JOIN_QUOTA_CONFIRMED", result_url=str(input_targets)[:300])
                    elif pending > 0 and uncertain == 0:
                        workflow_finish_task(wf_task_id, state="pending", phase="VERIFYING", verification_status="REQUEST_PENDING", result_url=str(input_targets)[:300], error_code="JOIN_QUOTA_PARTIAL", error_message=f"Confirmed JOINED {confirmed}/{limit}; {pending} request(s) pending approval.")
                    elif uncertain > 0:
                        workflow_finish_task(wf_task_id, state="unverified", phase="VERIFYING", verification_status="REQUEST_UNVERIFIED", result_url=str(input_targets)[:300], error_code="JOIN_CLICKED_UNVERIFIED", error_message=f"Confirmed JOINED {confirmed}/{limit}; some join actions remain unverified.")
                    else:
                        workflow_finish_task(wf_task_id, state="failed", verification_status="JOIN_QUOTA_PARTIAL", error_code="JOIN_QUOTA_PARTIAL", error_message=f"Confirmed JOINED {confirmed}/{limit}; no eligible candidate remained.")
                    record_profile_activity(acc_id, "join-group", target=str(input_targets)[:100], outcome=outcome)
                    if job_repo:
                        job_repo.update_job(job_id, progress_current=idx + 1)
                    if idx < total_acc - 1:
                        next_acc = scoped_pool[idx + 1].get("name", "profile tiếp theo")
                        if ret != 0:
                            rot_delay = 5
                            on_line(f"\n⚠️ Profile {acc_name} gặp sự cố. Nghỉ nhanh {rot_delay}s trước khi chuyển sang {next_acc}...\n")
                        else:
                            rot_delay = random.randint(profile_delay_min, profile_delay_max)
                            on_line(f"\n⏳ [Giãn cách] Đã hoàn tất profile {acc_name}. Nghỉ {rot_delay}s ({rot_delay//60} phút {rot_delay%60}s) trước khi xoay sang {next_acc}...\n")
                        if not sleep_with_cancel(rot_delay):
                            return False
                on_line(f"RUN_RESULT:{'failed' if join_failed else 'finished'}\n")
                return not join_failed
            else:
                target_id = account_id
                if not target_id or str(target_id).strip() in ("__rotate__", "None", ""):
                    all_accs = load_accounts()
                    target_id = all_accs[0].get("id") if all_accs else None
                wf_task_id = workflow_start_task(
                    job_id=job_id,
                    action="join-group",
                    profile_id=target_id,
                    target_url=str(input_targets)[:300],
                    metadata={"mode": "keywords", "target_joined": limit}
                )
                full_cmd = (
                    build_cmd_for_account(target_id)
                    + ["join-group", "--keywords", str(input_targets), "--limit", str(limit)]
                    + feed_flag
                    + rules_flag
                    + delay_args
                )
                join_single_res = {}
                def _capture_single_join_line(line):
                    on_line(line)
                    clean = (line or "").strip()
                    if clean.startswith("JOIN_RESULT:"):
                        try:
                            join_single_res.update(json.loads(clean[len("JOIN_RESULT:"):]))
                        except Exception:
                            pass
                ret = process_runner.run_command_sync(full_cmd, job_id=job_id, on_line=_capture_single_join_line, cwd=str(BASE_DIR))
                outcome = "finished" if ret == 0 else "failed"
                confirmed = int(join_single_res.get("joined_confirmed", 0))
                pending = int(join_single_res.get("pending_confirmed", 0))
                uncertain = int(join_single_res.get("unverified_attempts", 0))
                quota_met = bool(join_single_res.get("quota_met")) or confirmed >= limit
                if quota_met:
                    workflow_finish_task(wf_task_id, state="completed", verification_status="JOIN_QUOTA_CONFIRMED", result_url=str(input_targets)[:300])
                elif pending > 0 and uncertain == 0:
                    workflow_finish_task(wf_task_id, state="pending", phase="VERIFYING", verification_status="REQUEST_PENDING", result_url=str(input_targets)[:300], error_code="JOIN_QUOTA_PARTIAL", error_message=f"Confirmed JOINED {confirmed}/{limit}; {pending} request(s) pending approval.")
                elif uncertain > 0:
                    workflow_finish_task(wf_task_id, state="unverified", phase="VERIFYING", verification_status="REQUEST_UNVERIFIED", result_url=str(input_targets)[:300], error_code="JOIN_CLICKED_UNVERIFIED", error_message=f"Confirmed JOINED {confirmed}/{limit}; some join actions remain unverified.")
                else:
                    workflow_finish_task(wf_task_id, state="failed", verification_status="JOIN_QUOTA_PARTIAL", error_code="JOIN_QUOTA_PARTIAL", error_message=f"Confirmed JOINED {confirmed}/{limit}; no eligible candidate remained.")
                on_line(f"RUN_RESULT:{outcome}\n")
                record_profile_activity(target_id, "join-group", target=str(input_targets)[:100], outcome=outcome)
                return ret == 0

    # 5. CREATE-PAGE COMMAND
    if cmd == "create-page":
        page_name = data.get("name") or data.get("pageName") or data.get("page_name")
        category = data.get("category") or "Blogger"
        bio = data.get("bio") or ""
        avatar = data.get("avatar") or None
        cover = data.get("cover") or None

        if not page_name:
            on_line("Error: Chưa cung cấp tên Fanpage cần tạo.\n")
            on_line("RUN_RESULT:failed\n")
            return False

        target_id = account_id
        if not target_id or str(target_id).strip() in ("__rotate__", "None", ""):
            all_accs = load_accounts()
            target_id = all_accs[0].get("id") if all_accs else None

        on_line(f"🚩 Bắt đầu tự động tạo Fanpage cá nhân: '{page_name}' (Hạng mục: {category})...\n")
        full_cmd = build_cmd_for_account(target_id) + ["create-page", "--name", str(page_name), "--category", str(category)]
        if bio:
            full_cmd.extend(["--bio", str(bio)])
        if avatar:
            full_cmd.extend(["--avatar", str(avatar)])
        if cover:
            full_cmd.extend(["--cover", str(cover)])

        ret = process_runner.run_command_sync(full_cmd, job_id=job_id, on_line=on_line, cwd=str(BASE_DIR))
        outcome = "finished" if ret == 0 else "failed"
        on_line(f"RUN_RESULT:{outcome}\n")
        record_profile_activity(target_id, "create-page", target=page_name, outcome=outcome)
        return ret == 0

    # 6. COMMENT COMMAND
    if cmd == "comment":
        like_post = data.get("likePost", False)
        comment_tasks = data.get("tasks", [])
        if not comment_tasks:
            targets = data.get("targets", [])
            content = data.get("content", "")
            comment_tasks = [{"target": t, "content": content} for t in targets]

        if not comment_tasks:
            on_line("Error: Chưa có danh sách link bài viết hoặc nội dung comment.\n")
            return False

        total = len(comment_tasks)
        batch_failed = False
        comment_verified_count = 0
        comment_unverified_count = 0
        comment_failed_count = 0
        if job_repo:
            job_repo.update_job(job_id, progress_total=total)

        for i, task in enumerate(comment_tasks):
            if check_cancel():
                return False
            target_url = task.get("target", "").strip()
            comment_text = task.get("content", "").strip()
            if not target_url or not comment_text:
                batch_failed = True
                on_line(f"Error: Comment task {i+1} thiếu URL hoặc nội dung.\n")
                if job_repo:
                    job_repo.update_job(job_id, progress_current=i + 1)
                continue

            if rotate_accounts and accounts_pool:
                curr_acc = accounts_pool[i % len(accounts_pool)]
                curr_acc_id = curr_acc.get("id")
                on_line(f"🔄 [Luân phiên Profile GPM] Sử dụng: {curr_acc.get('name', curr_acc_id)} cho bình luận {i+1}/{total}\n")
            else:
                curr_acc_id = account_id

            task_comment = comment_text
            if auto_spin:
                try:
                    from ai_spinner import spin_comment
                    task_comment = spin_comment(comment_text, gemini_api_key)
                    on_line(f"🤖 [AI Comment Spinner] Đã tạo câu bình luận mới cho bài viết {i+1}/{total}!\n")
                except Exception:
                    task_comment = comment_text

            wf_task_id = workflow_start_task(
                job_id=job_id,
                action="comment",
                profile_id=curr_acc_id,
                target_url=target_url,
                metadata={"like_post": like_post, "comment_preview": task_comment[:80]}
            )
            on_line(f"\n========== [Bài viết {i+1}/{total}] ==========\n")
            on_line(f"Đang mở bài viết: {target_url}\n")

            full_cmd = build_cmd_for_account(curr_acc_id) + ["comment", target_url, task_comment]
            if like_post:
                full_cmd.append("--like")
            if not anti_hash_text:
                full_cmd.append("--no-anti-hash-text")

            structured_comment_res = {}
            def _capture_comment_line(line):
                on_line(line)
                clean = (line or "").strip()
                if clean.startswith("ACTION_RESULT:"):
                    try:
                        structured_comment_res.update(json.loads(clean[len("ACTION_RESULT:"):]))
                    except Exception:
                        pass

            ret = process_runner.run_command_sync(full_cmd, job_id=job_id, on_line=_capture_comment_line, cwd=str(BASE_DIR))
            comment_state = str(structured_comment_res.get("state") or "")
            comment_code = str(structured_comment_res.get("code") or "")
            if comment_state == "commented" and ret == 0:
                comment_verified_count += 1; outcome = "commented"
                workflow_finish_task(wf_task_id, state="completed", submission_status="SUBMIT_CONFIRMED", verification_status="COMMENT_VERIFIED", result_url=structured_comment_res.get("result_url") or target_url)
            elif comment_state == "unverified" or comment_code in {"COMMENT_UNVERIFIED", "SUBMIT_UNVERIFIED"}:
                comment_unverified_count += 1; outcome = "unverified"; batch_failed = True
                workflow_finish_task(wf_task_id, state="unverified", phase="VERIFYING", submission_status="SUBMIT_CONFIRMED", verification_status="COMMENT_UNVERIFIED", result_url=target_url, error_code=comment_code or "COMMENT_UNVERIFIED", error_message=structured_comment_res.get("message") or "Comment submitted but not verified.")
            else:
                comment_failed_count += 1; outcome = "failed_before_submit"; batch_failed = True
                workflow_finish_task(wf_task_id, state="failed", verification_status="FAILED", error_code=comment_code or "COMMENT_FAILED", error_message=structured_comment_res.get("message") or "Comment failed before verified submission.")
            record_profile_activity(curr_acc_id, "comment", target=target_url, content=task_comment, outcome=outcome)

            if job_repo:
                job_repo.update_job(job_id, progress_current=i + 1)

            if i < total - 1:
                delay = random.randint(delay_min, delay_max)
                mins = delay // 60
                secs = delay % 60
                on_line(f"\n⏳ [Giãn cách] Nghỉ ngẫu nhiên {delay} giây ({mins}p {secs}s) trước khi chuyển bài tiếp theo...\n")
                if auto_join_groups and group_keywords and delay >= 180:
                    on_line(f"\n🔍 [Tự động gia nhập Group] Tận dụng thời gian chờ để tìm và xin vào nhóm theo từ khóa: '{group_keywords}'...\n")
                    on_line("⏳ [GPM Cooldown] Nghỉ 7s để trình duyệt đóng hoàn tất trước khi mở lại profile...\n")
                    if not sleep_with_cancel(7):
                        return False
                    if check_cancel():
                        return False
                    jg_cmd = build_cmd_for_account(curr_acc_id) + ["join-group", "--keywords", group_keywords, "--limit", "1"]
                    process_runner.run_command_sync(jg_cmd, job_id=job_id, on_line=on_line, cwd=str(BASE_DIR))
                    if not sleep_with_cancel(5):
                        return False
                    on_line("⏳ Tiếp tục đếm ngược thời gian nghỉ...\n")
                if not sleep_with_cancel(delay):
                    return False

        on_line(f"📊 [Comment Summary] Verified {comment_verified_count} · Unverified {comment_unverified_count} · Failed Before Submit {comment_failed_count} · Total {total}.\n")
        on_line(f"RUN_RESULT:{'failed' if batch_failed else 'finished'}\n")
        on_line("\n[Hoàn thành bình luận danh sách bài viết!]\n" if not batch_failed else "\n[Hoàn thành với một số lỗi/chưa xác minh!]\n")
        return not batch_failed

    # 7. THREAD COMMAND — separate capability contract; never inherits post-only flags.
    if cmd == "thread":
        tasks = data.get("tasks", []) or []
        if not tasks:
            targets = data.get("targets", []) or []
            content = str(data.get("content") or "")
            tasks = [{"target": t, "content": content, "image": None} for t in targets]
        if not tasks or len(tasks) > 999:
            on_line("Error: Thread batch must contain 1-999 tasks.\nRUN_RESULT:failed\n")
            return False
        verified_count = unverified_count = failed_count = 0
        if job_repo: job_repo.update_job(job_id, progress_total=len(tasks))
        for i, task in enumerate(tasks):
            if check_cancel(): return False
            target=str(task.get("target") or "").strip(); text=str(task.get("content") or "").strip(); image=task.get("image")
            if not target or (not text and not image):
                failed_count += 1; on_line(f"❌ Thread {i+1}: thiếu target/content.\n"); continue
            if image and not is_uploaded_image(image):
                failed_count += 1; on_line(f"❌ Thread {i+1}: image path không hợp lệ.\n"); continue
            curr_acc_id = accounts_pool[i % len(accounts_pool)].get("id") if rotate_accounts and accounts_pool else account_id
            wf_task_id=workflow_start_task(job_id=job_id,action="thread",profile_id=curr_acc_id,target_url=target,metadata={"message_preview":text[:80]})
            full_cmd=build_cmd_for_account(curr_acc_id)+["thread",target,text]
            if image: full_cmd.extend(["--image",image])
            result={}
            def _capture_thread(line):
                on_line(line); clean=(line or "").strip()
                if clean.startswith("ACTION_RESULT:"):
                    try: result.update(json.loads(clean[len("ACTION_RESULT:"):]))
                    except Exception: pass
            ret=process_runner.run_command_sync(full_cmd,job_id=job_id,on_line=_capture_thread,cwd=str(BASE_DIR))
            state=str(result.get("state") or ""); code=str(result.get("code") or "")
            if state=="messaged" and ret==0:
                verified_count += 1; outcome="messaged"
                workflow_finish_task(wf_task_id,state="completed",submission_status="SUBMIT_CONFIRMED",verification_status="MESSAGE_VERIFIED",result_url=result.get("result_url") or target)
            elif state=="unverified" or code=="MESSAGE_UNVERIFIED":
                unverified_count += 1; outcome="unverified"
                workflow_finish_task(wf_task_id,state="unverified",phase="VERIFYING",submission_status="SUBMIT_CONFIRMED",verification_status="MESSAGE_UNVERIFIED",result_url=result.get("result_url") or target,error_code=code or "MESSAGE_UNVERIFIED",error_message=result.get("message") or "Message not verified")
            else:
                failed_count += 1; outcome="failed_before_submit"
                workflow_finish_task(wf_task_id,state="failed",verification_status="FAILED",error_code=code or "MESSAGE_FAILED",error_message=result.get("message") or "Message failed")
            record_profile_activity(curr_acc_id,"thread",target=target,content=text,outcome=outcome)
            if job_repo: job_repo.update_job(job_id,progress_current=i+1)
            if i < len(tasks)-1 and not sleep_with_cancel(random.randint(delay_min,delay_max)): return False
        on_line(f"📊 [Thread Summary] Verified {verified_count} · Unverified {unverified_count} · Failed Before Submit {failed_count}.\n")
        failed = failed_count > 0 or unverified_count > 0
        on_line(f"RUN_RESULT:{'failed' if failed else 'finished'}\n")
        return not failed

    # Profile rotation is LRU, not input-order round robin. Profiles with no
    # activity history sort first; every profile is consumed once before reuse.
    if rotate_accounts and accounts_pool:
        try:
            last_used = ActivityRepository().latest_activity_by_profile()
            accounts_pool = sorted(accounts_pool, key=lambda a: (last_used.get(str(a.get("id") or ""), ""), str(a.get("name") or a.get("id") or "")))
            order = ", ".join(str(a.get("name") or a.get("id")) for a in accounts_pool)
            on_line(f"[Profile Rotation] LRU order (idle longest first): {order}\n")
        except Exception as exc:
            on_line(f"[Profile Rotation] LRU history unavailable; keeping configured order: {exc}\n")

    # 8. POSTING (GROUP, PAGE, RECONCILE)
    tasks = data.get("tasks", [])
    if not tasks:
        targets = data.get("targets", [])
        content = data.get("content", "")
        tasks = [{"target": t, "content": content, "image": None} for t in targets]

    if not tasks:
        on_line("Error: No tasks or targets provided.\n")
        return False

    if not isinstance(tasks, list) or len(tasks) > 999:
        on_line("Error: Batch must contain between 1 and 999 tasks.\n")
        return False

    total = len(tasks)
    batch_failed = False
    actual_runs = 0
    skipped_duplicates = 0
    published_count = 0
    pending_count = 0
    moderation_skipped_count = 0
    unverified_count = 0
    failed_before_submit_count = 0
    if job_repo:
        job_repo.update_job(job_id, progress_total=total)

    for i, task in enumerate(tasks):
        if check_cancel():
            return False
        if not isinstance(task, dict):
            batch_failed = True
            if job_repo:
                job_repo.update_job(job_id, progress_current=i + 1)
            continue
        target = task.get("target", "").strip()
        content = task.get("content", "").strip()
        image = task.get("image", None)
        queue_item_id = str(task.get("queueItemId") or "").strip()

        task_feeling = task.get("feeling", feeling)
        task_checkin = task.get("checkin", checkin)

        if not target:
            batch_failed = True
            on_line(f"Error: Target {i+1} bị trống.\n")
            if job_repo:
                job_repo.update_job(job_id, progress_current=i + 1)
            continue
        if len(target) > 2_000 or len(content) > 60_000:
            on_line(f"Error: Target {i+1} exceeds the allowed size.\n")
            batch_failed = True
            if job_repo:
                job_repo.update_job(job_id, progress_current=i + 1)
            continue
        if image and not is_uploaded_image(image):
            on_line(f"Error: Target {i+1} has an invalid image path.\n")
            batch_failed = True
            if job_repo:
                job_repo.update_job(job_id, progress_current=i + 1)
            continue

        if skip_duplicate and cmd in ("group", "page"):
            is_dup, hours_ago, posted_at = is_recently_posted(target, hours=float(skip_duplicate_hours))
            if is_dup:
                skipped_duplicates += 1
                recent_state="unknown"
                recent_row = {}
                try:
                    for row in ActivityRepository().list_posted_links(limit=300):
                        if normalize_target_url(row.get("target") or "") == normalize_target_url(target):
                            recent_row = row
                            recent_state=str(row.get("publish_state") or "unknown").lower(); break
                except Exception: pass
                labels={"published":"đã xuất bản","pending":"đang chờ Facebook duyệt","submitted_unverified":"có thể đã gửi nhưng chưa xác minh permalink"}
                on_line(f"\n========== [Mục tiêu {i+1}/{total}] ==========\n")
                on_line(f"⏭️ [Khóa retry {skip_duplicate_hours}h] {target}: {labels.get(recent_state,recent_state)} lúc {posted_at} ({hours_ago}h trước). Không gửi lại tự động.\n")
                if queue_item_id and recent_state in ("published", "pending", "submitted_unverified"):
                    synced_state = {"published": "published", "pending": "pending", "submitted_unverified": "unverified"}[recent_state]
                    try:
                        from repositories.campaign_repo import CampaignRepository
                        synced = CampaignRepository().transition_queue_item(
                            queue_item_id, ("approved",), synced_state,
                            {
                                "error": None,
                                "result_url": recent_row.get("url") or recent_row.get("result_url") or "",
                                "published_at": posted_at if synced_state == "published" else None,
                            },
                            f"duplicate_lock_synced_{synced_state}",
                        )
                        if synced:
                            on_line(f"📦 [Queue Sync] {queue_item_id} → {synced_state}; đã rời hàng đợi hoạt động.\n")
                    except Exception as sync_err:
                        on_line(f"⚠️ [Queue Sync] Không thể đồng bộ {queue_item_id}: {sync_err}\n")
                if job_repo:
                    job_repo.update_job(job_id, progress_current=i + 1)
                continue

        task_content = content
        sig_mode = "linkless" if cmd in ("group", "page") else ("safe" if safe_signature else "canonical")
        if auto_spin and cmd in ("group", "page"):
            try:
                from ai_spinner import generate_unique_variant_with_evidence
                spin_result = generate_unique_variant_with_evidence(
                    content, gemini_api_key, brand_key=brand_key, include_signature=include_signature,
                    signature_mode=sig_mode, variant_seed=target,
                )
                task_content = spin_result["content"]
                if spin_result["mode"] == "gemini" and spin_result["changed"]:
                    on_line(
                        f"🤖 [AI Content Spinner] Gemini đã tạo biến thể Content Hub cho mục tiêu {i+1}/{total} "
                        f"({spin_result.get('model', 'unknown')} · key pool {spin_result.get('key_pool_size', 0)}).\n"
                    )
                elif spin_result["changed"]:
                    detail = f"; Gemini lỗi: {spin_result['error']}" if spin_result["error"] else ""
                    engine = "Content Hub Fallback" if spin_result.get("mode") == "content_hub_fallback" else "Local Spinner"
                    on_line(f"🔀 [{engine}] Đã tạo biến thể truth-safe cho mục tiêu {i+1}/{total}{detail}.\n")
                else:
                    pool = f" key pool={spin_result.get('key_pool_size', 0)}, attempted={spin_result.get('keys_attempted', 0)}."
                    detail = f" Gemini lỗi: {spin_result['error']}." if spin_result["error"] else ""
                    on_line(f"ℹ️ [Content Spinner] Nội dung không đổi; không có biến thể hợp lệ.{pool}{detail}\n")
            except Exception as spin_err:
                on_line(f"⚠️ [AI Spinner] Xào bài gặp lỗi ({spin_err}), dùng nội dung gốc.\n")
                from brand_profiles import apply_brand_signature
                task_content = apply_brand_signature(content, brand_key, include_signature, mode=sig_mode)
        elif cmd in ("group", "page"):
            from brand_profiles import apply_brand_signature
            task_content = apply_brand_signature(content, brand_key, include_signature, mode=sig_mode)

        if cmd in ("group", "page"):
            from composer_guard import dedupe_content_blocks, audit_final_content, normalize_single_cta
            task_content = normalize_single_cta(task_content, brand_key) if sig_mode == "linkless" else dedupe_content_blocks(task_content)
            content_audit = audit_final_content(task_content, brand_key, linkless=(sig_mode == "linkless"))
            if not content_audit["pass"]:
                batch_failed = True
                on_line(f"[FINAL_CONTENT_AUDIT_FAILED] Project={brand_key}; issues={','.join(content_audit['issues'])}. Stop before Facebook.\n")
                if job_repo:
                    job_repo.update_job(job_id, progress_current=i + 1)
                continue
            from brand_profiles import validate_brand_signature
            sig_ok, sig_missing = validate_brand_signature(task_content, brand_key, mode=sig_mode)
            if brand_key and not sig_ok:
                batch_failed = True
                on_line(f"❌ [FINAL_CONTENT_SIGNATURE_MISSING] Project={brand_key}; thiếu: {', '.join(sig_missing)}. Dừng trước khi mở Facebook.\n")
                if job_repo:
                    job_repo.update_job(job_id, progress_current=i + 1)
                continue
            has_sig="yes" if ("━━━━━━━━━━━━━━━━━━━━" in task_content or "-------------------" in task_content) else "no"
            has_tags="yes" if all(t.lower() in task_content.lower() for t in ("#UMEEHomestay","#LacasaHomestay")) else "no"
            preview=re.sub(r"\s+"," ",task_content).strip()[:120]
            on_line(f"🧾 [Spin Evidence] original={len(content)} chars → final={len(task_content)} chars · project={brand_key or 'none'} · signature={has_sig} ({sig_mode}) · global_tags={has_tags}\n")
            on_line(f"📝 [Final Content Preview] {preview}...\n")

        task_images = []
        if photo_folders and not image:
            selected_photo_folder = photo_folders[i % len(photo_folders)]
            task_images = pick_random_photos(selected_photo_folder, photo_count_mode, clean_exif=clean_exif)
            if task_images:
                on_line(f"📁 [Luân phiên ảnh] Folder {(i % len(photo_folders))+1}/{len(photo_folders)}: {selected_photo_folder} · đã chọn {len(task_images)} ảnh.\n")

        if rotate_accounts and accounts_pool:
            # Do not repeatedly assign a Group to a profile already proven not to be
            # a member of that exact Group. Preserve LRU order and round-robin fairness
            # among the remaining eligible profiles.
            eligible_pool = accounts_pool
            excluded_membership = set()
            if cmd == "group":
                try:
                    from repositories.workflow_repo import WorkflowRepository
                    excluded_membership = WorkflowRepository().membership_ineligible_profiles(target)
                    candidates = [a for a in accounts_pool if str(a.get("id") or "") not in excluded_membership]
                    if candidates:
                        eligible_pool = candidates
                except Exception as membership_history_err:
                    on_line(f"[Profile Eligibility] history unavailable: {membership_history_err}\n")
            curr_acc = eligible_pool[i % len(eligible_pool)]
            curr_acc_id = curr_acc.get("id")
            if excluded_membership:
                on_line(f"🧭 [Profile Eligibility] Bỏ {len(excluded_membership)} profile đã xác minh không phải member của Group này.\n")
            on_line(f"🔄 [Luân phiên Profile GPM] Sử dụng: {curr_acc.get('name', curr_acc_id)} cho bài đăng {i+1}/{total}\n")
        else:
            curr_acc_id = account_id

        on_line(f"\n========== [Target {i+1}/{total}] ==========\n")
        on_line(f"Posting to: {target}\n")

        if queue_item_id:
            try:
                from repositories.campaign_repo import CampaignRepository
                claim_from = ("unverified",) if cmd == "reconcile-post" else ("approved",)
                claim_to = "reconciling" if cmd == "reconcile-post" else "processing"
                claimed = CampaignRepository().transition_queue_item(
                    queue_item_id, claim_from, claim_to,
                    {"error": None, "processing_at": now_iso(), "account_id": curr_acc_id}, claim_to
                )
            except Exception as claim_err:
                on_line(f"❌ [Queue Authority] Không thể khóa mục {queue_item_id} để đăng: {claim_err}\n")
                batch_failed = True
                if job_repo:
                    job_repo.update_job(job_id, progress_current=i + 1)
                continue
            if not claimed:
                expected_state = "Chưa xác minh" if cmd == "reconcile-post" else "Đã duyệt"
                on_line(f"❌ [Queue Authority] Mục {queue_item_id} không còn ở trạng thái {expected_state}; từ chối thao tác để tránh duplicate/bypass.\n")
                batch_failed = True
                if job_repo:
                    job_repo.update_job(job_id, progress_current=i + 1)
                continue

        wf_task_id = workflow_start_task(
            job_id=job_id,
            action=cmd,
            profile_id=curr_acc_id,
            target_url=target,
            metadata={"queue_item_id": queue_item_id, "brand_key": brand_key, "action_name": cmd}
        )

        full_cmd = build_cmd_for_account(curr_acc_id) + [cmd, target, task_content]
        if cmd != "reconcile-post":
            if image:
                full_cmd.extend(["--image", image])
            elif task_images:
                full_cmd.extend(["--images"] + task_images)
            if task_feeling:
                full_cmd.append("--feeling")
            if task_checkin:
                full_cmd.append("--checkin")
            if not clean_exif:
                full_cmd.append("--no-clean-exif")
            if not anti_hash_text:
                full_cmd.append("--no-anti-hash-text")
            if brand_key:
                full_cmd.extend(["--brand-key", brand_key])

        structured_result = {}
        def _capture_post_line(line):
            on_line(line)
            clean = (line or "").strip()
            if clean.startswith("ACTION_RESULT:"):
                try:
                    structured_result.update(json.loads(clean[len("ACTION_RESULT:"):]))
                except Exception:
                    pass

        known_moderated = cmd == "group" and ModerationRepository().requires_approval(target)
        if known_moderated:
            on_line("🧠 [Group Moderation] Nhóm đã được ghi nhớ là cần quản trị viên duyệt; sau submit sẽ kết luận chờ duyệt.\n")
        actual_runs += 1
        ret = process_runner.run_command_sync(
            full_cmd, job_id=job_id, on_line=_capture_post_line, cwd=str(BASE_DIR),
            timeout_seconds=180 if cmd in ("group", "page") else 120,
        )
        if known_moderated and is_submit_uncertain(structured_result):
            structured_result.update({
                "success": True, "state": "pending", "code": "POST_PENDING",
                "message": "Facebook đã nhận submit; Group được ghi nhớ là cần quản trị viên duyệt."
            })
            ret = 0

        # A submit can succeed before Facebook exposes a permalink. Reconcile read-only
        # before declaring the task unresolved; never resubmit the post here.
        submit_was_triggered = is_submit_uncertain(structured_result)
        if cmd in ("group", "page") and submit_was_triggered:
            for reconcile_attempt, wait_seconds in enumerate((5, 15), 1):
                on_line(f"🔎 [Auto Reconcile {reconcile_attempt}/2] Facebook đã nhận submit nhưng chưa có permalink; chờ {wait_seconds}s rồi đối soát read-only.\n")
                if not sleep_with_cancel(wait_seconds):
                    return False
                reconcile_result = {}
                def _capture_reconcile_line(line):
                    on_line(line)
                    clean = (line or "").strip()
                    if clean.startswith("ACTION_RESULT:"):
                        try:
                            reconcile_result.update(json.loads(clean[len("ACTION_RESULT:"):]))
                        except Exception:
                            pass
                reconcile_cmd = build_cmd_for_account(curr_acc_id) + ["reconcile-post", target, task_content]
                reconcile_ret = process_runner.run_command_sync(reconcile_cmd, job_id=job_id, on_line=_capture_reconcile_line, cwd=str(BASE_DIR))
                reconciled_state = str(reconcile_result.get("state") or "")
                if reconciled_state in ("published", "pending"):
                    structured_result.clear(); structured_result.update(reconcile_result)
                    ret = reconcile_ret
                    on_line(f"✅ [Auto Reconcile] Đã xác định trạng thái Facebook: {reconciled_state}.\n")
                    break

        action_state = str(structured_result.get("state") or "")
        action_code = str(structured_result.get("code") or "")
        submit_was_triggered = is_submit_uncertain(structured_result)
        deferred_comment = None
        if cmd == "reconcile-post" and action_state == "published":
            try:
                deferred_comment = ModerationRepository().get_deferred(target, task_content, curr_acc_id)
            except Exception:
                deferred_comment = None

        if cmd == "group" and action_code == "GROUP_PENDING_CAPACITY":
            moderation_skipped_count += 1
            outcome = "skipped_moderation_capacity"
            pending_seen = int((structured_result.get("metadata") or {}).get("pending_count") or 0)
            try:
                ModerationRepository().record_pending_count(target, pending_seen, curr_acc_id, action_code)
            except Exception as moderation_err:
                on_line(f"[Moderation Registry] Cannot persist pending counter: {moderation_err}\n")
            on_line(f"[Moderation Capacity] SKIPPED target before composer: pending={pending_seen}, threshold=2.\n")
        elif action_state == "published":
            published_count += 1
            outcome = "published"

            # First comment runs immediately for published Group posts, or after moderation reconciliation.
            should_first_comment = (
                (cmd == "group" and auto_first_comment and brand_key)
                or (cmd == "reconcile-post" and bool(deferred_comment))
            )
            if should_first_comment:
                from brand_profiles import get_first_comment_text
                post_permalink = str(structured_result.get("result_url") or "").strip()
                comment_brand_key = str((deferred_comment or {}).get("brand_key") or brand_key).strip().lower()
                # Always regenerate from the current safe templates. This also prevents
                # old deferred rows containing a multi-link comment from being posted.
                first_comment_text = get_first_comment_text(comment_brand_key, variant_seed=target)
                if first_comment_text and post_permalink and ("/posts/" in post_permalink or "/permalink/" in post_permalink or "/share/" in post_permalink):
                    cooldown = ModerationRepository().comment_cooldown(target)
                    if cooldown:
                        on_line(f"🛑 [First Comment] Group đang cooldown đến {cooldown.get('cooldown_until')}; không gửi lại bình luận đã từng bị từ chối.\n")
                        if deferred_comment:
                            ModerationRepository().resolve_deferred(deferred_comment["id"], post_permalink, False)
                    else:
                        human_pause = random.randint(8, 15)
                        on_line(f"⏳ [Human Pause] Chờ {human_pause}s trước bình luận liên kết đã được bật rõ ràng...\n")
                        if not sleep_with_cancel(human_pause):
                            return False
                        on_line("💬 [First Comment] Đang nhập bình luận thông tin liên hệ bằng luồng human typing...\n")
                        try:
                            comment_cmd = build_cmd_for_account(curr_acc_id) + ["comment", post_permalink, first_comment_text, "--brand-key", comment_brand_key]
                            if not anti_hash_text:
                                comment_cmd.append("--no-anti-hash-text")
                            comment_result = {}
                            def _capture_comment_line(line):
                                on_line(line)
                                clean = line.strip()
                                if clean.startswith("ACTION_RESULT:"):
                                    try:
                                        comment_result.update(json.loads(clean[len("ACTION_RESULT:"):]))
                                    except (ValueError, TypeError):
                                        pass
                            return_code = process_runner.run_command_sync(
                                comment_cmd, job_id=job_id, on_line=_capture_comment_line,
                                cwd=str(BASE_DIR), timeout_seconds=120,
                            )
                            comment_verified = return_code == 0 and bool(comment_result.get("success"))
                            comment_code = str(comment_result.get("code") or "")
                            comment_state = str(comment_result.get("state") or "")
                            evidence_path = str((comment_result.get("metadata") or {}).get("evidence_path") or "")
                            comment_rejected = comment_code == "COMMENT_REJECTED" or comment_state == "rejected"
                            delivery_status = "rejected" if comment_rejected else ("verified" if comment_verified else "unverified")
                            ModerationRepository().record_comment_delivery(
                                target, post_permalink, curr_acc_id, comment_brand_key,
                                delivery_status, first_comment_text, evidence_path,
                            )
                            record_profile_activity(
                                curr_acc_id, "first-comment", target=target,
                                content=first_comment_text, outcome=delivery_status,
                            )
                            if comment_rejected:
                                on_line("❌ [First Comment] Facebook/Group đã từ chối bình luận. Đã lưu cooldown 24 giờ; không retry cùng nội dung.\n")
                            elif comment_verified:
                                on_line("✅ [First Comment] Facebook đã xác nhận bình luận thành công.\n")
                            else:
                                on_line("⚠️ [First Comment] Chưa có bằng chứng Facebook xác nhận bình luận; bài chính vẫn đã đăng.\n")
                            if deferred_comment:
                                ModerationRepository().resolve_deferred(
                                    deferred_comment["id"], post_permalink, comment_verified
                                )
                        except Exception as first_comment_err:
                            on_line(f"⚠️ [First Comment] Không thể bình luận tự động: {first_comment_err}\n")
        elif is_post_pending(structured_result):
            pending_count += 1
            outcome = "pending"
            if cmd == "group":
                try:
                    ModerationRepository().mark_requires_approval(
                        target, action_code or "facebook_pending_notice", curr_acc_id
                    )
                    on_line("💾 [Group Moderation] Đã lưu Group cần quản trị viên duyệt cho những lần đăng sau.\n")
                    if auto_first_comment and brand_key:
                        from brand_profiles import get_first_comment_text
                        comment_text = get_first_comment_text(brand_key, variant_seed=target)
                        ModerationRepository().defer_first_comment(
                            target, task_content, curr_acc_id, brand_key, comment_text
                        )
                        ReconcileRepository().enqueue(
                            target, task_content, curr_acc_id, queue_item_id or None,
                            delay_seconds=600, reconcile_kind="moderation", origin_job_id=job_id
                        )
                        on_line("🕒 [First Comment] Đã lưu first comment dạng text; sẽ đăng sau khi bài được duyệt và có permalink.\n")
                except Exception as moderation_err:
                    on_line(f"⚠️ [Group Moderation] Không thể lưu trạng thái chờ duyệt: {moderation_err}\n")
        elif submit_was_triggered:
            unverified_count += 1
            outcome = "submitted_unverified"
        else:
            failed_before_submit_count += 1
            batch_failed = True
            outcome = "failed_before_submit"

        # Durable reconciliation is created only after a real post submit becomes uncertain.
        if cmd in ("group", "page") and submit_was_triggered:
            try:
                rid = ReconcileRepository().enqueue(target, task_content, curr_acc_id, queue_item_id or None, delay_seconds=30, origin_job_id=job_id)
                on_line(f"🕒 [Durable Reconcile] Đã lên lịch 30s → 2m → 10m · id={rid[:10]}. Không repost.\n")
            except Exception as recon_err:
                on_line(f"⚠️ [Durable Reconcile] Không thể ghi lịch đối soát: {recon_err}\n")
                batch_failed = True

        # A scheduled reconcile advances its durable state after every read-only attempt and
        # synchronizes the linked Publication Queue without re-claiming/reposting the item.
        if cmd == "reconcile-post" and reconcile_record_id:
            try:
                durable_repo = ReconcileRepository()
                durable_record = durable_repo.get_item(reconcile_record_id)
                durable_state = durable_repo.finish_attempt(
                    reconcile_record_id, action_state, structured_result.get("result_url") or "",
                    structured_result.get("message") or ""
                )
                on_line(f"🧭 [Durable Reconcile] record={reconcile_record_id[:10]} → {durable_state}.\n")
                linked_queue_id = str((durable_record or {}).get("queue_item_id") or "").strip()
                if linked_queue_id:
                    from repositories.campaign_repo import CampaignRepository
                    queue_result_state = action_state if action_state in ("published", "pending") else ("manual_review" if durable_state == "manual_review" else "unverified")
                    CampaignRepository().apply_reconcile_result(
                        linked_queue_id, queue_result_state,
                        structured_result.get("result_url") or "",
                        structured_result.get("message") or ""
                    )
                    on_line(f"🔗 [Queue Sync] {linked_queue_id} → {queue_result_state}.\n")
            except Exception as recon_err:
                on_line(f"⚠️ [Durable Reconcile] Không thể cập nhật attempt/queue: {recon_err}\n")
                batch_failed = True
        elif cmd == "reconcile-post" and action_state not in ("published", "pending"):
            # Manual reconcile must not surface a green success when nothing was verified.
            batch_failed = True
        record_profile_activity(curr_acc_id, cmd, target=target, content=content, outcome=outcome)

        if cmd == "group" and action_code == "GROUP_PENDING_CAPACITY":
            workflow_finish_task(wf_task_id, state="completed", submission_status="NOT_SUBMITTED", verification_status="SKIPPED_MODERATION_CAPACITY", error_code=action_code, error_message=structured_result.get("message") or "Skipped before composer")
        elif action_state == "published" and ret == 0:
            workflow_finish_task(wf_task_id, state="published", submission_status="SUBMIT_CONFIRMED", verification_status="PERMALINK_FOUND", result_url=structured_result.get("result_url") or "")
        elif is_post_pending(structured_result):
            workflow_finish_task(wf_task_id, state="pending", submission_status="PENDING_APPROVAL", verification_status="PENDING_EVIDENCE", result_url=structured_result.get("result_url") or "")
        elif submit_was_triggered:
            workflow_finish_task(wf_task_id, state="unverified", phase="VERIFYING", submission_status="SUBMIT_CONFIRMED", verification_status="NO_PERMALINK", result_url=structured_result.get("result_url") or "", error_code=structured_result.get("code") or "SUBMITTED_NO_PERMALINK", error_message=structured_result.get("message") or "Submitted but permalink is not verified.")
        else:
            workflow_finish_task(wf_task_id, state="failed", verification_status="FAILED", error_code=structured_result.get("code") or "FAILED_BEFORE_SUBMIT", error_message=structured_result.get("message") or "Task failed before verified submission.")

        if queue_item_id:
            from repositories.campaign_repo import CampaignRepository
            transition_from = ("reconciling",) if cmd == "reconcile-post" else ("processing",)
            if cmd == "group" and action_code == "GROUP_PENDING_CAPACITY":
                final_queue_state = "approved"
                updates = {"error": structured_result.get("message") or "T?m b? qua v? nh?m c? >=2 b?i ch? duy?t."}
            elif action_state == "published" and ret == 0:
                final_queue_state = "published"
                updates = {"published_at": now_iso(), "result_url": structured_result.get("result_url") or "", "error": None}
            elif is_post_pending(structured_result) and ret == 0:
                final_queue_state = "pending"
                updates = {"result_url": structured_result.get("result_url") or "", "error": None}
            elif submit_was_triggered or cmd == "reconcile-post":
                final_queue_state = "unverified"
                updates = {"error": structured_result.get("message") or "Facebook có thể đã nhận bài nhưng chưa xác minh được permalink; chỉ đối soát, không tự động đăng lại."}
            else:
                final_queue_state = "failed"
                updates = {"error": structured_result.get("message") or "Thất bại trước khi có bằng chứng bài được gửi. Có thể chọn Thử lại thủ công."}
            try:
                transitioned = CampaignRepository().transition_queue_item(
                    queue_item_id, transition_from, final_queue_state, updates,
                    f"post_result:{action_state or outcome}"
                )
                if not transitioned:
                    on_line(f"⚠️ [Queue Authority] Không thể ghi kết quả cho {queue_item_id}; state đã thay đổi ngoài tiến trình.\n")
                    batch_failed = True
            except Exception as state_err:
                on_line(f"❌ [Queue Authority] Lỗi ghi state kết quả {queue_item_id}: {state_err}\n")
                batch_failed = True

        if job_repo:
            job_repo.update_job(job_id, progress_current=i + 1)

        if i < total - 1:
            delay = 2 if cmd == "reconcile-post" else (5 if outcome == "failed_before_submit" else random.randint(delay_min, delay_max))
            mins = delay // 60
            secs = delay % 60
            if outcome == "failed_before_submit":
                on_line(f"\n⚠️ Target {i+1} lỗi trước khi có bằng chứng submit. Nghỉ nhanh {delay}s trước target tiếp theo.\n")
            elif outcome == "submitted_unverified":
                on_line(f"\n🔎 Target {i+1} đã submit nhưng còn cần đối soát permalink. Giữ khóa chống duplicate và giãn cách {delay}s trước target tiếp theo.\n")
            else:
                on_line(f"\n⏳ [Giãn cách] Nghỉ ngẫu nhiên {delay} giây ({mins}p {secs}s) trước bài tiếp theo...\n")
            if auto_join_groups and group_keywords and delay >= 180:
                on_line(f"\n🔍 [Tự động gia nhập Group] Tận dụng thời gian chờ để tìm và xin vào nhóm theo từ khóa: '{group_keywords}'...\n")
                on_line("⏳ [GPM Cooldown] Nghỉ 7s để trình duyệt đóng hoàn tất trước khi mở lại profile...\n")
                if not sleep_with_cancel(7):
                    return False
                if check_cancel():
                    return False
                jg_cmd = build_cmd_for_account(curr_acc_id) + ["join-group", "--keywords", group_keywords, "--limit", "1"]
                process_runner.run_command_sync(jg_cmd, job_id=job_id, on_line=on_line, cwd=str(BASE_DIR))
                if not sleep_with_cancel(5):
                    return False
                on_line("⏳ Tiếp tục đếm ngược thời gian nghỉ...\n")
            if not sleep_with_cancel(delay):
                return False

    on_line(
        f"📊 [Batch Summary] Tổng {total} · Published {published_count} · Pending {pending_count} · "
        f"Submitted/Need Reconcile {unverified_count} · Retry Locked {skipped_duplicates} · "
        f"Failed Before Submit {failed_before_submit_count}.\n"
    )
    on_line(f"RUN_RESULT:{'failed' if batch_failed else 'finished'}\n")
    if batch_failed:
        on_line("\n[Batch completed: có lỗi trước submit; xem từng target để retry thủ công.]\n")
    elif unverified_count > 0:
        on_line("\n[Batch completed: không repost các bài chưa xác minh; durable reconcile đã được lên lịch.]\n")
    elif actual_runs == 0 and skipped_duplicates > 0:
        on_line("\n[Batch completed: 0 bài mới được gửi; tất cả mục tiêu đang bị khóa retry/đã xử lý gần đây.]\n")
    else:
        on_line("\n[Batch processing completed successfully!]\n")
    return not batch_failed
