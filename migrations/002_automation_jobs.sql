-- Automation Jobs Table for JobManager and Decoupled Subprocess Execution
CREATE TABLE IF NOT EXISTS automation_jobs (
    id TEXT PRIMARY KEY,
    command TEXT NOT NULL,
    account_id TEXT,
    state TEXT NOT NULL DEFAULT 'queued', -- queued, running, success, failed, cancelled, interrupted
    payload_json TEXT,
    pid INTEGER,
    progress_current INTEGER DEFAULT 0,
    progress_total INTEGER DEFAULT 0,
    log_file TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    raw_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_automation_jobs_state ON automation_jobs(state);
CREATE INDEX IF NOT EXISTS idx_automation_jobs_created ON automation_jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_automation_jobs_command ON automation_jobs(command);
