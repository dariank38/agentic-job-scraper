-- Migration: Add analysis_runs table for tracking analysis/search runs
-- Run this SQL to create the new table

CREATE TABLE IF NOT EXISTS analysis_runs (
    id SERIAL PRIMARY KEY,
    run_type VARCHAR(50) NOT NULL,
    channel_id INTEGER REFERENCES channels(id),
    status VARCHAR(50) DEFAULT 'running',
    messages_fetched INTEGER DEFAULT 0,
    messages_analyzed INTEGER DEFAULT 0,
    jobs_found INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Create index for faster queries on status
CREATE INDEX IF NOT EXISTS idx_analysis_runs_status ON analysis_runs(status);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_channel ON analysis_runs(channel_id);
