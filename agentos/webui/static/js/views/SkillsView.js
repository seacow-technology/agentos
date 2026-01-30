/**
 * SkillsView - Skills Management UI
 *
 * PR-4: Skills/Memory/Config Module
 * Coverage: GET /api/skills, GET /api/skills/{name}
 */

class SkillsView {
    constructor(container) {
        this.container = container;
        this.filterBar = null;
        this.dataTable = null;
        this.detailDrawer = null;
        this.currentFilters = {};
        this.skills = [];
        this.selectedSkill = null;

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="skills-view">
                <div class="view-header">
                    <div>
                        <h1>Skills Management</h1>
                        <p class="text-sm text-gray-600 mt-1">Manage available skills and extensions</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="skills-refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                    </div>
                </div>

                <div id="skills-filter-bar" class="filter-section"></div>

                <div id="skills-table" class="table-section"></div>

                <div id="skills-detail-drawer" class="drawer hidden">
                    <div class="drawer-overlay" id="skills-drawer-overlay"></div>
                    <div class="drawer-content">
                        <div class="drawer-header">
                            <h3>Skill Details</h3>
                            <button class="btn-close" id="skills-drawer-close">close</button>
                        </div>
                        <div class="drawer-body" id="skills-drawer-body">
                            <!-- Skill details will be rendered here -->
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.setupFilterBar();
        this.setupDataTable();
        this.setupEventListeners();
        this.loadSkills();
    }

    setupFilterBar() {
        const filterContainer = this.container.querySelector('#skills-filter-bar');

        this.filterBar = new FilterBar(filterContainer, {
            filters: [
                {
                    type: 'text',
                    key: 'q',
                    label: 'Search',
                    placeholder: 'Search skills by name or description...'
                },
                {
                    type: 'button',
                    key: 'reset',
                    label: 'Reset',
                    className: 'btn-secondary'
                }
            ],
            onChange: (filters) => this.handleFilterChange(filters),
            debounceMs: 300
        });
    }

    setupDataTable() {
        const tableContainer = this.container.querySelector('#skills-table');

        this.dataTable = new DataTable(tableContainer, {
            columns: [
                {
                    key: 'name',
                    label: 'Skill Name',
                    width: '20%',
                    render: (value) => `
                        <div class="flex items-center space-x-2">
                            <span class="font-mono text-sm font-semibold text-blue-600">${value}</span>
                            <button class="btn-icon copy-btn" data-copy="${value}" title="Copy skill name">
                                <span class="material-icons md-18">content_copy</span>
                            </button>
                        </div>
                    `
                },
                {
                    key: 'version',
                    label: 'Version',
                    width: '10%',
                    render: (value) => `<span class="badge badge-info">${value}</span>`
                },
                {
                    key: 'description',
                    label: 'Description',
                    width: '40%',
                    render: (value) => {
                        const truncated = value.length > 120 ? value.substring(0, 120) + '...' : value;
                        return `<span class="text-sm text-gray-700">${truncated}</span>`;
                    }
                },
                {
                    key: 'executable',
                    label: 'Executable',
                    width: '10%',
                    render: (value) => value
                        ? '<span class="badge badge-success"><span class="material-icons md-18">check</span> Yes</span>'
                        : '<span class="badge badge-error"><span class="material-icons md-18">cancel</span> No</span>'
                },
                {
                    key: 'last_execution',
                    label: 'Last Run',
                    width: '15%',
                    render: (value) => value
                        ? `<span class="text-xs text-gray-600">${new Date(value).toLocaleString()}</span>`
                        : '<span class="text-xs text-gray-400">Never</span>'
                },
                {
                    key: 'actions',
                    label: 'Actions',
                    width: '5%',
                    render: (_, row) => `
                        <button class="btn-sm btn-primary" data-action="view" data-skill="${row.name}">
                            View
                        </button>
                    `
                }
            ],
            emptyMessage: 'No skills found',
            onRowClick: (row) => this.showSkillDetail(row),
            pagination: true,
            pageSize: 10
        });
    }

    setupEventListeners() {
        // Refresh button
        const refreshBtn = this.container.querySelector('#skills-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadSkills(true));
        }

        // Drawer close
        const drawerOverlay = this.container.querySelector('#skills-drawer-overlay');
        const drawerClose = this.container.querySelector('#skills-drawer-close');

        if (drawerOverlay) {
            drawerOverlay.addEventListener('click', () => this.closeDrawer());
        }

        if (drawerClose) {
            drawerClose.addEventListener('click', () => this.closeDrawer());
        }

        // Event delegation for copy buttons
        this.container.addEventListener('click', (e) => {
            const copyBtn = e.target.closest('.copy-btn');
            if (copyBtn) {
                const text = copyBtn.dataset.copy;
                navigator.clipboard.writeText(text).then(() => {
                    if (window.showToast) {
                        window.showToast(`Copied: ${text}`, 'success', 1500);
                    }
                });
            }

            const actionBtn = e.target.closest('[data-action="view"]');
            if (actionBtn) {
                const skillName = actionBtn.dataset.skill;
                const skill = this.skills.find(s => s.name === skillName);
                if (skill) {
                    this.showSkillDetail(skill);
                }
            }
        });
    }

    handleFilterChange(filters) {
        this.currentFilters = filters;
        this.loadSkills();
    }

    async loadSkills(forceRefresh = false) {
        try {
            // Show loading state
            if (this.dataTable) {
                this.dataTable.setLoading(true);
            }

            // Build query params
            const params = new URLSearchParams();
            if (this.currentFilters.q) {
                params.append('q', this.currentFilters.q);
            }

            // Call API
            const response = await apiClient.get(`/api/skills?${params.toString()}`);

            if (!response.ok) {
                throw new Error(response.error || 'Failed to load skills');
            }

            this.skills = response.data || [];

            // Filter locally (API may not support all filters)
            let filteredSkills = this.skills;

            if (this.currentFilters.q) {
                const query = this.currentFilters.q.toLowerCase();
                filteredSkills = filteredSkills.filter(skill =>
                    skill.name.toLowerCase().includes(query) ||
                    skill.description.toLowerCase().includes(query)
                );
            }

            // Update table
            if (this.dataTable) {
                this.dataTable.setData(filteredSkills);
                this.dataTable.setLoading(false);
            }

            // Show success toast (only on manual refresh)
            if (forceRefresh && window.showToast) {
                window.showToast(`Loaded ${filteredSkills.length} skills`, 'success', 1500);
            }

        } catch (error) {
            console.error('Failed to load skills:', error);

            if (this.dataTable) {
                this.dataTable.setLoading(false);
                this.dataTable.showError(error.message || 'Failed to load skills');
            }

            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    async showSkillDetail(skill) {
        this.selectedSkill = skill;

        const drawer = this.container.querySelector('#skills-detail-drawer');
        const drawerBody = this.container.querySelector('#skills-drawer-body');

        if (!drawer || !drawerBody) return;

        // Show loading state
        drawerBody.innerHTML = '<div class="text-center py-8">Loading skill details...</div>';
        drawer.classList.remove('hidden');

        try {
            // Fetch full skill details
            const response = await apiClient.get(`/api/skills/${skill.name}`);

            if (!response.ok) {
                throw new Error(response.error || 'Failed to load skill details');
            }

            const skillDetail = response.data || skill;

            // Render detail view
            drawerBody.innerHTML = `
                <div class="skill-detail">
                    <!-- Header Section -->
                    <div class="detail-section">
                        <div class="flex items-center justify-between mb-4">
                            <div>
                                <h4 class="text-lg font-semibold text-gray-900">${skillDetail.name}</h4>
                                <p class="text-sm text-gray-600 mt-1">${skillDetail.description}</p>
                            </div>
                            <span class="badge badge-info">${skillDetail.version}</span>
                        </div>
                    </div>

                    <!-- Quick Info -->
                    <div class="detail-section">
                        <h5 class="detail-section-title">Quick Info</h5>
                        <div class="detail-grid">
                            <div class="detail-item">
                                <span class="detail-label">Executable</span>
                                <span class="detail-value">
                                    ${skillDetail.executable
                                        ? '<span class="badge badge-success"><span class="material-icons md-18">check</span> Yes</span>'
                                        : '<span class="badge badge-error"><span class="material-icons md-18">cancel</span> No</span>'}
                                </span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Last Execution</span>
                                <span class="detail-value">
                                    ${skillDetail.last_execution
                                        ? new Date(skillDetail.last_execution).toLocaleString()
                                        : '<span class="text-gray-400">Never</span>'}
                                </span>
                            </div>
                        </div>
                    </div>

                    <!-- Input Schema -->
                    ${skillDetail.input_schema && Object.keys(skillDetail.input_schema).length > 0 ? `
                        <div class="detail-section">
                            <h5 class="detail-section-title">Input Schema</h5>
                            <div class="json-viewer-container"></div>
                        </div>
                    ` : ''}

                    <!-- Output Schema -->
                    ${skillDetail.output_schema && Object.keys(skillDetail.output_schema).length > 0 ? `
                        <div class="detail-section">
                            <h5 class="detail-section-title">Output Schema</h5>
                            <div class="json-viewer-container-output"></div>
                        </div>
                    ` : ''}

                    <!-- Full Metadata -->
                    <div class="detail-section">
                        <h5 class="detail-section-title">Full Metadata</h5>
                        <div class="json-viewer-container-full"></div>
                    </div>

                    <!-- Actions -->
                    <div class="detail-section">
                        <h5 class="detail-section-title">Actions</h5>
                        <div class="flex gap-2 flex-wrap">
                            <button class="btn-sm btn-secondary" id="copy-skill-name">
                                <span class="material-icons md-18">content_copy</span> Copy Name
                            </button>
                            ${skillDetail.executable ? `
                                <button class="btn-sm btn-primary" id="try-skill" disabled>
                                    <span class="material-icons md-18">play_arrow</span> Try Skill (Coming Soon)
                                </button>
                            ` : ''}
                            <button class="btn-sm btn-secondary" id="view-logs">
                                <span class="material-icons md-18">description</span> View Logs
                            </button>
                        </div>
                    </div>
                </div>
            `;

            // Render JSON viewers
            if (skillDetail.input_schema && Object.keys(skillDetail.input_schema).length > 0) {
                const inputContainer = drawerBody.querySelector('.json-viewer-container');
                if (inputContainer) {
                    new JsonViewer(inputContainer, skillDetail.input_schema);
                }
            }

            if (skillDetail.output_schema && Object.keys(skillDetail.output_schema).length > 0) {
                const outputContainer = drawerBody.querySelector('.json-viewer-container-output');
                if (outputContainer) {
                    new JsonViewer(outputContainer, skillDetail.output_schema);
                }
            }

            const fullContainer = drawerBody.querySelector('.json-viewer-container-full');
            if (fullContainer) {
                new JsonViewer(fullContainer, skillDetail);
            }

            // Setup action buttons
            const copyBtn = drawerBody.querySelector('#copy-skill-name');
            if (copyBtn) {
                copyBtn.addEventListener('click', () => {
                    navigator.clipboard.writeText(skillDetail.name);
                    if (window.showToast) {
                        window.showToast('Skill name copied', 'success', 1500);
                    }
                });
            }

            const viewLogsBtn = drawerBody.querySelector('#view-logs');
            if (viewLogsBtn) {
                viewLogsBtn.addEventListener('click', () => {
                    if (window.navigateToView) {
                        window.navigateToView('logs', { contains: skillDetail.name });
                    }
                    this.closeDrawer();
                });
            }

        } catch (error) {
            console.error('Failed to load skill details:', error);
            drawerBody.innerHTML = `
                <div class="text-center py-8 text-red-600">
                    <p>Failed to load skill details</p>
                    <p class="text-sm mt-2">${error.message}</p>
                </div>
            `;

            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    closeDrawer() {
        const drawer = this.container.querySelector('#skills-detail-drawer');
        if (drawer) {
            drawer.classList.add('hidden');
        }
        this.selectedSkill = null;
    }

    destroy() {
        // Cleanup
        if (this.filterBar && this.filterBar.destroy) {
            this.filterBar.destroy();
        }
        if (this.dataTable && this.dataTable.destroy) {
            this.dataTable.destroy();
        }
        this.container.innerHTML = '';
    }
}
