/**
 * CommunicationView - CommunicationOS Control Panel
 *
 * Provides a comprehensive dashboard for monitoring and managing external communications:
 * - Network toggle (OFF / READONLY / ON)
 * - Policy configuration snapshot
 * - Recent audit logs with filtering
 * - Evidence viewer with citations and hashes
 * - Service status monitoring
 */

class CommunicationView {
    constructor(container) {
        this.container = container;
        this.filterBar = null;
        this.dataTable = null;
        this.currentFilters = {};
        this.audits = [];
        this.policy = null;
        this.status = null;
        this.autoRefreshInterval = null;
        this.autoRefreshEnabled = false;

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="communication-view">
                <div class="view-header">
                    <div>
                        <h1>CommunicationOS Control Panel</h1>
                        <p class="text-sm text-gray-600 mt-1">Monitor and manage external communication operations</p>
                    </div>
                    <div class="header-actions">
                        <div class="auto-refresh-toggle">
                            <label class="switch">
                                <input type="checkbox" id="comm-auto-refresh">
                                <span class="slider"></span>
                            </label>
                            <span class="toggle-label">Auto-refresh</span>
                        </div>
                        <button class="btn-refresh" id="comm-refresh-all">
                            <span class="material-icons md-18">refresh</span>
                            Refresh All
                        </button>
                    </div>
                </div>

                <!-- Dashboard Cards -->
                <div class="comm-dashboard">
                    <!-- Network Status Card -->
                    <div class="comm-card" id="network-status-card">
                        <div class="card-header">
                            <h3>Network Status</h3>
                            <span class="material-icons md-18">network_check</span>
                        </div>
                        <div class="card-body">
                            <div class="network-toggle-container">
                                <div class="network-mode">
                                    <span class="mode-label">Current Mode:</span>
                                    <span class="mode-value" id="network-mode-value">Loading...</span>
                                </div>
                                <div class="network-toggle-buttons">
                                    <button class="mode-btn mode-off" data-mode="off">
                                        <span class="material-icons">power_off</span>
                                        OFF
                                    </button>
                                    <button class="mode-btn mode-readonly" data-mode="readonly">
                                        <span class="material-icons">visibility</span>
                                        READONLY
                                    </button>
                                    <button class="mode-btn mode-on" data-mode="on">
                                        <span class="material-icons">power</span>
                                        ON
                                    </button>
                                </div>
                                <p class="mode-description" id="mode-description">
                                    Select a network mode to control external communications
                                </p>
                            </div>
                        </div>
                    </div>

                    <!-- Service Status Card -->
                    <div class="comm-card" id="service-status-card">
                        <div class="card-header">
                            <h3>Service Status</h3>
                            <span class="material-icons md-18">dns</span>
                        </div>
                        <div class="card-body">
                            <div class="status-container" id="service-status-container">
                                <div class="loading-spinner">Loading status...</div>
                            </div>
                        </div>
                    </div>

                    <!-- Policy Snapshot Card -->
                    <div class="comm-card" id="policy-snapshot-card">
                        <div class="card-header">
                            <h3>Policy Configuration</h3>
                            <span class="material-icons md-18">security</span>
                        </div>
                        <div class="card-body">
                            <div class="policy-container" id="policy-container">
                                <div class="loading-spinner">Loading policies...</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Recent Audits Section -->
                <div class="comm-section">
                    <div class="section-header">
                        <h2>Recent Audit Logs</h2>
                        <div class="section-actions">
                            <button class="btn-secondary" id="export-audits">
                                <span class="material-icons md-18">download</span>
                                Export
                            </button>
                        </div>
                    </div>

                    <div id="audits-filter-bar" class="filter-section"></div>

                    <div id="audits-table" class="table-section"></div>
                </div>

                <!-- Evidence Detail Drawer -->
                <div id="evidence-drawer" class="drawer hidden">
                    <div class="drawer-overlay" id="evidence-drawer-overlay"></div>
                    <div class="drawer-content">
                        <div class="drawer-header">
                            <h3>Evidence Details</h3>
                            <button class="btn-close" id="evidence-drawer-close">
                                <span class="material-icons">close</span>
                            </button>
                        </div>
                        <div class="drawer-body" id="evidence-drawer-body">
                            <!-- Evidence details will be rendered here -->
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.setupFilterBar();
        this.setupDataTable();
        this.setupEventListeners();
        this.loadAllData();
    }

    setupFilterBar() {
        const filterContainer = this.container.querySelector('#audits-filter-bar');

        this.filterBar = new FilterBar(filterContainer, {
            filters: [
                {
                    type: 'text',
                    key: 'request_id',
                    label: 'Request ID',
                    placeholder: 'Filter by request ID...'
                },
                {
                    type: 'select',
                    key: 'connector_type',
                    label: 'Connector Type',
                    options: [
                        { value: '', label: 'All Connectors' },
                        { value: 'web_search', label: 'Web Search' },
                        { value: 'web_fetch', label: 'Web Fetch' },
                        { value: 'email_send', label: 'Email Send' },
                    ]
                },
                {
                    type: 'select',
                    key: 'operation',
                    label: 'Operation',
                    options: [
                        { value: '', label: 'All Operations' },
                        { value: 'search', label: 'Search' },
                        { value: 'fetch', label: 'Fetch' },
                        { value: 'send', label: 'Send' },
                    ]
                },
                {
                    type: 'select',
                    key: 'status',
                    label: 'Status',
                    options: [
                        { value: '', label: 'All Statuses' },
                        { value: 'success', label: 'Success' },
                        { value: 'failed', label: 'Failed' },
                        { value: 'denied', label: 'Denied' },
                        { value: 'rate_limited', label: 'Rate Limited' },
                    ]
                },
                {
                    type: 'date',
                    key: 'start_date',
                    label: 'Start Date',
                    placeholder: 'YYYY-MM-DD'
                },
                {
                    type: 'date',
                    key: 'end_date',
                    label: 'End Date',
                    placeholder: 'YYYY-MM-DD'
                }
            ],
            onFilterChange: (filters) => {
                this.currentFilters = filters;
                this.loadAudits();
            }
        });
    }

    setupDataTable() {
        const tableContainer = this.container.querySelector('#audits-table');

        this.dataTable = new DataTable(tableContainer, {
            columns: [
                {
                    key: 'created_at',
                    label: 'Timestamp',
                    width: '180px',
                    render: (value) => new Date(value).toLocaleString()
                },
                {
                    key: 'request_id',
                    label: 'Request ID',
                    width: '150px',
                    render: (value) => `<code class="text-xs">${value.substring(0, 12)}...</code>`
                },
                {
                    key: 'connector_type',
                    label: 'Connector',
                    width: '120px',
                    render: (value) => this.renderConnectorBadge(value)
                },
                {
                    key: 'operation',
                    label: 'Operation',
                    width: '100px',
                    render: (value) => `<span class="operation-badge">${value}</span>`
                },
                {
                    key: 'status',
                    label: 'Status',
                    width: '100px',
                    render: (value) => this.renderStatusBadge(value)
                },
                {
                    key: 'risk_level',
                    label: 'Risk',
                    width: '80px',
                    render: (value) => this.renderRiskBadge(value)
                },
                {
                    key: 'id',
                    label: 'Actions',
                    width: '100px',
                    render: (value, row) => `
                        <button class="btn-icon view-evidence" data-id="${value}" title="View Evidence">
                            <span class="material-icons md-18">visibility</span>
                        </button>
                    `
                }
            ],
            onRowClick: (row) => {
                this.showEvidenceDetail(row.id);
            }
        });
    }

    setupEventListeners() {
        // Refresh button
        this.container.querySelector('#comm-refresh-all').addEventListener('click', () => {
            this.loadAllData();
        });

        // Auto-refresh toggle
        this.container.querySelector('#comm-auto-refresh').addEventListener('change', (e) => {
            this.toggleAutoRefresh(e.target.checked);
        });

        // Export button
        this.container.querySelector('#export-audits').addEventListener('click', () => {
            this.exportAudits();
        });

        // Evidence drawer close
        this.container.querySelector('#evidence-drawer-close').addEventListener('click', () => {
            this.hideEvidenceDrawer();
        });

        this.container.querySelector('#evidence-drawer-overlay').addEventListener('click', () => {
            this.hideEvidenceDrawer();
        });

        // View evidence buttons (delegated event)
        this.container.addEventListener('click', (e) => {
            const viewBtn = e.target.closest('.view-evidence');
            if (viewBtn) {
                const auditId = viewBtn.dataset.id;
                this.showEvidenceDetail(auditId);
            }
        });

        // Network mode buttons
        this.container.querySelectorAll('.mode-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const mode = btn.dataset.mode;
                this.setNetworkMode(mode);
            });
        });
    }

    /**
     * Load current network mode from API and update UI
     */
    async loadNetworkMode() {
        try {
            const response = await fetch('/api/communication/mode');
            const result = await response.json();

            if (result.ok && result.data && result.data.current_state) {
                const currentMode = result.data.current_state.mode;
                this.updateNetworkModeUI(currentMode);
            } else {
                // Set default mode if API returns no data
                this.updateNetworkModeUI('on');
                console.warn('Network mode API returned no data, using default mode');
            }
        } catch (error) {
            console.error('Error loading network mode:', error);
            // Set default mode on error
            this.updateNetworkModeUI('on');
            Toast.warning('Could not load network mode, showing default state');
        }
    }

    /**
     * Update network mode UI elements
     * @param {string} mode - Network mode ('off', 'readonly', or 'on')
     */
    updateNetworkModeUI(mode) {
        // Update button states
        this.container.querySelectorAll('.mode-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        const activeBtn = this.container.querySelector(`[data-mode="${mode}"]`);
        if (activeBtn) {
            activeBtn.classList.add('active');
        }

        // Update mode description
        const descriptions = {
            off: 'All external communications are disabled',
            readonly: 'External data can be fetched but not modified',
            on: 'All external communications are enabled'
        };

        const descriptionEl = this.container.querySelector('#mode-description');
        const modeValueEl = this.container.querySelector('#network-mode-value');

        if (descriptionEl) {
            descriptionEl.textContent = descriptions[mode] || 'Unknown mode';
        }
        if (modeValueEl) {
            modeValueEl.textContent = mode.toUpperCase();
        }
    }

    async loadAllData() {
        await Promise.all([
            this.loadNetworkMode(),
            this.loadStatus(),
            this.loadPolicy(),
            this.loadAudits()
        ]);
    }

    async loadStatus() {
        try {
            const response = await fetch('/api/communication/status');
            const result = await response.json();

            if (result.ok) {
                this.status = result.data;
                this.renderStatus();
            } else {
                Toast.error('Failed to load service status');
            }
        } catch (error) {
            console.error('Error loading status:', error);
            Toast.error('Failed to load service status');
        }
    }

    async loadPolicy() {
        try {
            const response = await fetch('/api/communication/policy');
            const result = await response.json();

            if (result.ok) {
                this.policy = result.data;
                this.renderPolicy();
            } else {
                Toast.error('Failed to load policy configuration');
            }
        } catch (error) {
            console.error('Error loading policy:', error);
            Toast.error('Failed to load policy configuration');
        }
    }

    async loadAudits() {
        try {
            // Build query params from filters
            const params = new URLSearchParams();
            if (this.currentFilters.connector_type) {
                params.append('connector_type', this.currentFilters.connector_type);
            }
            if (this.currentFilters.operation) {
                params.append('operation', this.currentFilters.operation);
            }
            if (this.currentFilters.status) {
                params.append('status', this.currentFilters.status);
            }
            if (this.currentFilters.start_date) {
                params.append('start_date', this.currentFilters.start_date + 'T00:00:00Z');
            }
            if (this.currentFilters.end_date) {
                params.append('end_date', this.currentFilters.end_date + 'T23:59:59Z');
            }
            params.append('limit', '50');

            const response = await fetch(`/api/communication/audits?${params}`);
            const result = await response.json();

            if (result.ok) {
                this.audits = result.data.audits;
                this.dataTable.setData(this.audits);
            } else {
                Toast.error('Failed to load audit logs');
            }
        } catch (error) {
            console.error('Error loading audits:', error);
            Toast.error('Failed to load audit logs');
        }
    }

    renderStatus() {
        const container = this.container.querySelector('#service-status-container');
        if (!this.status) {
            container.innerHTML = '<div class="text-gray-500">No status data available</div>';
            return;
        }

        const { status, connectors, statistics } = this.status;

        let html = `
            <div class="status-overview">
                <div class="status-badge status-${status}">
                    <span class="material-icons md-18">check_circle</span>
                    ${status.toUpperCase()}
                </div>
                <div class="status-timestamp">
                    Last updated: ${new Date(this.status.timestamp).toLocaleString()}
                </div>
            </div>

            <div class="connectors-list">
                <h4>Registered Connectors</h4>
        `;

        for (const [type, info] of Object.entries(connectors)) {
            html += `
                <div class="connector-item">
                    <div class="connector-info">
                        <span class="connector-name">${type}</span>
                        <span class="connector-status ${info.enabled ? 'enabled' : 'disabled'}">
                            ${info.enabled ? 'Enabled' : 'Disabled'}
                        </span>
                    </div>
                    <div class="connector-details">
                        <span>Operations: ${info.operations.join(', ')}</span>
                        <span>Rate Limit: ${info.rate_limit}/min</span>
                    </div>
                </div>
            `;
        }

        html += '</div>';

        if (statistics) {
            html += `
                <div class="statistics-panel">
                    <h4>Statistics</h4>
                    <div class="stat-grid">
                        <div class="stat-item">
                            <span class="stat-label">Total Requests</span>
                            <span class="stat-value">${statistics.total_requests || 0}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Success Rate</span>
                            <span class="stat-value">${(statistics.success_rate || 0).toFixed(1)}%</span>
                        </div>
                    </div>
                </div>
            `;
        }

        container.innerHTML = html;
    }

    renderPolicy() {
        const container = this.container.querySelector('#policy-container');
        if (!this.policy) {
            container.innerHTML = '<div class="text-gray-500">No policy data available</div>';
            return;
        }

        let html = '';

        for (const [type, policy] of Object.entries(this.policy)) {
            const statusClass = policy.enabled ? 'enabled' : 'disabled';
            html += `
                <div class="policy-item">
                    <div class="policy-header">
                        <span class="policy-name">${policy.name}</span>
                        <span class="policy-status ${statusClass}">
                            ${policy.enabled ? 'Enabled' : 'Disabled'}
                        </span>
                    </div>
                    <div class="policy-config">
                        <div class="config-row">
                            <span class="config-label">Rate Limit:</span>
                            <span class="config-value">${policy.rate_limit_per_minute} req/min</span>
                        </div>
                        <div class="config-row">
                            <span class="config-label">Timeout:</span>
                            <span class="config-value">${policy.timeout_seconds}s</span>
                        </div>
                        <div class="config-row">
                            <span class="config-label">Max Response:</span>
                            <span class="config-value">${policy.max_response_size_mb}MB</span>
                        </div>
                        <div class="config-row">
                            <span class="config-label">Sanitization:</span>
                            <span class="config-value">
                                ${policy.sanitize_inputs ? 'Input' : ''}
                                ${policy.sanitize_outputs ? 'Output' : ''}
                            </span>
                        </div>
                        ${policy.blocked_domains.length > 0 ? `
                            <div class="config-row">
                                <span class="config-label">Blocked Domains:</span>
                                <span class="config-value">${policy.blocked_domains.length} domain(s)</span>
                            </div>
                        ` : ''}
                        ${policy.allowed_domains.length > 0 ? `
                            <div class="config-row">
                                <span class="config-label">Allowed Domains:</span>
                                <span class="config-value">${policy.allowed_domains.length} domain(s)</span>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        }

        container.innerHTML = html;
    }

    async showEvidenceDetail(auditId) {
        try {
            const response = await fetch(`/api/communication/audits/${auditId}`);
            const result = await response.json();

            if (result.ok) {
                this.renderEvidenceDetail(result.data);
                this.showEvidenceDrawer();
            } else {
                Toast.error('Failed to load evidence details');
            }
        } catch (error) {
            console.error('Error loading evidence:', error);
            Toast.error('Failed to load evidence details');
        }
    }

    renderEvidenceDetail(evidence) {
        const body = this.container.querySelector('#evidence-drawer-body');

        const html = `
            <div class="evidence-detail">
                <div class="evidence-header">
                    <h4>Request Information</h4>
                    <div class="evidence-meta">
                        <span class="meta-item">
                            <span class="material-icons md-18">fingerprint</span>
                            ID: <code>${evidence.id}</code>
                        </span>
                        <span class="meta-item">
                            <span class="material-icons md-18">schedule</span>
                            ${new Date(evidence.created_at).toLocaleString()}
                        </span>
                    </div>
                </div>

                <div class="evidence-section">
                    <h5>Basic Information</h5>
                    <div class="info-grid">
                        <div class="info-item">
                            <span class="info-label">Request ID:</span>
                            <code>${evidence.request_id}</code>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Connector:</span>
                            ${this.renderConnectorBadge(evidence.connector_type)}
                        </div>
                        <div class="info-item">
                            <span class="info-label">Operation:</span>
                            <span class="operation-badge">${evidence.operation}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Status:</span>
                            ${this.renderStatusBadge(evidence.status)}
                        </div>
                    </div>
                </div>

                <div class="evidence-section">
                    <h5>Request Summary</h5>
                    <div class="json-viewer">
                        <pre>${JSON.stringify(evidence.request_summary, null, 2)}</pre>
                    </div>
                </div>

                ${evidence.response_summary ? `
                    <div class="evidence-section">
                        <h5>Response Summary</h5>
                        <div class="json-viewer">
                            <pre>${JSON.stringify(evidence.response_summary, null, 2)}</pre>
                        </div>
                    </div>
                ` : ''}

                <div class="evidence-section">
                    <h5>Metadata</h5>
                    <div class="json-viewer">
                        <pre>${JSON.stringify(evidence.metadata, null, 2)}</pre>
                    </div>
                </div>

                ${evidence.metadata.hash ? `
                    <div class="evidence-section">
                        <h5>Evidence Hash</h5>
                        <div class="hash-display">
                            <span class="material-icons md-18">verified</span>
                            <code>${evidence.metadata.hash}</code>
                        </div>
                    </div>
                ` : ''}

                ${evidence.metadata.citations ? `
                    <div class="evidence-section">
                        <h5>Citations</h5>
                        <div class="citations-list">
                            ${evidence.metadata.citations.map(c => `
                                <div class="citation-item">
                                    <a href="${c}" target="_blank" rel="noopener noreferrer">
                                        ${c}
                                        <span class="material-icons md-14">open_in_new</span>
                                    </a>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;

        body.innerHTML = html;
    }

    showEvidenceDrawer() {
        const drawer = this.container.querySelector('#evidence-drawer');
        drawer.classList.remove('hidden');
        setTimeout(() => drawer.classList.add('visible'), 10);
    }

    hideEvidenceDrawer() {
        const drawer = this.container.querySelector('#evidence-drawer');
        drawer.classList.remove('visible');
        setTimeout(() => drawer.classList.add('hidden'), 300);
    }

    /**
     * Set network mode via API
     * @param {string} mode - Network mode to set ('off', 'readonly', or 'on')
     */
    async setNetworkMode(mode) {
        // Validate mode
        const validModes = ['off', 'readonly', 'on'];
        if (!validModes.includes(mode)) {
            Toast.error(`Invalid network mode: ${mode}`);
            return;
        }

        // Layer 3: 二次确认对话框
        const modeDescriptions = {
            off: '所有外部通信将被禁用',
            readonly: '外部数据可以获取但不能修改',
            on: '所有外部通信将被启用'
        };

        const confirmed = await Dialog.confirm(
            `您即将切换到 ${mode.toUpperCase()} 模式。${modeDescriptions[mode]}。这会影响系统的外部通信权限。`,
            {
                title: '确认切换通信模式',
                confirmText: '确认切换',
                cancelText: '取消',
                danger: true
            }
        );

        if (!confirmed) {
            console.log('[CommunicationView] User cancelled mode switch confirmation');
            return;
        }

        // Disable all mode buttons during the request
        const modeButtons = this.container.querySelectorAll('.mode-btn');
        modeButtons.forEach(btn => {
            btn.disabled = true;
            btn.style.opacity = '0.6';
        });

        try {
            // CSRF Fix: Use fetchWithCSRF for protected endpoint
            // Layer 3: Add X-Confirm-Intent header for extra protection
            const response = await window.fetchWithCSRF('/api/communication/mode', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Confirm-Intent': 'mode-switch'  // Layer 3: Confirm Intent
                },
                body: JSON.stringify({
                    mode: mode,
                    updated_by: 'webui_user',
                    reason: 'Manual change from WebUI'
                })
            });

            const result = await response.json();

            if (response.ok && result.ok) {
                // Success - update UI
                this.updateNetworkModeUI(mode);
                Toast.success(`Network mode changed to ${mode.toUpperCase()}`);

                // Log the change details
                console.log('Network mode changed:', result.data);
            } else {
                // API returned an error
                const errorMessage = result.error || result.message || 'Failed to change network mode';

                // Handle permission errors
                if (response.status === 403) {
                    Toast.error("You don't have permission to change network mode. Please contact administrator.");
                } else if (response.status === 400) {
                    // Validation error
                    Toast.error(`Invalid request: ${errorMessage}`);
                } else {
                    Toast.error(`Failed to change network mode: ${errorMessage}`);
                }

                console.error('Failed to set network mode:', result);
            }
        } catch (error) {
            // Network or other error
            console.error('Error setting network mode:', error);

            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                Toast.error('Network error: Could not connect to server');
            } else {
                Toast.error('An unexpected error occurred while changing network mode');
            }
        } finally {
            // Re-enable all mode buttons
            modeButtons.forEach(btn => {
                btn.disabled = false;
                btn.style.opacity = '1';
            });
        }
    }

    toggleAutoRefresh(enabled) {
        this.autoRefreshEnabled = enabled;

        if (enabled) {
            this.autoRefreshInterval = setInterval(() => {
                this.loadAllData();
            }, 10000); // Refresh every 10 seconds
            Toast.success('Auto-refresh enabled');
        } else {
            if (this.autoRefreshInterval) {
                clearInterval(this.autoRefreshInterval);
                this.autoRefreshInterval = null;
            }
            Toast.info('Auto-refresh disabled');
        }
    }

    exportAudits() {
        if (this.audits.length === 0) {
            Toast.warning('No audit data to export');
            return;
        }

        const csv = this.convertToCSV(this.audits);
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `communication-audits-${new Date().toISOString()}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        Toast.success('Audit logs exported');
    }

    convertToCSV(data) {
        const headers = ['Timestamp', 'Request ID', 'Connector', 'Operation', 'Status', 'Risk Level'];
        const rows = data.map(item => [
            item.created_at,
            item.request_id,
            item.connector_type,
            item.operation,
            item.status,
            item.risk_level || 'N/A'
        ]);

        return [
            headers.join(','),
            ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
        ].join('\n');
    }

    renderConnectorBadge(type) {
        const badges = {
            web_search: { label: 'Web Search', color: 'blue' },
            web_fetch: { label: 'Web Fetch', color: 'green' },
            email_send: { label: 'Email Send', color: 'purple' },
        };

        const badge = badges[type] || { label: type, color: 'gray' };
        return `<span class="badge badge-${badge.color}">${badge.label}</span>`;
    }

    renderStatusBadge(status) {
        const badges = {
            success: { icon: 'check_circle', color: 'success' },
            failed: { icon: 'error', color: 'error' },
            denied: { icon: 'block', color: 'warning' },
            rate_limited: { icon: 'speed', color: 'warning' },
        };

        const badge = badges[status] || { icon: 'help', color: 'gray' };
        return `
            <span class="status-badge status-${badge.color}">
                <span class="material-icons md-14">${badge.icon}</span>
                ${status}
            </span>
        `;
    }

    renderRiskBadge(level) {
        if (!level) return '<span class="text-gray-400">-</span>';

        const badges = {
            low: 'success',
            medium: 'warning',
            high: 'error',
        };

        const color = badges[level.toLowerCase()] || 'gray';
        return `<span class="badge badge-${color}">${level}</span>`;
    }

    destroy() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
        }
    }
}

// Register view
window.CommunicationView = CommunicationView;
