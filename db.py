"""SQLite Database Manager for FB Automation.
Implements WAL mode, foreign key enforcement, 5-second busy timeout,
migration management, and safe online backup.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from paths import DB_FILE, MIGRATIONS_DIR, BACKUP_DIR


def connect_db(db_file: Optional[Path | str] = None) -> sqlite3.Connection:
    target = str(db_file or DB_FILE)
    conn = sqlite3.connect(target, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def transaction(conn: Optional[sqlite3.Connection] = None, db_file: Optional[Path | str] = None) -> Generator[sqlite3.Connection, None, None]:
    owns_conn = False
    if conn is None:
        conn = connect_db(db_file)
        owns_conn = True

    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if owns_conn:
            conn.close()


def get_applied_migrations(conn: sqlite3.Connection) -> set[int]:
    try:
        rows = conn.execute("SELECT version FROM schema_meta").fetchall()
        return {r["version"] for r in rows}
    except sqlite3.OperationalError:
        return set()


def init_db(db_file: Optional[Path | str] = None) -> None:
    if not MIGRATIONS_DIR.exists():
        raise RuntimeError(f"Migrations directory not found: {MIGRATIONS_DIR}")
    conn = connect_db(db_file)
    try:
        applied = get_applied_migrations(conn)
        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        for m_file in migration_files:
            try:
                version = int(m_file.stem.split("_")[0])
            except ValueError:
                continue

            if version not in applied:
                sql_script = m_file.read_text(encoding="utf-8")
                now_str = datetime.now().isoformat()
                script = f"""
BEGIN IMMEDIATE;
{sql_script}
INSERT OR IGNORE INTO schema_meta(version, applied_at)
VALUES ({version}, '{now_str}');
COMMIT;
"""
                try:
                    conn.executescript(script)
                except Exception:
                    try:
                        conn.execute("ROLLBACK")
                    except sqlite3.Error:
                        pass
                    raise
    finally:
        conn.close()


def backup_db(dest_path: Optional[Path | str] = None, source_file: Optional[Path | str] = None) -> str:
    src_conn = connect_db(source_file)
    if dest_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_path = BACKUP_DIR / f"app_backup_{timestamp}.db"

    dest_conn = sqlite3.connect(str(dest_path))
    try:
        src_conn.backup(dest_conn)
        return str(dest_path)
    finally:
        dest_conn.close()
        src_conn.close()
