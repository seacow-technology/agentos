/**
 * SkillsMarketplaceView - Marketplace-style Skills Management UI
 *
 * PR-0201-2026-6: WebUI Skills 页面 + Marketplace UX
 *
 * Features:
 * - Marketplace card layout for skills
 * - Import dialog (Local + GitHub)
 * - Enable/Disable with Admin Token
 * - Risk levels and permissions display
 * - Detailed skill information
 */

class SkillsMarketplaceView {
    constructor(container) {
        this.container = container;
        this.skills = [];
        this.currentFilter = 'all';
        this.apiClient = window.apiClient || new ApiClient();

        this.init();
    }

    async init() {
        this.render();
        await this.loadSkills();
        this.setupEventListeners();
    }

    render() {
        this.container.innerHTML = `
            <div class="skills-marketplace-view">
                <div class="view-header">
                    <div class="header-left">
                        <h1>Skills Marketplace</h1>
                        <p class="text-sm text-gray-600 mt-1">
                            Import, enable, and manage skills with granular permissions
                        </p>
                    </div>
                    <div class="header-actions">
                        <button class="btn btn-primary" id="import-skill-btn">
                            <span class="material-icons md-18">add</span>
                            Import Skill
                        </button>
                        <button class="btn btn-secondary" id="refresh-skills-btn">
                            <span class="material-icons md-18">refresh</span>
                            Refresh
                        </button>
                    </div>
                </div>

                <div class="filters-bar">
                    <div class="filter-group">
                        <label>Status:</label>
                        <select id="status-filter" class="form-select">
                            <option value="all">All</option>
                            <option value="enabled">Enabled</option>
                            <option value="disabled">Disabled</option>
                            <option value="imported_disabled">Imported (Disabled)</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label>Risk:</label>
                        <select id="risk-filter" class="form-select">
                            <option value="all">All Levels</option>
                            <option value="pure">Pure</option>
                            <option value="io">I/O</option>
                            <option value="action">Action</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label>Source:</label>
                        <select id="source-filter" class="form-select">
                            <option value="all">All Sources</option>
                            <option value="local">Local</option>
                            <option value="github">GitHub</option>
                        </select>
                    </div>
                </div>

                <div id="skills-grid" class="skills-grid">
                    <div class="loading-state">
                        <span class="material-icons spinning">refresh</span>
                        <p>Loading skills...</p>
                    </div>
                </div>

                <div id="empty-state" class="empty-state hidden">
                    <span class="material-icons">extension</span>
                    <h3>No Skills Found</h3>
                    <p>Import your first skill to get started</p>
                    <button class="btn btn-primary" id="import-first-skill-btn">
                        <span class="material-icons md-18">add</span>
                        Import Skill
                    </button>
                </div>
            </div>
        `;
    }

    setupEventListeners() {
        // Import button
        const importBtn = this.container.querySelector('#import-skill-btn');
        const importFirstBtn = this.container.querySelector('#import-first-skill-btn');

        if (importBtn) {
            importBtn.addEventListener('click', () => this.openImportDialog());
        }
        if (importFirstBtn) {
            importFirstBtn.addEventListener('click', () => this.openImportDialog());
        }

        // Refresh button
        const refreshBtn = this.container.querySelector('#refresh-skills-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadSkills(true));
        }

        // Filters
        const statusFilter = this.container.querySelector('#status-filter');
        const riskFilter = this.container.querySelector('#risk-filter');
        const sourceFilter = this.container.querySelector('#source-filter');

        if (statusFilter) {
            statusFilter.addEventListener('change', (e) => this.filterSkills());
        }
        if (riskFilter) {
            riskFilter.addEventListener('change', (e) => this.filterSkills());
        }
        if (sourceFilter) {
            sourceFilter.addEventListener('change', (e) => this.filterSkills());
        }

        // Event delegation for card actions
        this.container.addEventListener('click', (e) => {
            const enableBtn = e.target.closest('[data-action="enable"]');
            const disableBtn = e.target.closest('[data-action="disable"]');
            const viewBtn = e.target.closest('[data-action="view"]');
            const deleteBtn = e.target.closest('[data-action="delete"]');

            if (enableBtn) {
                const skillId = enableBtn.dataset.skillId;
                this.enableSkill(skillId);
            } else if (disableBtn) {
                const skillId = disableBtn.dataset.skillId;
                this.disableSkill(skillId);
            } else if (viewBtn) {
                const skillId = viewBtn.dataset.skillId;
                this.showSkillDetail(skillId);
            } else if (deleteBtn) {
                const skillId = deleteBtn.dataset.skillId;
                this.deleteSkill(skillId);
            }
        });
    }

    async loadSkills(forceRefresh = false) {
        try {
            const gridContainer = this.container.querySelector('#skills-grid');
            if (!gridContainer) return;

            // Show loading state
            if (forceRefresh) {
                gridContainer.innerHTML = `
                    <div class="loading-state">
                        <span class="material-icons spinning">refresh</span>
                        <p>Loading skills...</p>
                    </div>
                `;
            }

            // Call API
            const response = await this.apiClient.get('/api/skills/');

            if (!response.ok) {
                throw new Error(response.error || 'Failed to load skills');
            }

            this.skills = response.data?.skills || response.data || [];

            // Render skills
            this.renderSkillsGrid();

            if (forceRefresh && window.showToast) {
                window.showToast(`Loaded ${this.skills.length} skills`, 'success', 1500);
            }

        } catch (error) {
            console.error('Failed to load skills:', error);

            const gridContainer = this.container.querySelector('#skills-grid');
            if (gridContainer) {
                gridContainer.innerHTML = `
                    <div class="error-state">
                        <span class="material-icons">error</span>
                        <h3>Failed to Load Skills</h3>
                        <p>${error.message}</p>
                        <button class="btn btn-secondary" onclick="location.reload()">
                            Retry
                        </button>
                    </div>
                `;
            }

            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    filterSkills() {
        const statusFilter = this.container.querySelector('#status-filter')?.value || 'all';
        const riskFilter = this.container.querySelector('#risk-filter')?.value || 'all';
        const sourceFilter = this.container.querySelector('#source-filter')?.value || 'all';

        let filtered = this.skills;

        if (statusFilter !== 'all') {
            filtered = filtered.filter(skill => skill.status === statusFilter);
        }

        if (riskFilter !== 'all') {
            filtered = filtered.filter(skill => {
                const manifest = this.parseManifest(skill);
                return manifest.capabilities?.class === riskFilter;
            });
        }

        if (sourceFilter !== 'all') {
            filtered = filtered.filter(skill => skill.source_type === sourceFilter);
        }

        this.renderSkillsGrid(filtered);
    }

    renderSkillsGrid(skillsToRender = null) {
        const skills = skillsToRender || this.skills;
        const gridContainer = this.container.querySelector('#skills-grid');
        const emptyState = this.container.querySelector('#empty-state');

        if (!gridContainer) return;

        if (skills.length === 0) {
            gridContainer.classList.add('hidden');
            if (emptyState) {
                emptyState.classList.remove('hidden');
            }
            return;
        }

        gridContainer.classList.remove('hidden');
        if (emptyState) {
            emptyState.classList.add('hidden');
        }

        gridContainer.innerHTML = skills.map(skill => this.renderSkillCard(skill)).join('');
    }

    renderSkillCard(skill) {
        const manifest = this.parseManifest(skill);
        const riskClass = manifest.capabilities?.class || 'unknown';
        const statusBadge = this.getStatusBadgeHTML(skill.status);
        const riskBadge = this.getRiskBadgeHTML(riskClass);
        const permissions = this.getPermissionsSummary(manifest);

        return `
            <div class="skill-card" data-skill-id="${skill.skill_id}">
                <div class="card-header">
                    <div class="card-title-row">
                        <h3 class="skill-name">${this.escapeHtml(skill.name || skill.skill_id)}</h3>
                        ${statusBadge}
                    </div>
                    <div class="skill-meta">
                        <span class="skill-version">v${skill.version || '1.0.0'}</span>
                        <span class="skill-source">
                            <span class="material-icons md-14">
                                ${skill.source_type === 'github' ? 'cloud' : 'folder'}
                            </span>
                            ${skill.source_type || 'local'}
                        </span>
                    </div>
                </div>

                <div class="card-body">
                    <p class="skill-id">${skill.skill_id}</p>
                    <p class="skill-description">
                        ${this.escapeHtml(manifest.description || 'No description available')}
                    </p>

                    <div class="skill-badges">
                        ${riskBadge}
                        ${skill.trust_level ? `<span class="badge badge-info">Trust: ${skill.trust_level}</span>` : ''}
                    </div>

                    <div class="permissions-summary">
                        <h4>Permissions</h4>
                        ${permissions}
                    </div>
                </div>

                <div class="card-footer">
                    <button class="btn btn-sm btn-secondary" data-action="view" data-skill-id="${skill.skill_id}">
                        <span class="material-icons md-14">info</span>
                        View Details
                    </button>
                    ${this.renderActionButtons(skill)}
                </div>
            </div>
        `;
    }

    renderActionButtons(skill) {
        if (skill.status === 'enabled') {
            return `
                <button class="btn btn-sm btn-warning" data-action="disable" data-skill-id="${skill.skill_id}">
                    <span class="material-icons md-14">block</span>
                    Disable
                </button>
            `;
        } else {
            return `
                <button class="btn btn-sm btn-success" data-action="enable" data-skill-id="${skill.skill_id}">
                    <span class="material-icons md-14">check_circle</span>
                    Enable
                </button>
                <button class="btn btn-sm btn-error" data-action="delete" data-skill-id="${skill.skill_id}">
                    <span class="material-icons md-14">delete</span>
                    Delete
                </button>
            `;
        }
    }

    getStatusBadgeHTML(status) {
        const badges = {
            'enabled': '<span class="badge badge-success">Enabled</span>',
            'disabled': '<span class="badge badge-warning">Disabled</span>',
            'imported_disabled': '<span class="badge badge-secondary">Imported</span>'
        };
        return badges[status] || '<span class="badge badge-secondary">Unknown</span>';
    }

    getRiskBadgeHTML(riskClass) {
        const badges = {
            'pure': '<span class="risk-badge risk-pure">PURE</span>',
            'io': '<span class="risk-badge risk-io">I/O</span>',
            'action': '<span class="risk-badge risk-action">ACTION</span>'
        };
        return badges[riskClass] || '<span class="risk-badge risk-unknown">UNKNOWN</span>';
    }

    getPermissionsSummary(manifest) {
        const perms = manifest.requires?.permissions || {};
        let items = [];

        if (perms.net?.allow_domains && perms.net.allow_domains.length > 0) {
            items.push(`<span class="perm-item">
                <span class="material-icons md-14">language</span>
                Network: ${perms.net.allow_domains.length} domain(s)
            </span>`);
        }

        if (perms.fs?.read || perms.fs?.write) {
            const fsPerms = [];
            if (perms.fs.read) fsPerms.push('read');
            if (perms.fs.write) fsPerms.push('write');
            items.push(`<span class="perm-item">
                <span class="material-icons md-14">folder</span>
                Filesystem: ${fsPerms.join(', ')}
            </span>`);
        }

        if (perms.actions && Object.keys(perms.actions).length > 0) {
            items.push(`<span class="perm-item">
                <span class="material-icons md-14">bolt</span>
                Actions: ${Object.keys(perms.actions).length}
            </span>`);
        }

        if (items.length === 0) {
            return '<span class="perm-item text-gray-500">No special permissions</span>';
        }

        return items.join('');
    }

    parseManifest(skill) {
        try {
            if (typeof skill.manifest_json === 'string') {
                return JSON.parse(skill.manifest_json);
            }
            return skill.manifest_json || {};
        } catch (error) {
            console.warn('Failed to parse manifest:', error);
            return {};
        }
    }

    async enableSkill(skillId) {
        const token = await this.promptAdminToken('Enable Skill');
        if (!token) return;

        try {
            const response = await this.apiClient.post(`/api/skills/${skillId}/enable`, {}, {
                headers: { 'X-Admin-Token': token }
            });

            if (!response.ok) {
                throw new Error(response.error || 'Failed to enable skill');
            }

            if (window.showToast) {
                window.showToast('Skill enabled successfully', 'success');
            }

            await this.loadSkills(true);

        } catch (error) {
            console.error('Failed to enable skill:', error);
            if (window.showToast) {
                window.showToast(`Failed to enable: ${error.message}`, 'error');
            }
        }
    }

    async disableSkill(skillId) {
        const token = await this.promptAdminToken('Disable Skill');
        if (!token) return;

        try {
            const response = await this.apiClient.post(`/api/skills/${skillId}/disable`, {}, {
                headers: { 'X-Admin-Token': token }
            });

            if (!response.ok) {
                throw new Error(response.error || 'Failed to disable skill');
            }

            if (window.showToast) {
                window.showToast('Skill disabled successfully', 'success');
            }

            await this.loadSkills(true);

        } catch (error) {
            console.error('Failed to disable skill:', error);
            if (window.showToast) {
                window.showToast(`Failed to disable: ${error.message}`, 'error');
            }
        }
    }

    async deleteSkill(skillId) {
        if (!confirm('Are you sure you want to delete this skill? This action cannot be undone.')) {
            return;
        }

        const token = await this.promptAdminToken('Delete Skill');
        if (!token) return;

        try {
            const response = await this.apiClient.delete(`/api/skills/${skillId}`, {
                headers: { 'X-Admin-Token': token }
            });

            if (!response.ok) {
                throw new Error(response.error || 'Failed to delete skill');
            }

            if (window.showToast) {
                window.showToast('Skill deleted successfully', 'success');
            }

            await this.loadSkills(true);

        } catch (error) {
            console.error('Failed to delete skill:', error);
            if (window.showToast) {
                window.showToast(`Failed to delete: ${error.message}`, 'error');
            }
        }
    }

    promptAdminToken(action) {
        return new Promise((resolve) => {
            const token = prompt(`${action}\n\nEnter Admin Token:`);
            resolve(token);
        });
    }

    openImportDialog() {
        const dialog = new SkillImportDialog(this);
        dialog.show();
    }

    showSkillDetail(skillId) {
        const skill = this.skills.find(s => s.skill_id === skillId);
        if (!skill) {
            if (window.showToast) {
                window.showToast('Skill not found', 'error');
            }
            return;
        }

        const detailView = new SkillDetailDialog(skill, this);
        detailView.show();
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    destroy() {
        // Cleanup
        this.container.innerHTML = '';
    }
}


/**
 * SkillImportDialog - Import skill from Local or GitHub
 */
class SkillImportDialog {
    constructor(parentView) {
        this.parentView = parentView;
        this.apiClient = window.apiClient || new ApiClient();
        this.dialog = null;
    }

    show() {
        // Create modal overlay
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-header">
                    <h2>Import Skill</h2>
                    <button class="btn-close" id="close-import-dialog">
                        <span class="material-icons">close</span>
                    </button>
                </div>

                <div class="modal-body">
                    <div class="tabs-container">
                        <div class="tabs">
                            <button class="tab-btn active" data-tab="local">
                                <span class="material-icons md-18">folder</span>
                                Local
                            </button>
                            <button class="tab-btn" data-tab="github">
                                <span class="material-icons md-18">cloud</span>
                                GitHub
                            </button>
                        </div>

                        <div class="tab-content active" id="tab-local">
                            <div class="form-group">
                                <label>Local Path <span class="required">*</span></label>
                                <input
                                    type="text"
                                    id="local-path"
                                    class="form-input"
                                    placeholder="/path/to/skill"
                                />
                                <small class="form-help">
                                    Path to the directory containing skill.json manifest
                                </small>
                            </div>
                        </div>

                        <div class="tab-content" id="tab-github">
                            <div class="form-group">
                                <label>Owner <span class="required">*</span></label>
                                <input
                                    type="text"
                                    id="github-owner"
                                    class="form-input"
                                    placeholder="username or organization"
                                />
                            </div>
                            <div class="form-group">
                                <label>Repository <span class="required">*</span></label>
                                <input
                                    type="text"
                                    id="github-repo"
                                    class="form-input"
                                    placeholder="repository-name"
                                />
                            </div>
                            <div class="form-group">
                                <label>Ref (Branch/Tag)</label>
                                <input
                                    type="text"
                                    id="github-ref"
                                    class="form-input"
                                    placeholder="main, v1.0.0, etc."
                                />
                                <small class="form-help">
                                    Leave empty to use default branch
                                </small>
                            </div>
                            <div class="form-group">
                                <label>Subdirectory</label>
                                <input
                                    type="text"
                                    id="github-subdir"
                                    class="form-input"
                                    placeholder="skills/example"
                                />
                                <small class="form-help">
                                    Path to skill directory within the repository
                                </small>
                            </div>
                        </div>
                    </div>

                    <div id="preview-area" class="preview-area hidden">
                        <h3>Manifest Preview</h3>
                        <pre id="manifest-preview" class="json-preview"></pre>
                    </div>

                    <div id="import-error" class="alert alert-error hidden">
                        <!-- Error messages will appear here -->
                    </div>
                </div>

                <div class="modal-footer">
                    <button class="btn btn-secondary" id="preview-import-btn">
                        <span class="material-icons md-18">visibility</span>
                        Preview
                    </button>
                    <button class="btn btn-primary" id="confirm-import-btn">
                        <span class="material-icons md-18">download</span>
                        Import
                    </button>
                    <button class="btn btn-secondary" id="cancel-import-btn">
                        Cancel
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        this.dialog = modal;

        this.setupEventListeners();
    }

    setupEventListeners() {
        if (!this.dialog) return;

        // Close button
        const closeBtn = this.dialog.querySelector('#close-import-dialog');
        const cancelBtn = this.dialog.querySelector('#cancel-import-btn');

        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.close());
        }
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.close());
        }

        // Close on overlay click
        this.dialog.addEventListener('click', (e) => {
            if (e.target === this.dialog) {
                this.close();
            }
        });

        // Tab switching
        const tabBtns = this.dialog.querySelectorAll('.tab-btn');
        tabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                // Remove active class from all
                this.dialog.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                this.dialog.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

                // Add active class to clicked tab
                btn.classList.add('active');
                const tabId = btn.dataset.tab;
                const tabContent = this.dialog.querySelector(`#tab-${tabId}`);
                if (tabContent) {
                    tabContent.classList.add('active');
                }
            });
        });

        // Preview button
        const previewBtn = this.dialog.querySelector('#preview-import-btn');
        if (previewBtn) {
            previewBtn.addEventListener('click', () => this.previewImport());
        }

        // Import button
        const importBtn = this.dialog.querySelector('#confirm-import-btn');
        if (importBtn) {
            importBtn.addEventListener('click', () => this.confirmImport());
        }
    }

    async previewImport() {
        // TODO: Implement preview if API supports dry-run
        const errorDiv = this.dialog.querySelector('#import-error');
        if (errorDiv) {
            errorDiv.textContent = 'Preview feature coming soon. You can proceed with import.';
            errorDiv.classList.remove('hidden');
        }
    }

    async confirmImport() {
        const activeTab = this.dialog.querySelector('.tab-btn.active')?.dataset.tab;
        const token = await this.promptAdminToken();

        if (!token) return;

        let importData;

        try {
            if (activeTab === 'local') {
                const path = this.dialog.querySelector('#local-path')?.value?.trim();
                if (!path) {
                    throw new Error('Please enter a local path');
                }
                importData = { type: 'local', path };
            } else if (activeTab === 'github') {
                const owner = this.dialog.querySelector('#github-owner')?.value?.trim();
                const repo = this.dialog.querySelector('#github-repo')?.value?.trim();
                const ref = this.dialog.querySelector('#github-ref')?.value?.trim();
                const subdir = this.dialog.querySelector('#github-subdir')?.value?.trim();

                if (!owner || !repo) {
                    throw new Error('Please enter owner and repository name');
                }

                importData = {
                    type: 'github',
                    owner,
                    repo,
                    ref: ref || null,
                    subdir: subdir || null
                };
            } else {
                throw new Error('Invalid tab selected');
            }

            // Show loading state
            const importBtn = this.dialog.querySelector('#confirm-import-btn');
            if (importBtn) {
                importBtn.disabled = true;
                importBtn.innerHTML = '<span class="material-icons md-18 spinning">refresh</span> Importing...';
            }

            // Call API
            const response = await this.apiClient.post('/api/skills/import', importData, {
                headers: { 'X-Admin-Token': token }
            });

            if (!response.ok) {
                throw new Error(response.error || 'Failed to import skill');
            }

            const result = response.data;

            if (window.showToast) {
                window.showToast(
                    `Skill imported: ${result.skill_id} (${result.status})`,
                    'success'
                );
            }

            this.close();

            // Refresh parent view
            if (this.parentView && this.parentView.loadSkills) {
                await this.parentView.loadSkills(true);
            }

        } catch (error) {
            console.error('Import failed:', error);

            const errorDiv = this.dialog.querySelector('#import-error');
            if (errorDiv) {
                errorDiv.innerHTML = `
                    <span class="material-icons">error</span>
                    <strong>Import Failed:</strong> ${error.message}
                `;
                errorDiv.classList.remove('hidden');
            }

            // Reset button
            const importBtn = this.dialog.querySelector('#confirm-import-btn');
            if (importBtn) {
                importBtn.disabled = false;
                importBtn.innerHTML = '<span class="material-icons md-18">download</span> Import';
            }

            if (window.showToast) {
                window.showToast(`Import failed: ${error.message}`, 'error');
            }
        }
    }

    promptAdminToken() {
        return new Promise((resolve) => {
            const token = prompt('Import requires admin privileges.\n\nEnter Admin Token:');
            resolve(token);
        });
    }

    close() {
        if (this.dialog) {
            this.dialog.remove();
            this.dialog = null;
        }
    }
}


/**
 * SkillDetailDialog - Show detailed skill information
 */
class SkillDetailDialog {
    constructor(skill, parentView) {
        this.skill = skill;
        this.parentView = parentView;
        this.apiClient = window.apiClient || new ApiClient();
        this.dialog = null;
    }

    show() {
        const manifest = this.parseManifest();

        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-dialog modal-xl">
                <div class="modal-header">
                    <div>
                        <h2>${this.escapeHtml(this.skill.name || this.skill.skill_id)}</h2>
                        <p class="text-sm text-gray-600">${this.skill.skill_id}</p>
                    </div>
                    <button class="btn-close" id="close-detail-dialog">
                        <span class="material-icons">close</span>
                    </button>
                </div>

                <div class="modal-body skill-detail-content">
                    ${this.renderOverview(manifest)}
                    ${this.renderPermissions(manifest)}
                    ${this.renderLimits(manifest)}
                    ${this.renderManifest(manifest)}
                </div>

                <div class="modal-footer">
                    ${this.renderActionButtons()}
                    <button class="btn btn-secondary" id="close-detail-btn">
                        Close
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        this.dialog = modal;

        this.setupEventListeners();
    }

    renderOverview(manifest) {
        const riskClass = manifest.capabilities?.class || 'unknown';

        return `
            <section class="detail-section">
                <h3>Overview</h3>
                <dl class="detail-dl">
                    <dt>Skill ID</dt>
                    <dd><code>${this.skill.skill_id}</code></dd>

                    <dt>Version</dt>
                    <dd>${this.skill.version || '1.0.0'}</dd>

                    <dt>Status</dt>
                    <dd>${this.getStatusBadgeHTML(this.skill.status)}</dd>

                    <dt>Source</dt>
                    <dd>
                        <span class="source-badge">
                            <span class="material-icons md-14">
                                ${this.skill.source_type === 'github' ? 'cloud' : 'folder'}
                            </span>
                            ${this.skill.source_type || 'local'}
                        </span>
                        ${this.skill.source_ref ? `<code class="ml-2">${this.skill.source_ref}</code>` : ''}
                    </dd>

                    <dt>Risk Class</dt>
                    <dd>${this.getRiskBadgeHTML(riskClass)}</dd>

                    <dt>Trust Level</dt>
                    <dd>${this.skill.trust_level || 'N/A'}</dd>

                    ${this.skill.repo_hash ? `
                        <dt>Repository Hash</dt>
                        <dd><code class="hash">${this.skill.repo_hash}</code></dd>
                    ` : ''}

                    <dt>Description</dt>
                    <dd>${this.escapeHtml(manifest.description || 'No description available')}</dd>
                </dl>
            </section>
        `;
    }

    renderPermissions(manifest) {
        const perms = manifest.requires?.permissions || {};

        if (!perms || Object.keys(perms).length === 0) {
            return `
                <section class="detail-section">
                    <h3>Permissions</h3>
                    <p class="text-gray-600">No special permissions required.</p>
                </section>
            `;
        }

        let html = '<section class="detail-section"><h3>Permissions</h3><ul class="permissions-list">';

        if (perms.net?.allow_domains && perms.net.allow_domains.length > 0) {
            html += `
                <li class="permission-item">
                    <span class="material-icons">language</span>
                    <div>
                        <strong>Network Access</strong>
                        <p>Allowed domains:</p>
                        <ul class="domain-list">
                            ${perms.net.allow_domains.map(domain => `<li><code>${domain}</code></li>`).join('')}
                        </ul>
                    </div>
                </li>
            `;
        }

        if (perms.fs) {
            html += `
                <li class="permission-item">
                    <span class="material-icons">folder</span>
                    <div>
                        <strong>Filesystem Access</strong>
                        <p>
                            Read: ${perms.fs.read ? '✅ Yes' : '❌ No'} |
                            Write: ${perms.fs.write ? '✅ Yes' : '❌ No'}
                        </p>
                    </div>
                </li>
            `;
        }

        if (perms.actions && Object.keys(perms.actions).length > 0) {
            html += `
                <li class="permission-item">
                    <span class="material-icons">bolt</span>
                    <div>
                        <strong>Actions</strong>
                        <pre class="json-preview">${JSON.stringify(perms.actions, null, 2)}</pre>
                    </div>
                </li>
            `;
        }

        html += '</ul></section>';
        return html;
    }

    renderLimits(manifest) {
        const limits = manifest.limits || {};

        return `
            <section class="detail-section">
                <h3>Limits</h3>
                <dl class="detail-dl">
                    <dt>Max Runtime</dt>
                    <dd>${limits.max_runtime_ms ? `${limits.max_runtime_ms} ms` : 'N/A'}</dd>

                    <dt>Max Tokens</dt>
                    <dd>${limits.max_tokens || 'N/A'}</dd>
                </dl>
            </section>
        `;
    }

    renderManifest(manifest) {
        return `
            <section class="detail-section">
                <h3>Full Manifest</h3>
                <pre class="json-preview">${JSON.stringify(manifest, null, 2)}</pre>
            </section>
        `;
    }

    renderActionButtons() {
        if (this.skill.status === 'enabled') {
            return `
                <button class="btn btn-warning" id="disable-skill-detail-btn">
                    <span class="material-icons md-18">block</span>
                    Disable Skill
                </button>
            `;
        } else {
            return `
                <button class="btn btn-success" id="enable-skill-detail-btn">
                    <span class="material-icons md-18">check_circle</span>
                    Enable Skill
                </button>
            `;
        }
    }

    setupEventListeners() {
        if (!this.dialog) return;

        const closeBtn = this.dialog.querySelector('#close-detail-dialog');
        const closeDetailBtn = this.dialog.querySelector('#close-detail-btn');
        const enableBtn = this.dialog.querySelector('#enable-skill-detail-btn');
        const disableBtn = this.dialog.querySelector('#disable-skill-detail-btn');

        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.close());
        }
        if (closeDetailBtn) {
            closeDetailBtn.addEventListener('click', () => this.close());
        }

        if (enableBtn) {
            enableBtn.addEventListener('click', async () => {
                await this.parentView.enableSkill(this.skill.skill_id);
                this.close();
            });
        }

        if (disableBtn) {
            disableBtn.addEventListener('click', async () => {
                await this.parentView.disableSkill(this.skill.skill_id);
                this.close();
            });
        }

        // Close on overlay click
        this.dialog.addEventListener('click', (e) => {
            if (e.target === this.dialog) {
                this.close();
            }
        });
    }

    parseManifest() {
        try {
            if (typeof this.skill.manifest_json === 'string') {
                return JSON.parse(this.skill.manifest_json);
            }
            return this.skill.manifest_json || {};
        } catch (error) {
            console.warn('Failed to parse manifest:', error);
            return {};
        }
    }

    getStatusBadgeHTML(status) {
        const badges = {
            'enabled': '<span class="badge badge-success">Enabled</span>',
            'disabled': '<span class="badge badge-warning">Disabled</span>',
            'imported_disabled': '<span class="badge badge-secondary">Imported</span>'
        };
        return badges[status] || '<span class="badge badge-secondary">Unknown</span>';
    }

    getRiskBadgeHTML(riskClass) {
        const badges = {
            'pure': '<span class="risk-badge risk-pure">PURE</span>',
            'io': '<span class="risk-badge risk-io">I/O</span>',
            'action': '<span class="risk-badge risk-action">ACTION</span>'
        };
        return badges[riskClass] || '<span class="risk-badge risk-unknown">UNKNOWN</span>';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    close() {
        if (this.dialog) {
            this.dialog.remove();
            this.dialog = null;
        }
    }
}


// Export for use in main.js
if (typeof window !== 'undefined') {
    window.SkillsMarketplaceView = SkillsMarketplaceView;
    window.SkillImportDialog = SkillImportDialog;
    window.SkillDetailDialog = SkillDetailDialog;
}
