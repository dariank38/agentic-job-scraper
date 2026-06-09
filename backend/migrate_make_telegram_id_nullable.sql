-- Make telegram_id nullable in messages table for website sources
ALTER TABLE messages 
ALTER COLUMN telegram_id DROP NOT NULL;
