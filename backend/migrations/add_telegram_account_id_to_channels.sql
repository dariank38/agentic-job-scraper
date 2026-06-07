-- Migration: Add telegram_account_id column to channels table
-- Run this SQL to add the foreign key to associate channels with Telegram accounts

ALTER TABLE channels ADD COLUMN IF NOT EXISTS telegram_account_id INTEGER REFERENCES telegram_accounts(id);
