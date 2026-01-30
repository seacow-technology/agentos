/**
 * GovernanceFindingsView - Lead Agent Risk Findings Dashboard
 *
 * PR-4: Governance / Findings Aggregation Page
 * Coverage: GET /api/lead/findings, GET /api/lead/stats
 */

class GovernanceFindingsView {
    constructor(container) {
        this.container = container;
        this.filterBar = null;
        this.dataTable = null;
        this.currentFilters = {};
        this.findings = [];
        this.stats = null;

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="governance-findings-view">
                <div class="view-header">
                    <div>
                        <h1>Governance Findings</h1>
                        <p class="text-sm text-gray-600 mt-1">Security and compliance findings</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="findings-refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                        <button class="btn-primary" id="findings-scan">
                            <span class="icon"><span class="material-icons md-18">search</span></span> Run Scan
                        </button>
                    </div>
                </div>

                <!-- Statistics Cards -->
                <div id="findings-stats" class="stats-section">
                    <div class="loading-spinner">Loading statistics...</div>
                </div>

                <!-- Filter Bar -->
                <div id="findings-filter-bar" class="filter-section"></div>

                <!-- Findings Table -->
                <div id="findings-table" class="table-section"></div>
            </div>
        `;

        this.setupEventListeners();
        this.loadStats();
        this.setupFilterBar();
        this.setupDataTable();
        this.loadFindings();
    }

    setupEventListeners() {
        // Refresh button
        this.container.querySelector('#findings-refresh').addEventListener('click', () => {
            this.refreshAll();
        });

        // Scan button
        this.container.querySelector('#findings-scan').addEventListener('click', () => {
            this.runScan();
        });
    }

    setupFilterBar() {
        const filterContainer = this.container.querySelector('#findings-filter-bar');

        this.filterBar = new FilterBar(filterContainer, {
            filters: [
                {
                    type: 'select',
                    key: 'severity',
                    label: 'Severity',
                    options: [
                        { value: '', label: 'All Severities' },
                        { value: 'CRITICAL', label: 'Critical' },
                        { value: 'HIGH', label: 'High' },
                        { value: 'MEDIUM', label: 'Medium' },
                        { value: 'LOW', label: 'Low' }
                    ]
                },
                {
                    type: 'select',
                    key: 'window',
                    label: 'Window',
                    options: [
                        { value: '', label: 'All Windows' },
                        { value: '24h', label: 'Last 24 hours' },
                        { value: '7d', label: 'Last 7 days' },
                        { value: '30d', label: 'Last 30 days' }
                    ]
                },
                {
                    type: 'button',
                    key: 'reset',
                    label: 'Reset',
                    className: 'btn-secondary',
                    onClick: () => this.resetFilters()
                }
            ],
            onChange: (filters) => this.handleFilterChange(filters),
            debounceMs: 300
        });
    }

    setupDataTable() {
        const tableContainer = this.container.querySelector('#findings-table');

        this.dataTable = new DataTable(tableContainer, {
            columns: [
                {
                    key: 'code',
                    label: 'Code',
                    width: '150px',
                    render: (value) => `<code class="code-inline">${value}</code>`
                },
                {
                    key: 'severity',
                    label: 'Severity',
                    width: '120px',
                    render: (value) => this.renderSeverity(value)
                },
                {
                    key: 'window_kind',
                    label: 'Window',
                    width: '100px',
                    render: (value) => value || 'N/A'
                },
                {
                    key: 'count',
                    label: 'Count',
                    width: '80px',
                    align: 'right',
                    render: (value) => value || 1
                },
                {
                    key: 'last_seen_at',
                    label: 'Last Seen',
                    width: '180px',
                    render: (value) => this.formatTimestamp(value)
                },
                {
                    key: 'linked_task_id',
                    label: 'Linked Task',
                    width: '200px',
                    render: (value, row) => this.renderLinkedTask(value, row)
                }
            ],
            data: [],
            emptyText: 'No findings found',
            loadingText: 'Loading findings...',
            onRowClick: (finding) => this.showFindingDetail(finding),
            pagination: true,
            pageSize: 20
        });
    }

    handleFilterChange(filters) {
        this.currentFilters = filters;
        this.loadFindings();
    }

    resetFilters() {
        this.currentFilters = {};
        this.filterBar.reset();
        this.loadFindings();
    }

    async loadStats() {
        const statsContainer = this.container.querySelector('#findings-stats');
        statsContainer.innerHTML = '<div class="loading-spinner">Loading statistics...</div>';

        try {
            const result = await apiClient.get('/api/lead/stats', {
                requestId: `lead-stats-${Date.now()}`
            });

            if (result.ok) {
                this.stats = result.data;
                this.renderStats();
            } else {
                statsContainer.innerHTML = `
                    <div class="error-message">
                        <span class="material-icons md-18">warning</span>
                        Failed to load statistics: ${result.message}
                    </div>
                `;
            }
        } catch (error) {
            console.error('Failed to load stats:', error);
            statsContainer.innerHTML = `
                <div class="error-message">
                    <span class="material-icons md-18">warning</span>
                    Failed to load statistics
                </div>
            `;
        }
    }

    renderStats() {
        const statsContainer = this.container.querySelector('#findings-stats');

        if (!this.stats) {
            statsContainer.innerHTML = '<div class="empty-state">No statistics available</div>';
            return;
        }

        const { total_findings, by_severity, by_window, unlinked_count } = this.stats;

        statsContainer.innerHTML = `
            <div class="stats-grid">
                <!-- Total Findings Card -->
                <div class="stat-card stat-card-primary">
                    <div class="stat-icon">
                        <span class="material-icons md-36">bug_report</span>
                    </div>
                    <div class="stat-content">
                        <div class="stat-label">Total Findings</div>
                        <div class="stat-value">${total_findings}</div>
                    </div>
                </div>

                <!-- Unlinked Count Card -->
                <div class="stat-card stat-card-warning">
                    <div class="stat-icon">
                        <span class="material-icons md-36">link_off</span>
                    </div>
                    <div class="stat-content">
                        <div class="stat-label">Unlinked Findings</div>
                        <div class="stat-value">${unlinked_count}</div>
                        <div class="stat-description">Need follow-up tasks</div>
                    </div>
                </div>

                <!-- Severity Distribution Card -->
                <div class="stat-card stat-card-full">
                    <div class="stat-header">
                        <span class="material-icons md-24">priority_high</span>
                        <h3>By Severity</h3>
                    </div>
                    <div class="severity-chart">
                        ${this.renderSeverityChart(by_severity)}
                    </div>
                </div>

                <!-- Window Distribution Card -->
                <div class="stat-card stat-card-full">
                    <div class="stat-header">
                        <span class="material-icons md-24">schedule</span>
                        <h3>By Time Window</h3>
                    </div>
                    <div class="window-chart">
                        ${this.renderWindowChart(by_window)}
                    </div>
                </div>
            </div>
        `;
    }

    renderSeverityChart(by_severity) {
        const severities = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
        const colors = {
            'CRITICAL': '#dc3545',
            'HIGH': '#fd7e14',
            'MEDIUM': '#ffc107',
            'LOW': '#28a745'
        };

        const total = Object.values(by_severity).reduce((sum, val) => sum + val, 0);

        if (total === 0) {
            return '<div class="chart-empty">No data available</div>';
        }

        let html = '<div class="severity-bars">';

        severities.forEach(severity => {
            const count = by_severity[severity] || 0;
            const percentage = total > 0 ? (count / total * 100).toFixed(1) : 0;
            const color = colors[severity];

            html += `
                <div class="severity-bar-item">
                    <div class="severity-bar-label">
                        <span class="severity-badge-mini" style="background-color: ${color}"></span>
                        <span class="severity-name">${severity}</span>
                        <span class="severity-count">${count}</span>
                    </div>
                    <div class="severity-bar-container">
                        <div class="severity-bar-fill" style="width: ${percentage}%; background-color: ${color}"></div>
                    </div>
                    <div class="severity-bar-percent">${percentage}%</div>
                </div>
            `;
        });

        html += '</div>';
        return html;
    }

    renderWindowChart(by_window) {
        const windows = ['24h', '7d', '30d'];
        const windowLabels = {
            '24h': 'Last 24 hours',
            '7d': 'Last 7 days',
            '30d': 'Last 30 days'
        };

        const total = Object.values(by_window).reduce((sum, val) => sum + val, 0);

        if (total === 0) {
            return '<div class="chart-empty">No data available</div>';
        }

        let html = '<div class="window-bars">';

        windows.forEach(window => {
            const count = by_window[window] || 0;
            const percentage = total > 0 ? (count / total * 100).toFixed(1) : 0;

            html += `
                <div class="window-bar-item">
                    <div class="window-bar-label">
                        <span class="window-name">${windowLabels[window]}</span>
                        <span class="window-count">${count}</span>
                    </div>
                    <div class="window-bar-container">
                        <div class="window-bar-fill" style="width: ${percentage}%"></div>
                    </div>
                    <div class="window-bar-percent">${percentage}%</div>
                </div>
            `;
        });

        html += '</div>';
        return html;
    }

    async loadFindings(forceRefresh = false) {
        this.dataTable.setLoading(true);

        try {
            // Build query parameters
            const params = new URLSearchParams();
            params.append('limit', '100');

            if (this.currentFilters.severity) {
                params.append('severity', this.currentFilters.severity);
            }
            if (this.currentFilters.window) {
                params.append('window', this.currentFilters.window);
            }

            const url = `/api/lead/findings?${params.toString()}`;
            const result = await apiClient.get(url, {
                requestId: `lead-findings-${Date.now()}`
            });

            if (result.ok) {
                this.findings = result.data.findings || [];
                this.dataTable.setData(this.findings);

                if (forceRefresh) {
                    showToast('Findings refreshed', 'success', 2000);
                }
            } else {
                showToast(`Failed to load findings: ${result.message}`, 'error');
                this.dataTable.setData([]);
            }
        } catch (error) {
            console.error('Failed to load findings:', error);
            showToast('Failed to load findings', 'error');
            this.dataTable.setData([]);
        } finally {
            this.dataTable.setLoading(false);
        }
    }

    async refreshAll() {
        await Promise.all([
            this.loadStats(),
            this.loadFindings(true)
        ]);
        showToast('Data refreshed', 'success', 2000);
    }

    async runScan() {
        try {
            // Show confirmation dialog
            const confirmed = await Dialog.confirm(
                'Run a risk scan? This will analyze recent events and create follow-up tasks for new findings.',
                {
                    title: 'Run Risk Scan',
                    confirmText: 'Run Scan',
                    cancelText: 'Cancel'
                }
            );

            if (!confirmed) {
                return;
            }

            showToast('Starting risk scan...', 'info', 2000);

            // Run scan with dry_run=false to create tasks
            const result = await apiClient.post('/api/lead/scan', {
                window: '24h',
                dry_run: false
            }, {
                requestId: `lead-scan-${Date.now()}`
            });

            if (result.ok) {
                const { findings_count, new_findings, tasks_created } = result.data;
                showToast(
                    `Scan complete: ${findings_count} findings, ${new_findings} new, ${tasks_created} tasks created`,
                    'success',
                    5000
                );
                this.refreshAll();
            } else {
                showToast(`Scan failed: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Failed to run scan:', error);
            showToast('Failed to run scan', 'error');
        }
    }

    showFindingDetail(finding) {
        // If there's a linked task, navigate to task detail
        if (finding.linked_task_id) {
            window.navigateToView('tasks', { task_id: finding.linked_task_id });
        } else {
            // Show finding details in a toast (could be enhanced with a modal)
            showToast(
                `Finding: ${finding.code} | Severity: ${finding.severity} | Count: ${finding.count || 1}`,
                'info',
                4000
            );
        }
    }

    renderSeverity(severity) {
        const severityMap = {
            'CRITICAL': { label: 'Critical', class: 'severity-critical', icon: 'error' },
            'HIGH': { label: 'High', class: 'severity-high', icon: 'warning' },
            'MEDIUM': { label: 'Medium', class: 'severity-medium', icon: 'info' },
            'LOW': { label: 'Low', class: 'severity-low', icon: 'check_circle' }
        };

        const config = severityMap[severity] || { label: severity, class: 'severity-unknown', icon: 'help' };
        return `<span class="severity-badge ${config.class}">
            <span class="material-icons md-16">${config.icon}</span> ${config.label}
        </span>`;
    }

    renderLinkedTask(taskId, _finding) {
        if (!taskId) {
            return '<span class="text-muted">No task</span>';
        }

        return `
            <a href="#" class="task-link" data-task-id="${taskId}" onclick="event.stopPropagation(); window.navigateToView('tasks', { task_id: '${taskId}' }); return false;">
                <code>${taskId}</code>
                <span class="material-icons md-16">open_in_new</span>
            </a>
        `;
    }

    formatTimestamp(timestamp) {
        if (!timestamp) return 'N/A';

        try {
            const date = new Date(timestamp);
            const now = new Date();
            const diff = now - date;

            // Less than 1 minute
            if (diff < 60000) {
                return 'Just now';
            }

            // Less than 1 hour
            if (diff < 3600000) {
                const minutes = Math.floor(diff / 60000);
                return `${minutes}m ago`;
            }

            // Less than 24 hours
            if (diff < 86400000) {
                const hours = Math.floor(diff / 3600000);
                return `${hours}h ago`;
            }

            // Less than 7 days
            if (diff < 604800000) {
                const days = Math.floor(diff / 86400000);
                return `${days}d ago`;
            }

            // Format as date
            return date.toLocaleString();
        } catch (e) {
            return timestamp;
        }
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

// Export to global scope (type declared in types/global.d.ts)
window.GovernanceFindingsView = GovernanceFindingsView;
