/**
 * SkillOS Service
 *
 * API functions for SkillOS:
 * - Skills management
 * - Extensions management
 * - Extension templates
 * - Extension execution
 * - Extension governance
 */

import { get, post, put, del } from '@platform/http';

// ============================================================================
// Temporary Types (Will be replaced by @modules imports in A8)
// ============================================================================

export interface Skill {
  id: string;
  name: string;
  description?: string;
  version: string;
  status: 'installed' | 'available' | 'disabled';
  created_at: string;
}

export interface ListSkillsRequest {
  status?: string;
  page?: number;
  limit?: number;
}

export interface ListSkillsResponse {
  skills: Skill[];
  total: number;
}

export interface GetSkillResponse {
  skill: Skill;
}

export interface InstallSkillRequest {
  skill_id: string;
  version?: string;
}

export interface InstallSkillResponse {
  skill: Skill;
}

export interface Extension {
  id: string;
  name: string;
  description?: string;
  version: string;
  status: 'enabled' | 'disabled';
  created_at: string;
}

export interface ListExtensionsRequest {
  status?: string;
  page?: number;
  limit?: number;
}

export interface ListExtensionsResponse {
  extensions: Extension[];
  total: number;
}

export interface GetExtensionResponse {
  extension: Extension;
}

export interface CreateExtensionRequest {
  name: string;
  description?: string;
  code: string;
  config?: Record<string, unknown>;
}

export interface CreateExtensionResponse {
  extension: Extension;
}

export interface UpdateExtensionRequest {
  name?: string;
  description?: string;
  code?: string;
  config?: Record<string, unknown>;
}

export interface UpdateExtensionResponse {
  extension: Extension;
}

export interface EnableExtensionResponse {
  extension: Extension;
}

export interface DisableExtensionResponse {
  extension: Extension;
}

export interface ExtensionTemplate {
  id: string;
  name: string;
  description?: string;
  template_code: string;
  category: string;
}

export interface ListExtensionTemplatesRequest {
  category?: string;
  page?: number;
  limit?: number;
}

export interface ListExtensionTemplatesResponse {
  templates: ExtensionTemplate[];
  total: number;
}

export interface GetExtensionTemplateResponse {
  template: ExtensionTemplate;
}

export interface ExecuteExtensionRequest {
  input?: Record<string, unknown>;
  context?: Record<string, unknown>;
}

export interface ExecuteExtensionResponse {
  output: Record<string, unknown>;
  execution_time_ms: number;
  status: 'success' | 'failure';
}

export interface ExtensionGovernanceRule {
  id: string;
  rule_type: string;
  config: Record<string, unknown>;
  enabled: boolean;
}

export interface ListExtensionGovernanceRulesResponse {
  rules: ExtensionGovernanceRule[];
  total: number;
}

export interface ValidateExtensionRequest {
  code: string;
}

export interface ValidateExtensionResponse {
  valid: boolean;
  errors?: string[];
  warnings?: string[];
}

// ============================================================================
// Service Functions
// ============================================================================

export const skillosService = {
  // Skills Management
  async listSkills(params?: ListSkillsRequest): Promise<ListSkillsResponse> {
    return get('/api/skills', { params });
  },

  async getSkill(id: string): Promise<GetSkillResponse> {
    return get(`/api/skills/${id}`);
  },

  async installSkill(data: InstallSkillRequest): Promise<InstallSkillResponse> {
    return post('/api/skills/install', data);
  },

  async uninstallSkill(id: string): Promise<void> {
    return post(`/api/skills/${id}/uninstall`);
  },

  async enableSkill(id: string): Promise<{ skill: Skill }> {
    return post(`/api/skills/${id}/enable`);
  },

  async disableSkill(id: string): Promise<{ skill: Skill }> {
    return post(`/api/skills/${id}/disable`);
  },

  // Extensions Management
  async listExtensions(params?: ListExtensionsRequest): Promise<ListExtensionsResponse> {
    return get('/api/extensions', { params });
  },

  async getExtension(id: string): Promise<GetExtensionResponse> {
    return get(`/api/extensions/${id}`);
  },

  async createExtension(data: CreateExtensionRequest): Promise<CreateExtensionResponse> {
    return post('/api/extensions', data);
  },

  async updateExtension(id: string, data: UpdateExtensionRequest): Promise<UpdateExtensionResponse> {
    return put(`/api/extensions/${id}`, data);
  },

  async deleteExtension(id: string): Promise<void> {
    return del(`/api/extensions/${id}`);
  },

  async enableExtension(id: string): Promise<EnableExtensionResponse> {
    return post(`/api/extensions/${id}/enable`);
  },

  async disableExtension(id: string): Promise<DisableExtensionResponse> {
    return post(`/api/extensions/${id}/disable`);
  },

  // Extension Templates
  async listExtensionTemplates(params?: ListExtensionTemplatesRequest): Promise<ListExtensionTemplatesResponse> {
    return get('/api/extensions/templates', { params });
  },

  async getExtensionTemplate(id: string): Promise<GetExtensionTemplateResponse> {
    return get(`/api/extensions/templates/${id}`);
  },

  async createExtensionFromTemplate(templateId: string, data: { name: string; variables?: Record<string, unknown> }): Promise<CreateExtensionResponse> {
    return post(`/api/extensions/templates/${templateId}/create`, data);
  },

  // Extension Execution
  async executeExtension(id: string, data?: ExecuteExtensionRequest): Promise<ExecuteExtensionResponse> {
    return post(`/api/extensions/execute/${id}`, data);
  },

  async validateExtension(data: ValidateExtensionRequest): Promise<ValidateExtensionResponse> {
    return post('/api/extensions/validate', data);
  },

  // Extension Governance
  async listExtensionGovernanceRules(): Promise<ListExtensionGovernanceRulesResponse> {
    return get('/api/extensions_governance/rules');
  },

  async getExtensionGovernanceStatus(id: string): Promise<{ status: Record<string, unknown> }> {
    return get(`/api/extensions_governance/${id}/status`);
  },

  async requestExtensionApproval(id: string): Promise<{ approval_request_id: string }> {
    return post(`/api/extensions_governance/${id}/request-approval`);
  },

  // Extension Installation
  async installExtensionUpload(file: File): Promise<{ install_id: string; extension_id?: string; status: string }> {
    const formData = new FormData();
    formData.append('file', file);
    return post('/api/extensions/install', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },

  async installExtensionUrl(url: string, sha256?: string): Promise<{ install_id: string; extension_id?: string; status: string }> {
    return post('/api/extensions/install-url', { url, sha256 });
  },

  async getInstallProgress(installId: string): Promise<{
    install_id: string;
    extension_id: string;
    status: string;
    progress: number;
    current_step?: string;
    total_steps?: number;
    completed_steps?: number;
    error?: string;
  }> {
    return get(`/api/extensions/install/${installId}`);
  },

  // Extension Configuration
  async getExtensionConfig(id: string): Promise<{ config: Record<string, unknown> }> {
    return get(`/api/extensions/${id}/config`);
  },

  async updateExtensionConfig(id: string, config: Record<string, unknown>): Promise<{ success: boolean }> {
    return put(`/api/extensions/${id}/config`, { config });
  },
};
