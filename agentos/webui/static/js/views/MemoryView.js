/**
 * MemoryView - Memory Management UI
 *
 * PR-4: Skills/Memory/Config Module
 * Coverage: GET /api/memory/search, POST /api/memory/upsert, GET /api/memory/{id}
 */

class MemoryView {
    constructor(container) {
        this.container = container;
        this.filterBar = null;
        this.dataTable = null;
        this.detailDrawer = null;
        this.currentFilters = {};
        this.memories = [];
        this.selectedMemory = null;

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="memory-view">
                <div class="view-header">
                    <div>
                        <h1>Memory Management</h1>
                        <p class="text-sm text-gray-600 mt-1">Store and retrieve long-term memory</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="memory-refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                        <button class="btn-primary" id="memory-add">
                            <span class="icon"><span class="material-icons md-18">add</span></span> Add Memory
                        </button>
                    </div>
                </div>

                <div id="memory-filter-bar" class="filter-section"></div>

                <div id="memory-table" class="table-section"></div>

                <div id="memory-detail-drawer" class="drawer hidden">
                    <div class="drawer-overlay" id="memory-drawer-overlay"></div>
                    <div class="drawer-content">
                        <div class="drawer-header">
                            <h3>Memory Details</h3>
                            <button class="btn-close" id="memory-drawer-close">
                                <span class="material-icons">close</span>
                            </button>
                        </div>
                        <div class="drawer-body" id="memory-drawer-body">
                            <!-- Memory details will be rendered here -->
                        </div>
                    </div>
                </div>

                <div id="memory-add-drawer" class="drawer hidden">
                    <div class="drawer-overlay" id="memory-add-overlay"></div>
                    <div class="drawer-content">
                        <div class="drawer-header">
                            <h3>Add Memory Item</h3>
                            <button class="btn-close" id="memory-add-close">
                                <span class="material-icons">close</span>
                            </button>
                        </div>
                        <div class="drawer-body" id="memory-add-body">
                            <!-- Add memory form will be rendered here -->
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.setupFilterBar();
        this.setupDataTable();
        this.setupEventListeners();
        this.loadMemories();
    }

    setupFilterBar() {
        const filterContainer = this.container.querySelector('#memory-filter-bar');

        this.filterBar = new FilterBar(filterContainer, {
            filters: [
                {
                    type: 'text',
                    key: 'q',
                    label: 'Search',
                    placeholder: 'Search by key or value...'
                },
                {
                    type: 'text',
                    key: 'namespace',
                    label: 'Namespace',
                    placeholder: 'Filter by namespace...'
                },
                {
                    type: 'time-range',
                    key: 'time_range',
                    label: 'Time Range',
                    placeholder: 'Select time range'
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
        const tableContainer = this.container.querySelector('#memory-table');

        this.dataTable = new DataTable(tableContainer, {
            columns: [
                {
                    key: 'id',
                    label: 'Memory ID',
                    width: '20%',
                    render: (value) => `
                        <div class="flex items-center space-x-2">
                            <span class="font-mono text-xs text-blue-600">${value}</span>
                            <button class="btn-icon copy-btn" data-copy="${value}" title="Copy ID">
                                <span class="material-icons md-18">content_copy</span>
                            </button>
                        </div>
                    `
                },
                {
                    key: 'namespace',
                    label: 'Namespace',
                    width: '15%',
                    render: (value) => `<span class="badge badge-info">${value}</span>`
                },
                {
                    key: 'value',
                    label: 'Value',
                    width: '35%',
                    render: (value) => {
                        const truncated = value.length > 100 ? value.substring(0, 100) + '...' : value;
                        return `<span class="text-sm text-gray-700">${this.escapeHtml(truncated)}</span>`;
                    }
                },
                {
                    key: 'source_type',
                    label: 'Source',
                    width: '10%',
                    render: (value) => value
                        ? `<span class="badge badge-${value === 'manual' ? 'warning' : 'info'}">${value}</span>`
                        : '<span class="text-xs text-gray-400">N/A</span>'
                },
                {
                    key: 'updated_at',
                    label: 'Last Updated',
                    width: '15%',
                    render: (value, row) => {
                        const updated = value || row.created_at;
                        const versionBadge = row.version && row.version > 1
                            ? `<span class="badge badge-sm badge-info ml-1">v${row.version}</span>`
                            : '';
                        return `
                            <span class="text-xs text-gray-600" title="${new Date(updated).toLocaleString()}">
                                ${this.formatRelativeTime(new Date(updated))}${versionBadge}
                            </span>
                        `;
                    }
                },
                {
                    key: 'actions',
                    label: 'Actions',
                    width: '5%',
                    render: (_, row) => `
                        <button class="btn-sm btn-primary" data-action="view" data-memory="${row.id}">
                            View
                        </button>
                    `
                }
            ],
            emptyMessage: 'No memory items found',
            onRowClick: (row) => this.showMemoryDetail(row),
            pagination: true,
            pageSize: 10
        });
    }

    setupEventListeners() {
        // Refresh button
        const refreshBtn = this.container.querySelector('#memory-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadMemories(true));
        }

        // Add button
        const addBtn = this.container.querySelector('#memory-add');
        if (addBtn) {
            addBtn.addEventListener('click', () => this.showAddMemoryDrawer());
        }

        // Detail drawer close
        const detailOverlay = this.container.querySelector('#memory-drawer-overlay');
        const detailClose = this.container.querySelector('#memory-drawer-close');

        if (detailOverlay) {
            detailOverlay.addEventListener('click', () => this.closeDrawer());
        }

        if (detailClose) {
            detailClose.addEventListener('click', () => this.closeDrawer());
        }

        // Add drawer close
        const addOverlay = this.container.querySelector('#memory-add-overlay');
        const addClose = this.container.querySelector('#memory-add-close');

        if (addOverlay) {
            addOverlay.addEventListener('click', () => this.closeAddDrawer());
        }

        if (addClose) {
            addClose.addEventListener('click', () => this.closeAddDrawer());
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
                const memoryId = actionBtn.dataset.memory;
                const memory = this.memories.find(m => m.id === memoryId);
                if (memory) {
                    this.showMemoryDetail(memory);
                }
            }
        });
    }

    handleFilterChange(filters) {
        this.currentFilters = filters;
        this.loadMemories();
    }

    async loadMemories(forceRefresh = false) {
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
            if (this.currentFilters.namespace) {
                params.append('namespace', this.currentFilters.namespace);
            }
            params.append('limit', '200'); // Max results

            // Call API
            const response = await apiClient.get(`/api/memory/search?${params.toString()}`);

            if (!response.ok) {
                throw new Error(response.error || 'Failed to load memory items');
            }

            this.memories = response.data || [];

            // Client-side time range filtering (if API doesn't support it)
            let filteredMemories = this.memories;

            if (this.currentFilters.time_range) {
                const { from, to } = this.currentFilters.time_range;
                if (from || to) {
                    filteredMemories = filteredMemories.filter(memory => {
                        const createdAt = new Date(memory.created_at);
                        if (from && createdAt < new Date(from)) return false;
                        if (to && createdAt > new Date(to)) return false;
                        return true;
                    });
                }
            }

            // Update table
            if (this.dataTable) {
                this.dataTable.setData(filteredMemories);
                this.dataTable.setLoading(false);
            }

            // Show success toast (only on manual refresh)
            if (forceRefresh && window.showToast) {
                window.showToast(`Loaded ${filteredMemories.length} memory items`, 'success', 1500);
            }

        } catch (error) {
            console.error('Failed to load memory items:', error);

            if (this.dataTable) {
                this.dataTable.setLoading(false);
                this.dataTable.showError(error.message || 'Failed to load memory items');
            }

            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    async showMemoryDetail(memory) {
        this.selectedMemory = memory;

        const drawer = this.container.querySelector('#memory-detail-drawer');
        const drawerBody = this.container.querySelector('#memory-drawer-body');

        if (!drawer || !drawerBody) return;

        // Show loading state
        drawerBody.innerHTML = '<div class="text-center py-8">Loading memory details...</div>';
        drawer.classList.remove('hidden');

        try {
            // Fetch full memory details (optional, may not be needed)
            const response = await apiClient.get(`/api/memory/${memory.id}`);

            const memoryDetail = response.ok ? (response.data || memory) : memory;

            // Render detail view
            drawerBody.innerHTML = `
                <div class="memory-detail">
                    <!-- Header Section -->
                    <div class="detail-section">
                        <div class="flex items-center justify-between mb-4">
                            <div class="flex-1">
                                <h4 class="text-lg font-semibold text-gray-900 font-mono">${this.escapeHtml(memoryDetail.id)}</h4>
                                <p class="text-sm text-gray-600 mt-1">${this.escapeHtml(memoryDetail.key)}</p>
                            </div>
                            <span class="badge badge-info">${memoryDetail.namespace}</span>
                        </div>
                    </div>

                    <!-- Value Section -->
                    <div class="detail-section">
                        <h5 class="detail-section-title">Value</h5>
                        <div class="bg-gray-50 p-4 rounded border border-gray-200">
                            <pre class="text-sm whitespace-pre-wrap">${this.escapeHtml(memoryDetail.value)}</pre>
                        </div>
                    </div>

                    <!-- Quick Info -->
                    <div class="detail-section">
                        <h5 class="detail-section-title">Metadata</h5>
                        <div class="detail-grid">
                            <div class="detail-item">
                                <span class="detail-label">Namespace</span>
                                <span class="detail-value">${memoryDetail.namespace}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Created</span>
                                <span class="detail-value">${new Date(memoryDetail.created_at).toLocaleString()}</span>
                            </div>
                            ${memoryDetail.updated_at ? `
                                <div class="detail-item">
                                    <span class="detail-label">Last Updated</span>
                                    <span class="detail-value">
                                        ${new Date(memoryDetail.updated_at).toLocaleString()}
                                        <span class="text-xs text-gray-500 ml-1">(${this.formatRelativeTime(new Date(memoryDetail.updated_at))})</span>
                                    </span>
                                </div>
                            ` : ''}
                            ${memoryDetail.version && memoryDetail.version > 1 ? `
                                <div class="detail-item">
                                    <span class="detail-label">Version</span>
                                    <span class="detail-value">
                                        <span class="badge badge-info">v${memoryDetail.version}</span>
                                        ${memoryDetail.supersedes ? `<span class="text-xs text-gray-500 ml-2">Updated from previous version</span>` : ''}
                                    </span>
                                </div>
                            ` : ''}
                            ${!memoryDetail.is_active || memoryDetail.is_active === false ? `
                                <div class="detail-item">
                                    <span class="detail-label">Status</span>
                                    <span class="detail-value">
                                        <span class="badge badge-warning">Superseded</span>
                                        ${memoryDetail.superseded_at ? `<span class="text-xs text-gray-500 ml-2">${this.formatRelativeTime(new Date(memoryDetail.superseded_at))}</span>` : ''}
                                    </span>
                                </div>
                            ` : ''}
                            ${memoryDetail.source_type ? `
                                <div class="detail-item">
                                    <span class="detail-label">Source Type</span>
                                    <span class="detail-value">
                                        <span class="badge badge-info">${memoryDetail.source_type}</span>
                                    </span>
                                </div>
                            ` : ''}
                            ${memoryDetail.source ? `
                                <div class="detail-item">
                                    <span class="detail-label">Source ID</span>
                                    <span class="detail-value font-mono text-xs">${memoryDetail.source}</span>
                                </div>
                            ` : ''}
                            ${memoryDetail.ttl ? `
                                <div class="detail-item">
                                    <span class="detail-label">TTL</span>
                                    <span class="detail-value">${memoryDetail.ttl} seconds</span>
                                </div>
                            ` : ''}
                        </div>
                    </div>

                    <!-- Full JSON -->
                    <div class="detail-section">
                        <h5 class="detail-section-title">Full Data</h5>
                        <div class="json-viewer-container"></div>
                    </div>

                    <!-- Actions -->
                    <div class="detail-section">
                        <h5 class="detail-section-title">Actions</h5>
                        <div class="flex gap-2 flex-wrap">
                            <button class="btn-sm btn-secondary" id="copy-memory-id">
                                <span class="material-icons md-18">content_copy</span> Copy ID
                            </button>
                            ${(memoryDetail.version && memoryDetail.version > 1) || memoryDetail.supersedes || memoryDetail.superseded_by ? `
                                <button class="btn-sm btn-secondary" id="view-history">
                                    <span class="material-icons md-18">history</span> View History
                                </button>
                            ` : ''}
                            ${memoryDetail.source ? `
                                <button class="btn-sm btn-secondary" id="view-source">
                                    <span class="material-icons md-18">link</span> View Source
                                </button>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;

            // Render JSON viewer
            const jsonContainer = drawerBody.querySelector('.json-viewer-container');
            if (jsonContainer) {
                new JsonViewer(jsonContainer, memoryDetail);
            }

            // Setup action buttons
            const copyBtn = drawerBody.querySelector('#copy-memory-id');
            if (copyBtn) {
                copyBtn.addEventListener('click', () => {
                    navigator.clipboard.writeText(memoryDetail.id);
                    if (window.showToast) {
                        window.showToast('Memory ID copied', 'success', 1500);
                    }
                });
            }

            const viewHistoryBtn = drawerBody.querySelector('#view-history');
            if (viewHistoryBtn) {
                viewHistoryBtn.addEventListener('click', () => this.showVersionHistory(memoryDetail));
            }

            const viewSourceBtn = drawerBody.querySelector('#view-source');
            if (viewSourceBtn) {
                viewSourceBtn.addEventListener('click', () => {
                    if (window.navigateToView) {
                        if (memoryDetail.source_type === 'task') {
                            window.navigateToView('tasks', { task_id: memoryDetail.source });
                        } else if (memoryDetail.source_type === 'session') {
                            window.navigateToView('sessions', { session_id: memoryDetail.source });
                        }
                    }
                    this.closeDrawer();
                });
            }

        } catch (error) {
            console.error('Failed to load memory details:', error);
            drawerBody.innerHTML = `
                <div class="text-center py-8 text-red-600">
                    <p>Failed to load memory details</p>
                    <p class="text-sm mt-2">${error.message}</p>
                </div>
            `;

            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    showAddMemoryDrawer() {
        const drawer = this.container.querySelector('#memory-add-drawer');
        const drawerBody = this.container.querySelector('#memory-add-body');

        if (!drawer || !drawerBody) return;

        drawerBody.innerHTML = `
            <div class="memory-add-form">
                <div class="detail-section">
                    <p class="text-sm text-gray-600 mb-4">
                        Create a new memory item. All fields are required.
                    </p>

                    <div class="space-y-4">
                        <div class="form-group">
                            <label for="memory-namespace" class="form-label">Namespace *</label>
                            <input
                                type="text"
                                id="memory-namespace"
                                class="form-control"
                                placeholder="default"
                                value="default"
                                required
                            />
                            <small class="text-xs text-gray-500">Group/category for this memory item</small>
                        </div>

                        <div class="form-group">
                            <label for="memory-key" class="form-label">Key *</label>
                            <input
                                type="text"
                                id="memory-key"
                                class="form-control"
                                placeholder="user_preference"
                                required
                            />
                            <small class="text-xs text-gray-500">Unique identifier within the namespace</small>
                        </div>

                        <div class="form-group">
                            <label for="memory-value" class="form-label">Value *</label>
                            <textarea
                                id="memory-value"
                                class="form-control"
                                rows="4"
                                placeholder="Enter memory content..."
                                required
                            ></textarea>
                            <small class="text-xs text-gray-500">The actual data to store</small>
                        </div>

                        <div class="form-group">
                            <label for="memory-source" class="form-label">Source (Optional)</label>
                            <input
                                type="text"
                                id="memory-source"
                                class="form-control"
                                placeholder="task_id or session_id"
                            />
                            <small class="text-xs text-gray-500">Related task/session ID</small>
                        </div>

                        <div class="form-group">
                            <label for="memory-ttl" class="form-label">TTL (seconds, Optional)</label>
                            <input
                                type="number"
                                id="memory-ttl"
                                class="form-control"
                                placeholder="3600"
                                min="0"
                            />
                            <small class="text-xs text-gray-500">Time to live in seconds (0 = never expires)</small>
                        </div>
                    </div>

                    <div class="mt-6 flex gap-2">
                        <button class="btn-primary" id="memory-save-btn">
                            <span class="material-icons md-18">save</span> Save Memory
                        </button>
                        <button class="btn-secondary" id="memory-cancel-btn">
                            Cancel
                        </button>
                    </div>

                    <div id="memory-save-status" class="mt-4"></div>
                </div>
            </div>
        `;

        drawer.classList.remove('hidden');

        // Setup form handlers
        const saveBtn = drawerBody.querySelector('#memory-save-btn');
        const cancelBtn = drawerBody.querySelector('#memory-cancel-btn');

        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.handleSaveMemory());
        }

        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.closeAddDrawer());
        }
    }

    async showVersionHistory(memory) {
        try {
            // Fetch version history from API
            const response = await apiClient.get(`/api/memory/${memory.id}/history`);

            if (!response.ok) {
                throw new Error(response.error || 'Failed to load version history');
            }

            const history = response.data || [];

            if (history.length === 0) {
                if (window.showToast) {
                    window.showToast('No version history available', 'info');
                }
                return;
            }

            // Display history in drawer body
            const drawerBody = this.container.querySelector('#memory-drawer-body');
            if (!drawerBody) return;

            drawerBody.innerHTML = `
                <div class="memory-history">
                    <div class="detail-section">
                        <div class="flex items-center justify-between mb-4">
                            <div>
                                <h4 class="text-lg font-semibold text-gray-900">Version History</h4>
                                <p class="text-sm text-gray-600 mt-1">
                                    ${history.length} version(s) found
                                </p>
                            </div>
                            <button class="btn-sm btn-secondary" id="back-to-detail">
                                <span class="material-icons md-18">arrow_back</span> Back
                            </button>
                        </div>
                    </div>

                    <div class="detail-section">
                        <div class="space-y-4">
                            ${history.map((version, index) => {
                                const isActive = version.is_active !== false;
                                const isCurrent = index === history.length - 1;

                                return `
                                    <div class="memory-version-item p-4 border rounded ${isActive ? 'border-blue-300 bg-blue-50' : 'border-gray-200 bg-gray-50'}">
                                        <div class="flex items-start justify-between mb-3">
                                            <div>
                                                <div class="flex items-center gap-2">
                                                    <span class="badge ${isActive ? 'badge-success' : 'badge-secondary'}">
                                                        v${version.version || index + 1}
                                                    </span>
                                                    ${isCurrent ? '<span class="badge badge-info">Latest</span>' : ''}
                                                    ${isActive ? '<span class="badge badge-success">Active</span>' : '<span class="badge badge-warning">Superseded</span>'}
                                                </div>
                                                <p class="text-xs text-gray-600 mt-1 font-mono">${version.id}</p>
                                            </div>
                                            <div class="text-right text-xs text-gray-600">
                                                ${version.updated_at ? new Date(version.updated_at).toLocaleString() : new Date(version.created_at).toLocaleString()}
                                            </div>
                                        </div>

                                        <div class="mb-2">
                                            <span class="text-xs font-semibold text-gray-700">Value:</span>
                                            <div class="bg-white p-2 rounded border border-gray-200 mt-1">
                                                <pre class="text-xs whitespace-pre-wrap">${this.escapeHtml(version.value || JSON.stringify(version.content, null, 2))}</pre>
                                            </div>
                                        </div>

                                        ${version.confidence ? `
                                            <div class="text-xs text-gray-600">
                                                Confidence: <span class="font-semibold">${(version.confidence * 100).toFixed(0)}%</span>
                                            </div>
                                        ` : ''}

                                        ${version.superseded_at && !isActive ? `
                                            <div class="text-xs text-gray-600 mt-1">
                                                Superseded: ${this.formatRelativeTime(new Date(version.superseded_at))}
                                            </div>
                                        ` : ''}
                                    </div>
                                `;
                            }).join('')}
                        </div>
                    </div>
                </div>
            `;

            // Setup back button
            const backBtn = drawerBody.querySelector('#back-to-detail');
            if (backBtn) {
                backBtn.addEventListener('click', () => this.showMemoryDetail(memory));
            }

        } catch (error) {
            console.error('Failed to load version history:', error);
            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    async handleSaveMemory() {
        const namespace = document.getElementById('memory-namespace')?.value?.trim();
        const key = document.getElementById('memory-key')?.value?.trim();
        const value = document.getElementById('memory-value')?.value?.trim();
        const source = document.getElementById('memory-source')?.value?.trim();
        const ttl = document.getElementById('memory-ttl')?.value;

        const statusDiv = document.getElementById('memory-save-status');

        // Validation
        if (!namespace || !key || !value) {
            if (statusDiv) {
                statusDiv.innerHTML = '<p class="text-sm text-red-600">All required fields must be filled</p>';
            }
            return;
        }

        try {
            // Show loading
            if (statusDiv) {
                statusDiv.innerHTML = '<p class="text-sm text-blue-600">Saving memory item...</p>';
            }

            // Build request body
            const requestBody = {
                namespace,
                key,
                value,
                source_type: 'manual'
            };

            if (source) {
                requestBody.source = source;
                // Infer source type from ID format
                if (source.startsWith('task_')) {
                    requestBody.source_type = 'task';
                } else if (source.startsWith('session_') || source.includes('-')) {
                    requestBody.source_type = 'session';
                }
            }

            if (ttl && parseInt(ttl) > 0) {
                requestBody.ttl = parseInt(ttl);
            }

            // Call API
            const response = await apiClient.post('/api/memory/upsert', requestBody);

            if (!response.ok) {
                throw new Error(response.error || 'Failed to save memory item');
            }

            // Success
            if (window.showToast) {
                window.showToast('Memory item saved successfully', 'success');
            }

            // Close drawer and refresh list
            this.closeAddDrawer();
            this.loadMemories(true);

        } catch (error) {
            console.error('Failed to save memory:', error);

            if (statusDiv) {
                statusDiv.innerHTML = `<p class="text-sm text-red-600">Error: ${error.message}</p>`;
            }

            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    closeDrawer() {
        const drawer = this.container.querySelector('#memory-detail-drawer');
        if (drawer) {
            drawer.classList.add('hidden');
        }
        this.selectedMemory = null;
    }

    closeAddDrawer() {
        const drawer = this.container.querySelector('#memory-add-drawer');
        if (drawer) {
            drawer.classList.add('hidden');
        }
    }

    // Utility functions
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatRelativeTime(date) {
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        return date.toLocaleDateString();
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
