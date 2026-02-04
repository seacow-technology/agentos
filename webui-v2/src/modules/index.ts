/**
 * Modules - Central Export
 *
 * All DTO types organized by 7 OS domains + system
 */

// Common types (used across modules)
export * from './common'

// 7 OS Modules
export * as AgentOS from './agentos'
export * as MemoryOS from './memoryos'
export * as BrainOS from './brainos'
export * as SkillOS from './skillos'
export * as NetworkOS from './networkos'
export * as CommunicationOS from './communicationos'
export * as AppOS from './appos'

// System (config, providers, models)
export * as System from './system'
