/**
 * KnowledgeSourcesView - Data Source Management for RAG
 *
 * Phase 2: Knowledge Sources
 * Coverage: GET/POST/PATCH/DELETE /api/knowledge/sources
 */

class KnowledgeSourcesView {
    constructor(container) {
        this.container = container;
        this.filterBar = null;
        this.dataTable = null;
        this.currentFilters = {};
        this.sources = [];

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="knowledge-sources-view">
                <div class="view-header">
                    <div>
                        <h1>Data Sources</h1>
                        <p class="text-sm text-gray-600 mt-1">Manage knowledge base data sources and indexing</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-primary" id="sources-add">
                            <span class="icon"><span class="material-icons md-18">add</span></span> Add Source
                        </button>
                        <button class="btn-refresh" id="sources-refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                    </div>
                </div>

                <!-- Filter Bar -->
                <div id="sources-filter-bar" class="filter-section"></div>

                <!-- Table Section -->
                <div class="results-section">
                    <div class="results-header">
                        <span class="results-count" id="sources-count">Loading...</span>
                    </div>
                    <div id="sources-table" class="table-section"></div>
                </div>

                <!-- Add/Edit Modal -->
                <div id="sources-modal" class="modal hidden">
                    <div class="modal-overlay" id="sources-modal-overlay"></div>
                    <div class="modal-content modal-lg">
                        <div class="modal-header">
                            <h3 id="sources-modal-title">Add Data Source</h3>
                            <button class="modal-close" id="sources-modal-close">close</button>
                        </div>
                        <div class="modal-body">
                            <form id="sources-form">
                                <div class="form-group">
                                    <label>Type *</label>
                                    <select id="source-type" class="input-sm" required>
                                        <option value="">Select Type</option>
                                        <option value="directory">Directory</option>
                                        <option value="file">File</option>
                                        <option value="git">Git Repository</option>
                                    </select>
                                </div>

                                <div class="form-group">
                                    <label>Path *</label>
                                    <input
                                        type="text"
                                        id="source-path"
                                        class="input-sm"
                                        placeholder="e.g., /path/to/docs or https://github.com/user/repo"
                                        required
                                    />
                                </div>

                                <div class="form-group">
                                    <label>Configuration (JSON)</label>
                                    <textarea
                                        id="source-config"
                                        class="input-sm"
                                        rows="6"
                                        placeholder='{"file_types": ["md", "txt"], "recursive": true}'
                                    ></textarea>
                                </div>

                                <div class="form-actions">
                                    <button type="submit" class="btn-primary">
                                        <span class="icon"><span class="material-icons md-18">save</span></span>
                                        Save
                                    </button>
                                    <button type="button" class="btn-secondary" id="sources-form-cancel">
                                        Cancel
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>

                <!-- Detail Drawer -->
                <div id="sources-drawer" class="drawer hidden">
                    <div class="drawer-overlay" id="sources-drawer-overlay"></div>
                    <div class="drawer-content">
                        <div class="drawer-header">
                            <h3>Source Details</h3>
                            <button class="btn-close" id="sources-drawer-close">
                                <span class="material-icons">close</span>
                            </button>
                        </div>
                        <div class="drawer-body" id="sources-drawer-body">
                            <!-- Source details will be rendered here -->
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.setupFilterBar();
        this.setupDataTable();
        this.setupEventListeners();
        this.loadSources();
    }

    setupFilterBar() {
        const filterContainer = this.container.querySelector('#sources-filter-bar');

        this.filterBar = new FilterBar(filterContainer, {
            filters: [
                {
                    type: 'select',
                    key: 'type',
                    label: 'Type',
                    options: [
                        { value: '', label: 'All Types' },
                        { value: 'directory', label: 'Directory' },
                        { value: 'file', label: 'File' },
                        { value: 'git', label: 'Git Repository' }
                    ]
                },
                {
                    type: 'select',
                    key: 'status',
                    label: 'Status',
                    options: [
                        { value: '', label: 'All Statuses' },
                        { value: 'pending', label: 'Pending' },
                        { value: 'indexed', label: 'Indexed' },
                        { value: 'failed', label: 'Failed' }
                    ]
                },
                {
                    type: 'text',
                    key: 'path_contains',
                    label: 'Path Contains',
                    placeholder: 'Filter by path...'
                }
            ],
            onFilterChange: (filters) => {
                this.currentFilters = filters;
                this.applyFilters();
            }
        });
    }

    setupDataTable() {
        const tableContainer = this.container.querySelector('#sources-table');

        this.dataTable = new DataTable(tableContainer, {
            columns: [
                { key: 'path', label: 'Path', width: '30%' },
                { key: 'type', label: 'Type', width: '120px' },
                { key: 'chunk_count', label: 'Chunks', width: '100px' },
                { key: 'last_indexed_at', label: 'Last Indexed', width: '180px' },
                { key: 'status', label: 'Status', width: '120px' },
                { key: 'actions', label: 'Actions', width: '180px' }
            ],
            onRowClick: (row, event) => {
                // Don't open drawer if clicking on action buttons
                if (!event.target.closest('button')) {
                    this.showSourceDetail(row);
                }
            },
            emptyMessage: 'No data sources found. Click "Add Source" to create one.',
            pagination: true,
            pageSize: 10
        });
    }

    setupEventListeners() {
        // Add source button
        const addBtn = this.container.querySelector('#sources-add');
        addBtn.addEventListener('click', () => this.showAddModal());

        // Refresh button
        const refreshBtn = this.container.querySelector('#sources-refresh');
        refreshBtn.addEventListener('click', () => this.loadSources());

        // Modal close
        const modalClose = this.container.querySelector('#sources-modal-close');
        const modalOverlay = this.container.querySelector('#sources-modal-overlay');
        const formCancel = this.container.querySelector('#sources-form-cancel');

        modalClose.addEventListener('click', () => this.closeModal());
        modalOverlay.addEventListener('click', () => this.closeModal());
        formCancel.addEventListener('click', () => this.closeModal());

        // Form submit
        const form = this.container.querySelector('#sources-form');
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleFormSubmit();
        });

        // Drawer close
        const drawerClose = this.container.querySelector('#sources-drawer-close');
        const drawerOverlay = this.container.querySelector('#sources-drawer-overlay');

        drawerClose.addEventListener('click', () => this.closeDrawer());
        drawerOverlay.addEventListener('click', () => this.closeDrawer());
    }

    async loadSources() {
        try {
            const response = await fetch('/api/knowledge/sources');
            const data = await response.json();

            if (data.ok) {
                this.sources = data.data.sources || [];
                this.applyFilters();
                this.updateCount();
            } else {
                Toast.error(`Failed to load sources: ${data.error || 'Unknown error'}`);
                this.sources = [];
                this.renderSources([]);
            }
        } catch (error) {
            console.error('Load sources error:', error);
            Toast.error(`Load error: ${error.message}`);
            this.sources = [];
            this.renderSources([]);
        }
    }

    applyFilters() {
        let filtered = [...this.sources];

        // Apply type filter
        if (this.currentFilters.type) {
            filtered = filtered.filter(s => s.type === this.currentFilters.type);
        }

        // Apply status filter
        if (this.currentFilters.status) {
            filtered = filtered.filter(s => s.status === this.currentFilters.status);
        }

        // Apply path filter
        if (this.currentFilters.path_contains) {
            const search = this.currentFilters.path_contains.toLowerCase();
            filtered = filtered.filter(s => s.path.toLowerCase().includes(search));
        }

        this.renderSources(filtered);
        this.updateCount(filtered.length);
    }

    renderSources(sources) {
        const tableData = sources.map(source => {
            return {
                path: this.truncatePath(source.path, 50),
                type: this.renderTypeBadge(source.type),
                chunk_count: source.chunk_count.toLocaleString(),
                last_indexed_at: source.last_indexed_at
                    ? new Date(source.last_indexed_at).toLocaleString()
                    : '-',
                status: this.renderStatusBadge(source.status),
                actions: this.renderActions(source),
                _raw: source
            };
        });

        this.dataTable.setData(tableData);
    }

    truncatePath(path, maxLength) {
        if (path.length <= maxLength) return path;
        return '...' + path.substring(path.length - maxLength + 3);
    }

    renderTypeBadge(type) {
        const badges = {
            'directory': '<span class="tag-badge">Directory</span>',
            'file': '<span class="tag-badge">File</span>',
            'git': '<span class="tag-badge">Git</span>'
        };
        return badges[type] || type;
    }

    renderStatusBadge(status) {
        const badges = {
            'pending': '<span class="status-badge status-pending">Pending</span>',
            'indexed': '<span class="status-badge status-success">Indexed</span>',
            'failed': '<span class="status-badge status-error">Failed</span>'
        };
        return badges[status] || status;
    }

    renderActions(source) {
        return `
            <div class="actions">
                <button class="btn-xs btn-secondary" onclick="window.currentSourcesView.showEditModal('${source.source_id}')">
                    <span class="material-icons md-16">edit</span>
                </button>
                <button class="btn-xs btn-danger" onclick="window.currentSourcesView.deleteSource('${source.source_id}')">
                    <span class="material-icons md-16">delete</span>
                </button>
            </div>
        `;
    }

    updateCount(count) {
        const countEl = this.container.querySelector('#sources-count');
        const total = count !== undefined ? count : this.sources.length;
        countEl.textContent = total === 1 ? '1 source' : `${total} sources`;
    }

    showAddModal() {
        window.currentSourcesView = this;
        this.currentSourceId = null;

        const modal = this.container.querySelector('#sources-modal');
        const title = this.container.querySelector('#sources-modal-title');
        const form = this.container.querySelector('#sources-form');

        title.textContent = 'Add Data Source';
        form.reset();

        modal.classList.remove('hidden');
        modal.style.display = 'flex';
    }

    showEditModal(sourceId) {
        window.currentSourcesView = this;
        this.currentSourceId = sourceId;

        const source = this.sources.find(s => s.source_id === sourceId);
        if (!source) return;

        const modal = this.container.querySelector('#sources-modal');
        const title = this.container.querySelector('#sources-modal-title');

        title.textContent = 'Edit Data Source';

        // Populate form
        this.container.querySelector('#source-type').value = source.type;
        this.container.querySelector('#source-path').value = source.path;
        this.container.querySelector('#source-config').value = source.config
            ? JSON.stringify(source.config, null, 2)
            : '';

        modal.classList.remove('hidden');
        modal.style.display = 'flex';
    }

    closeModal() {
        const modal = this.container.querySelector('#sources-modal');
        modal.classList.add('hidden');
        modal.style.display = 'none';
    }

    async handleFormSubmit() {
        try {
            const type = this.container.querySelector('#source-type').value;
            const path = this.container.querySelector('#source-path').value;
            const configText = this.container.querySelector('#source-config').value.trim();

            let config = null;
            if (configText) {
                try {
                    config = JSON.parse(configText);
                } catch (e) {
                    Toast.error('Invalid JSON in configuration');
                    return;
                }
            }

            if (this.currentSourceId) {
                // Update existing source
                // CSRF Fix: Use fetchWithCSRF for protected endpoint
                const response = await window.fetchWithCSRF(`/api/knowledge/sources/${this.currentSourceId}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path, config })
                });

                const data = await response.json();
                if (data.ok) {
                    Toast.success('Source updated successfully');
                    this.closeModal();
                    this.loadSources();
                } else {
                    Toast.error(`Update failed: ${data.error}`);
                }
            } else {
                // Create new source
                // CSRF Fix: Use fetchWithCSRF for protected endpoint
                const response = await window.fetchWithCSRF('/api/knowledge/sources', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ type, path, config })
                });

                const data = await response.json();
                if (data.ok) {
                    Toast.success('Source created successfully');
                    this.closeModal();
                    this.loadSources();
                } else {
                    Toast.error(`Creation failed: ${data.error}`);
                }
            }
        } catch (error) {
            console.error('Form submit error:', error);
            Toast.error(`Error: ${error.message}`);
        }
    }

    async deleteSource(sourceId) {
        const confirmed = await Dialog.confirm('Are you sure you want to delete this data source?', {
            title: 'Delete Data Source',
            confirmText: 'Delete',
            danger: true
        });
        if (!confirmed) {
            return;
        }

        try {
            // CSRF Fix: Use fetchWithCSRF for protected endpoint
            const response = await window.fetchWithCSRF(`/api/knowledge/sources/${sourceId}`, {
                method: 'DELETE'
            });

            const data = await response.json();
            if (data.ok) {
                Toast.success('Source deleted successfully');
                this.loadSources();
            } else {
                Toast.error(`Delete failed: ${data.error}`);
            }
        } catch (error) {
            console.error('Delete error:', error);
            Toast.error(`Delete error: ${error.message}`);
        }
    }

    showSourceDetail(row) {
        const source = row._raw;
        if (!source) return;

        const drawer = this.container.querySelector('#sources-drawer');
        const drawerBody = this.container.querySelector('#sources-drawer-body');

        drawerBody.innerHTML = `
            <div class="source-detail">
                <div class="detail-section">
                    <h4>Basic Information</h4>
                    <div class="detail-info">
                        <div class="info-row">
                            <span class="info-label">Source ID:</span>
                            <span class="info-value code">${source.source_id}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Type:</span>
                            <span class="info-value">${source.type}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Path:</span>
                            <span class="info-value">${source.path}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Status:</span>
                            <span class="info-value">${this.renderStatusBadge(source.status)}</span>
                        </div>
                    </div>
                </div>

                <div class="detail-section">
                    <h4>Statistics</h4>
                    <div class="detail-info">
                        <div class="info-row">
                            <span class="info-label">Chunk Count:</span>
                            <span class="info-value">${source.chunk_count.toLocaleString()}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Last Indexed:</span>
                            <span class="info-value">${source.last_indexed_at ? new Date(source.last_indexed_at).toLocaleString() : 'Never'}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Created At:</span>
                            <span class="info-value">${new Date(source.created_at).toLocaleString()}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Updated At:</span>
                            <span class="info-value">${new Date(source.updated_at).toLocaleString()}</span>
                        </div>
                    </div>
                </div>

                <div class="detail-section">
                    <h4>Configuration</h4>
                    <div class="content-preview">
                        <pre>${JSON.stringify(source.config || {}, null, 2)}</pre>
                    </div>
                </div>

                <div class="detail-actions">
                    <button class="btn-primary" onclick="window.currentSourcesView.showEditModal('${source.source_id}')">
                        <span class="icon"><span class="material-icons md-18">edit</span></span>
                        Edit
                    </button>
                    <button class="btn-danger" onclick="window.currentSourcesView.deleteSource('${source.source_id}')">
                        <span class="icon"><span class="material-icons md-18">delete</span></span>
                        Delete
                    </button>
                </div>
            </div>
        `;

        window.currentSourcesView = this;
        drawer.classList.remove('hidden');
    }

    closeDrawer() {
        const drawer = this.container.querySelector('#sources-drawer');
        drawer.classList.add('hidden');
    }

    destroy() {
        // Clean up components
        if (this.filterBar && typeof this.filterBar.destroy === 'function') {
            this.filterBar.destroy();
        }
        if (this.dataTable && typeof this.dataTable.destroy === 'function') {
            this.dataTable.destroy();
        }
        // Clear container
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}

// Export for use in main.js
window.KnowledgeSourcesView = KnowledgeSourcesView;
