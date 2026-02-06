-- AgentOS v0.3 Schema Extensions
-- New tables for v0.3 features: FailurePack, LearningPack, PolicyLineage, ResourceBudget

-- FailurePacks: Record structured failures
CREATE TABLE IF NOT EXISTS failure_packs (
    id TEXT PRIMARY KEY,
    run_id INTEGER NOT NULL,
    task_id TEXT NOT NULL,
    failure_type TEXT NOT NULL, -- schema_validation_failure, lock_conflict, etc.
    root_cause_summary TEXT NOT NULL,
    evidence_refs TEXT NOT NULL, -- JSON array
    suggested_actions TEXT, -- JSON array
    retriable BOOLEAN DEFAULT 0,
    risk_delta TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES task_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_failure_packs_run_id ON failure_packs(run_id);
CREATE INDEX IF NOT EXISTS idx_failure_packs_task_id ON failure_packs(task_id);
CREATE INDEX IF NOT EXISTS idx_failure_packs_type ON failure_packs(failure_type);

-- LearningPacks: Record learning proposals
CREATE TABLE IF NOT EXISTS learning_packs (
    id TEXT PRIMARY KEY,
    source_runs TEXT NOT NULL, -- JSON array of run IDs
    pattern TEXT NOT NULL,
    proposed_memory_items TEXT, -- JSON array
    proposed_policy_patch TEXT, -- JSON object
    confidence REAL DEFAULT 0.0,
    verification_plan TEXT,
    status TEXT DEFAULT 'proposed', -- proposed, approved, applied, rejected
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    applied_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_learning_packs_status ON learning_packs(status);
CREATE INDEX IF NOT EXISTS idx_learning_packs_confidence ON learning_packs(confidence);

-- PolicyLineage: Track policy evolution
CREATE TABLE IF NOT EXISTS policy_lineage (
    policy_id TEXT PRIMARY KEY,
    parent_policy_id TEXT,
    source_learning_pack_id TEXT,
    diff TEXT NOT NULL, -- JSON object
    effective_from TIMESTAMP,
    effective_until TIMESTAMP,
    rollback_conditions TEXT, -- JSON object
    status TEXT DEFAULT 'canary', -- canary, active, frozen, rolled_back
    applied_to TEXT, -- JSON object {project_ids, task_types}
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_policy_id) REFERENCES policy_lineage(policy_id),
    FOREIGN KEY (source_learning_pack_id) REFERENCES learning_packs(id)
);

CREATE INDEX IF NOT EXISTS idx_policy_lineage_status ON policy_lineage(status);
CREATE INDEX IF NOT EXISTS idx_policy_lineage_parent ON policy_lineage(parent_policy_id);

-- RunTapes: Complete execution tapes for replay
CREATE TABLE IF NOT EXISTS run_tapes (
    id TEXT PRIMARY KEY,
    run_id INTEGER NOT NULL,
    steps TEXT NOT NULL, -- JSON array of step objects
    metadata TEXT, -- JSON object
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES task_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_run_tapes_run_id ON run_tapes(run_id);

-- ResourceUsage: Track resource consumption
CREATE TABLE IF NOT EXISTS resource_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0,
    execution_time_ms INTEGER DEFAULT 0,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES task_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_resource_usage_run_id ON resource_usage(run_id);

-- Healing Actions: Record healing action executions
CREATE TABLE IF NOT EXISTS healing_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    failure_pack_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    parameters TEXT, -- JSON object
    risk_level TEXT NOT NULL,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN,
    result_summary TEXT,
    FOREIGN KEY (failure_pack_id) REFERENCES failure_packs(id)
);

CREATE INDEX IF NOT EXISTS idx_healing_actions_failure ON healing_actions(failure_pack_id);
CREATE INDEX IF NOT EXISTS idx_healing_actions_type ON healing_actions(action_type);
