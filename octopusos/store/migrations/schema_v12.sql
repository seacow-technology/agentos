-- Migration v12: Task Routing Support
-- Adds routing fields to tasks table for PR-2 (Chat→Task Router Integration)

-- Add routing fields to tasks table
ALTER TABLE tasks ADD COLUMN route_plan_json TEXT DEFAULT NULL;
ALTER TABLE tasks ADD COLUMN requirements_json TEXT DEFAULT NULL;
ALTER TABLE tasks ADD COLUMN selected_instance_id TEXT DEFAULT NULL;
ALTER TABLE tasks ADD COLUMN router_version TEXT DEFAULT NULL;

-- Add index for selected_instance_id for queries
CREATE INDEX IF NOT EXISTS idx_tasks_selected_instance ON tasks(selected_instance_id);

-- Update schema version
INSERT OR REPLACE INTO schema_version (version) VALUES ('0.12.0');
