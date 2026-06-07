-- Migration: Add channel_name column to jobs table
-- Run this SQL to add the channel name field for reference when job details are incomplete

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS channel_name VARCHAR(255);
