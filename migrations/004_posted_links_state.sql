-- Add url_type and publish_state to posted_links
ALTER TABLE posted_links ADD COLUMN url_type TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE posted_links ADD COLUMN publish_state TEXT NOT NULL DEFAULT 'unknown';
CREATE INDEX IF NOT EXISTS idx_posted_links_state ON posted_links(publish_state, created_at DESC);
