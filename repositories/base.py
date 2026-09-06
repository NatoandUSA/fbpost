"""Base repository providing database access and serialization helpers."""

import json
from typing import Any, Optional
import sqlite3

from db import connect_db, transaction


class BaseRepository:
    def __init__(self, db_file: Optional[str] = None):
        self.db_file = db_file

    def get_conn(self) -> sqlite3.Connection:
        return connect_db(self.db_file)

    def transaction(self, conn: Optional[sqlite3.Connection] = None):
        return transaction(conn, db_file=self.db_file)

    @staticmethod
    def dumps(obj: Any) -> str:
        return json.dumps(obj, ensure_ascii=False)

    @staticmethod
    def loads(val: Optional[str], default: Any = None) -> Any:
        if not val:
            return default
        try:
            return json.loads(val)
        except (ValueError, TypeError):
            return default
