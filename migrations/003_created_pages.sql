-- Created Pages
CREATE TABLE IF NOT EXISTS created_pages (
    id TEXT PRIMARY KEY,
    page_name TEXT NOT NULL,
    category TEXT,
    page_url TEXT,
    account_id TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'created',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_created_pages_account ON created_pages(account_id, created_at DESC);
