/**
 * HistoryView - Command History UI
 *
 * Coverage: GET /api/history
 */

class HistoryView {
    constructor(container) {
        this.container = container;
        this.filterBar = null;
        this.dataTable = null;
        this.currentFilters = {
            command_id: '',
            status: '',
            session_id: '',
            limit: 100
        };

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="history-view">
                <div class="view-header">
                    <div class="header-title">
                        <h1>Command History</h1>
                        <p class="text-sm text-gray-600 mt-1">Browse command execution history</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="history-refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                        <button class="btn-secondary" id="history-view-pinned">
                            <span class="icon"><span class="material-icons md-18">attachment</span></span> Pinned
                        </button>
                    </div>
                </div>

                <div class="filter-section" id="history-filter"></div>

                <div class="table-section" id="history-table"></div>

                <!-- History Detail Drawer -->
                <div id="history-drawer" class="drawer hidden">
                    <div class="drawer-overlay"></div>
                    <div class="drawer-content">
                        <div class="drawer-header">
                            <h3>Command Details</h3>
                            <button class="btn-close">×</button>
                        </div>
                        <div class="drawer-body" id="history-drawer-body"></div>
                    </div>
                </div>
            </div>
        `;

        this.setupFilterBar();
        this.setupDataTable();
        this.setupEventListeners();
        this.loadHistory();
    }

    setupFilterBar() {
        const filterSection = document.getElementById('history-filter');
        if (!filterSection) return;

        this.filterBar = new FilterBar(filterSection, {
            filters: [
                {
                    type: 'text',
                    key: 'command_id',
                    label: 'Command ID',
                    placeholder: 'e.g., kb:search'
                },
                {
                    type: 'select',
                    key: 'status',
                    label: 'Status',
                    options: [
                        { value: '', label: 'All' },
                        { value: 'success', label: 'Success' },
                        { value: 'failure', label: 'Failure' },
                        { value: 'running', label: 'Running' }
                    ]
                },
                {
                    type: 'text',
                    key: 'session_id',
                    label: 'Session ID',
                    placeholder: 'Filter by session'
                }
            ],
            onChange: (filters) => {
                Object.assign(this.currentFilters, filters);
                this.loadHistory();
            }
        });
    }

    setupDataTable() {
        const tableSection = document.getElementById('history-table');
        if (!tableSection) return;

        this.dataTable = new DataTable(tableSection, {
            columns: [
                {
                    key: 'executed_at',
                    label: 'Time',
                    render: (value) => {
                        const date = new Date(value);
                        return `<div class="text-sm">
                            <div class="font-medium">${date.toLocaleTimeString()}</div>
                            <div class="text-gray-500">${date.toLocaleDateString()}</div>
                        </div>`;
                    }
                },
                {
                    key: 'command_id',
                    label: 'Command',
                    render: (value, row) => {
                        const pinIcon = row.is_pinned ? '<span class="material-icons md-14">attachment</span>' : '';
                        return `<div class="flex items-center gap-2">
                            ${pinIcon}
                            <code class="text-xs font-mono">${value}</code>
                        </div>`;
                    }
                },
                {
                    key: 'status',
                    label: 'Status',
                    render: (value) => this.renderStatusBadge(value)
                },
                {
                    key: 'duration_ms',
                    label: 'Duration',
                    render: (value) => value ? `${value}ms` : '-'
                },
                {
                    key: 'result_summary',
                    label: 'Result',
                    render: (value) => {
                        if (!value) return '-';
                        const truncated = value.length > 50 ? value.substring(0, 50) + '...' : value;
                        return `<div class="text-sm text-gray-700">${this.escapeHtml(truncated)}</div>`;
                    }
                }
            ],
            emptyMessage: 'No command history found',
            onRowClick: (row) => this.showHistoryDetail(row),
            pagination: true,
            pageSize: 10
        });
    }

    setupEventListeners() {
        // Refresh button
        const refreshBtn = document.getElementById('history-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadHistory(true));
        }

        // View pinned button
        const pinnedBtn = document.getElementById('history-view-pinned');
        if (pinnedBtn) {
            pinnedBtn.addEventListener('click', () => this.loadPinned());
        }

        // Drawer overlay and close button
        const drawer = document.getElementById('history-drawer');
        const overlay = drawer?.querySelector('.drawer-overlay');
        const closeBtn = drawer?.querySelector('.btn-close');

        if (overlay) {
            overlay.addEventListener('click', () => this.closeDrawer());
        }

        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.closeDrawer());
        }
    }

    async loadHistory(forceRefresh = false) {
        if (this.dataTable) {
            this.dataTable.setLoading(true);
        }

        try {
            // Build query params
            const params = new URLSearchParams();
            if (this.currentFilters.command_id) {
                params.append('command_id', this.currentFilters.command_id);
            }
            if (this.currentFilters.status) {
                params.append('status', this.currentFilters.status);
            }
            if (this.currentFilters.session_id) {
                params.append('session_id', this.currentFilters.session_id);
            }
            params.append('limit', this.currentFilters.limit);

            const response = await apiClient.get(`/api/history?${params}`);

            if (!response.ok) {
                throw new Error(response.error || 'Failed to load history');
            }

            const history = response.data || [];

            if (this.dataTable) {
                this.dataTable.setData(history);
                this.dataTable.setLoading(false);  // check_circle Close加载Status
            }

            if (forceRefresh && window.showToast) {
                window.showToast(`Loaded ${history.length} history entries`, 'success', 1500);
            }

        } catch (error) {
            console.error('Failed to load history:', error);

            if (this.dataTable) {
                this.dataTable.setData([]);
                this.dataTable.setLoading(false);
            }

            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    async loadPinned() {
        if (this.dataTable) {
            this.dataTable.setLoading(true);
        }

        try {
            const response = await apiClient.get('/api/history/pinned');

            if (!response.ok) {
                throw new Error(response.error || 'Failed to load pinned commands');
            }

            const pinned = response.data || [];

            if (this.dataTable) {
                this.dataTable.setData(pinned);
                this.dataTable.setLoading(false);  // check_circle Close加载Status
            }

            if (window.showToast) {
                window.showToast(`Loaded ${pinned.length} pinned commands`, 'success', 1500);
            }

        } catch (error) {
            console.error('Failed to load pinned commands:', error);

            if (this.dataTable) {
                this.dataTable.setData([]);
                this.dataTable.setLoading(false);
            }

            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    showHistoryDetail(history) {
        const drawer = document.getElementById('history-drawer');
        const drawerBody = document.getElementById('history-drawer-body');

        if (!drawer || !drawerBody) return;

        // Render history detail
        drawerBody.innerHTML = `
            <div class="history-detail">
                <!-- Basic Info -->
                <div class="detail-section">
                    <h4>Basic Information</h4>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <label>History ID</label>
                            <div class="detail-value">
                                <code>${history.id}</code>
                                <button class="btn-copy" data-copy="${history.id}">
                                    <span class="material-icons md-14">content_copy</span>
                                </button>
                            </div>
                        </div>
                        <div class="detail-item">
                            <label>Command ID</label>
                            <div class="detail-value">
                                <code>${this.escapeHtml(history.command_id)}</code>
                            </div>
                        </div>
                        <div class="detail-item">
                            <label>Status</label>
                            <div class="detail-value">${this.renderStatusBadge(history.status)}</div>
                        </div>
                        <div class="detail-item">
                            <label>Executed At</label>
                            <div class="detail-value">${new Date(history.executed_at).toLocaleString()}</div>
                        </div>
                        ${history.duration_ms ? `
                            <div class="detail-item">
                                <label>Duration</label>
                                <div class="detail-value">${history.duration_ms}ms</div>
                            </div>
                        ` : ''}
                        ${history.session_id ? `
                            <div class="detail-item">
                                <label>Session ID</label>
                                <div class="detail-value">
                                    <code>${this.escapeHtml(history.session_id)}</code>
                                    <button class="btn-link" id="view-session">View Session</button>
                                </div>
                            </div>
                        ` : ''}
                        ${history.task_id ? `
                            <div class="detail-item">
                                <label>Task ID</label>
                                <div class="detail-value">
                                    <code>${this.escapeHtml(history.task_id)}</code>
                                    <button class="btn-link" id="view-task">View Task</button>
                                </div>
                            </div>
                        ` : ''}
                    </div>
                </div>

                <!-- Arguments -->
                ${history.args && Object.keys(history.args).length > 0 ? `
                    <div class="detail-section">
                        <h4>Arguments</h4>
                        <div class="json-viewer-container"></div>
                    </div>
                ` : ''}

                <!-- Result Summary -->
                ${history.result_summary ? `
                    <div class="detail-section">
                        <h4>Result Summary</h4>
                        <div class="detail-description">${this.escapeHtml(history.result_summary)}</div>
                    </div>
                ` : ''}

                <!-- Error -->
                ${history.error ? `
                    <div class="detail-section">
                        <h4>Error</h4>
                        <div class="error-box">${this.escapeHtml(history.error)}</div>
                    </div>
                ` : ''}

                <!-- Actions -->
                <div class="detail-section">
                    <h4>Actions</h4>
                    <div class="detail-actions">
                        ${history.is_pinned ? `
                            <button class="btn-secondary" id="unpin-command">
                                <span class="material-icons md-18">attachment</span> Unpin
                            </button>
                        ` : `
                            <button class="btn-primary" id="pin-command">
                                <span class="material-icons md-18">attachment</span> Pin
                            </button>
                        `}
                        <button class="btn-secondary" id="copy-command-id">
                            <span class="material-icons md-18">content_copy</span> Copy Command ID
                        </button>
                        ${history.task_id ? `
                            <button class="btn-secondary" id="view-provenance" data-task-id="${this.escapeHtml(history.task_id)}">
                                <span class="material-icons md-18">search</span> View Provenance
                            </button>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;

        // Render JSON viewer for args
        if (history.args && Object.keys(history.args).length > 0) {
            const jsonContainer = drawerBody.querySelector('.json-viewer-container');
            if (jsonContainer) {
                new JsonViewer(jsonContainer, history.args);
            }
        }

        // Setup copy buttons
        drawerBody.querySelectorAll('.btn-copy').forEach(btn => {
            btn.addEventListener('click', () => {
                const text = btn.dataset.copy;
                navigator.clipboard.writeText(text);
                if (window.showToast) {
                    window.showToast('Copied to clipboard', 'success', 1000);
                }
            });
        });

        // Setup pin/unpin buttons
        const pinBtn = drawerBody.querySelector('#pin-command');
        if (pinBtn) {
            pinBtn.addEventListener('click', () => this.pinCommand(history));
        }

        const unpinBtn = drawerBody.querySelector('#unpin-command');
        if (unpinBtn) {
            unpinBtn.addEventListener('click', () => this.unpinCommand(history));
        }

        // Setup copy command ID button
        const copyIdBtn = drawerBody.querySelector('#copy-command-id');
        if (copyIdBtn) {
            copyIdBtn.addEventListener('click', () => {
                navigator.clipboard.writeText(history.command_id);
                if (window.showToast) {
                    window.showToast('Command ID copied', 'success', 1000);
                }
            });
        }

        // Setup view provenance button
        const provenanceBtn = drawerBody.querySelector('#view-provenance');
        if (provenanceBtn) {
            provenanceBtn.addEventListener('click', () => {
                const taskId = provenanceBtn.dataset.taskId;
                // Navigate to governance dashboard with task filter
                // For now, navigate to governance findings view
                if (typeof updateNavigationActive === 'function') {
                    updateNavigationActive('governance-findings');
                    loadView('governance-findings');
                    // Store the task_id for the view to use
                    sessionStorage.setItem('governance_filter_task_id', taskId);
                } else {
                    // Fallback
                    window.location.hash = `governance-findings?task_id=${taskId}`;
                }
            });
        }

        // Setup navigation buttons
        const viewSessionBtn = drawerBody.querySelector('#view-session');
        if (viewSessionBtn) {
            viewSessionBtn.addEventListener('click', () => {
                if (window.navigateToView) {
                    window.navigateToView('chat', { session_id: history.session_id });
                }
                this.closeDrawer();
            });
        }

        const viewTaskBtn = drawerBody.querySelector('#view-task');
        if (viewTaskBtn) {
            viewTaskBtn.addEventListener('click', () => {
                if (window.navigateToView) {
                    window.navigateToView('tasks', { task_id: history.task_id });
                }
                this.closeDrawer();
            });
        }

        // Show drawer
        drawer.classList.remove('hidden');
    }

    async pinCommand(history) {
        try {
            const response = await apiClient.post(`/api/history/${history.id}/pin`, {
                note: null
            });

            if (!response.ok) {
                throw new Error(response.error || 'Failed to pin command');
            }

            if (window.showToast) {
                window.showToast('Command pinned successfully', 'success', 1500);
            }

            // Reload history and close drawer
            this.loadHistory();
            this.closeDrawer();

        } catch (error) {
            console.error('Failed to pin command:', error);
            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    async unpinCommand(history) {
        try {
            const response = await apiClient.delete(`/api/history/${history.id}/pin`);

            if (!response.ok) {
                throw new Error(response.error || 'Failed to unpin command');
            }

            if (window.showToast) {
                window.showToast('Command unpinned successfully', 'success', 1500);
            }

            // Reload history and close drawer
            this.loadHistory();
            this.closeDrawer();

        } catch (error) {
            console.error('Failed to unpin command:', error);
            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    closeDrawer() {
        const drawer = document.getElementById('history-drawer');
        if (drawer) {
            drawer.classList.add('hidden');
        }
    }

    renderStatusBadge(status) {
        const statusMap = {
            'success': { label: 'Success', class: 'status-success' },
            'failure': { label: 'Failed', class: 'status-error' },
            'running': { label: 'Running', class: 'status-running' },
        };

        const statusInfo = statusMap[status] || { label: status, class: 'status-unknown' };

        return `<span class="status-badge ${statusInfo.class}">${statusInfo.label}</span>`;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    destroy() {
        // Cleanup
        if (this.filterBar && typeof this.filterBar.destroy === 'function') {
            this.filterBar.destroy();
        }
        if (this.dataTable && typeof this.dataTable.destroy === 'function') {
            this.dataTable.destroy();
        }
        this.container.innerHTML = '';
    }
}
