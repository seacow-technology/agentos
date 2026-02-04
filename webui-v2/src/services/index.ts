/**
 * Services Layer - Unified Export
 *
 * Exports all domain-specific service modules.
 * Each service contains typed API functions that communicate with the backend.
 *
 * Usage:
 *   import { agentosService, memoryosService } from '@services';
 *   const projects = await agentosService.listProjects();
 *
 * Organization:
 * - agentos.service.ts: Projects, Tasks, Repos, Sessions, Task Templates, Dependencies, Events, Audit
 * - memoryos.service.ts: Memory search, timeline, proposals
 * - brainos.service.ts: Knowledge, decisions, review queue, governance, intent, metrics
 * - skillos.service.ts: Skills, extensions, templates, execution, governance
 * - networkos.service.ts: Capabilities, governance dashboard, guardians, execution policies, evidence
 * - communicationos.service.ts: Channels, marketplace, sessions, voice, MCP
 * - appos.service.ts: Application management, lifecycle, status
 * - system.service.ts: Config, providers, models, health, secrets, auth, history, logs, share, preview, snippets, budget, mode, demo, metrics
 */

// AgentOS - Core project and task management
export { agentosService } from './agentos.service';
export type * from './agentos.service';

// MemoryOS - Memory management and proposals
export { memoryosService } from './memoryos.service';
export type * from './memoryos.service';

// BrainOS - Knowledge and decision management
export { brainosService } from './brainos.service';
export type * from './brainos.service';

// SkillOS - Skills and extensions management
export { skillosService } from './skillos.service';
export type * from './skillos.service';

// NetworkOS - Governance and capability management
export { networkosService } from './networkos.service';
export type * from './networkos.service';

// CommunicationOS - Channels and external communication
export { communicationosService } from './communicationos.service';
export type * from './communicationos.service';

// AppOS - Application lifecycle management
export { apposService } from './appos.service';
export type * from './appos.service';

// System - Configuration, providers, models, and system utilities
export { systemService } from './system.service';
export type * from './system.service';
