-- Add operations table for tracking ongoing operations
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

-- Create index for faster queries on running operations
CREATE INDEX IF NOT EXISTS idx_operations_status ON operations(status);
CREATE INDEX IF NOT EXISTS idx_operations_channel ON operations(channel_id);
