-- Add CASCADE delete to operations.channel_id foreign key
ALTER TABLE operations DROP CONSTRAINT operations_channel_id_fkey;
ALTER TABLE operations ADD CONSTRAINT operations_channel_id_fkey FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE;
