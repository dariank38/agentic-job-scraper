-- Migration: Add telegram_accounts table for multi-account support
-- Run this SQL to create the new table

CREATE TABLE IF NOT EXISTS telegram_accounts (
    id SERIAL PRIMARY KEY,
    api_id INTEGER NOT NULL,
    api_hash VARCHAR(255) NOT NULL,
    phone_number VARCHAR(50) NOT NULL UNIQUE,
    session_name VARCHAR(255) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    is_authenticated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP
);

-- Create index on is_active for faster queries
CREATE INDEX IF NOT EXISTS idx_telegram_accounts_is_active ON telegram_accounts(is_active);
CREATE INDEX IF NOT EXISTS idx_telegram_accounts_is_authenticated ON telegram_accounts(is_authenticated);
