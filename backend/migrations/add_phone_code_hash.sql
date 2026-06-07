-- Migration: Add phone_code_hash column to telegram_accounts table
-- Run this SQL to add the new column for authentication flow

ALTER TABLE telegram_accounts ADD COLUMN IF NOT EXISTS phone_code_hash VARCHAR(255);
