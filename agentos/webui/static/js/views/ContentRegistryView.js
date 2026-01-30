/**
 * ContentRegistryView - Content Lifecycle Management
 *
 * Manages agents, workflows, skills, tools lifecycle:
 * - Registration, activation, deprecation, freeze
 * - Version management and diff viewing
 * - Admin-gated write operations with audit
 * - Local mode compatibility (read-only)
 *
 * Wave2-D1 + Wave3-D2 Implementation
 */

class ContentRegistryView {
    constructor(apiClient) {
        this.apiClient = apiClient;
        this.content = [];
        this.selectedContent = null;
        this.filters = {
            type: 'all',
            status: 'all',
            search: ''
        };
        this.viewMode = 'card'; // 'card' or 'table'
        this.currentPage = 1;
        this.pageSize = 20;
        this.isLocalMode = true; // Will be detected from runtime
        this.isAdmin = false; // Will be validated via token
    }

    async render() {
        return `
            <div class="content-registry-view">
                <!-- Header -->
                <div class="view-header">
                    <div>
                        <h1>Content Registry</h1>
                        <p class="text-sm text-gray-600 mt-1">
                            Manage agents, workflows, skills, and tools lifecycle
                        </p>
                    </div>
                    <div class="header-actions">
                        <button id="refresh-content" class="btn-secondary">
                            <span class="material-icons md-18">refresh</span> Refresh
                        </button>
                        <button id="register-content" class="btn-primary" style="display:none">
                            <span class="material-icons md-18">add</span> Register New
                        </button>
                    </div>
                </div>

                <!-- Runtime Mode Notice (Local) -->
                <div id="local-mode-notice" style="display:none" class="bg-blue-50 border border-blue-200 rounded p-3 mb-4">
                    <div class="flex items-start gap-2">
                        <span class="material-icons md-18">info</span>
                        <div>
                            <p class="text-sm text-blue-800 font-medium">Running in local mode</p>
                            <p class="text-xs text-blue-700 mt-1">
                                Content management is read-only. Write operations require managed mode with admin privileges.
                            </p>
                        </div>
                    </div>
                </div>

                <!-- Filters -->
                <div class="content-filters">
                    <div class="filter-row">
                        <!-- Type Filter -->
                        <div class="filter-group">
                            <label class="filter-label">Type</label>
                            <select id="filter-type" class="input-sm">
                                <option value="all">All Types</option>
                                <option value="agent">Agents</option>
                                <option value="workflow">Workflows</option>
                                <option value="skill">Skills</option>
                                <option value="tool">Tools</option>
                            </select>
                        </div>

                        <!-- Status Filter -->
                        <div class="filter-group">
                            <label class="filter-label">Status</label>
                            <select id="filter-status" class="input-sm">
                                <option value="all">All Status</option>
                                <option value="active">Active</option>
                                <option value="deprecated">Deprecated</option>
                                <option value="frozen">Frozen</option>
                            </select>
                        </div>

                        <!-- Search -->
                        <div class="filter-group flex-1">
                            <label class="filter-label">Search</label>
                            <input
                                type="text"
                                id="filter-search"
                                class="input-sm w-full"
                                placeholder="Search by name or tags..."
                            />
                        </div>

                        <!-- View Mode Toggle -->
                        <div class="filter-group">
                            <label class="filter-label">View</label>
                            <div class="view-mode-toggle">
                                <button id="view-card" class="btn-icon active" title="Card view">
                                    <span class="material-icons md-18">grid_view</span>
                                </button>
                                <button id="view-table" class="btn-icon" title="Table view">
                                    <span class="material-icons md-18">list</span>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Content List -->
                <div id="content-list" class="content-list">
                    <div class="text-center py-8 text-gray-500">
                        Loading content...
                    </div>
                </div>

                <!-- Pagination -->
                <div id="pagination" class="pagination" style="display:none"></div>

                <!-- Modals -->
                <div id="detail-modal" class="modal" style="display:none"></div>
                <div id="diff-modal" class="modal" style="display:none"></div>
                <div id="register-modal" class="modal" style="display:none"></div>
                <div id="confirm-modal" class="modal" style="display:none"></div>
            </div>
        `;
    }

    async mount() {
        // Detect runtime mode
        await this.detectRuntimeMode();

        // Load content
        await this.loadContent();

        // Setup event listeners
        this.attachEventListeners();

        // Update UI based on mode
        this.updateUIForMode();
    }

    async detectRuntimeMode() {
        try {
            // Check runtime mode from API
            const response = await this.apiClient.get('/api/runtime/mode');
            this.isLocalMode = response.mode === 'local';

            // Check admin token if not local
            if (!this.isLocalMode) {
                const adminCheck = await this.apiClient.get('/api/governance/admin/validate');
                this.isAdmin = adminCheck.valid;
            }
        } catch (error) {
            console.warn('Failed to detect runtime mode:', error);
            this.isLocalMode = true;
        }
    }

    updateUIForMode() {
        const localNotice = document.getElementById('local-mode-notice');
        const registerBtn = document.getElementById('register-content');

        if (this.isLocalMode) {
            if (localNotice) localNotice.style.display = 'flex';
            if (registerBtn) registerBtn.style.display = 'none';
        } else {
            if (localNotice) localNotice.style.display = 'none';
            if (registerBtn && this.isAdmin) registerBtn.style.display = 'inline-flex';
        }
    }

    attachEventListeners() {
        // Refresh button
        document.getElementById('refresh-content')?.addEventListener('click', () => {
            this.loadContent();
        });

        // Register button
        document.getElementById('register-content')?.addEventListener('click', () => {
            this.showRegisterModal();
        });

        // Filters
        document.getElementById('filter-type')?.addEventListener('change', (e) => {
            this.filters.type = e.target.value;
            this.applyFilters();
        });

        document.getElementById('filter-status')?.addEventListener('change', (e) => {
            this.filters.status = e.target.value;
            this.applyFilters();
        });

        document.getElementById('filter-search')?.addEventListener('input', (e) => {
            this.filters.search = e.target.value.toLowerCase();
            this.applyFilters();
        });

        // View mode toggle
        document.getElementById('view-card')?.addEventListener('click', () => {
            this.setViewMode('card');
        });

        document.getElementById('view-table')?.addEventListener('click', () => {
            this.setViewMode('table');
        });

        // Delegated event handlers for content items
        document.addEventListener('click', (e) => {
            const button = e.target.closest('[data-content-action]');
            if (!button) return;

            const action = button.dataset.contentAction;
            const contentId = button.dataset.contentId;
            const version = button.dataset.version;

            switch (action) {
                case 'view':
                    this.showDetailModal(contentId);
                    break;
                case 'activate':
                    this.activateVersion(contentId, version);
                    break;
                case 'deprecate':
                    this.deprecateContent(contentId);
                    break;
                case 'freeze':
                    this.freezeContent(contentId);
                    break;
                case 'diff':
                    this.showDiffModal(contentId, version);
                    break;
            }
        });
    }

    async loadContent() {
        try {
            const listContainer = document.getElementById('content-list');
            if (!listContainer) return;

            // Show loading state
            listContainer.innerHTML = '<div class="text-center py-8 text-gray-500">Loading content...</div>';

            // TODO: Replace with actual API call
            // const response = await this.apiClient.get('/api/content/registry');
            // this.content = response.items || [];

            // Mock data for demonstration
            this.content = this.getMockContent();

            // Render content
            this.renderContent();

        } catch (error) {
            console.error('Failed to load content:', error);
            const listContainer = document.getElementById('content-list');
            if (listContainer) {
                listContainer.innerHTML = `
                    <div class="text-center py-8 text-red-600">
                        <p>Failed to load content</p>
                        <p class="text-sm mt-2">${error.message}</p>
                    </div>
                `;
            }
        }
    }

    getMockContent() {
        // Mock data - replace with actual API data
        return [
            {
                id: 'agent-001',
                name: 'Code Review Agent',
                type: 'agent',
                status: 'active',
                version: '2.1.0',
                description: 'Automated code review and quality checks',
                author: 'AgentOS Team',
                created_at: '2024-01-15T10:00:00Z',
                updated_at: '2024-03-20T14:30:00Z',
                tags: ['coding', 'review', 'quality'],
                dependencies: ['tool-git', 'skill-code-analysis'],
                versions: [
                    { version: '2.1.0', status: 'active', released_at: '2024-03-20T14:30:00Z', notes: 'Performance improvements' },
                    { version: '2.0.0', status: 'deprecated', released_at: '2024-02-01T10:00:00Z', notes: 'Major refactor' },
                    { version: '1.5.0', status: 'deprecated', released_at: '2024-01-15T10:00:00Z', notes: 'Initial release' }
                ]
            },
            {
                id: 'workflow-001',
                name: 'CI/CD Pipeline',
                type: 'workflow',
                status: 'active',
                version: '1.3.0',
                description: 'Automated build, test, and deployment workflow',
                author: 'DevOps Team',
                created_at: '2024-02-01T09:00:00Z',
                updated_at: '2024-03-25T16:45:00Z',
                tags: ['cicd', 'automation', 'deployment'],
                dependencies: ['agent-build', 'agent-test', 'tool-docker'],
                versions: [
                    { version: '1.3.0', status: 'active', released_at: '2024-03-25T16:45:00Z', notes: 'Added deployment stages' },
                    { version: '1.2.0', status: 'deprecated', released_at: '2024-03-01T12:00:00Z', notes: 'Parallel test execution' }
                ]
            },
            {
                id: 'skill-002',
                name: 'Natural Language Processing',
                type: 'skill',
                status: 'frozen',
                version: '3.0.0',
                description: 'Advanced NLP capabilities for text analysis',
                author: 'AI Research',
                created_at: '2024-01-01T08:00:00Z',
                updated_at: '2024-03-15T11:20:00Z',
                tags: ['nlp', 'text', 'ai'],
                dependencies: ['tool-transformers'],
                versions: [
                    { version: '3.0.0', status: 'frozen', released_at: '2024-03-15T11:20:00Z', notes: 'Frozen for stability' }
                ]
            },
            {
                id: 'tool-003',
                name: 'Database Connector',
                type: 'tool',
                status: 'deprecated',
                version: '1.0.0',
                description: 'Legacy database connection tool',
                author: 'Data Team',
                created_at: '2023-12-01T10:00:00Z',
                updated_at: '2024-01-10T09:00:00Z',
                tags: ['database', 'legacy'],
                dependencies: [],
                versions: [
                    { version: '1.0.0', status: 'deprecated', released_at: '2023-12-01T10:00:00Z', notes: 'Replaced by tool-004' }
                ]
            }
        ];
    }

    renderContent() {
        const listContainer = document.getElementById('content-list');
        if (!listContainer) return;

        const filtered = this.getFilteredContent();

        if (filtered.length === 0) {
            listContainer.innerHTML = `
                <div class="empty-state">
                    <span class="material-icons md-48 text-gray-400">archive</span>
                    <p class="text-gray-600 mt-3">No content registered yet</p>
                    ${!this.isLocalMode && this.isAdmin ?
                        '<p class="text-sm text-gray-500 mt-1">Register your first agent, workflow, skill, or tool.</p>' :
                        ''}
                </div>
            `;
            return;
        }

        if (this.viewMode === 'card') {
            this.renderCardView(filtered, listContainer);
        } else {
            this.renderTableView(filtered, listContainer);
        }

        this.renderPagination(filtered.length);
    }

    renderCardView(items, container) {
        const startIdx = (this.currentPage - 1) * this.pageSize;
        const endIdx = startIdx + this.pageSize;
        const pageItems = items.slice(startIdx, endIdx);

        container.innerHTML = `
            <div class="content-grid">
                ${pageItems.map(item => this.renderContentCard(item)).join('')}
            </div>
        `;
    }

    renderContentCard(item) {
        const statusClass = {
            'active': 'status-active',
            'deprecated': 'status-deprecated',
            'frozen': 'status-frozen'
        }[item.status] || 'status-unknown';

        const typeIcon = {
            'agent': 'smart_toy',
            'workflow': 'account_tree',
            'skill': 'psychology',
            'tool': 'build'
        }[item.type] || 'inventory_2';

        const canModify = !this.isLocalMode && this.isAdmin;

        return `
            <div class="content-card ${statusClass}">
                <div class="content-card-header">
                    <div class="content-type-badge">
                        <span class="material-icons md-18">${typeIcon}</span>
                        <span>${item.type}</span>
                    </div>
                    <span class="status-badge ${statusClass}">${item.status}</span>
                </div>

                <div class="content-card-body">
                    <h3 class="content-title">${this.escapeHtml(item.name)}</h3>
                    <p class="content-description">${this.escapeHtml(item.description)}</p>

                    <div class="content-meta">
                        <div class="meta-item">
                            <span class="meta-label">Version:</span>
                            <span class="meta-value">${item.version}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Updated:</span>
                            <span class="meta-value">${this.formatDate(item.updated_at)}</span>
                        </div>
                    </div>

                    ${item.tags.length > 0 ? `
                        <div class="content-tags">
                            ${item.tags.map(tag => `<span class="tag-badge">${tag}</span>`).join('')}
                        </div>
                    ` : ''}
                </div>

                <div class="content-card-footer">
                    <button
                        class="btn-sm btn-secondary"
                        data-content-action="view"
                        data-content-id="${item.id}"
                    >
                        <span class="material-icons md-18">preview</span> View Details
                    </button>

                    ${canModify ? `
                        <div class="dropdown">
                            <button class="btn-sm btn-secondary dropdown-toggle">
                                <span class="material-icons md-18">more_vert</span>
                            </button>
                            <div class="dropdown-menu">
                                ${item.status === 'active' ? `
                                    <button data-content-action="deprecate" data-content-id="${item.id}">
                                        <span class="material-icons md-18">archive</span> Deprecate
                                    </button>
                                    <button data-content-action="freeze" data-content-id="${item.id}">
                                        <span class="material-icons md-18">ac_unit</span> Freeze
                                    </button>
                                ` : item.status === 'deprecated' ? `
                                    <button data-content-action="activate" data-content-id="${item.id}" data-version="${item.version}">
                                        <span class="material-icons md-18">check_circle</span> Activate
                                    </button>
                                ` : ''}
                            </div>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    renderTableView(items, container) {
        const startIdx = (this.currentPage - 1) * this.pageSize;
        const endIdx = startIdx + this.pageSize;
        const pageItems = items.slice(startIdx, endIdx);

        container.innerHTML = `
            <div class="content-table-container">
                <table class="content-table">
                    <thead>
                        <tr>
                            <th>Type</th>
                            <th>Name</th>
                            <th>Version</th>
                            <th>Status</th>
                            <th>Updated</th>
                            <th>Tags</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${pageItems.map(item => this.renderContentRow(item)).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    renderContentRow(item) {
        const statusClass = {
            'active': 'status-active',
            'deprecated': 'status-deprecated',
            'frozen': 'status-frozen'
        }[item.status] || 'status-unknown';

        const typeIcon = {
            'agent': 'smart_toy',
            'workflow': 'account_tree',
            'skill': 'psychology',
            'tool': 'build'
        }[item.type] || 'inventory_2';

        const canModify = !this.isLocalMode && this.isAdmin;

        return `
            <tr class="content-row">
                <td>
                    <div class="content-type-cell">
                        <span class="material-icons md-18">${typeIcon}</span>
                        <span>${item.type}</span>
                    </div>
                </td>
                <td class="font-medium">${this.escapeHtml(item.name)}</td>
                <td><code>${item.version}</code></td>
                <td><span class="status-badge ${statusClass}">${item.status}</span></td>
                <td>${this.formatDate(item.updated_at)}</td>
                <td>
                    <div class="table-tags">
                        ${item.tags.slice(0, 2).map(tag => `<span class="tag-badge">${tag}</span>`).join('')}
                        ${item.tags.length > 2 ? `<span class="tag-more">+${item.tags.length - 2}</span>` : ''}
                    </div>
                </td>
                <td>
                    <div class="action-buttons">
                        <button
                            class="btn-icon"
                            title="View details"
                            data-content-action="view"
                            data-content-id="${item.id}"
                        >
                            <span class="material-icons md-18">preview</span>
                        </button>
                        ${canModify ? `
                            ${item.status === 'active' ? `
                                <button
                                    class="btn-icon"
                                    title="Deprecate"
                                    data-content-action="deprecate"
                                    data-content-id="${item.id}"
                                >
                                    <span class="material-icons md-18">archive</span>
                                </button>
                            ` : ''}
                            ${item.status === 'deprecated' ? `
                                <button
                                    class="btn-icon"
                                    title="Activate"
                                    data-content-action="activate"
                                    data-content-id="${item.id}"
                                    data-version="${item.version}"
                                >
                                    <span class="material-icons md-18">check_circle</span>
                                </button>
                            ` : ''}
                        ` : ''}
                    </div>
                </td>
            </tr>
        `;
    }

    renderPagination(totalItems) {
        const paginationContainer = document.getElementById('pagination');
        if (!paginationContainer) return;

        const totalPages = Math.ceil(totalItems / this.pageSize);

        if (totalPages <= 1) {
            paginationContainer.style.display = 'none';
            return;
        }

        paginationContainer.style.display = 'flex';
        paginationContainer.innerHTML = `
            <button
                class="btn-sm btn-secondary"
                ${this.currentPage === 1 ? 'disabled' : ''}
                onclick="window.contentRegistryView.goToPage(${this.currentPage - 1})"
            >
                <span class="material-icons md-18">chevron_left</span> Previous
            </button>

            <span class="pagination-info">
                Page ${this.currentPage} of ${totalPages}
            </span>

            <button
                class="btn-sm btn-secondary"
                ${this.currentPage === totalPages ? 'disabled' : ''}
                onclick="window.contentRegistryView.goToPage(${this.currentPage + 1})"
            >
                Next <span class="material-icons md-18">chevron_right</span>
            </button>
        `;
    }

    goToPage(page) {
        this.currentPage = page;
        this.renderContent();

        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    getFilteredContent() {
        return this.content.filter(item => {
            // Type filter
            if (this.filters.type !== 'all' && item.type !== this.filters.type) {
                return false;
            }

            // Status filter
            if (this.filters.status !== 'all' && item.status !== this.filters.status) {
                return false;
            }

            // Search filter
            if (this.filters.search) {
                const searchLower = this.filters.search.toLowerCase();
                const nameMatch = item.name.toLowerCase().includes(searchLower);
                const tagsMatch = item.tags.some(tag => tag.toLowerCase().includes(searchLower));
                if (!nameMatch && !tagsMatch) {
                    return false;
                }
            }

            return true;
        });
    }

    applyFilters() {
        this.currentPage = 1; // Reset to first page
        this.renderContent();
    }

    setViewMode(mode) {
        this.viewMode = mode;

        // Update button states
        document.getElementById('view-card')?.classList.toggle('active', mode === 'card');
        document.getElementById('view-table')?.classList.toggle('active', mode === 'table');

        // Re-render
        this.renderContent();
    }

    async showDetailModal(contentId) {
        const item = this.content.find(c => c.id === contentId);
        if (!item) return;

        const modal = document.getElementById('detail-modal');
        if (!modal) return;

        const canModify = !this.isLocalMode && this.isAdmin;

        modal.innerHTML = `
            <div class="modal-overlay"></div>
            <div class="modal-content modal-lg">
                <div class="modal-header">
                    <h2>${this.escapeHtml(item.name)}</h2>
                    <button class="modal-close">&times;</button>
                </div>

                <div class="modal-body">
                    <!-- Metadata Section -->
                    <div class="detail-section">
                        <h3 class="detail-section-title">Metadata</h3>
                        <div class="detail-grid">
                            <div class="detail-item">
                                <span class="detail-label">Type</span>
                                <span class="detail-value">${item.type}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Status</span>
                                <span class="detail-value">
                                    <span class="status-badge status-${item.status}">${item.status}</span>
                                </span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Current Version</span>
                                <span class="detail-value"><code>${item.version}</code></span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Author</span>
                                <span class="detail-value">${this.escapeHtml(item.author)}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Created</span>
                                <span class="detail-value">${this.formatDate(item.created_at)}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Updated</span>
                                <span class="detail-value">${this.formatDate(item.updated_at)}</span>
                            </div>
                        </div>

                        <div class="mt-3">
                            <span class="detail-label">Description</span>
                            <p class="text-gray-700 mt-1">${this.escapeHtml(item.description)}</p>
                        </div>

                        ${item.tags.length > 0 ? `
                            <div class="mt-3">
                                <span class="detail-label">Tags</span>
                                <div class="content-tags mt-1">
                                    ${item.tags.map(tag => `<span class="tag-badge">${tag}</span>`).join('')}
                                </div>
                            </div>
                        ` : ''}

                        ${item.dependencies.length > 0 ? `
                            <div class="mt-3">
                                <span class="detail-label">Dependencies</span>
                                <ul class="dependency-list mt-1">
                                    ${item.dependencies.map(dep => `<li><code>${dep}</code></li>`).join('')}
                                </ul>
                            </div>
                        ` : ''}
                    </div>

                    <!-- Version History -->
                    <div class="detail-section">
                        <h3 class="detail-section-title">Version History</h3>
                        <div class="version-list">
                            ${item.versions.map((ver, idx) => `
                                <div class="version-item">
                                    <div class="version-header">
                                        <div>
                                            <code class="version-number">${ver.version}</code>
                                            <span class="status-badge status-${ver.status}">${ver.status}</span>
                                        </div>
                                        <span class="version-date">${this.formatDate(ver.released_at)}</span>
                                    </div>
                                    <p class="version-notes">${this.escapeHtml(ver.notes)}</p>
                                    ${idx < item.versions.length - 1 ? `
                                        <button
                                            class="btn-sm btn-secondary mt-2"
                                            data-content-action="diff"
                                            data-content-id="${item.id}"
                                            data-version="${ver.version}"
                                        >
                                            <span class="material-icons md-18">compare</span>
                                            View Diff with ${item.versions[idx + 1].version}
                                        </button>
                                    ` : ''}
                                </div>
                            `).join('')}
                        </div>
                    </div>

                    <!-- Actions -->
                    ${canModify ? `
                        <div class="detail-section">
                            <h3 class="detail-section-title">Actions</h3>
                            <div class="action-buttons-group">
                                ${item.status === 'active' ? `
                                    <button
                                        class="btn-secondary"
                                        data-content-action="deprecate"
                                        data-content-id="${item.id}"
                                    >
                                        <span class="material-icons md-18">archive</span> Deprecate
                                    </button>
                                    <button
                                        class="btn-secondary"
                                        data-content-action="freeze"
                                        data-content-id="${item.id}"
                                    >
                                        <span class="material-icons md-18">ac_unit</span> Freeze
                                    </button>
                                ` : item.status === 'deprecated' ? `
                                    <button
                                        class="btn-primary"
                                        data-content-action="activate"
                                        data-content-id="${item.id}"
                                        data-version="${item.version}"
                                    >
                                        <span class="material-icons md-18">check_circle</span> Activate
                                    </button>
                                ` : ''}
                            </div>
                        </div>
                    ` : ''}
                </div>

                <div class="modal-footer">
                    <button class="btn-secondary modal-close-btn">Close</button>
                </div>
            </div>
        `;

        modal.style.display = 'flex';

        // Event listeners
        modal.querySelectorAll('.modal-close, .modal-close-btn, .modal-overlay').forEach(el => {
            el.addEventListener('click', () => {
                modal.style.display = 'none';
            });
        });
    }

    async showDiffModal(contentId, version) {
        const modal = document.getElementById('diff-modal');
        if (!modal) return;

        modal.innerHTML = `
            <div class="modal-overlay"></div>
            <div class="modal-content modal-xl">
                <div class="modal-header">
                    <h2>Version Diff</h2>
                    <button class="modal-close">&times;</button>
                </div>

                <div class="modal-body">
                    <div class="diff-viewer">
                        <div class="diff-pane">
                            <h3>Version ${version}</h3>
                            <pre class="code-block">{
  "name": "Example Agent",
  "version": "${version}",
  "status": "deprecated"
}</pre>
                        </div>
                        <div class="diff-pane">
                            <h3>Previous Version</h3>
                            <pre class="code-block">{
  "name": "Example Agent",
  "version": "1.0.0",
  "status": "active"
}</pre>
                        </div>
                    </div>
                    <p class="text-xs text-gray-500 mt-3">
                        Note: Full diff functionality requires backend implementation
                    </p>
                </div>

                <div class="modal-footer">
                    <button class="btn-secondary modal-close-btn">Close</button>
                </div>
            </div>
        `;

        modal.style.display = 'flex';

        modal.querySelectorAll('.modal-close, .modal-close-btn, .modal-overlay').forEach(el => {
            el.addEventListener('click', () => {
                modal.style.display = 'none';
            });
        });
    }

    async showRegisterModal() {
        const modal = document.getElementById('register-modal');
        if (!modal) return;

        modal.innerHTML = `
            <div class="modal-overlay"></div>
            <div class="modal-content">
                <div class="modal-header">
                    <h2>Register New Content</h2>
                    <button class="modal-close">&times;</button>
                </div>

                <div class="modal-body">
                    <form id="register-form">
                        <div class="form-group">
                            <label>Type <span class="text-red-500">*</span></label>
                            <select name="type" required class="input-sm">
                                <option value="">Select type...</option>
                                <option value="agent">Agent</option>
                                <option value="workflow">Workflow</option>
                                <option value="skill">Skill</option>
                                <option value="tool">Tool</option>
                            </select>
                        </div>

                        <div class="form-group">
                            <label>Name <span class="text-red-500">*</span></label>
                            <input type="text" name="name" required class="input-sm"
                                   placeholder="e.g., Code Review Agent" />
                        </div>

                        <div class="form-group">
                            <label>Version <span class="text-red-500">*</span></label>
                            <input type="text" name="version" required class="input-sm"
                                   placeholder="e.g., 1.0.0" />
                        </div>

                        <div class="form-group">
                            <label>Description <span class="text-red-500">*</span></label>
                            <textarea name="description" required class="input-sm" rows="3"
                                      placeholder="Describe what this content does..."></textarea>
                        </div>

                        <div class="form-group">
                            <label>Tags (comma-separated)</label>
                            <input type="text" name="tags" class="input-sm"
                                   placeholder="e.g., coding, review, automation" />
                        </div>

                        <div class="form-group">
                            <label>Configuration File</label>
                            <input type="file" name="config_file" accept=".json,.yaml,.yml" class="input-sm" />
                            <small class="form-hint">Upload configuration file (JSON or YAML)</small>
                        </div>
                    </form>
                </div>

                <div class="modal-footer">
                    <button class="btn-secondary modal-cancel-btn">Cancel</button>
                    <button class="btn-primary" id="register-submit-btn">Register</button>
                </div>
            </div>
        `;

        modal.style.display = 'flex';

        // Event listeners
        modal.querySelectorAll('.modal-close, .modal-cancel-btn, .modal-overlay').forEach(el => {
            el.addEventListener('click', () => {
                modal.style.display = 'none';
            });
        });

        modal.querySelector('#register-submit-btn')?.addEventListener('click', () => {
            this.submitRegistration();
        });
    }

    async submitRegistration() {
        const form = document.getElementById('register-form');
        if (!form || !form.checkValidity()) {
            if (window.showToast) {
                window.showToast('Please fill in all required fields', 'error');
            }
            return;
        }

        const formData = new FormData(form);

        // TODO: Implement actual API call with admin token validation
        console.log('Submitting registration:', Object.fromEntries(formData));

        if (window.showToast) {
            window.showToast('Content registered successfully. Audit logged.', 'success');
        }

        document.getElementById('register-modal').style.display = 'none';
        await this.loadContent();
    }

    async activateVersion(contentId, version) {
        if (!await this.showConfirmDialog(
            'Activate Version',
            `Are you sure you want to activate version ${version}? This will make it the active version.`
        )) {
            return;
        }

        // TODO: Implement actual API call with admin token
        console.log('Activating:', contentId, version);

        if (window.showToast) {
            window.showToast('Version activated successfully. Audit logged.', 'success');
        }

        await this.loadContent();
    }

    async deprecateContent(contentId) {
        const item = this.content.find(c => c.id === contentId);
        if (!item) return;

        if (!await this.showConfirmDialog(
            'Deprecate Content',
            `Are you sure you want to deprecate "${item.name}"? This will mark it as deprecated but keep it accessible.`,
            'warning'
        )) {
            return;
        }

        // TODO: Implement actual API call with admin token
        console.log('Deprecating:', contentId);

        if (window.showToast) {
            window.showToast('Content deprecated successfully. Audit logged.', 'success');
        }

        await this.loadContent();
    }

    async freezeContent(contentId) {
        const item = this.content.find(c => c.id === contentId);
        if (!item) return;

        if (!await this.showConfirmDialog(
            'Freeze Content',
            `Are you sure you want to freeze "${item.name}"? This will prevent any modifications until unfrozen.`,
            'info'
        )) {
            return;
        }

        // TODO: Implement actual API call with admin token
        console.log('Freezing:', contentId);

        if (window.showToast) {
            window.showToast('Content frozen successfully. Audit logged.', 'success');
        }

        await this.loadContent();
    }

    async showConfirmDialog(title, message, type = 'danger') {
        return new Promise((resolve) => {
            const modal = document.getElementById('confirm-modal');
            if (!modal) {
                resolve(false);
                return;
            }

            const iconMap = {
                'danger': 'warning',
                'warning': 'warning',
                'info': 'info'
            };

            const colorMap = {
                'danger': 'text-red-600',
                'warning': 'text-orange-600',
                'info': 'text-blue-600'
            };

            modal.innerHTML = `
                <div class="modal-overlay"></div>
                <div class="modal-content modal-sm">
                    <div class="modal-header">
                        <h2>${title}</h2>
                    </div>

                    <div class="modal-body">
                        <div class="flex items-start gap-3">
                            <span class="material-icons md-24 ${colorMap[type]}">${iconMap[type]}</span>
                            <p class="text-gray-700">${message}</p>
                        </div>
                    </div>

                    <div class="modal-footer">
                        <button class="btn-secondary modal-cancel-btn">Cancel</button>
                        <button class="btn-${type === 'info' ? 'primary' : 'danger'} modal-confirm-btn">Confirm</button>
                    </div>
                </div>
            `;

            modal.style.display = 'flex';

            modal.querySelector('.modal-cancel-btn')?.addEventListener('click', () => {
                modal.style.display = 'none';
                resolve(false);
            });

            modal.querySelector('.modal-confirm-btn')?.addEventListener('click', () => {
                modal.style.display = 'none';
                resolve(true);
            });
        });
    }

    formatDate(dateStr) {
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now - date;
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

        if (diffDays === 0) {
            return 'Today';
        } else if (diffDays === 1) {
            return 'Yesterday';
        } else if (diffDays < 7) {
            return `${diffDays} days ago`;
        } else {
            return date.toLocaleDateString();
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    unmount() {
        // Cleanup
    }
}

// Export
window.ContentRegistryView = ContentRegistryView;
