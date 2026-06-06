-- Migration: Add last fetch tracking to channels table
-- This adds columns to track the number of new messages fetched and the timestamp of the last fetch

-- Add last_fetch_new_count column
ALTER TABLE channels ADD COLUMN last_fetch_new_count INTEGER DEFAULT 0;

-- Add last_fetch_at column
ALTER TABLE channels ADD COLUMN last_fetch_at TIMESTAMP;
