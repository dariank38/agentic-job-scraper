-- Make developer.message_id nullable to allow keeping developers when messages are deleted
-- This allows the cleanup feature to delete old messages (and their jobs) while preserving developers

ALTER TABLE developers ALTER COLUMN message_id DROP NOT NULL;
