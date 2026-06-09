-- Add extraction_prompt column to website_sources table
ALTER TABLE website_sources 
ADD COLUMN IF NOT EXISTS extraction_prompt TEXT;
