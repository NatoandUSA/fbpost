ALTER TABLE reconciliation_queue ADD COLUMN origin_job_id TEXT;
CREATE INDEX IF NOT EXISTS idx_reconcile_origin_job ON reconciliation_queue(origin_job_id, status);
