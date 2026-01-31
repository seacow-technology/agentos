/**
 * LogsView - System Logs UI
 *
 * PR-2: Observability Module - Logs View
 * Coverage: GET /api/logs, GET /api/logs/tail
 */

class LogsView {
    constructor(container) {
        this.container = container;
        this.filterBar = null;
        this.dataTable = null;
        this.currentFilters = {};
        this.logs = [];
        this.tailMode = false;
        this.tailInterval = null;
        this.lastLogTimestamp = null;

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="logs-view">
                <div class="view-header">
                    <div>
                        <h1>System Logs</h1>
                        <p class="text-sm text-gray-600 mt-1">Real-time system logs and diagnostics</p>
                    </div>
                    <div class="header-actions">
                        <div class="tail-toggle">
                            <label class="switch">
                                <input type="checkbox" id="logs-tail-toggle">
                                <span class="slider"></span>
                            </label>
                            <span class="toggle-label">Tail Mode</span>
                        </div>
                        <button class="btn-refresh" id="logs-refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                        <button class="btn-secondary" id="logs-clear">
                            <span class="icon"><span class="material-icons md-18">delete</span></span> Clear
                        </button>
                        <button class="btn-secondary" id="logs-download">
                            <span class="icon"><span class="material-icons md-18">arrow_downward</span></span> Download
                        </button>
                    </div>
                </div>

                <div id="logs-filter-bar" class="filter-section"></div>

                <div class="tail-status" id="logs-tail-status" style="display: none;">
                    <div class="status-indicator pulsing"></div>
                    <span>Tailing logs...</span>
                </div>

                <div id="logs-table" class="table-section"></div>

                <div id="logs-detail-drawer" class="drawer hidden">
                    <div class="drawer-overlay" id="logs-drawer-overlay"></div>
                    <div class="drawer-content">
                        <div class="drawer-header">
                            <h3>Log Details</h3>
                            <button class="btn-close" id="logs-drawer-close">
                                <span class="material-icons">close</span>
                            </button>
                        </div>
                        <div class="drawer-body" id="logs-drawer-body">
                            <!-- Log details will be rendered here -->
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.setupFilterBar();
        this.setupDataTable();
        this.setupEventListeners();
        this.loadLogs();
    }

    setupFilterBar() {
        const filterContainer = this.container.querySelector('#logs-filter-bar');

        this.filterBar = new FilterBar(filterContainer, {
            filters: [
                {
                    type: 'multi-select',
                    key: 'level',
                    label: 'Log Level',
                    options: [
                        { value: 'DEBUG', label: 'DEBUG' },
                        { value: 'INFO', label: 'INFO' },
                        { value: 'WARNING', label: 'WARNING' },
                        { value: 'ERROR', label: 'ERROR' },
                        { value: 'CRITICAL', label: 'CRITICAL' }
                    ]
                },
                {
                    type: 'text',
                    key: 'contains',
                    label: 'Contains',
                    placeholder: 'Search log messages...'
                },
                {
                    type: 'text',
                    key: 'logger',
                    label: 'Logger',
                    placeholder: 'Filter by logger name...'
                },
                {
                    type: 'text',
                    key: 'task_id',
                    label: 'Task ID',
                    placeholder: 'Filter by task...'
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
        const tableContainer = this.container.querySelector('#logs-table');

        this.dataTable = new DataTable(tableContainer, {
            columns: [
                {
                    key: 'timestamp',
                    label: 'Timestamp',
                    width: '180px',
                    render: (value) => this.formatTimestamp(value)
                },
                {
                    key: 'level',
                    label: 'Level',
                    width: '100px',
                    render: (value) => this.renderLogLevel(value)
                },
                {
                    key: 'logger',
                    label: 'Logger',
                    width: '200px',
                    render: (value) => `<code class="code-inline">${value || 'root'}</code>`
                },
                {
                    key: 'message',
                    label: 'Message',
                    width: '500px',
                    render: (value) => {
                        const msg = value || '';
                        return msg.length > 100 ? msg.substring(0, 100) + '...' : msg;
                    }
                },
                {
                    key: 'task_id',
                    label: 'Task',
                    width: '120px',
                    render: (value) => value ? `<code class="code-inline">${value.substring(0, 8)}...</code>` : 'N/A'
                }
            ],
            data: [],
            emptyText: 'No logs found',
            loadingText: 'Loading logs...',
            onRowClick: (log) => this.showLogDetail(log),
            pagination: true,
            pageSize: 10
        });
    }

    setupEventListeners() {
        // Tail toggle
        this.container.querySelector('#logs-tail-toggle').addEventListener('change', (e) => {
            this.toggleTailMode(e.target.checked);
        });

        // Refresh button
        this.container.querySelector('#logs-refresh').addEventListener('click', () => {
            this.loadLogs(true);
        });

        // Clear button
        this.container.querySelector('#logs-clear').addEventListener('click', async () => {
            const confirmed = await Dialog.confirm('Clear all displayed logs?', {
                title: 'Clear Logs',
                confirmText: 'Clear',
                danger: true
            });
            if (confirmed) {
                this.logs = [];
                this.dataTable.setData([]);
            }
        });

        // Download button
        this.container.querySelector('#logs-download').addEventListener('click', () => {
            this.downloadLogs();
        });

        // Drawer close
        this.container.querySelector('#logs-drawer-close').addEventListener('click', () => {
            this.hideLogDetail();
        });

        this.container.querySelector('#logs-drawer-overlay').addEventListener('click', () => {
            this.hideLogDetail();
        });

        // Keyboard shortcut
        const handleKeydown = (e) => {
            if (e.key === 'Escape' && !this.container.querySelector('#logs-detail-drawer').classList.contains('hidden')) {
                this.hideLogDetail();
            }
        };
        document.addEventListener('keydown', handleKeydown);
    }

    handleFilterChange(filters) {
        this.currentFilters = filters;
        this.loadLogs();
    }

    async loadLogs(forceRefresh = false) {
        this.dataTable.setLoading(true);

        try {
            // Build query parameters
            const params = new URLSearchParams();

            if (this.currentFilters.level && this.currentFilters.level.length > 0) {
                // Multi-select: join with comma
                params.append('level', this.currentFilters.level.join(','));
            }
            if (this.currentFilters.contains) {
                params.append('contains', this.currentFilters.contains);
            }
            if (this.currentFilters.logger) {
                params.append('logger', this.currentFilters.logger);
            }
            if (this.currentFilters.task_id) {
                params.append('task_id', this.currentFilters.task_id);
            }
            if (this.currentFilters.time_range) {
                const { start, end } = this.currentFilters.time_range;
                if (start) params.append('start_time', start);
                if (end) params.append('end_time', end);
            }

            // Limit to recent logs if no filters
            if (!this.currentFilters.time_range) {
                params.append('limit', '500');
            }

            const url = `/api/logs${params.toString() ? '?' + params.toString() : ''}`;
            const result = await apiClient.get(url, {
                requestId: `logs-list-${Date.now()}`
            });

            if (result.ok) {
                this.logs = result.data.logs || result.data || [];

                // Sort by timestamp descending (newest first)
                this.logs.sort((a, b) => {
                    const timeA = new Date(a.timestamp || a.created_at || 0);
                    const timeB = new Date(b.timestamp || b.created_at || 0);
                    return timeB - timeA;
                });

                // Update last log timestamp for tail mode
                if (this.logs.length > 0) {
                    this.lastLogTimestamp = this.logs[0].timestamp || this.logs[0].created_at;
                }

                this.dataTable.setData(this.logs);

                if (forceRefresh) {
                    showToast('Logs refreshed', 'success', 2000);
                }
            } else {
                const errorMsg = result.error || result.message || 'Unknown error';
                showToast(`Failed to load logs: ${errorMsg}`, 'error');
                this.dataTable.setData([]);
            }
        } catch (error) {
            console.error('Failed to load logs:', error);
            const errorMsg = error.message || String(error);
            showToast(`Failed to load logs: ${errorMsg}`, 'error');
            this.dataTable.setData([]);
        } finally {
            this.dataTable.setLoading(false);
        }
    }

    toggleTailMode(enabled) {
        this.tailMode = enabled;
        const statusBar = this.container.querySelector('#logs-tail-status');

        if (enabled) {
            statusBar.style.display = 'flex';
            this.startTailing();
        } else {
            statusBar.style.display = 'none';
            this.stopTailing();
        }
    }

    startTailing() {
        // Poll for new logs every 3 seconds
        this.tailInterval = setInterval(() => {
            this.fetchNewLogs();
        }, 3000);

        // Initial fetch
        this.fetchNewLogs();
    }

    stopTailing() {
        if (this.tailInterval) {
            clearInterval(this.tailInterval);
            this.tailInterval = null;
        }
    }

    async fetchNewLogs() {
        try {
            const params = new URLSearchParams();

            // Only fetch logs after the last known timestamp
            if (this.lastLogTimestamp) {
                params.append('after', this.lastLogTimestamp);
            }

            // Apply current filters
            if (this.currentFilters.level && this.currentFilters.level.length > 0) {
                params.append('level', this.currentFilters.level.join(','));
            }
            if (this.currentFilters.contains) {
                params.append('contains', this.currentFilters.contains);
            }
            if (this.currentFilters.logger) {
                params.append('logger', this.currentFilters.logger);
            }
            if (this.currentFilters.task_id) {
                params.append('task_id', this.currentFilters.task_id);
            }

            const url = `/api/logs/tail${params.toString() ? '?' + params.toString() : ''}`;
            const result = await apiClient.get(url, {
                requestId: `logs-tail-${Date.now()}`,
                timeout: 5000
            });

            if (result.ok) {
                const newLogs = result.data.logs || result.data || [];

                if (newLogs.length > 0) {
                    // Prepend new logs
                    this.logs = [...newLogs, ...this.logs];

                    // Update last timestamp
                    this.lastLogTimestamp = newLogs[0].timestamp || newLogs[0].created_at;

                    // Update table
                    this.dataTable.setData(this.logs);

                    // Limit total logs in memory (keep last 5000)
                    if (this.logs.length > 5000) {
                        this.logs = this.logs.slice(0, 5000);
                    }
                }
            }
        } catch (error) {
            console.error('Failed to fetch new logs:', error);
        }
    }

    showLogDetail(log) {
        const drawer = this.container.querySelector('#logs-detail-drawer');
        const drawerBody = this.container.querySelector('#logs-drawer-body');

        drawer.classList.remove('hidden');

        drawerBody.innerHTML = `
            <div class="log-detail">
                <div class="detail-section">
                    <h4>Log Information</h4>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <label>Timestamp</label>
                            <div class="detail-value">${this.formatTimestamp(log.timestamp || log.created_at)}</div>
                        </div>
                        <div class="detail-item">
                            <label>Level</label>
                            <div class="detail-value">${this.renderLogLevel(log.level)}</div>
                        </div>
                        <div class="detail-item">
                            <label>Logger</label>
                            <div class="detail-value"><code>${log.logger || 'root'}</code></div>
                        </div>
                        ${log.task_id ? `
                            <div class="detail-item">
                                <label>Task ID</label>
                                <div class="detail-value">
                                    <code>${log.task_id}</code>
                                    <button class="btn-link" data-task="${log.task_id}">View Task</button>
                                </div>
                            </div>
                        ` : ''}
                        ${log.filename ? `
                            <div class="detail-item">
                                <label>File</label>
                                <div class="detail-value"><code>${log.filename}:${log.lineno || '?'}</code></div>
                            </div>
                        ` : ''}
                        ${log.funcName ? `
                            <div class="detail-item">
                                <label>Function</label>
                                <div class="detail-value"><code>${log.funcName}()</code></div>
                            </div>
                        ` : ''}
                    </div>
                </div>

                <div class="detail-section">
                    <h4>Message</h4>
                    <div class="log-message ${log.level ? 'log-level-' + log.level.toLowerCase() : ''}">
                        <pre>${log.message || 'No message'}</pre>
                    </div>
                </div>

                ${log.exc_info || log.stack_trace ? `
                    <div class="detail-section">
                        <h4>Stack Trace</h4>
                        <div class="stack-trace">
                            <pre>${log.exc_info || log.stack_trace}</pre>
                        </div>
                    </div>
                ` : ''}

                <div class="detail-section">
                    <h4>Full Log Data</h4>
                    <div id="log-json-viewer"></div>
                </div>
            </div>
        `;

        // Render JSON viewer
        const jsonContainer = drawerBody.querySelector('#log-json-viewer');
        new JsonViewer(jsonContainer, log, {
            collapsed: false,
            maxDepth: 3,
            showToolbar: true,
            fileName: `log-${log.timestamp || 'unknown'}.json`
        });

        // Setup action buttons
        this.setupLogDetailActions(log);
    }

    setupLogDetailActions(log) {
        const drawerBody = this.container.querySelector('#logs-drawer-body');

        // Store log reference for potential future actions
        drawerBody.dataset.logTimestamp = log.timestamp || log.created_at || '';

        // View task button
        const taskBtn = drawerBody.querySelector('.btn-link[data-task]');
        if (taskBtn) {
            taskBtn.addEventListener('click', () => {
                const taskId = taskBtn.getAttribute('data-task');
                window.navigateToView('tasks', { task_id: taskId });
                this.hideLogDetail();
            });
        }
    }

    hideLogDetail() {
        const drawer = this.container.querySelector('#logs-detail-drawer');
        drawer.classList.add('hidden');
    }

    downloadLogs() {
        try {
            // Convert logs to JSON
            const logsJson = JSON.stringify(this.logs, null, 2);
            const blob = new Blob([logsJson], { type: 'application/json' });
            const url = URL.createObjectURL(blob);

            // Create download link
            const a = document.createElement('a');
            a.href = url;
            a.download = `agentos-logs-${new Date().toISOString()}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);

            URL.revokeObjectURL(url);

            showToast('Logs downloaded', 'success', 2000);
        } catch (error) {
            console.error('Failed to download logs:', error);
            showToast('Failed to download logs', 'error');
        }
    }

    renderLogLevel(level) {
        const levelMap = {
            'DEBUG': { label: 'DEBUG', class: 'log-level-debug', icon: '<span class="material-icons md-18">search</span>' },
            'INFO': { label: 'INFO', class: 'log-level-info', icon: '<span class="material-icons md-18">info</span>' },
            'WARNING': { label: 'WARNING', class: 'log-level-warning', icon: '<span class="material-icons md-18">warning</span>' },
            'ERROR': { label: 'ERROR', class: 'log-level-error', icon: '<span class="material-icons md-18">cancel</span>' },
            'CRITICAL': { label: 'CRITICAL', class: 'log-level-critical', icon: '<span class="material-icons md-18">local_fire_department</span>' }
        };

        const config = levelMap[level] || { label: level, class: 'log-level-default', icon: '<span class="material-icons md-18">edit_note</span>' };
        return `<span class="log-level ${config.class}">${config.icon} ${config.label}</span>`;
    }

    formatTimestamp(timestamp) {
        if (!timestamp) return 'N/A';

        try {
            // Task #14: Defensive check for timezone
            if (typeof timestamp === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(timestamp)) {
                const isDev = (typeof process !== 'undefined' && process.env && process.env.NODE_ENV === 'development') ||
                              window.location.hostname === 'localhost' ||
                              window.location.hostname === '127.0.0.1';

                if (isDev) {
                    console.warn(`[LogsView] Received timestamp without timezone: ${timestamp}. Assuming UTC.`);
                }

                timestamp = timestamp + 'Z';
            }

            const date = new Date(timestamp);

            if (isNaN(date.getTime())) {
                console.error(`[LogsView] Invalid timestamp: ${timestamp}`);
                return 'Invalid Date';
            }

            return date.toLocaleString('en-US', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                fractionalSecondDigits: 3,
                hour12: false
            });
        } catch (e) {
            console.error(`[LogsView] Error formatting timestamp: ${timestamp}`, e);
            return 'N/A';
        }
    }

    destroy() {
        this.stopTailing();
        this.container.innerHTML = '';
    }
}

// Export
window.LogsView = LogsView;
