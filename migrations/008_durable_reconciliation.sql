CREATE TABLE IF NOT EXISTS reconciliation_queue (
    id TEXT PRIMARY KEY,
    target_url TEXT NOT NULL,
    content TEXT NOT NULL,
    account_id TEXT,
    queue_item_id TEXT,
    attempt INTEGER NOT NULL DEFAULT 0,
    next_reconcile_at TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    last_error TEXT,
    result_url TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reconcile_due ON reconciliation_queue(status, next_reconcile_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_reconcile_active_unique
ON reconciliation_queue(target_url, account_id, content)
WHERE status IN ('pending','running');
