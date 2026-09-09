CREATE TABLE IF NOT EXISTS group_catalog (
    id TEXT PRIMARY KEY,
    canonical_url TEXT NOT NULL UNIQUE,
    facebook_group_id TEXT,
    name TEXT NOT NULL DEFAULT '',
    privacy TEXT NOT NULL DEFAULT '',
    member_count INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'manual',
    enabled INTEGER NOT NULL DEFAULT 1,
    auto_post_enabled INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_group_catalog_enabled
ON group_catalog(enabled, member_count DESC);
CREATE TABLE IF NOT EXISTS profile_presets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    profile_names_json TEXT NOT NULL DEFAULT '[]',
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workflow_tasks (
    id TEXT PRIMARY KEY,
    job_id TEXT,
    task_key TEXT NOT NULL UNIQUE,
    action TEXT NOT NULL,
    profile_id TEXT,
    target_url TEXT NOT NULL DEFAULT '',
    phase TEXT NOT NULL DEFAULT 'QUEUED',
    submission_status TEXT NOT NULL DEFAULT 'NOT_SUBMITTED',
    verification_status TEXT NOT NULL DEFAULT 'NOT_STARTED',
    state TEXT NOT NULL DEFAULT 'queued',
    progress INTEGER NOT NULL DEFAULT 0,
    result_url TEXT NOT NULL DEFAULT '',
    error_code TEXT,
    error_message TEXT,
    evidence_dir TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_workflow_tasks_job
ON workflow_tasks(job_id, state, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_tasks_profile
ON workflow_tasks(profile_id, state, updated_at DESC);

CREATE TABLE IF NOT EXISTS workflow_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    phase TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(task_id) REFERENCES workflow_tasks(id) ON DELETE CASCADE,
    UNIQUE(task_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_workflow_events_task
ON workflow_events(task_id, seq);
