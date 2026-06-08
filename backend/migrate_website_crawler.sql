-- Non-destructive database migration for website crawler feature
-- Run this against your PostgreSQL database

-- 1. Create website_sources table
CREATE TABLE IF NOT EXISTS website_sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    url VARCHAR NOT NULL UNIQUE,
    site_type VARCHAR NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    last_fetch_new_count INTEGER DEFAULT 0,
    last_fetch_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Add new columns to messages table
ALTER TABLE messages 
ADD COLUMN IF NOT EXISTS website_post_id VARCHAR,
ADD COLUMN IF NOT EXISTS website_source_id INTEGER REFERENCES website_sources(id) ON DELETE CASCADE,
ADD COLUMN IF NOT EXISTS source_type VARCHAR DEFAULT 'telegram';

-- 3. Make channel_id nullable in messages table
ALTER TABLE messages 
ALTER COLUMN channel_id DROP NOT NULL;

-- 4. Add new columns to jobs table
ALTER TABLE jobs 
ADD COLUMN IF NOT EXISTS website_source_id INTEGER REFERENCES website_sources(id) ON DELETE CASCADE;

-- 5. Make channel_id nullable in jobs table
ALTER TABLE jobs 
ALTER COLUMN channel_id DROP NOT NULL;

-- 6. Add new columns to developers table
ALTER TABLE developers 
ADD COLUMN IF NOT EXISTS website_source_id INTEGER REFERENCES website_sources(id) ON DELETE CASCADE;

-- 7. Make channel_id nullable in developers table
ALTER TABLE developers 
ALTER COLUMN channel_id DROP NOT NULL;

-- 8. Create indexes for new columns
CREATE INDEX IF NOT EXISTS ix_messages_website_post_id ON messages(website_post_id);
CREATE INDEX IF NOT EXISTS ix_messages_website_source_id ON messages(website_source_id);
CREATE INDEX IF NOT EXISTS ix_jobs_website_source_id ON jobs(website_source_id);
CREATE INDEX IF NOT EXISTS ix_developers_website_source_id ON developers(website_source_id);
