-- Migration: Add autonomous system tables
-- Run this against the existing PostgreSQL database.

CREATE TABLE IF NOT EXISTS autonomous_states (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fetch_outcomes (
    id SERIAL PRIMARY KEY,
    source_id INTEGER,
    source_type VARCHAR(50) DEFAULT 'website',
    fetched_at TIMESTAMP DEFAULT NOW(),
    new_jobs_found INTEGER DEFAULT 0,
    new_messages INTEGER DEFAULT 0,
    duration_seconds INTEGER,
    error_type VARCHAR(50),
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_fetch_outcomes_source_id ON fetch_outcomes(source_id);
CREATE INDEX IF NOT EXISTS idx_fetch_outcomes_fetched_at ON fetch_outcomes(fetched_at);

CREATE TABLE IF NOT EXISTS source_scorings (
    source_id INTEGER PRIMARY KEY,
    source_type VARCHAR(50) NOT NULL,
    hourly_yield_24h INTEGER DEFAULT 0,
    hourly_yield_7d INTEGER DEFAULT 0,
    best_window_start VARCHAR(10),
    best_window_end VARCHAR(10),
    recommended_interval_minutes INTEGER DEFAULT 60,
    consecutive_failures INTEGER DEFAULT 0,
    last_optimized_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
