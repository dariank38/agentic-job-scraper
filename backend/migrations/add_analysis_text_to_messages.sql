-- Add analysis_text column to messages table for condensed text for Ollama analysis
ALTER TABLE messages ADD COLUMN analysis_text TEXT;
