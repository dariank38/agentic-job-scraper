-- Add source_type column to jobs table
ALTER TABLE jobs ADD COLUMN source_type VARCHAR(20);

-- Make message_id nullable for website sources
ALTER TABLE jobs ALTER COLUMN message_id DROP NOT NULL;

-- Update existing jobs to have source_type = 'telegram'
UPDATE jobs SET source_type = 'telegram' WHERE message_id IS NOT NULL;

-- Create index on source_type for faster filtering
CREATE INDEX idx_jobs_source_type ON jobs(source_type);
