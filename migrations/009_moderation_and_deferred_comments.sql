CREATE TABLE IF NOT EXISTS group_moderation_registry (
    group_url TEXT PRIMARY KEY,
    requires_approval INTEGER NOT NULL DEFAULT 1,
    evidence TEXT NOT NULL,
    confirmed_count INTEGER NOT NULL DEFAULT 1,
    last_confirmed_at TEXT NOT NULL,
    last_profile_id TEXT
);

CREATE TABLE IF NOT EXISTS deferred_first_comments (
    id TEXT PRIMARY KEY,
    group_url TEXT NOT NULL,
    content TEXT NOT NULL,
    account_id TEXT,
    brand_key TEXT NOT NULL,
    comment_text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    post_url TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(group_url, content, account_id)
);

CREATE INDEX IF NOT EXISTS idx_deferred_comment_status
ON deferred_first_comments(status, updated_at);

ALTER TABLE reconciliation_queue ADD COLUMN reconcile_kind TEXT NOT NULL DEFAULT 'uncertain';