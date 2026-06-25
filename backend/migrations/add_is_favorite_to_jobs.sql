-- Add is_favorite column to jobs table for favorite job feature
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS is_favorite BOOLEAN DEFAULT FALSE;
