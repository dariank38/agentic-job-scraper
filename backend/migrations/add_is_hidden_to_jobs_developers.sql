-- Add is_hidden column to jobs and developers tables for soft-delete
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN DEFAULT FALSE;
ALTER TABLE developers ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN DEFAULT FALSE;
