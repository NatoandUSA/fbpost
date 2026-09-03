CREATE TABLE IF NOT EXISTS submissions (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  team       TEXT NOT NULL,
  name       TEXT,
  shop       TEXT,
  data       TEXT NOT NULL,
  appeal     TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_created ON submissions (created_at DESC);
