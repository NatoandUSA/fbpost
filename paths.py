"""Central path configuration for FB Automation.
Separates application code from mutable runtime data to ensure
safe, loss-free upgrades and backups.
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent
VERSION_FILE = BASE_DIR / "VERSION"

DATA_DIR = Path(os.getenv("FB_AUTOMATION_DATA_DIR", str(BASE_DIR / "data"))).resolve()
UPLOAD_DIR = DATA_DIR / "uploads"
LOG_DIR = DATA_DIR / "logs"
JOBS_LOG_DIR = LOG_DIR / "jobs"
BACKUP_DIR = DATA_DIR / "backups"
DB_FILE = DATA_DIR / "app.db"
MIGRATIONS_DIR = BASE_DIR / "migrations"

for d in (DATA_DIR, UPLOAD_DIR, LOG_DIR, JOBS_LOG_DIR, BACKUP_DIR):
    d.mkdir(parents=True, exist_ok=True)


def get_version() -> str:
    if VERSION_FILE.exists():
        try:
            return VERSION_FILE.read_text(encoding="utf-8-sig").strip()
        except OSError:
            pass
    return "6.0.8"
