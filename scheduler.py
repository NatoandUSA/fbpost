import csv
import json
import logging
import io
import os
from datetime import datetime
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from fb_page_api import post_to_page

LOG_FILE = "scheduler.log"
CONFIG_FILE = "config.json"

# Setup logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def fetch_sheets_data(csv_url):
    """Fetch and parse Google Sheets CSV. Returns list of row dicts."""
    try:
        resp = requests.get(csv_url, timeout=15)
        resp.raise_for_status()
        reader = csv.reader(io.StringIO(resp.text))
        rows = []
        for i, row in enumerate(reader):
            if len(row) < 4:
                continue
            # Skip header if first row looks like a header
            if i == 0 and not row[0].strip().lstrip('-').isdigit() and 'page' in row[0].lower():
                continue
            rows.append({
                "row_index": i,
                "page_id": row[0].strip(),
                "content": row[1].strip(),
                "image_url": row[2].strip() if len(row) > 2 else "",
                "scheduled_time": row[3].strip() if len(row) > 3 else "",
                "status": row[4].strip().lower() if len(row) > 4 else "pending",
            })
        return rows
    except Exception as e:
        logger.error(f"Lỗi đọc Google Sheets: {e}")
        return []

def run_scheduler_job():
    """Main job: read Sheets, find pending posts due now, post them."""
    config = load_config()
    token = config.get("page_access_token", "")
    csv_url = config.get("sheets_csv_url", "")

    if not token or not csv_url:
        logger.warning("Chưa cấu hình token hoặc Sheets URL. Bỏ qua.")
        return

    logger.info("🔍 Đang kiểm tra Google Sheets...")
    rows = fetch_sheets_data(csv_url)
    now = datetime.now()

    posted_count = 0
    for row in rows:
        if row["status"] != "pending":
            continue

        # Parse scheduled time
        try:
            sched_time = datetime.strptime(row["scheduled_time"], "%Y-%m-%d %H:%M")
        except:
            try:
                sched_time = datetime.strptime(row["scheduled_time"], "%d/%m/%Y %H:%M")
            except:
                logger.warning(f"Row {row['row_index']}: Không đọc được thời gian '{row['scheduled_time']}'")
                continue

        if sched_time > now:
            logger.info(f"Row {row['row_index']}: Chưa đến giờ đăng ({row['scheduled_time']})")
            continue

        # Time to post!
        page_id = row["page_id"]
        logger.info(f"📢 Đang đăng bài lên Page {page_id}...")
        success, result = post_to_page(
            page_id=page_id,
            page_access_token=token,
            content=row["content"],
            image_url=row.get("image_url")
        )

        if success:
            posted_count += 1
            logger.info(f"✅ Row {row['row_index']} - Đăng thành công! Post ID: {result.get('post_id')} | Nội dung: {result.get('content_preview')}...")
        else:
            logger.error(f"❌ Row {row['row_index']} - Đăng thất bại: {result}")

    if posted_count == 0:
        logger.info("✨ Không có bài nào cần đăng lúc này.")
    else:
        logger.info(f"🎉 Hoàn tất! Đã đăng {posted_count} bài trong lần chạy này.")

def start_scheduler(interval_minutes=5):
    global scheduler
    if scheduler.running:
        logger.info("Scheduler đang chạy rồi.")
        return True
    try:
        scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")
        scheduler.add_job(
            run_scheduler_job,
            "interval",
            minutes=interval_minutes,
            id="page_post_job",
            next_run_time=datetime.now()  # Run immediately on start
        )
        scheduler.start()
        logger.info(f"🚀 Scheduler đã khởi động! Kiểm tra mỗi {interval_minutes} phút.")
        return True
    except Exception as e:
        logger.error(f"Lỗi khởi động scheduler: {e}")
        return False

def stop_scheduler():
    global scheduler
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("🛑 Scheduler đã dừng.")
        return True
    return False

def get_scheduler_status():
    return {
        "running": scheduler.running,
        "jobs": [
            {
                "id": job.id,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
            }
            for job in scheduler.get_jobs()
        ] if scheduler.running else []
    }

def get_log_tail(lines=50):
    """Return last N lines of the scheduler log file."""
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
    return [l.rstrip() for l in all_lines[-lines:]]

def preview_sheets(csv_url):
    """Return parsed rows for UI preview."""
    return fetch_sheets_data(csv_url)
