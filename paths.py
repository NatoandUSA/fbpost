"""Central path configuration for FB Automation.
Separates application code from mutable runtime data to ensure
safe, loss-free upgrades and backups.
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent
VERSION_FILE = BASE_DIR / "VERSION"

def _default_data_dir() -> Path:
    env = os.getenv("FB_AUTOMATION_DATA_DIR", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    parts = BASE_DIR.parts
    lowered = [part.casefold() for part in parts]
    if "release" in lowered:
        idx = lowered.index("release")
        repo_root = Path(*parts[:idx])
        return (repo_root / "data").resolve()
    return (BASE_DIR / "data").resolve()

DATA_DIR = _default_data_dir()
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
    return "6.1.1"
