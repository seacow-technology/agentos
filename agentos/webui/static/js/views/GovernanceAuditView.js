/**
 * GovernanceAuditView - AgentOS v3 Governance Audit Log
 *
 * Task #29: Display governance audit with permission checks and risk scoring
 *
 * Features:
 * - All permission check records
 * - Show agent_id, capability_id, result (allowed/denied), reason
 * - Filter by agent, capability, result
 * - Statistics: success rate, denied count
 * - Risk score history (placeholder for future implementation)
 */

class GovernanceAuditView {
    constructor(container) {
        this.container = container;
        this.invocations = [];
        this.stats = { total: 0, allowed: 0, denied: 0, success_rate: 0 };
        this.pagination = { limit: 100, offset: 0, has_more: false };
        this.filters = { agent_id: null, capability_id: null, allowed: null };

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="governance-audit-view">
                <div class="view-header">
                    <div>
                        <h1>Governance Audit</h1>
                        <p class="text-sm text-gray-600 mt-1">Permission checks, risk scoring, and policy evaluations</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="ga-refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                        <button class="btn-secondary" id="ga-export">
                            <span class="icon"><span class="material-icons md-18">download</span></span> Export
                        </button>
                    </div>
                </div>

                <!-- Stats Cards -->
                <div class="stats-grid" id="ga-stats-grid">
                    <!-- Stats will be rendered here -->
                </div>

                <!-- Filters -->
                <div class="filters-bar">
                    <div class="filter-group">
                        <label>Agent ID:</label>
                        <input type="text" id="ga-filter-agent" class="filter-input" placeholder="agent_id">
                    </div>
                    <div class="filter-group">
                        <label>Capability ID:</label>
                        <input type="text" id="ga-filter-capability" class="filter-input" placeholder="capability_id">
                    </div>
                    <div class="filter-group">
                        <label>Result:</label>
                        <select id="ga-filter-allowed" class="filter-select">
                            <option value="">All</option>
                            <option value="true">Allowed</option>
                            <option value="false">Denied</option>
                        </select>
                    </div>
                    <button class="btn-primary" id="ga-apply-filters">Apply Filters</button>
                    <button class="btn-secondary" id="ga-clear-filters">Clear</button>
                </div>

                <!-- Invocation Table -->
                <div class="table-container">
                    <table class="audit-table" id="ga-table">
                        <thead>
                            <tr>
                                <th>Invocation ID</th>
                                <th>Agent</th>
                                <th>Capability</th>
                                <th>Operation</th>
                                <th>Result</th>
                                <th>Reason</th>
                                <th>Timestamp</th>
                            </tr>
                        </thead>
                        <tbody id="ga-table-body">
                            <!-- Rows will be rendered here -->
                        </tbody>
                    </table>
                </div>

                <!-- Pagination -->
                <div class="pagination-bar" id="ga-pagination">
                    <!-- Pagination controls will be rendered here -->
                </div>
            </div>
        `;

        this.setupEventListeners();
        this.loadAudit();
    }

    setupEventListeners() {
        // Refresh button
        const refreshBtn = this.container.querySelector('#ga-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadAudit());
        }

        // Export button
        const exportBtn = this.container.querySelector('#ga-export');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportAudit());
        }

        // Apply filters button
        const applyBtn = this.container.querySelector('#ga-apply-filters');
        if (applyBtn) {
            applyBtn.addEventListener('click', () => {
                this.applyFilters();
                this.loadAudit();
            });
        }

        // Clear filters button
        const clearBtn = this.container.querySelector('#ga-clear-filters');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                this.clearFilters();
                this.loadAudit();
            });
        }
    }

    applyFilters() {
        const agentInput = this.container.querySelector('#ga-filter-agent');
        const capabilityInput = this.container.querySelector('#ga-filter-capability');
        const allowedSelect = this.container.querySelector('#ga-filter-allowed');

        this.filters.agent_id = agentInput.value.trim() || null;
        this.filters.capability_id = capabilityInput.value.trim() || null;
        this.filters.allowed = allowedSelect.value ? (allowedSelect.value === 'true') : null;
        this.pagination.offset = 0; // Reset to first page
    }

    clearFilters() {
        this.filters = { agent_id: null, capability_id: null, allowed: null };
        this.pagination.offset = 0;

        const agentInput = this.container.querySelector('#ga-filter-agent');
        const capabilityInput = this.container.querySelector('#ga-filter-capability');
        const allowedSelect = this.container.querySelector('#ga-filter-allowed');

        if (agentInput) agentInput.value = '';
        if (capabilityInput) capabilityInput.value = '';
        if (allowedSelect) allowedSelect.value = '';
    }

    async loadAudit() {
        try {
            // Build query params
            const params = new URLSearchParams({
                limit: this.pagination.limit,
                offset: this.pagination.offset
            });

            if (this.filters.agent_id) {
                params.append('agent_id', this.filters.agent_id);
            }

            if (this.filters.capability_id) {
                params.append('capability_id', this.filters.capability_id);
            }

            if (this.filters.allowed !== null) {
                params.append('allowed', this.filters.allowed);
            }

            const response = await fetch(`/api/capability/governance/audit?${params}`);
            const result = await response.json();

            if (result.ok && result.data) {
                this.invocations = result.data.invocations;
                this.stats = result.data.stats;
                this.pagination = result.data.pagination;
                this.renderStats();
                this.renderTable();
                this.renderPagination();
            } else {
                this.renderError(result.error || 'Failed to load audit log');
            }
        } catch (error) {
            console.error('Failed to load audit log:', error);
            this.renderError('Failed to connect to API');
        }
    }

    renderStats() {
        const statsGrid = this.container.querySelector('#ga-stats-grid');
        if (!statsGrid) return;

        statsGrid.innerHTML = `
            <div class="stat-card stat-blue">
                <div class="stat-icon">
                    <span class="material-icons md-36">assessment</span>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${this.formatNumber(this.stats.total)}</div>
                    <div class="stat-label">Total Invocations</div>
                </div>
            </div>
            <div class="stat-card stat-green">
                <div class="stat-icon">
                    <span class="material-icons md-36">check_circle</span>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${this.formatNumber(this.stats.allowed)}</div>
                    <div class="stat-label">Allowed</div>
                </div>
            </div>
            <div class="stat-card stat-red">
                <div class="stat-icon">
                    <span class="material-icons md-36">block</span>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${this.formatNumber(this.stats.denied)}</div>
                    <div class="stat-label">Denied</div>
                </div>
            </div>
            <div class="stat-card stat-purple">
                <div class="stat-icon">
                    <span class="material-icons md-36">trending_up</span>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${this.stats.success_rate}%</div>
                    <div class="stat-label">Success Rate</div>
                </div>
            </div>
        `;
    }

    renderTable() {
        const tbody = this.container.querySelector('#ga-table-body');
        if (!tbody) return;

        if (this.invocations.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="empty-cell">
                        <div class="empty-state">
                            <span class="material-icons md-48">security</span>
                            <p>No audit records found</p>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = this.invocations.map(inv => {
            const resultClass = inv.allowed ? 'result-allowed' : 'result-denied';
            const resultIcon = inv.allowed ? 'check_circle' : 'block';

            return `
                <tr class="audit-row ${resultClass}">
                    <td>
                        <code>${inv.invocation_id}</code>
                    </td>
                    <td>
                        <span class="agent-id">${inv.agent_id}</span>
                    </td>
                    <td>
                        <code class="capability-id">${inv.capability_id}</code>
                    </td>
                    <td>
                        <span class="operation">${inv.operation}</span>
                    </td>
                    <td>
                        <span class="result-badge ${resultClass}">
                            <span class="material-icons md-14">${resultIcon}</span>
                            ${inv.allowed ? 'Allowed' : 'Denied'}
                        </span>
                    </td>
                    <td>
                        <span class="reason ${inv.allowed ? '' : 'text-red-600'}">${inv.reason || 'N/A'}</span>
                    </td>
                    <td>
                        <span class="timestamp">${this.formatTimestamp(inv.timestamp)}</span>
                    </td>
                </tr>
            `;
        }).join('');
    }

    renderPagination() {
        const paginationBar = this.container.querySelector('#ga-pagination');
        if (!paginationBar) return;

        const { limit, offset, has_more } = this.pagination;
        const currentPage = Math.floor(offset / limit) + 1;
        const showing_end = offset + this.invocations.length;

        paginationBar.innerHTML = `
            <div class="pagination-info">
                Showing ${offset + 1} - ${showing_end} ${has_more ? '(more available)' : ''}
            </div>
            <div class="pagination-controls">
                <button class="btn-icon" ${offset === 0 ? 'disabled' : ''} onclick="window.gaPrevPage()">
                    <span class="material-icons md-18">chevron_left</span>
                </button>
                <span class="page-info">Page ${currentPage}</span>
                <button class="btn-icon" ${!has_more ? 'disabled' : ''} onclick="window.gaNextPage()">
                    <span class="material-icons md-18">chevron_right</span>
                </button>
            </div>
        `;
    }

    renderError(message) {
        const tbody = this.container.querySelector('#ga-table-body');
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="empty-cell">
                        <div class="error-state">
                            <span class="material-icons md-48">error_outline</span>
                            <p>${message}</p>
                        </div>
                    </td>
                </tr>
            `;
        }
    }

    formatTimestamp(timestamp) {
        if (!timestamp) return 'N/A';

        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;

        const diffHours = Math.floor(diffMins / 60);
        if (diffHours < 24) return `${diffHours}h ago`;

        return date.toLocaleString();
    }

    formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    }

    exportAudit() {
        // Generate CSV export
        const csv = this.generateCSV();
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `governance_audit_${new Date().toISOString()}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    }

    generateCSV() {
        const headers = ['Invocation ID', 'Agent', 'Capability', 'Operation', 'Result', 'Reason', 'Timestamp'];
        const rows = this.invocations.map(inv => [
            inv.invocation_id,
            inv.agent_id,
            inv.capability_id,
            inv.operation,
            inv.allowed ? 'Allowed' : 'Denied',
            inv.reason || '',
            inv.timestamp
        ]);

        return [headers, ...rows].map(row => row.map(cell => `"${cell}"`).join(',')).join('\n');
    }

    nextPage() {
        if (this.pagination.has_more) {
            this.pagination.offset += this.pagination.limit;
            this.loadAudit();
        }
    }

    prevPage() {
        if (this.pagination.offset > 0) {
            this.pagination.offset = Math.max(0, this.pagination.offset - this.pagination.limit);
            this.loadAudit();
        }
    }

    destroy() {
        // Cleanup
    }
}

// Global functions for pagination
window.gaNextPage = function() {
    if (window.currentGovernanceAuditView) {
        window.currentGovernanceAuditView.nextPage();
    }
};

window.gaPrevPage = function() {
    if (window.currentGovernanceAuditView) {
        window.currentGovernanceAuditView.prevPage();
    }
};

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = GovernanceAuditView;
}
