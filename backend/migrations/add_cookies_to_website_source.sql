-- Migration: Add cookies column to website_sources for authenticated scraping

ALTER TABLE website_sources ADD COLUMN IF NOT EXISTS cookies TEXT;
