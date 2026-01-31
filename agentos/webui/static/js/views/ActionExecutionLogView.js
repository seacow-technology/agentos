/**
 * ActionExecutionLogView - AgentOS v3 Action Execution Log
 *
 * Task #29: Display action execution log with side effects and rollbacks
 *
 * Features:
 * - All action execution records
 * - Show decision_id relationship, side effects, execution results
 * - Color coding: success (green), failure (red), rolled_back (yellow)
 * - Filter by status, agent_id, decision_id
 * - Pagination support
 */

class ActionExecutionLogView {
    constructor(container) {
        this.container = container;
        this.actions = [];
        this.pagination = { total: 0, limit: 50, offset: 0 };
        this.stats = { total: 0, allowed: 0, denied: 0 };
        this.filters = { status: null, agent_id: null, decision_id: null };

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="action-log-view">
                <div class="view-header">
                    <div>
                        <h1>Action Execution Log</h1>
                        <p class="text-sm text-gray-600 mt-1">All action executions with side effects and rollback history</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="al-refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                    </div>
                </div>

                <!-- Filters -->
                <div class="filters-bar">
                    <div class="filter-group">
                        <label>Status:</label>
                        <select id="al-filter-status" class="filter-select">
                            <option value="">All</option>
                            <option value="success">Success</option>
                            <option value="failure">Failure</option>
                            <option value="rolled_back">Rolled Back</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label>Agent ID:</label>
                        <input type="text" id="al-filter-agent" class="filter-input" placeholder="agent_id">
                    </div>
                    <div class="filter-group">
                        <label>Decision ID:</label>
                        <input type="text" id="al-filter-decision" class="filter-input" placeholder="decision_id">
                    </div>
                    <button class="btn-primary" id="al-apply-filters">Apply Filters</button>
                    <button class="btn-secondary" id="al-clear-filters">Clear</button>
                </div>

                <!-- Action Table -->
                <div class="table-container">
                    <table class="action-log-table" id="al-table">
                        <thead>
                            <tr>
                                <th>Execution ID</th>
                                <th>Action Type</th>
                                <th>Agent</th>
                                <th>Decision</th>
                                <th>Status</th>
                                <th>Execution Time</th>
                                <th>Side Effects</th>
                                <th>Executed At</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="al-table-body">
                            <!-- Rows will be rendered here -->
                        </tbody>
                    </table>
                </div>

                <!-- Pagination -->
                <div class="pagination-bar" id="al-pagination">
                    <!-- Pagination controls will be rendered here -->
                </div>
            </div>
        `;

        this.setupEventListeners();
        this.loadActions();
    }

    setupEventListeners() {
        // Refresh button
        const refreshBtn = this.container.querySelector('#al-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadActions());
        }

        // Apply filters button
        const applyBtn = this.container.querySelector('#al-apply-filters');
        if (applyBtn) {
            applyBtn.addEventListener('click', () => {
                this.applyFilters();
                this.loadActions();
            });
        }

        // Clear filters button
        const clearBtn = this.container.querySelector('#al-clear-filters');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                this.clearFilters();
                this.loadActions();
            });
        }
    }

    applyFilters() {
        const statusSelect = this.container.querySelector('#al-filter-status');
        const agentInput = this.container.querySelector('#al-filter-agent');
        const decisionInput = this.container.querySelector('#al-filter-decision');

        this.filters.status = statusSelect.value || null;
        this.filters.agent_id = agentInput.value.trim() || null;
        this.filters.decision_id = decisionInput.value.trim() || null;
        this.pagination.offset = 0; // Reset to first page
    }

    clearFilters() {
        this.filters = { status: null, agent_id: null, decision_id: null };
        this.pagination.offset = 0;

        const statusSelect = this.container.querySelector('#al-filter-status');
        const agentInput = this.container.querySelector('#al-filter-agent');
        const decisionInput = this.container.querySelector('#al-filter-decision');

        if (statusSelect) statusSelect.value = '';
        if (agentInput) agentInput.value = '';
        if (decisionInput) decisionInput.value = '';
    }

    async loadActions() {
        try {
            // Build query params
            const params = new URLSearchParams({
                limit: this.pagination.limit,
                offset: this.pagination.offset
            });

            if (this.filters.status) {
                params.append('status', this.filters.status);
            }

            if (this.filters.agent_id) {
                params.append('agent_id', this.filters.agent_id);
            }

            if (this.filters.decision_id) {
                params.append('decision_id', this.filters.decision_id);
            }

            const response = await fetch(`/api/capability/actions/log?${params}`);
            const result = await response.json();

            if (result.ok && result.data) {
                this.actions = result.data.actions;
                this.pagination = result.data.pagination;
                this.renderTable();
                this.renderPagination();
            } else {
                this.renderError(result.error || 'Failed to load actions');
            }
        } catch (error) {
            console.error('Failed to load actions:', error);
            this.renderError('Failed to connect to API');
        }
    }

    renderTable() {
        const tbody = this.container.querySelector('#al-table-body');
        if (!tbody) return;

        if (this.actions.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9" class="empty-cell">
                        <div class="empty-state">
                            <span class="material-icons md-48">play_circle_outline</span>
                            <p>No actions found</p>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = this.actions.map(action => {
            const statusClass = this.getStatusClass(action.status);
            const statusIcon = this.getStatusIcon(action.status);

            return `
                <tr class="action-row ${statusClass}">
                    <td>
                        <code class="execution-id">${action.execution_id.substring(0, 12)}...</code>
                    </td>
                    <td>
                        <span class="action-type">${action.action_type}</span>
                    </td>
                    <td>
                        <span class="agent-id">${action.agent_id}</span>
                    </td>
                    <td>
                        ${action.decision_id ? `<code>${action.decision_id.substring(0, 12)}...</code>` : '<span class="text-gray-400">N/A</span>'}
                    </td>
                    <td>
                        <span class="status-badge ${statusClass}">
                            <span class="material-icons md-14">${statusIcon}</span>
                            ${action.status}
                        </span>
                    </td>
                    <td>
                        <span class="execution-time">${action.execution_time_ms}ms</span>
                    </td>
                    <td>
                        ${this.renderSideEffects(action.side_effects)}
                    </td>
                    <td>
                        <span class="timestamp">${this.formatTimestamp(action.executed_at)}</span>
                    </td>
                    <td>
                        <button class="btn-icon" onclick="window.viewActionDetails('${action.execution_id}')" title="View Details">
                            <span class="material-icons md-18">visibility</span>
                        </button>
                        ${action.rollback_info ? `
                            <button class="btn-icon text-yellow-600" onclick="window.viewRollbackDetails('${action.execution_id}')" title="View Rollback">
                                <span class="material-icons md-18">undo</span>
                            </button>
                        ` : ''}
                    </td>
                </tr>
                ${action.error_message ? `
                    <tr class="error-row">
                        <td colspan="9">
                            <div class="error-message">
                                <span class="material-icons md-18">error</span>
                                <strong>Error:</strong> ${this.escapeHtml(action.error_message)}
                            </div>
                        </td>
                    </tr>
                ` : ''}
                ${action.rollback_info ? `
                    <tr class="rollback-row">
                        <td colspan="9">
                            <div class="rollback-info">
                                <span class="material-icons md-18">undo</span>
                                <strong>Rollback:</strong>
                                Rolled back by ${action.rollback_info.rolled_back_by} at ${this.formatTimestamp(action.rollback_info.rolled_back_at)}
                                (Status: ${action.rollback_info.status})
                            </div>
                        </td>
                    </tr>
                ` : ''}
            `;
        }).join('');
    }

    renderSideEffects(sideEffects) {
        if (!sideEffects || sideEffects.length === 0) {
            return '<span class="text-gray-400">None</span>';
        }

        return `
            <div class="side-effects-list">
                ${sideEffects.map(se => {
                    const severityClass = this.getSeverityClass(se.severity);
                    return `
                        <span class="side-effect-badge ${severityClass}" title="${this.escapeHtml(se.description)}">
                            ${se.type} (${se.severity})
                        </span>
                    `;
                }).join('')}
            </div>
        `;
    }

    renderPagination() {
        const paginationBar = this.container.querySelector('#al-pagination');
        if (!paginationBar) return;

        const { total, limit, offset, has_more } = this.pagination;
        const currentPage = Math.floor(offset / limit) + 1;
        const totalPages = Math.ceil(total / limit);

        paginationBar.innerHTML = `
            <div class="pagination-info">
                Showing ${offset + 1} - ${Math.min(offset + limit, total)} of ${total} actions
            </div>
            <div class="pagination-controls">
                <button class="btn-icon" ${offset === 0 ? 'disabled' : ''} onclick="window.alPrevPage()">
                    <span class="material-icons md-18">chevron_left</span>
                </button>
                <span class="page-info">Page ${currentPage} of ${totalPages}</span>
                <button class="btn-icon" ${!has_more ? 'disabled' : ''} onclick="window.alNextPage()">
                    <span class="material-icons md-18">chevron_right</span>
                </button>
            </div>
        `;
    }

    renderError(message) {
        const tbody = this.container.querySelector('#al-table-body');
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9" class="empty-cell">
                        <div class="error-state">
                            <span class="material-icons md-48">error_outline</span>
                            <p>${message}</p>
                        </div>
                    </td>
                </tr>
            `;
        }
    }

    getStatusClass(status) {
        const classes = {
            success: 'status-success',
            failure: 'status-failure',
            rolled_back: 'status-rolled-back'
        };
        return classes[status] || 'status-default';
    }

    getStatusIcon(status) {
        const icons = {
            success: 'check_circle',
            failure: 'error',
            rolled_back: 'undo'
        };
        return icons[status] || 'radio_button_unchecked';
    }

    getSeverityClass(severity) {
        const classes = {
            low: 'severity-low',
            medium: 'severity-medium',
            high: 'severity-high',
            critical: 'severity-critical'
        };
        return classes[severity?.toLowerCase()] || 'severity-default';
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

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    nextPage() {
        if (this.pagination.has_more) {
            this.pagination.offset += this.pagination.limit;
            this.loadActions();
        }
    }

    prevPage() {
        if (this.pagination.offset > 0) {
            this.pagination.offset = Math.max(0, this.pagination.offset - this.pagination.limit);
            this.loadActions();
        }
    }

    destroy() {
        // Cleanup
    }
}

// Global functions for pagination and actions
window.alNextPage = function() {
    if (window.currentActionLogView) {
        window.currentActionLogView.nextPage();
    }
};

window.alPrevPage = function() {
    if (window.currentActionLogView) {
        window.currentActionLogView.prevPage();
    }
};

window.viewActionDetails = function(executionId) {
    alert(`View details for action: ${executionId}\n\n(Details modal to be implemented)`);
};

window.viewRollbackDetails = function(executionId) {
    alert(`View rollback details for action: ${executionId}\n\n(Rollback modal to be implemented)`);
};

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ActionExecutionLogView;
}
