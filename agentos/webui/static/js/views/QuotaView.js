/**
 * QuotaView - Quota Monitoring
 *
 * Features:
 * - Real-time quota status for all capabilities
 * - Visual progress bars with color-coded status
 * - Last triggered timestamps
 * - Filter by trust tier and status
 * - Read-only interface with admin token reminder
 *
 * PR-2: WebUI Views - Task 2
 */

class QuotaView {
    constructor() {
        this.container = null;
        this.currentFilter = {
            trust_tier: 'all',
            status: 'all'
        };
        this.websocket = null;  // L-21: WebSocket connection
        this.presetManager = new FilterPresetManager();  // L-23: Filter presets
    }

    /**
     * Render the view
     * @param {HTMLElement} container - Container element
     */
    async render(container) {
        this.container = container;

        container.innerHTML = `
            <div class="quota-view">
                <div class="view-header">
                    <div>
                        <h1>Quota Monitoring</h1>
                        <p class="text-sm text-gray-600 mt-1">Real-time capability quota status</p>
                    </div>
                    <div class="header-actions">
                        <button id="btnRefreshQuota" class="btn-secondary">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                    </div>
                </div>

                <div class="filter-section">
                    <div class="alert alert-info">
                        <span class="material-icons md-18">info</span>
                        <span>Quotas can only be modified via CLI with admin token. WebUI is read-only.</span>
                    </div>
                    <div class="filter-bar">
                        <div class="filter-item">
                            <label class="filter-label">Trust Tier</label>
                            <select id="filterTrustTier" class="filter-select">
                                <option value="all">All Tiers</option>
                                <option value="T0">T0 - Local Extension</option>
                                <option value="T1">T1 - Local MCP</option>
                                <option value="T2">T2 - Remote MCP</option>
                                <option value="T3">T3 - Cloud MCP</option>
                            </select>
                        </div>
                        <div class="filter-item">
                            <label class="filter-label">Status</label>
                            <select id="filterStatus" class="filter-select">
                                <option value="all">All Status</option>
                                <option value="ok">OK</option>
                                <option value="warning">Warning</option>
                                <option value="denied">Denied</option>
                            </select>
                        </div>
                        <div class="filter-item">
                            <label class="filter-label">Filter Presets</label>
                            <div style="display: flex; gap: 0.5rem;">
                                <select id="filterPresets" class="filter-select" style="flex: 1;">
                                    <option value="">Select preset...</option>
                                </select>
                                <button id="btnSavePreset" class="btn-secondary" title="Save current filter">
                                    <span class="material-icons md-18">bookmark_add</span>
                                </button>
                                <button id="btnDeletePreset" class="btn-secondary" title="Delete selected preset">
                                    <span class="material-icons md-18">delete</span>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="table-section">
                    <div id="quotaContent">
                        <div class="text-center py-8">
                            <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
                            <p class="mt-4 text-gray-600">Loading quota data...</p>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Attach event listeners
        document.getElementById('btnRefreshQuota')?.addEventListener('click', () => {
            this.loadQuotaData();
        });

        document.getElementById('filterTrustTier')?.addEventListener('change', (e) => {
            this.currentFilter.trust_tier = e.target.value;
            this.loadQuotaData();
        });

        document.getElementById('filterStatus')?.addEventListener('change', (e) => {
            this.currentFilter.status = e.target.value;
            this.loadQuotaData();
        });

        // L-23: Filter preset listeners
        this.loadPresetList();

        document.getElementById('filterPresets')?.addEventListener('change', (e) => {
            const presetName = e.target.value;
            if (presetName) {
                this.loadPreset(presetName);
            }
        });

        document.getElementById('btnSavePreset')?.addEventListener('click', () => {
            this.saveCurrentPreset();
        });

        document.getElementById('btnDeletePreset')?.addEventListener('click', () => {
            this.deleteSelectedPreset();
        });

        // Load data
        await this.loadQuotaData();

        // L-21: Connect to WebSocket for real-time updates
        this.connectWebSocket();
    }

    /**
     * L-21: Connect to governance WebSocket for real-time updates
     */
    connectWebSocket() {
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/governance`;

            this.websocket = new WebSocket(wsUrl);

            this.websocket.onopen = () => {
                console.log('Quota WebSocket connected');
            };

            this.websocket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };

            this.websocket.onerror = (error) => {
                console.error('Quota WebSocket error:', error);
            };

            this.websocket.onclose = () => {
                console.log('Quota WebSocket disconnected');
                // Attempt to reconnect after 5 seconds
                setTimeout(() => {
                    if (this.container) {
                        this.connectWebSocket();
                    }
                }, 5000);
            };

            // Send keepalive ping every 30 seconds
            this.pingInterval = setInterval(() => {
                if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                    this.websocket.send('ping');
                }
            }, 30000);

        } catch (error) {
            console.error('Failed to connect to quota WebSocket:', error);
        }
    }

    /**
     * L-21: Handle WebSocket messages
     * @param {Object} data - WebSocket message data
     */
    handleWebSocketMessage(data) {
        if (data.type === 'governance_snapshot' || data.type === 'quota_update') {
            // Reload quota data to reflect real-time changes
            this.loadQuotaData();
        }
    }

    /**
     * L-23: Load preset list into dropdown
     */
    loadPresetList() {
        const presetSelect = document.getElementById('filterPresets');
        if (!presetSelect) return;

        const presets = this.presetManager.listPresets();

        // Clear existing options (except first)
        while (presetSelect.options.length > 1) {
            presetSelect.remove(1);
        }

        // Add preset options
        presets.forEach(name => {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = name;
            presetSelect.appendChild(option);
        });
    }

    /**
     * L-23: Save current filter as preset
     */
    saveCurrentPreset() {
        const name = prompt('Enter preset name:');
        if (!name || name.trim() === '') return;

        this.presetManager.savePreset(name.trim(), this.currentFilter);
        this.loadPresetList();

        // Show success message
        this.showToast(`Preset "${name}" saved successfully`);
    }

    /**
     * L-23: Load a saved preset
     * @param {string} name - Preset name
     */
    loadPreset(name) {
        const filters = this.presetManager.loadPreset(name);
        if (!filters) return;

        // Apply filters
        this.currentFilter = filters;

        // Update UI
        const trustTierSelect = document.getElementById('filterTrustTier');
        const statusSelect = document.getElementById('filterStatus');

        if (trustTierSelect) trustTierSelect.value = filters.trust_tier;
        if (statusSelect) statusSelect.value = filters.status;

        // Reload data
        this.loadQuotaData();

        this.showToast(`Preset "${name}" loaded`);
    }

    /**
     * L-23: Delete selected preset
     */
    deleteSelectedPreset() {
        const presetSelect = document.getElementById('filterPresets');
        if (!presetSelect) return;

        const name = presetSelect.value;
        if (!name) {
            alert('Please select a preset to delete');
            return;
        }

        if (confirm(`Delete preset "${name}"?`)) {
            this.presetManager.deletePreset(name);
            this.loadPresetList();
            presetSelect.value = '';
            this.showToast(`Preset "${name}" deleted`);
        }
    }

    /**
     * Show toast notification
     * @param {string} message - Message to display
     */
    showToast(message) {
        // Simple toast implementation
        const toast = document.createElement('div');
        toast.className = 'toast-notification';
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            background: #10B981;
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 0.5rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            z-index: 9999;
            animation: slideIn 0.3s ease;
        `;

        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transition = 'opacity 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    /**
     * Load quota data from API
     */
    async loadQuotaData() {
        const contentDiv = document.getElementById('quotaContent');
        if (!contentDiv) return;

        try {
            const params = new URLSearchParams({
                trust_tier: this.currentFilter.trust_tier,
                status: this.currentFilter.status
            });

            const response = await fetch(`/api/governance/quotas?${params}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            this.renderQuotaTable(contentDiv, data.quotas);
        } catch (error) {
            console.error('Failed to load quota data:', error);
            this.renderError(contentDiv, error);
        }
    }

    /**
     * Render quota table
     * @param {HTMLElement} container - Content container
     * @param {Array} quotas - Quota data array
     */
    renderQuotaTable(container, quotas) {
        if (quotas.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">inventory_2</div>
                    <h3>No Quotas Found</h3>
                    <p>No capabilities match the current filters</p>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <div class="data-table-wrapper">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Capability ID</th>
                            <th>Trust Tier</th>
                            <th>Calls/min</th>
                            <th>Usage</th>
                            <th>Status</th>
                            <th>Last Triggered</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${quotas.map(quota => this.renderQuotaRow(quota)).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    /**
     * Render a single quota row
     * @param {Object} quota - Quota data
     * @returns {string} HTML string
     */
    renderQuotaRow(quota) {
        // Get calls per minute quota (primary quota to display)
        const callsQuota = quota.quota.calls_per_minute || {};
        const used = callsQuota.used || 0;
        const limit = callsQuota.limit || 1;
        const percentage = Math.min(callsQuota.usage_percent || 0, 100);

        const statusClass = this.getStatusClass(percentage);
        const statusLabel = this.getStatusLabel(percentage);

        return `
            <tr class="quota-row">
                <td>
                    <button class="btn-link" onclick="window.loadView('capability-detail', '${quota.capability_id}')">
                        ${quota.capability_id}
                    </button>
                </td>
                <td>
                    <span class="trust-tier-badge tier-${quota.trust_tier}">${quota.trust_tier}</span>
                </td>
                <td>
                    <span class="quota-fraction">${used} / ${limit}</span>
                </td>
                <td>
                    <div class="quota-progress-container">
                        <div class="quota-progress-bar">
                            <div class="quota-progress-fill ${statusClass}" style="width: ${percentage}%"></div>
                        </div>
                        <span class="quota-percentage">${percentage.toFixed(1)}%</span>
                    </div>
                </td>
                <td>
                    <span class="status-badge status-${statusClass}">${statusLabel}</span>
                </td>
                <td>
                    ${quota.last_triggered
                        ? `<button class="btn-link" onclick="window.loadView('audit-detail', '${quota.capability_id}')">
                             ${this.formatTimeAgo(quota.last_triggered)}
                           </button>`
                        : '<span class="text-muted">Never</span>'
                    }
                </td>
            </tr>
        `;
    }

    /**
     * Get status class based on percentage
     * @param {number} percentage - Usage percentage
     * @returns {string} CSS class
     */
    getStatusClass(percentage) {
        if (percentage < 80) return 'ok';
        if (percentage < 100) return 'warning';
        return 'denied';
    }

    /**
     * Get status label based on percentage
     * @param {number} percentage - Usage percentage
     * @returns {string} Status label
     */
    getStatusLabel(percentage) {
        if (percentage < 80) return 'OK';
        if (percentage < 100) return 'Warning';
        return 'Denied';
    }

    /**
     * Format timestamp to relative time
     * @param {string} timestamp - ISO timestamp
     * @returns {string} Relative time string
     */
    formatTimeAgo(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins} min ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        return `${diffDays}d ago`;
    }

    /**
     * Render error state
     * @param {HTMLElement} container - Content container
     * @param {Error} error - Error object
     */
    renderError(container, error) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">warning</div>
                <h3>Failed to Load Quota Data</h3>
                <p>${error.message}</p>
                <button class="btn-primary" onclick="window.loadView('governance-quotas')">
                    Retry
                </button>
            </div>
        `;
    }

    /**
     * Destroy the view
     */
    destroy() {
        // L-21: Close WebSocket connection
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }

        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}

/**
 * L-23: Filter Preset Manager
 *
 * Manages saved filter presets using localStorage
 */
class FilterPresetManager {
    constructor() {
        this.prefix = 'quota_filter_preset_';
    }

    /**
     * Save a filter preset
     * @param {string} name - Preset name
     * @param {Object} filters - Filter configuration
     */
    savePreset(name, filters) {
        try {
            const key = this.prefix + name;
            localStorage.setItem(key, JSON.stringify(filters));
        } catch (error) {
            console.error('Failed to save preset:', error);
        }
    }

    /**
     * Load a filter preset
     * @param {string} name - Preset name
     * @returns {Object|null} Filter configuration or null if not found
     */
    loadPreset(name) {
        try {
            const key = this.prefix + name;
            const data = localStorage.getItem(key);
            return data ? JSON.parse(data) : null;
        } catch (error) {
            console.error('Failed to load preset:', error);
            return null;
        }
    }

    /**
     * Delete a filter preset
     * @param {string} name - Preset name
     */
    deletePreset(name) {
        try {
            const key = this.prefix + name;
            localStorage.removeItem(key);
        } catch (error) {
            console.error('Failed to delete preset:', error);
        }
    }

    /**
     * List all saved presets
     * @returns {Array<string>} Array of preset names
     */
    listPresets() {
        try {
            const presets = [];
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (key && key.startsWith(this.prefix)) {
                    presets.push(key.replace(this.prefix, ''));
                }
            }
            return presets.sort();
        } catch (error) {
            console.error('Failed to list presets:', error);
            return [];
        }
    }
}

// Export to window
window.QuotaView = QuotaView;
window.FilterPresetManager = FilterPresetManager;
