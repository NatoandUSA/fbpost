"""Repository for application configuration and settings."""

from datetime import datetime
from typing import Any, Dict, Optional
from repositories.base import BaseRepository


class SettingsRepository(BaseRepository):
    CONFIG_KEY = "global_config"

    def get_config(self) -> Dict[str, Any]:
        conn = self.get_conn()
        try:
            row = conn.execute("SELECT value_json FROM settings WHERE key = ?", (self.CONFIG_KEY,)).fetchone()
            if row:
                return self.loads(row["value_json"], default={})
            return {}
        finally:
            conn.close()

    def save_config(self, config: Dict[str, Any]) -> bool:
        now_str = datetime.now().isoformat()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO settings (key, value_json, updated_at)
                VALUES (?, ?, ?)
                """,
                (self.CONFIG_KEY, self.dumps(config), now_str),
            )
        return True

    def get_setting(self, key: str, default: Any = None) -> Any:
        conn = self.get_conn()
        try:
            row = conn.execute("SELECT value_json FROM settings WHERE key = ?", (key,)).fetchone()
            if row:
                return self.loads(row["value_json"], default=default)
            return default
        finally:
            conn.close()

    def set_setting(self, key: str, value: Any) -> bool:
        now_str = datetime.now().isoformat()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO settings (key, value_json, updated_at)
                VALUES (?, ?, ?)
                """,
                (key, self.dumps(value), now_str),
            )
        return True
