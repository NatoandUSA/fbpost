"""Job Executor Service.
Contains execution logic for all automation commands:
auth, interact, scrape, join-group, create-page, comment, group, page, thread.
Integrates with ProcessRunner for process tree execution and cancellation.
"""

import os
import sys
import re
import time
import random
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from paths import BASE_DIR, UPLOAD_DIR
from utils import (
    load_accounts,
    is_recently_posted,
    pick_random_photos,
)
import server
from services.process_runner import ProcessRunner
from repositories.job_repo import JobRepository

def load_config():
    return server.load_config()

def load_accounts():
    return server.load_accounts()

def record_profile_activity(*args, **kwargs):
    return server.record_profile_activity(*args, **kwargs)


def is_uploaded_image(value: str) -> bool:
    try:
        return Path(value).resolve().is_relative_to(UPLOAD_DIR)
    except (OSError, ValueError):
        return False


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
    account_id = data.get("accountId")
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
    gemini_api_key = data.get("geminiApiKey") or cfg.get("gemini_api_key", "")
    photo_folder = data.get("photoFolder", "").strip()
    photo_count_mode = data.get("photoCountMode", "2-4")
    skip_duplicate = data.get("skipDuplicate24h", True)
    clean_exif = data.get("cleanExif", True)
    anti_hash_text = data.get("antiHashText", False)

    auto_join_groups = data.get("autoJoinGroups", cfg.get("auto_join_groups", False))
    group_keywords = str(data.get("groupKeywords") or cfg.get("group_keywords", "Homestay Huế, Du lịch Huế")).strip()

    def build_cmd_for_account(acc_id):
        cmd_list = [sys.executable, "main.py"]
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
            if sec % 5 == 0 or sec <= 5:
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
            accounts_pool = [a for a in all_accs if a.get("id")]
        except Exception:
            accounts_pool = []

        if not accounts_pool and (data.get("accountIds") or data.get("accounts")):
            if data.get("accounts"):
                accounts_pool = data.get("accounts")
            elif data.get("accountIds"):
                accounts_pool = [{"id": aid, "name": aid} for aid in data.get("accountIds")]

        if not accounts_pool:
            on_line("⚠️ [Cảnh báo Anti-Spam] Bạn đã bật chế độ Luân phiên nhưng chưa có tài khoản Facebook nào trong danh sách 'Tài khoản đã lưu'.\n")
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

            ret = process_runner.run_command_sync(full_cmd, job_id=job_id, on_line=on_line, cwd=str(BASE_DIR))
            outcome = "finished" if ret == 0 else "failed"
            if ret != 0:
                interact_failed = True
            record_profile_activity(cur_id, "interact", target="newsfeed", content=cur_comments, outcome=outcome)

            if job_repo:
                job_repo.update_job(job_id, progress_current=acc_idx + 1)

            if acc_idx < total_accs - 1:
                delay = random.randint(delay_min, delay_max)
                mins = delay // 60
                secs = delay % 60
                on_line(f"\n⏳ [Anti-Spam] Nghỉ {delay}s ({mins}p {secs}s) trước khi đổi sang Profile tiếp theo...\n")
                if not sleep_with_cancel(delay):
                    return False

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
        # Giới hạn tối đa 2 nhóm cho mỗi profile một lần mở trình duyệt
        limit = min(max(1, int(data.get("limit", 2))), 2)

        # Chế độ tương tác feed & delay
        interact_feed = data.get("interactFeed", True)
        feed_flag = ["--interact-feed"] if interact_feed else ["--no-interact-feed"]
        delay_args = ["--delay-min", "60", "--delay-max", "180"]
        if gemini_api_key:
            delay_args.extend(["--gemini-key", str(gemini_api_key)])

        # URL Mode: chia thành các đợt tối đa 2 URLs / profile và xoay vòng profile
        if mode == "urls" and urls:
            urls_list = [u.strip() for u in re.split(r"[\r\n,;]+", urls) if u.strip()]
            on_line(f"🔗 Bắt đầu kiểm tra & tự động xin gia nhập danh sách {len(urls_list)} link nhóm Facebook...\n")
            on_line("🛡️ [Quy chuẩn An toàn] Mỗi profile chỉ vào tối đa 2 nhóm/phiên mở trình duyệt & nghỉ ngẫu nhiên 1 - 3 phút.\n")

            # Chia chunks tối đa 2 URLs mỗi đợt
            chunk_size = 2
            url_chunks = [urls_list[i:i + chunk_size] for i in range(0, len(urls_list), chunk_size)]
            total_chunks = len(url_chunks)

            # Xác định danh sách tài khoản thực hiện xoay tua
            active_pool = accounts_pool if (rotate_accounts and accounts_pool) else []
            if not active_pool:
                target_id = account_id
                if not target_id or str(target_id).strip() in ("__rotate__", "None", ""):
                    all_accs = load_accounts()
                    target_id = all_accs[0].get("id") if all_accs else None
                active_pool = [{"id": target_id, "name": target_id or "default"}]

            pool_len = len(active_pool)
            join_failed = False
            if job_repo:
                job_repo.update_job(job_id, progress_total=total_chunks)

            for chunk_idx, chunk in enumerate(url_chunks):
                if check_cancel():
                    return False
                acc = active_pool[chunk_idx % pool_len]
                acc_id = acc.get("id")
                acc_name = acc.get("name", acc_id)
                chunk_targets = ",".join(chunk)

                on_line(f"\n========== [Đợt {chunk_idx + 1}/{total_chunks} | Profile: {acc_name} (Xử lý {len(chunk)} nhóm)] ==========\n")
                full_cmd = (
                    build_cmd_for_account(acc_id)
                    + ["join-group", "--keywords", chunk_targets, "--limit", str(len(chunk))]
                    + feed_flag
                    + delay_args
                )
                ret = process_runner.run_command_sync(full_cmd, job_id=job_id, on_line=on_line, cwd=str(BASE_DIR))
                outcome = "finished" if ret == 0 else "failed"
                if ret != 0:
                    join_failed = True
                record_profile_activity(acc_id, "join-group", target=chunk_targets[:100], outcome=outcome)
                if job_repo:
                    job_repo.update_job(job_id, progress_current=chunk_idx + 1)

                if chunk_idx < total_chunks - 1:
                    rot_delay = random.randint(60, 180)
                    next_acc = active_pool[(chunk_idx + 1) % pool_len].get("name", "profile tiếp theo")
                    on_line(f"\n⏳ [Anti-Spam] Đã hoàn thành đợt của {acc_name}. Nghỉ an toàn {rot_delay}s ({rot_delay//60} phút {rot_delay%60}s) trước khi xoay sang {next_acc}...\n")
                    if not sleep_with_cancel(rot_delay):
                        return False

            on_line(f"RUN_RESULT:{'failed' if join_failed else 'finished'}\n")
            return not join_failed

        # Keyword Mode
        else:
            kw_list = [k.strip() for k in re.split(r"[\r\n,;]+", str(raw_keywords)) if k.strip() and k.strip() != "None"]
            input_targets = ", ".join(kw_list) if kw_list else "Homestay Huế, Du lịch Huế"
            on_line(f"🔍 Bắt đầu tìm kiếm & tự động xin gia nhập nhóm Facebook theo từ khóa: '{input_targets}'...\n")
            on_line("🛡️ [Quy chuẩn An toàn] Mỗi profile chỉ vào tối đa 2 nhóm/phiên mở trình duyệt & nghỉ ngẫu nhiên 1 - 3 phút.\n")

            if rotate_accounts and accounts_pool:
                total_acc = len(accounts_pool)
                join_failed = False
                if job_repo:
                    job_repo.update_job(job_id, progress_total=total_acc)
                for idx, acc in enumerate(accounts_pool):
                    if check_cancel():
                        return False
                    acc_id = acc.get("id")
                    acc_name = acc.get("name", acc_id)
                    on_line(f"\n========== [Profile {idx+1}/{total_acc}: {acc_name} (Tối đa 2 nhóm)] ==========\n")
                    full_cmd = (
                        build_cmd_for_account(acc_id)
                        + ["join-group", "--keywords", str(input_targets), "--limit", str(limit)]
                        + feed_flag
                        + delay_args
                    )
                    ret = process_runner.run_command_sync(full_cmd, job_id=job_id, on_line=on_line, cwd=str(BASE_DIR))
                    outcome = "finished" if ret == 0 else "failed"
                    if ret != 0:
                        join_failed = True
                    record_profile_activity(acc_id, "join-group", target=str(input_targets)[:100], outcome=outcome)
                    if job_repo:
                        job_repo.update_job(job_id, progress_current=idx + 1)
                    if idx < total_acc - 1:
                        rot_delay = random.randint(60, 180)
                        next_acc = accounts_pool[idx + 1].get("name", "profile tiếp theo")
                        on_line(f"\n⏳ [Anti-Spam] Đã hoàn tất profile {acc_name}. Nghỉ an toàn {rot_delay}s ({rot_delay//60} phút {rot_delay%60}s) trước khi xoay sang {next_acc}...\n")
                        if not sleep_with_cancel(rot_delay):
                            return False
                on_line(f"RUN_RESULT:{'failed' if join_failed else 'finished'}\n")
                return not join_failed
            else:
                target_id = account_id
                if not target_id or str(target_id).strip() in ("__rotate__", "None", ""):
                    all_accs = load_accounts()
                    target_id = all_accs[0].get("id") if all_accs else None
                full_cmd = (
                    build_cmd_for_account(target_id)
                    + ["join-group", "--keywords", str(input_targets), "--limit", str(limit)]
                    + feed_flag
                    + delay_args
                )
                ret = process_runner.run_command_sync(full_cmd, job_id=job_id, on_line=on_line, cwd=str(BASE_DIR))
                outcome = "finished" if ret == 0 else "failed"
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
        like_post = data.get("likePost", True)
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

            on_line(f"\n========== [Bài viết {i+1}/{total}] ==========\n")
            on_line(f"Đang mở bài viết: {target_url}\n")

            full_cmd = build_cmd_for_account(curr_acc_id) + ["comment", target_url, task_comment]
            if like_post:
                full_cmd.append("--like")
            if not anti_hash_text:
                full_cmd.append("--no-anti-hash-text")

            ret = process_runner.run_command_sync(full_cmd, job_id=job_id, on_line=on_line, cwd=str(BASE_DIR))
            outcome = "finished" if ret == 0 else "failed"
            if ret != 0:
                batch_failed = True
            record_profile_activity(curr_acc_id, "comment", target=target_url, content=task_comment, outcome=outcome)

            if job_repo:
                job_repo.update_job(job_id, progress_current=i + 1)

            if i < total - 1:
                delay = random.randint(delay_min, delay_max)
                mins = delay // 60
                secs = delay % 60
                on_line(f"\n⏳ [Anti-Spam An Toàn] Nghỉ ngẫu nhiên {delay} giây ({mins}p {secs}s) trước khi chuyển bài tiếp theo...\n")
                if auto_join_groups and group_keywords:
                    on_line(f"\n🔍 [Tự động gia nhập Group] Tận dụng thời gian chờ để tìm và xin vào nhóm theo từ khóa: '{group_keywords}'...\n")
                    on_line("⏳ [GPM Cooldown] Nghỉ an toàn 7s để trình duyệt đóng hoàn tất trước khi mở lại profile...\n")
                    if not sleep_with_cancel(7):
                        return False
                    if check_cancel():
                        return False
                    jg_cmd = build_cmd_for_account(curr_acc_id) + ["join-group", "--keywords", group_keywords, "--limit", "1"]
                    process_runner.run_command_sync(jg_cmd, job_id=job_id, on_line=on_line, cwd=str(BASE_DIR))
                    if not sleep_with_cancel(5):
                        return False
                    on_line("⏳ Tiếp tục đếm ngược thời gian nghỉ an toàn...\n")
                if not sleep_with_cancel(delay):
                    return False

        on_line(f"RUN_RESULT:{'failed' if batch_failed else 'finished'}\n")
        on_line("\n[Hoàn thành bình luận danh sách bài viết!]\n" if not batch_failed else "\n[Hoàn thành với một số lỗi!]\n")
        return not batch_failed

    # 7. POSTING (GROUP, PAGE, THREAD)
    tasks = data.get("tasks", [])
    if not tasks:
        targets = data.get("targets", [])
        content = data.get("content", "")
        tasks = [{"target": t, "content": content, "image": None} for t in targets]

    if not tasks:
        on_line("Error: No tasks or targets provided.\n")
        return False

    if not isinstance(tasks, list) or len(tasks) > 100:
        on_line("Error: Batch must contain between 1 and 100 tasks.\n")
        return False

    total = len(tasks)
    batch_failed = False
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
            is_dup, hours_ago, posted_at = is_recently_posted(target, hours=24.0)
            if is_dup:
                on_line(f"\n========== [Mục tiêu {i+1}/{total}] ==========\n")
                on_line(f"⏭️ [Bỏ qua trùng lặp 24h] Nhóm/Trang {target} đã được đăng lúc {posted_at} ({hours_ago}h trước). Tự động bỏ qua để bảo vệ tài khoản.\n")
                continue

        task_content = content
        if auto_spin and cmd in ("group", "page"):
            try:
                from ai_spinner import generate_unique_variant
                task_content = generate_unique_variant(content, gemini_api_key)
                on_line(f"🤖 [AI Content Spinner] Đã tạo biến thể bài viết mới cho mục tiêu {i+1}/{total}!\n")
            except Exception as spin_err:
                on_line(f"⚠️ [AI Spinner] Xào bài gặp lỗi ({spin_err}), dùng nội dung gốc.\n")
                task_content = content

        task_images = []
        if photo_folder and not image:
            task_images = pick_random_photos(photo_folder, photo_count_mode, clean_exif=clean_exif)
            if task_images:
                on_line(f"📁 [Thư mục ảnh] Đã bốc ngẫu nhiên {len(task_images)} ảnh cho mục tiêu {i+1}/{total}.\n")

        if rotate_accounts and accounts_pool:
            curr_acc = accounts_pool[i % len(accounts_pool)]
            curr_acc_id = curr_acc.get("id")
            on_line(f"🔄 [Luân phiên Profile GPM] Sử dụng: {curr_acc.get('name', curr_acc_id)} cho bài đăng {i+1}/{total}\n")
        else:
            curr_acc_id = account_id

        on_line(f"\n========== [Target {i+1}/{total}] ==========\n")
        on_line(f"Posting to: {target}\n")

        full_cmd = build_cmd_for_account(curr_acc_id) + [cmd, target, task_content]
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

        ret = process_runner.run_command_sync(full_cmd, job_id=job_id, on_line=on_line, cwd=str(BASE_DIR))
        outcome = "finished" if ret == 0 else "failed"
        if ret != 0:
            batch_failed = True
        record_profile_activity(curr_acc_id, cmd, target=target, content=content, outcome=outcome)

        if job_repo:
            job_repo.update_job(job_id, progress_current=i + 1)

        if i < total - 1:
            delay = random.randint(delay_min, delay_max)
            mins = delay // 60
            secs = delay % 60
            on_line(f"\n⏳ [Anti-Spam An Toàn] Nghỉ ngẫu nhiên {delay} giây ({mins}p {secs}s) trước bài tiếp theo...\n")
            if auto_join_groups and group_keywords:
                on_line(f"\n🔍 [Tự động gia nhập Group] Tận dụng thời gian chờ để tìm và xin vào nhóm theo từ khóa: '{group_keywords}'...\n")
                on_line("⏳ [GPM Cooldown] Nghỉ an toàn 7s để trình duyệt đóng hoàn tất trước khi mở lại profile...\n")
                if not sleep_with_cancel(7):
                    return False
                if check_cancel():
                    return False
                jg_cmd = build_cmd_for_account(curr_acc_id) + ["join-group", "--keywords", group_keywords, "--limit", "1"]
                process_runner.run_command_sync(jg_cmd, job_id=job_id, on_line=on_line, cwd=str(BASE_DIR))
                if not sleep_with_cancel(5):
                    return False
                on_line("⏳ Tiếp tục đếm ngược thời gian nghỉ an toàn...\n")
            if not sleep_with_cancel(delay):
                return False

    on_line(f"RUN_RESULT:{'failed' if batch_failed else 'finished'}\n")
    on_line("\n[Batch processing completed successfully!]\n" if not batch_failed else "\n[Batch processing completed with errors.]\n")
    return not batch_failed
