-- Add state to joined_groups
ALTER TABLE joined_groups ADD COLUMN state TEXT NOT NULL DEFAULT 'unknown';
CREATE INDEX IF NOT EXISTS idx_joined_groups_state ON joined_groups(state, joined_at DESC);
