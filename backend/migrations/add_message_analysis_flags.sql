-- Migration: Add needs_reanalysis and analysis_status columns to messages table
-- This adds columns to track which messages need re-analysis and their analysis status

-- Add needs_reanalysis column
ALTER TABLE messages ADD COLUMN IF NOT EXISTS needs_reanalysis BOOLEAN DEFAULT FALSE;

-- Add analysis_status column
ALTER TABLE messages ADD COLUMN IF NOT EXISTS analysis_status VARCHAR(50) DEFAULT 'pending';
