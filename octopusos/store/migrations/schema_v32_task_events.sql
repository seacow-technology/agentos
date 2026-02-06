-- Migration v0.32: Task Events System for Runner UI Visualization
-- Description: Event-driven data foundation for pipeline factory-style UI
-- Purpose: Enable real-time task execution progress visualization
-- Migration from v0.31 -> v0.32
--
-- Background:
--   - AgentOS needs a "pipeline factory" style UI for non-technical users
--   - task_audits is for audit trails (user decisions, governance)
--   - task_events is for runner lifecycle visualization (phases, progress, span relationships)
--
-- Design Principles:
--   - Strict monotonic sequence per task (seq field)
--   - Span-based hierarchy (span_id, parent_span_id) for parallel work items
--   - Phase tracking (planning/executing/verifying/recovery)
--   - Actor attribution (runner/supervisor/worker/lease/recovery)
--   - Evidence references in payload (checkpoint_id, artifact_id, etc.)
--
-- Use Cases:
--   - Real-time pipeline graph rendering
--   - Timeline view with phase transitions
--   - Work item progress tracking (parallel branches)
--   - Next-step prediction based on event history
--
-- Reference:
--   - PR-V1: Runner UI Event Model & API Infrastructure
--
-- ============================================
-- Phase 1: Create task_events Table
-- ============================================

CREATE TABLE IF NOT EXISTS task_events (
    -- Primary key
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Task association
    task_id TEXT NOT NULL,

    -- Event classification
    event_type TEXT NOT NULL,         -- 'runner_spawn', 'phase_enter', 'phase_exit', 'checkpoint_commit',
                                       -- 'work_item_start', 'work_item_complete', 'evidence_collected', etc.

    -- Phase context
    phase TEXT,                        -- 'planning', 'executing', 'verifying', 'recovery', null (for system events)

    -- Actor attribution
    actor TEXT NOT NULL,               -- 'runner', 'supervisor', 'worker', 'lease', 'recovery', 'system'

    -- Span-based hierarchy (for parallel work items and branching)
    span_id TEXT NOT NULL,             -- Unique span identifier (ULID or UUID)
    parent_span_id TEXT,               -- Parent span (null for main runner span)

    -- Strict monotonic sequence (per task_id)
    seq INTEGER NOT NULL,              -- Strictly increasing sequence number (per task_id)

    -- Event payload (JSON)
    payload TEXT NOT NULL DEFAULT '{}', -- JSON containing:
                                        --   - progress: {current: 1, total: 3, percentage: 33}
                                        --   - evidence_refs: {checkpoint_id: "...", artifact_id: "..."}
                                        --   - explanation: "Completed planning phase with 3 steps"
                                        --   - work_item_id: "..." (if applicable)
                                        --   - error_code: "..." (if error)

    -- Timestamp
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key constraints
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);

-- ============================================
-- Phase 2: Indexes for Performance
-- ============================================

-- Index 1: Primary query pattern - Get events for a task ordered by seq
CREATE INDEX IF NOT EXISTS idx_task_events_task_seq
ON task_events(task_id, seq ASC);

-- Index 2: Time-based query (pagination by created_at)
CREATE INDEX IF NOT EXISTS idx_task_events_task_created
ON task_events(task_id, created_at DESC);

-- Index 3: Span hierarchy queries (find children of a span)
CREATE INDEX IF NOT EXISTS idx_task_events_parent_span
ON task_events(parent_span_id)
WHERE parent_span_id IS NOT NULL;

-- Index 4: Phase-based filtering
CREATE INDEX IF NOT EXISTS idx_task_events_task_phase
ON task_events(task_id, phase)
WHERE phase IS NOT NULL;

-- Index 5: Event type queries (for event-driven processing)
CREATE INDEX IF NOT EXISTS idx_task_events_type_created
ON task_events(event_type, created_at DESC);

-- ============================================
-- Phase 3: Seq Generation Support
-- ============================================

-- Create a helper table for per-task sequence counters
-- This ensures strict monotonic increment even under concurrent writes
CREATE TABLE IF NOT EXISTS task_event_seq_counters (
    task_id TEXT PRIMARY KEY,
    next_seq INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);

-- Index for quick lookup
CREATE INDEX IF NOT EXISTS idx_event_seq_counters_task
ON task_event_seq_counters(task_id);

-- ============================================
-- Phase 4: Trigger for Seq Enforcement
-- ============================================

-- Trigger 1: Initialize seq counter when first event is inserted for a task
CREATE TRIGGER IF NOT EXISTS init_task_event_seq_counter
AFTER INSERT ON task_events
FOR EACH ROW
WHEN NOT EXISTS (SELECT 1 FROM task_event_seq_counters WHERE task_id = NEW.task_id)
BEGIN
    INSERT INTO task_event_seq_counters (task_id, next_seq)
    VALUES (NEW.task_id, NEW.seq + 1);
END;

-- ============================================
-- Phase 5: Usage Examples & Documentation
-- ============================================

-- ===== Example 1: Insert a runner spawn event =====
--
-- INSERT INTO task_events (task_id, event_type, phase, actor, span_id, parent_span_id, seq, payload)
-- VALUES (
--     'task_01xyz',
--     'runner_spawn',
--     NULL,
--     'runner',
--     'span_main_001',
--     NULL,
--     1,
--     json_object(
--         'runner_pid', 12345,
--         'runner_version', 'v0.4.0',
--         'explanation', 'Runner process spawned for task execution'
--     )
-- );

-- ===== Example 2: Insert a phase transition event =====
--
-- INSERT INTO task_events (task_id, event_type, phase, actor, span_id, parent_span_id, seq, payload)
-- VALUES (
--     'task_01xyz',
--     'phase_enter',
--     'planning',
--     'runner',
--     'span_main_001',
--     NULL,
--     2,
--     json_object(
--         'previous_phase', NULL,
--         'explanation', 'Entered planning phase'
--     )
-- );

-- ===== Example 3: Insert a work item start event (parallel branch) =====
--
-- INSERT INTO task_events (task_id, event_type, phase, actor, span_id, parent_span_id, seq, payload)
-- VALUES (
--     'task_01xyz',
--     'work_item_start',
--     'executing',
--     'worker',
--     'span_work_001',
--     'span_main_001',
--     5,
--     json_object(
--         'work_item_id', 'wi_001',
--         'work_type', 'tool_execution',
--         'explanation', 'Started work item: git status'
--     )
-- );

-- ===== Example 4: Insert a checkpoint commit event =====
--
-- INSERT INTO task_events (task_id, event_type, phase, actor, span_id, parent_span_id, seq, payload)
-- VALUES (
--     'task_01xyz',
--     'checkpoint_commit',
--     'executing',
--     'runner',
--     'span_main_001',
--     NULL,
--     10,
--     json_object(
--         'checkpoint_id', 'ckpt_001',
--         'checkpoint_type', 'iteration_complete',
--         'evidence_refs', json_object(
--             'artifacts', json_array('artifact_001', 'artifact_002')
--         ),
--         'explanation', 'Checkpoint committed after iteration 1'
--     )
-- );

-- ===== Query Pattern 1: Get all events for a task (paginated) =====
--
-- SELECT * FROM task_events
-- WHERE task_id = 'task_01xyz'
--   AND seq > 100  -- Resume from last seen seq
-- ORDER BY seq ASC
-- LIMIT 100;

-- ===== Query Pattern 2: Get latest N events for a task =====
--
-- SELECT * FROM task_events
-- WHERE task_id = 'task_01xyz'
-- ORDER BY seq DESC
-- LIMIT 50;

-- ===== Query Pattern 3: Get span hierarchy (for graph rendering) =====
--
-- WITH RECURSIVE span_tree AS (
--     -- Root span
--     SELECT event_id, task_id, span_id, parent_span_id, event_type, seq, payload
--     FROM task_events
--     WHERE task_id = 'task_01xyz' AND parent_span_id IS NULL
--
--     UNION ALL
--
--     -- Child spans
--     SELECT e.event_id, e.task_id, e.span_id, e.parent_span_id, e.event_type, e.seq, e.payload
--     FROM task_events e
--     INNER JOIN span_tree st ON e.parent_span_id = st.span_id
-- )
-- SELECT * FROM span_tree ORDER BY seq ASC;

-- ===== Query Pattern 4: Get events by phase =====
--
-- SELECT * FROM task_events
-- WHERE task_id = 'task_01xyz' AND phase = 'executing'
-- ORDER BY seq ASC;

-- ===== Query Pattern 5: Get checkpoint events with evidence =====
--
-- SELECT event_id, task_id, seq, json_extract(payload, '$.checkpoint_id') AS checkpoint_id,
--        json_extract(payload, '$.evidence_refs') AS evidence_refs
-- FROM task_events
-- WHERE task_id = 'task_01xyz' AND event_type = 'checkpoint_commit'
-- ORDER BY seq ASC;

-- ============================================
-- Phase 6: Validation Constraints
-- ============================================

-- Constraint 1: Ensure seq is always positive
CREATE TRIGGER IF NOT EXISTS validate_task_event_seq_positive
BEFORE INSERT ON task_events
FOR EACH ROW
WHEN NEW.seq <= 0
BEGIN
    SELECT RAISE(ABORT, 'task_events.seq must be positive (> 0)');
END;

-- Constraint 2: Ensure event_type is not empty
CREATE TRIGGER IF NOT EXISTS validate_task_event_type
BEFORE INSERT ON task_events
FOR EACH ROW
WHEN NEW.event_type IS NULL OR NEW.event_type = ''
BEGIN
    SELECT RAISE(ABORT, 'task_events.event_type cannot be empty');
END;

-- Constraint 3: Ensure actor is not empty
CREATE TRIGGER IF NOT EXISTS validate_task_event_actor
BEFORE INSERT ON task_events
FOR EACH ROW
WHEN NEW.actor IS NULL OR NEW.actor = ''
BEGIN
    SELECT RAISE(ABORT, 'task_events.actor cannot be empty');
END;

-- Constraint 4: Ensure span_id is not empty
CREATE TRIGGER IF NOT EXISTS validate_task_event_span_id
BEFORE INSERT ON task_events
FOR EACH ROW
WHEN NEW.span_id IS NULL OR NEW.span_id = ''
BEGIN
    SELECT RAISE(ABORT, 'task_events.span_id cannot be empty');
END;

-- ============================================
-- Phase 7: Update Schema Version
-- ============================================

INSERT OR REPLACE INTO schema_version (version) VALUES ('0.32.0');

-- ============================================
-- Design Notes
-- ============================================

-- ===== Why task_events instead of extending task_audits? =====
--
-- task_audits:
--   - Purpose: Audit trail for governance and compliance
--   - Contains: User decisions, approval flows, policy violations
--   - Retention: Long-term, regulatory requirements
--   - Schema: Optimized for audit queries (who did what when)
--
-- task_events:
--   - Purpose: Real-time UI visualization and progress tracking
--   - Contains: Runner lifecycle, phase transitions, work item progress
--   - Retention: Short-term, tied to task lifecycle
--   - Schema: Optimized for sequential access and span hierarchy
--
-- Separation of concerns:
--   - task_audits: Immutable audit log (never delete)
--   - task_events: Operational telemetry (can be pruned/archived)
--   - Different query patterns, different indexes, different retention policies

-- ===== Seq Generation Strategy =====
--
-- Option 1: Application-level sequence generator (CHOSEN)
--   - Use task_event_seq_counters table
--   - SELECT + UPDATE in transaction (with SQLiteWriter serialization)
--   - Guarantees strict monotonic increment
--   - No gaps, predictable ordering
--
-- Option 2: Auto-increment per task
--   - SQLite doesn't support per-group auto-increment
--   - Would require complex triggers or application logic
--
-- Option 3: Timestamp-based ordering
--   - Vulnerable to clock skew and concurrent writes
--   - Not suitable for strict ordering requirements

-- ===== Span Hierarchy Model =====
--
-- span_id and parent_span_id create a tree structure:
--
--   Main Runner (span_main)
--   ├── Planning Phase (span_plan)
--   ├── Executing Phase (span_exec)
--   │   ├── Work Item 1 (span_work_1)
--   │   ├── Work Item 2 (span_work_2)  [parallel]
--   │   └── Work Item 3 (span_work_3)  [parallel]
--   └── Verifying Phase (span_verify)
--
-- This enables:
--   - Pipeline graph rendering (show parallel branches)
--   - Progress aggregation (roll up work item progress)
--   - Drill-down navigation (click span to see details)

-- ===== Event Type Vocabulary =====
--
-- System lifecycle:
--   - runner_spawn: Runner process started
--   - runner_exit: Runner process exited
--   - runner_heartbeat: Runner still alive
--
-- Phase transitions:
--   - phase_enter: Entered a new phase
--   - phase_exit: Exited a phase
--
-- Work items:
--   - work_item_start: Work item started
--   - work_item_progress: Work item progress update
--   - work_item_complete: Work item completed
--   - work_item_failed: Work item failed
--
-- Checkpoints:
--   - checkpoint_commit: Checkpoint saved
--   - checkpoint_verified: Checkpoint verification passed
--   - checkpoint_invalid: Checkpoint verification failed
--
-- Evidence:
--   - evidence_collected: Evidence artifact collected
--   - evidence_linked: Evidence linked to checkpoint
--
-- Recovery:
--   - recovery_initiated: Recovery process started
--   - recovery_checkpoint_loaded: Checkpoint restored
--   - recovery_complete: Recovery successful

-- ============================================
-- Performance Considerations
-- ============================================

-- ===== Index Usage =====
--
-- idx_task_events_task_seq:
--   - Primary query: Get events for task ordered by seq
--   - Covers: Pagination, tail logs, event streaming
--
-- idx_task_events_task_created:
--   - Secondary query: Get latest events by timestamp
--   - Covers: Recent events, real-time monitoring
--
-- idx_task_events_parent_span:
--   - Recursive queries: Build span tree
--   - Covers: Graph rendering, hierarchy navigation
--
-- idx_task_events_task_phase:
--   - Phase filtering: Show events in specific phase
--   - Covers: Phase timeline, drill-down views
--
-- idx_task_events_type_created:
--   - Event-driven processing: Subscribe to event types
--   - Covers: Webhooks, integrations, event handlers

-- ===== Estimated Storage =====
--
-- Average event size: ~500 bytes (with JSON payload)
-- Events per task: ~1000 (typical runner lifecycle)
-- 1000 tasks: ~500 MB
-- 10000 tasks: ~5 GB
--
-- Mitigation strategies:
--   - Archive old events (tasks completed > 30 days)
--   - Compress JSON payloads
--   - Implement event pruning policy

-- ===== Concurrent Write Handling =====
--
-- SQLiteWriter serializes all writes to prevent database locks
-- Seq generation must be atomic:
--   1. SELECT next_seq FROM task_event_seq_counters WHERE task_id = ?
--   2. INSERT INTO task_events (task_id, seq, ...) VALUES (?, next_seq, ...)
--   3. UPDATE task_event_seq_counters SET next_seq = next_seq + 1 WHERE task_id = ?
--
-- All three steps must execute in a single transaction via SQLiteWriter.submit()

-- ============================================
-- Completion
-- ============================================
--
-- v0.32 Migration Complete!
--
-- Changes Summary:
-- - Added task_events table (event-driven UI data)
-- - Added task_event_seq_counters table (strict seq generation)
-- - Added 5 performance indexes
-- - Added 4 validation triggers
-- - Supports span-based hierarchy for parallel work items
-- - Supports phase tracking and actor attribution
-- - Optimized for real-time UI streaming and pagination
--
-- Next Steps:
-- 1. Implement EventService for seq generation and event insertion
-- 2. Create API endpoints: GET /api/tasks/{id}/events, GET /api/tasks/{id}/graph
-- 3. Add event emission in Runner, WorkItems, Checkpoints
-- 4. Build WebUI components for timeline and pipeline graph
--
-- Version: v0.32.0
-- Date: 2026-01-29
-- Author: Backend Agent (PR-V1)
-- Reference: Runner UI Visualization System
--
