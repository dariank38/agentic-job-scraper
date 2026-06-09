-- Fix skills column default value to avoid "unhashable type: 'list'" error
-- This migration changes the default from list to NULL for both jobs and developers tables

-- Fix jobs table
ALTER TABLE jobs ALTER COLUMN skills DROP DEFAULT;
ALTER TABLE jobs ALTER COLUMN skills SET DEFAULT NULL;

-- Fix developers table
ALTER TABLE developers ALTER COLUMN skills DROP DEFAULT;
ALTER TABLE developers ALTER COLUMN skills SET DEFAULT NULL;
