ALTER TABLE group_moderation_registry ADD COLUMN pending_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE group_moderation_registry ADD COLUMN last_pending_checked_at TEXT;
ALTER TABLE group_moderation_registry ADD COLUMN skip_threshold INTEGER NOT NULL DEFAULT 2;
