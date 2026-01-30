/**
 * LeadScanHistoryView - Lead Agent Risk Mining UI
 *
 * PR-4: Lead Agent Risk Mining and Follow-up Task Creation
 * Coverage: POST /api/lead/scan, GET /api/lead/findings, GET /api/lead/stats
 *
 * This view provides manual trigger for Lead Agent scans and displays findings.
 * Lead Agent normally runs automatically via Cron (24h/7d/30d windows).
 */

class LeadScanHistoryView {
    constructor(container) {
        this.container = container;
        this.scanResult = null;
        this.findings = [];
        this.stats = null;
        this.dataTable = null;
        this.isScanning = false;

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="lead-scan-history-view">
                <div class="view-header">
                    <div>
                        <h1>Lead Agent - Risk Mining</h1>
                        <p class="text-sm text-gray-600 mt-1">Risk mining scan history and results</p>
                    </div>
                    <div class="header-actions">
                        <button id="lead-run-dry" class="btn-secondary" ${this.isScanning ? 'disabled' : ''}>
                            <span class="icon"><span class="material-icons md-18">search</span></span> Dry Run (Preview)
                        </button>
                        <button id="lead-run-real" class="btn-danger" ${this.isScanning ? 'disabled' : ''}>
                            <span class="icon"><span class="material-icons md-18">warning</span></span> Real Run (Create Tasks)
                        </button>
                        <button id="lead-refresh" class="btn-refresh" ${this.isScanning ? 'disabled' : ''}>
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                    </div>
                </div>

                <div class="info-banner">
                    <span class="material-icons md-18">info</span>
                    <span>Lead Agent runs automatically via Cron (every 24h/7d/30d). This page allows manual scanning and viewing results.</span>
                </div>

                <!-- Configuration Info Section -->
                <div id="lead-config-info" class="config-info-section hidden">
                    <!-- Config info will be rendered here -->
                </div>

                <div class="scan-config-section">
                    <div class="config-card">
                        <label class="config-label">Scan Window:</label>
                        <select id="lead-scan-window" class="select-field">
                            <option value="24h" selected>24h (Last 24 hours)</option>
                            <option value="7d">7d (Last 7 days)</option>
                            <option value="30d">30d (Last 30 days)</option>
                        </select>
                        <p class="config-help">Select the time window for risk mining. Longer windows may find more patterns but take longer to process.</p>
                    </div>
                </div>

                <!-- Stats Section -->
                <div id="lead-stats-section" class="stats-section hidden">
                    <h3>Lead Agent Statistics</h3>
                    <div class="stats-grid" id="lead-stats-grid">
                        <!-- Stats will be rendered here -->
                    </div>
                </div>

                <!-- Scan Result Section -->
                <div id="lead-scan-result" class="scan-result-section hidden">
                    <!-- Scan results will be rendered here -->
                </div>

                <!-- Findings Section -->
                <div class="findings-section">
                    <h3>Recent Findings</h3>
                    <div id="lead-findings-table" class="table-section">
                        <!-- Findings table will be rendered here -->
                    </div>
                </div>
            </div>
        `;

        this.setupEventListeners();
        this.setupDataTable();
        this.loadStats();
        this.loadFindings();
    }

    setupEventListeners() {
        // Dry Run button
        const dryRunBtn = this.container.querySelector('#lead-run-dry');
        if (dryRunBtn) {
            dryRunBtn.addEventListener('click', () => this.runScan(true));
        }

        // Real Run button
        const realRunBtn = this.container.querySelector('#lead-run-real');
        if (realRunBtn) {
            realRunBtn.addEventListener('click', () => this.confirmRealRun());
        }

        // Refresh button
        const refreshBtn = this.container.querySelector('#lead-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refresh());
        }
    }

    setupDataTable() {
        const tableContainer = this.container.querySelector('#lead-findings-table');

        this.dataTable = new DataTable(tableContainer, {
            columns: [
                {
                    key: 'code',
                    label: 'Finding Code',
                    width: '250px',
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
                    render: (value) => `<span class="badge badge-secondary">${value}</span>`
                },
                {
                    key: 'count',
                    label: 'Count',
                    width: '80px',
                    render: (value) => `<span class="count-badge">${value}</span>`
                },
                {
                    key: 'last_seen_at',
                    label: 'Last Seen',
                    width: '180px',
                    render: (value) => this.formatTimestamp(value)
                },
                {
                    key: 'linked_task_id',
                    label: 'Follow-up Task',
                    width: '200px',
                    render: (value) => value
                        ? `<button class="btn-link task-link" data-task-id="${value}">${value}</button>`
                        : '<span class="text-muted">None</span>'
                }
            ],
            data: [],
            emptyText: 'No findings yet. Run a scan to discover risks.',
            loadingText: 'Loading findings...',
            onRowClick: null, // Will handle task links separately
            pagination: true,
            pageSize: 20
        });
    }

    async confirmRealRun() {
        const confirmed = await Dialog.confirm(
            'This will create follow-up tasks for new findings. Continue?',
            {
                title: 'Confirm Real Run',
                confirmText: 'Run Scan',
                danger: true
            }
        );

        if (confirmed) {
            this.runScan(false);
        }
    }

    async runScan(dryRun = true) {
        if (this.isScanning) {
            showToast('Scan already in progress', 'warning');
            return;
        }

        this.isScanning = true;
        this.setButtonsDisabled(true);

        const window = this.container.querySelector('#lead-scan-window').value;
        const scanType = dryRun ? 'Dry Run' : 'Real Run';

        try {
            showToast(`Starting ${scanType} (${window})...`, 'info', 2000);

            // Build query parameters
            const params = new URLSearchParams();
            params.append('window', window);
            params.append('dry_run', dryRun);

            const result = await apiClient.post(`/api/lead/scan?${params.toString()}`, {}, {
                requestId: `lead-scan-${Date.now()}`,
                timeout: 120000 // 2 minutes timeout for scanning
            });

            if (result.ok) {
                this.scanResult = result.data;
                this.renderScanResult(result.data);

                // Render config info if available
                if (result.data.config_info) {
                    this.renderConfigInfo(result.data.config_info);
                }

                showToast(
                    `Scan completed: ${result.data.findings_count} findings (${result.data.new_findings} new)`,
                    'success',
                    3000
                );

                // Refresh findings and stats
                await this.loadFindings();
                await this.loadStats();
            } else {
                showToast(`Scan failed: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Failed to run scan:', error);
            showToast('Failed to run scan', 'error');
        } finally {
            this.isScanning = false;
            this.setButtonsDisabled(false);
        }
    }

    renderConfigInfo(configInfo) {
        const configSection = this.container.querySelector('#lead-config-info');

        if (!configInfo) {
            configSection.classList.add('hidden');
            return;
        }

        configSection.classList.remove('hidden');

        // Config source mapping
        const sourceConfig = {
            'file': { icon: 'description', color: 'info', text: 'Config File', desc: 'Loaded from YAML configuration file' },
            'env': { icon: 'code', color: 'success', text: 'Environment Variable', desc: 'Loaded from LEAD_CONFIG env var' },
            'cli': { icon: 'terminal', color: 'warning', text: 'CLI Override', desc: 'Loaded from command line parameter' },
            'default': { icon: 'settings', color: 'secondary', text: 'Default Config', desc: 'Using hardcoded default values' }
        };

        const source = sourceConfig[configInfo.source] || sourceConfig.default;
        const thresholds = configInfo.thresholds_summary || {};

        configSection.innerHTML = `
            <div class="config-info-card">
                <div class="config-header">
                    <div class="config-header-left">
                        <span class="material-icons md-18">settings</span>
                        <h4>Configuration Information</h4>
                    </div>
                    <div class="config-source-badge badge-${source.color}">
                        <span class="material-icons md-18">${source.icon}</span>
                        ${source.text}
                    </div>
                </div>

                <div class="config-body">
                    <div class="config-meta">
                        <div class="config-meta-item">
                            <span class="config-meta-label">Source:</span>
                            <span class="config-meta-value">${source.desc}</span>
                        </div>
                        ${configInfo.config_path ? `
                            <div class="config-meta-item">
                                <span class="config-meta-label">Path:</span>
                                <code class="config-meta-value code-inline">${configInfo.config_path}</code>
                            </div>
                        ` : ''}
                        <div class="config-meta-item">
                            <span class="config-meta-label">Version:</span>
                            <span class="config-meta-value">${configInfo.config_version || 'N/A'}</span>
                        </div>
                        ${configInfo.config_hash ? `
                            <div class="config-meta-item">
                                <span class="config-meta-label">Hash:</span>
                                <code class="config-meta-value code-inline">${configInfo.config_hash}</code>
                                <span class="config-meta-hint">(for change tracking)</span>
                            </div>
                        ` : ''}
                    </div>

                    <div class="config-thresholds">
                        <h5><span class="material-icons md-18">tune</span> Rule Thresholds</h5>
                        <div class="thresholds-grid">
                            <div class="threshold-item">
                                <span class="threshold-label">Spike Threshold</span>
                                <span class="threshold-value">${thresholds.spike_threshold || 'N/A'}</span>
                            </div>
                            <div class="threshold-item">
                                <span class="threshold-label">Pause Count</span>
                                <span class="threshold-value">${thresholds.pause_count_threshold || 'N/A'}</span>
                            </div>
                            <div class="threshold-item">
                                <span class="threshold-label">Retry Threshold</span>
                                <span class="threshold-value">${thresholds.retry_threshold || 'N/A'}</span>
                            </div>
                            <div class="threshold-item">
                                <span class="threshold-label">Decision Lag</span>
                                <span class="threshold-value">${thresholds.decision_lag_threshold_ms || 'N/A'}ms</span>
                            </div>
                            <div class="threshold-item">
                                <span class="threshold-label">Redline Ratio</span>
                                <span class="threshold-value">${thresholds.redline_ratio_increase_threshold ? (thresholds.redline_ratio_increase_threshold * 100).toFixed(0) + '%' : 'N/A'}</span>
                            </div>
                            <div class="threshold-item">
                                <span class="threshold-label">High Risk Allow</span>
                                <span class="threshold-value">${thresholds.high_risk_allow_threshold || 'N/A'}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    renderScanResult(scanData) {
        const resultSection = this.container.querySelector('#lead-scan-result');

        resultSection.classList.remove('hidden');
        resultSection.innerHTML = `
            <div class="scan-result-card">
                <div class="scan-header">
                    <div class="scan-header-left">
                        <span class="scan-id">Scan ID: ${scanData.scan_id}</span>
                        ${scanData.dry_run
                            ? '<span class="scan-mode dry-run"><span class="material-icons md-18">preview</span> DRY RUN</span>'
                            : '<span class="scan-mode real-run"><span class="material-icons md-18">play_arrow</span> REAL RUN</span>'
                        }
                    </div>
                    <div class="scan-timestamp">${this.formatTimestamp(new Date().toISOString())}</div>
                </div>

                <div class="scan-stats">
                    <div class="stat-item">
                        <div class="stat-icon"><span class="material-icons md-18">schedule</span></div>
                        <div class="stat-content">
                            <span class="stat-label">Window</span>
                            <span class="stat-value">${scanData.window.kind || 'N/A'}</span>
                        </div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-icon"><span class="material-icons md-18">search</span></div>
                        <div class="stat-content">
                            <span class="stat-label">Findings</span>
                            <span class="stat-value">${scanData.findings_count}</span>
                        </div>
                    </div>
                    <div class="stat-item highlight">
                        <div class="stat-icon"><span class="material-icons md-18">new_releases</span></div>
                        <div class="stat-content">
                            <span class="stat-label">New Findings</span>
                            <span class="stat-value">${scanData.new_findings}</span>
                        </div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-icon"><span class="material-icons md-18">task</span></div>
                        <div class="stat-content">
                            <span class="stat-label">Tasks Created</span>
                            <span class="stat-value">${scanData.tasks_created}</span>
                        </div>
                    </div>
                </div>

                ${scanData.top_findings && scanData.top_findings.length > 0 ? `
                    <div class="top-findings">
                        <h4><span class="material-icons md-18">priority_high</span> Top Findings</h4>
                        <ul class="findings-list">
                            ${scanData.top_findings.slice(0, 10).map(finding => `
                                <li class="finding-item">
                                    ${this.renderSeverity(finding.severity)}
                                    <code class="finding-code">${finding.code}</code>
                                    <span class="finding-count">count: ${finding.count}</span>
                                    ${finding.linked_task_id
                                        ? `<button class="btn-link task-link" data-task-id="${finding.linked_task_id}">Task: ${finding.linked_task_id}</button>`
                                        : ''
                                    }
                                </li>
                            `).join('')}
                        </ul>
                    </div>
                ` : ''}
            </div>
        `;

        // Setup task link handlers
        this.setupTaskLinks(resultSection);

        // Scroll to result
        resultSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    async loadStats() {
        try {
            const result = await apiClient.get('/api/lead/stats', {
                requestId: `lead-stats-${Date.now()}`
            });

            if (result.ok) {
                this.stats = result.data;
                this.renderStats(result.data);
            } else {
                console.error('Failed to load stats:', result.message);
            }
        } catch (error) {
            console.error('Failed to load stats:', error);
        }
    }

    renderStats(stats) {
        const statsSection = this.container.querySelector('#lead-stats-section');
        const statsGrid = this.container.querySelector('#lead-stats-grid');

        if (!stats || stats.total_findings === 0) {
            statsSection.classList.add('hidden');
            return;
        }

        statsSection.classList.remove('hidden');

        const bySeverity = stats.by_severity || {};
        // byWindow stats available but not currently displayed in UI
        // const byWindow = stats.by_window || {};

        statsGrid.innerHTML = `
            <div class="stat-card">
                <div class="stat-card-icon"><span class="material-icons md-24">analytics</span></div>
                <div class="stat-card-content">
                    <div class="stat-card-label">Total Findings</div>
                    <div class="stat-card-value">${stats.total_findings}</div>
                </div>
            </div>

            <div class="stat-card">
                <div class="stat-card-icon critical"><span class="material-icons md-24">error</span></div>
                <div class="stat-card-content">
                    <div class="stat-card-label">Critical</div>
                    <div class="stat-card-value">${bySeverity.CRITICAL || 0}</div>
                </div>
            </div>

            <div class="stat-card">
                <div class="stat-card-icon high"><span class="material-icons md-24">warning</span></div>
                <div class="stat-card-content">
                    <div class="stat-card-label">High</div>
                    <div class="stat-card-value">${bySeverity.HIGH || 0}</div>
                </div>
            </div>

            <div class="stat-card">
                <div class="stat-card-icon medium"><span class="material-icons md-24">info</span></div>
                <div class="stat-card-content">
                    <div class="stat-card-label">Medium</div>
                    <div class="stat-card-value">${bySeverity.MEDIUM || 0}</div>
                </div>
            </div>

            <div class="stat-card">
                <div class="stat-card-icon low"><span class="material-icons md-24">check_circle</span></div>
                <div class="stat-card-content">
                    <div class="stat-card-label">Low</div>
                    <div class="stat-card-value">${bySeverity.LOW || 0}</div>
                </div>
            </div>

            <div class="stat-card">
                <div class="stat-card-icon"><span class="material-icons md-24">link_off</span></div>
                <div class="stat-card-content">
                    <div class="stat-card-label">Unlinked (Need Tasks)</div>
                    <div class="stat-card-value">${stats.unlinked_count}</div>
                </div>
            </div>
        `;
    }

    async loadFindings(forceRefresh = false) {
        this.dataTable.setLoading(true);

        try {
            const params = new URLSearchParams();
            params.append('limit', '200'); // Load more findings for comprehensive view

            const result = await apiClient.get(`/api/lead/findings?${params.toString()}`, {
                requestId: `lead-findings-${Date.now()}`
            });

            if (result.ok) {
                this.findings = result.data.findings || [];
                this.dataTable.setData(this.findings);

                // Setup task link handlers after table renders
                this.setupTaskLinks(this.container.querySelector('#lead-findings-table'));

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

    setupTaskLinks(parentElement) {
        const taskLinks = parentElement.querySelectorAll('.task-link');
        taskLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.stopPropagation();
                const taskId = link.getAttribute('data-task-id');
                if (taskId && window.navigateToView) {
                    window.navigateToView('tasks', { task_id: taskId });
                }
            });
        });
    }

    async refresh() {
        showToast('Refreshing...', 'info', 1000);
        await Promise.all([
            this.loadStats(),
            this.loadFindings(true)
        ]);
    }

    setButtonsDisabled(disabled) {
        const buttons = [
            this.container.querySelector('#lead-run-dry'),
            this.container.querySelector('#lead-run-real'),
            this.container.querySelector('#lead-refresh')
        ];

        buttons.forEach(btn => {
            if (btn) {
                btn.disabled = disabled;
                if (disabled) {
                    btn.classList.add('disabled');
                } else {
                    btn.classList.remove('disabled');
                }
            }
        });

        // Show scanning indicator
        if (disabled) {
            const select = this.container.querySelector('#lead-scan-window');
            if (select) {
                select.disabled = true;
            }
        } else {
            const select = this.container.querySelector('#lead-scan-window');
            if (select) {
                select.disabled = false;
            }
        }
    }

    renderSeverity(severity) {
        const severityMap = {
            'CRITICAL': { label: 'Critical', class: 'severity-critical', icon: 'error' },
            'HIGH': { label: 'High', class: 'severity-high', icon: 'warning' },
            'MEDIUM': { label: 'Medium', class: 'severity-medium', icon: 'info' },
            'LOW': { label: 'Low', class: 'severity-low', icon: 'check_circle' }
        };

        const severityUpper = severity ? severity.toUpperCase() : 'LOW';
        const config = severityMap[severityUpper] || severityMap.LOW;

        return `<span class="severity-badge ${config.class}">
            <span class="material-icons md-18">${config.icon}</span> ${config.label}
        </span>`;
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

            // Format as date
            return date.toLocaleString();
        } catch (e) {
            return timestamp;
        }
    }

    destroy() {
        // Cleanup
        if (this.dataTable) {
            this.dataTable = null;
        }
        this.container.innerHTML = '';
    }
}

// Export to global scope (type declared in types/global.d.ts)
window.LeadScanHistoryView = LeadScanHistoryView;
