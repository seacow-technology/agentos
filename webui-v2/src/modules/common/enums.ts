/**
 * Common enumerations used across modules
 */

// Task Status
export enum TaskStatus {
  DRAFT = 'draft',
  APPROVED = 'approved',
  QUEUED = 'queued',
  RUNNING = 'running',
  COMPLETED = 'completed',
  SUCCEEDED = 'succeeded',
  FAILED = 'failed',
  ERROR = 'error',
  PENDING = 'pending',
}

// Priority Levels
export enum Priority {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
}

// Project Status
export enum ProjectStatus {
  ACTIVE = 'active',
  ARCHIVED = 'archived',
  DELETED = 'deleted',
}

// Repository Role
export enum RepoRole {
  CODE = 'code',
  DOCS = 'docs',
  TESTS = 'tests',
  CONFIG = 'config',
  DATA = 'data',
  INFRA = 'infra',
  MONO_SUBDIR = 'mono-subdir',
}

// Provider Type
export enum ProviderType {
  LOCAL = 'local',
  CLOUD = 'cloud',
}

// Provider State
export enum ProviderState {
  IDLE = 'idle',
  STARTING = 'starting',
  RUNNING = 'running',
  STOPPING = 'stopping',
  ERROR = 'error',
  UNKNOWN = 'unknown',
}

// Skill Status
export enum SkillStatus {
  ENABLED = 'enabled',
  DISABLED = 'disabled',
  IMPORTED_DISABLED = 'imported_disabled',
}

// Memory Source Type
export enum MemorySourceType {
  TASK = 'task',
  SESSION = 'session',
  MANUAL = 'manual',
  RULE_EXTRACTION = 'rule_extraction',
  EXPLICIT = 'explicit',
  SYSTEM = 'system',
}
