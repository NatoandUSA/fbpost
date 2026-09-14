CREATE TABLE IF NOT EXISTS comment_delivery_events (
    id TEXT PRIMARY KEY,
    group_url TEXT NOT NULL,
    post_url TEXT NOT NULL DEFAULT '',
    profile_id TEXT,
    brand_key TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    url_count INTEGER NOT NULL DEFAULT 0,
    evidence TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_comment_delivery_profile
ON comment_delivery_events(profile_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_comment_delivery_group
ON comment_delivery_events(group_url, status, created_at DESC);

CREATE TABLE IF NOT EXISTS group_comment_policy (
    group_url TEXT PRIMARY KEY,
    rejected_count INTEGER NOT NULL DEFAULT 0,
    cooldown_until TEXT,
    last_status TEXT NOT NULL DEFAULT '',
    last_profile_id TEXT,
    updated_at TEXT NOT NULL
);
