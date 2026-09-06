-- Schema migration metadata
CREATE TABLE IF NOT EXISTS schema_meta (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

-- Settings and application configuration
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Accounts (Facebook / GPM)
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    name TEXT,
    type TEXT,
    profile_path_or_id TEXT,
    proxy TEXT,
    status TEXT,
    created_at TEXT,
    raw_json TEXT
);

-- Account Vault
CREATE TABLE IF NOT EXISTS vault_entries (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    account_name TEXT NOT NULL,
    email TEXT NOT NULL,
    password TEXT,
    notes TEXT,
    date_added TEXT,
    password_changed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    raw_json TEXT
);

-- Group Registry
CREATE TABLE IF NOT EXISTS groups (
    id TEXT PRIMARY KEY,
    name TEXT,
    url TEXT NOT NULL,
    category TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    raw_json TEXT
);

-- Campaigns
CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    brand TEXT,
    target TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    raw_json TEXT
);

-- Publication Jobs
CREATE TABLE IF NOT EXISTS publication_jobs (
    id TEXT PRIMARY KEY,
    campaign_id TEXT,
    target TEXT,
    content TEXT,
    image_url TEXT,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    approved_at TEXT,
    published_at TEXT,
    error TEXT,
    idempotency_key TEXT,
    raw_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_publication_jobs_state ON publication_jobs(state);
CREATE INDEX IF NOT EXISTS idx_publication_jobs_campaign ON publication_jobs(campaign_id);

-- Manual Group Queue
CREATE TABLE IF NOT EXISTS manual_group_queue (
    id TEXT PRIMARY KEY,
    profile_id TEXT,
    group_url TEXT,
    content TEXT,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    raw_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_manual_group_queue_state ON manual_group_queue(state);

-- Activity Log
CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    profile_id TEXT,
    action TEXT NOT NULL,
    target TEXT,
    content TEXT,
    outcome TEXT
);
CREATE INDEX IF NOT EXISTS idx_activity_log_timestamp ON activity_log(timestamp DESC);

-- Posted Links
CREATE TABLE IF NOT EXISTS posted_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    target TEXT,
    content TEXT,
    note TEXT,
    account_id TEXT,
    status TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_posted_links_created ON posted_links(created_at DESC);

-- Joined Groups
CREATE TABLE IF NOT EXISTS joined_groups (
    id TEXT PRIMARY KEY,
    group_name TEXT,
    keyword TEXT,
    url TEXT,
    account_id TEXT,
    joined_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_joined_groups_joined_at ON joined_groups(joined_at DESC);
