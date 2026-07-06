-- Merged database migrations for Agentic Job Scraper
-- Apply this file once to bring an existing database up to date.
-- Each statement uses IF NOT EXISTS / DROP IF EXISTS to be idempotent.

-- 1. telegram_accounts table (must exist before channels references it)
-- Migration: Add telegram_accounts table for multi-account support
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

CREATE INDEX IF NOT EXISTS idx_telegram_accounts_is_active ON telegram_accounts(is_active);
CREATE INDEX IF NOT EXISTS idx_telegram_accounts_is_authenticated ON telegram_accounts(is_authenticated);

-- 2. phone_code_hash for telegram_accounts authentication flow
ALTER TABLE telegram_accounts ADD COLUMN IF NOT EXISTS phone_code_hash VARCHAR(255);

-- 3. telegram_account_id foreign key on channels
ALTER TABLE channels ADD COLUMN IF NOT EXISTS telegram_account_id INTEGER REFERENCES telegram_accounts(id);

-- 4. last fetch tracking on channels
ALTER TABLE channels ADD COLUMN IF NOT EXISTS last_fetch_new_count INTEGER DEFAULT 0;
ALTER TABLE channels ADD COLUMN IF NOT EXISTS last_fetch_at TIMESTAMP;

-- 5. website crawler foundation (website_sources table and website source columns)
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

ALTER TABLE messages
ADD COLUMN IF NOT EXISTS website_post_id VARCHAR,
ADD COLUMN IF NOT EXISTS website_source_id INTEGER REFERENCES website_sources(id) ON DELETE CASCADE,
ADD COLUMN IF NOT EXISTS source_type VARCHAR DEFAULT 'telegram';

ALTER TABLE messages
ALTER COLUMN channel_id DROP NOT NULL;

ALTER TABLE messages
ALTER COLUMN telegram_id DROP NOT NULL;

ALTER TABLE jobs
ADD COLUMN IF NOT EXISTS website_source_id INTEGER REFERENCES website_sources(id) ON DELETE CASCADE;

ALTER TABLE jobs
ALTER COLUMN channel_id DROP NOT NULL;

ALTER TABLE developers
ADD COLUMN IF NOT EXISTS website_source_id INTEGER REFERENCES website_sources(id) ON DELETE CASCADE;

ALTER TABLE developers
ALTER COLUMN channel_id DROP NOT NULL;

CREATE INDEX IF NOT EXISTS ix_messages_website_post_id ON messages(website_post_id);
CREATE INDEX IF NOT EXISTS ix_messages_website_source_id ON messages(website_source_id);
CREATE INDEX IF NOT EXISTS ix_jobs_website_source_id ON jobs(website_source_id);
CREATE INDEX IF NOT EXISTS ix_developers_website_source_id ON developers(website_source_id);

-- 6. cookies on website_sources for authenticated scraping
ALTER TABLE website_sources ADD COLUMN IF NOT EXISTS cookies TEXT;

-- 7. extraction_prompt on website_sources for custom extraction
ALTER TABLE website_sources ADD COLUMN IF NOT EXISTS extraction_prompt TEXT;

-- 8. source_type on jobs and make message_id nullable for website sources
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS source_type VARCHAR(20);
ALTER TABLE jobs ALTER COLUMN message_id DROP NOT NULL;
UPDATE jobs SET source_type = 'telegram' WHERE message_id IS NOT NULL AND source_type IS NULL;
CREATE INDEX IF NOT EXISTS idx_jobs_source_type ON jobs(source_type);

-- 9. analysis_text on messages for condensed analysis input
ALTER TABLE messages ADD COLUMN IF NOT EXISTS analysis_text TEXT;

-- 10. message analysis flags
ALTER TABLE messages ADD COLUMN IF NOT EXISTS needs_reanalysis BOOLEAN DEFAULT FALSE;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS analysis_status VARCHAR(50) DEFAULT 'pending';

-- 11. skip_reason on messages
ALTER TABLE messages ADD COLUMN IF NOT EXISTS skip_reason TEXT;

-- 12. channel_name on jobs
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS channel_name VARCHAR(255);

-- 13. is_hidden soft-delete flags on jobs and developers
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN DEFAULT FALSE;
ALTER TABLE developers ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN DEFAULT FALSE;

-- 14. is_favorite on jobs
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS is_favorite BOOLEAN DEFAULT FALSE;

-- 15. fix skills column defaults
ALTER TABLE jobs ALTER COLUMN skills DROP DEFAULT;
ALTER TABLE jobs ALTER COLUMN skills SET DEFAULT NULL;
ALTER TABLE developers ALTER COLUMN skills DROP DEFAULT;
ALTER TABLE developers ALTER COLUMN skills SET DEFAULT NULL;

-- 16. make developers.message_id nullable for cleanup retention
ALTER TABLE developers ALTER COLUMN message_id DROP NOT NULL;

-- 17. operations table (depends on channels)
CREATE TABLE IF NOT EXISTS operations (
    id SERIAL PRIMARY KEY,
    operation_type VARCHAR(50) NOT NULL,
    channel_id INTEGER REFERENCES channels(id),
    channel_username VARCHAR(255),
    status VARCHAR(50) DEFAULT 'running',
    current INTEGER DEFAULT 0,
    total INTEGER DEFAULT 0,
    analyzed INTEGER DEFAULT 0,
    jobs_found INTEGER DEFAULT 0,
    developers_found INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_operations_status ON operations(status);
CREATE INDEX IF NOT EXISTS idx_operations_channel ON operations(channel_id);

-- 18. add CASCADE delete to operations.channel_id
ALTER TABLE operations DROP CONSTRAINT IF EXISTS operations_channel_id_fkey;
ALTER TABLE operations ADD CONSTRAINT operations_channel_id_fkey FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE;

-- 19. analysis_runs table (depends on channels)
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

CREATE INDEX IF NOT EXISTS idx_analysis_runs_status ON analysis_runs(status);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_channel ON analysis_runs(channel_id);

-- 20. Drop deprecated autonomous system tables
DROP TABLE IF EXISTS autonomous_states;
DROP TABLE IF EXISTS fetch_outcomes;
DROP TABLE IF EXISTS source_scorings;

-- 21. Jobees-compatible fields and publish tracking on jobs
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS salary VARCHAR(120);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS salary_level VARCHAR(20);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS category VARCHAR(40);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS priority VARCHAR(4);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS jd TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS hr_contact VARCHAR(255);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS hr_contact_type VARCHAR(20) DEFAULT 'telegram';
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS channel_contact VARCHAR(255);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS channel_contact_type VARCHAR(20) DEFAULT 'telegram';
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS published_to_jobees BOOLEAN DEFAULT FALSE;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS published_at TIMESTAMP;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS jobees_job_id VARCHAR(255);
CREATE INDEX IF NOT EXISTS idx_jobs_published_to_jobees ON jobs(published_to_jobees);
