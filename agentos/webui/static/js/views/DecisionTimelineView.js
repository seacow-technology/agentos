/**
 * DecisionTimelineView - AgentOS v3 Decision Plans Timeline
 *
 * Task #29: Display decision plans with freeze status and related actions
 *
 * Features:
 * - Timeline display of all decision plans
 * - Show plan content, freeze status, related actions
 * - Filter by status (draft/frozen/archived), task_id
 * - Click to view details
 * - Pagination support
 */

class DecisionTimelineView {
    constructor(container) {
        this.container = container;
        this.decisions = [];
        this.pagination = { total: 0, limit: 50, offset: 0 };
        this.filters = { status: null, task_id: null };

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="decision-timeline-view">
                <div class="view-header">
                    <div>
                        <h1>Decision Timeline</h1>
                        <p class="text-sm text-gray-600 mt-1">All decision plans with freeze status</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="dt-refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                    </div>
                </div>

                <!-- Filters -->
                <div class="filters-bar">
                    <div class="filter-group">
                        <label>Status:</label>
                        <select id="dt-filter-status" class="filter-select">
                            <option value="">All</option>
                            <option value="draft">Draft</option>
                            <option value="frozen">Frozen</option>
                            <option value="archived">Archived</option>
                            <option value="rolled_back">Rolled Back</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label>Task ID:</label>
                        <input type="text" id="dt-filter-task" class="filter-input" placeholder="task-xxx">
                    </div>
                    <button class="btn-primary" id="dt-apply-filters">Apply Filters</button>
                    <button class="btn-secondary" id="dt-clear-filters">Clear</button>
                </div>

                <!-- Timeline -->
                <div class="timeline-container" id="dt-timeline">
                    <!-- Timeline items will be rendered here -->
                </div>

                <!-- Pagination -->
                <div class="pagination-bar" id="dt-pagination">
                    <!-- Pagination controls will be rendered here -->
                </div>
            </div>
        `;

        this.setupEventListeners();
        this.loadDecisions();
    }

    setupEventListeners() {
        // Refresh button
        const refreshBtn = this.container.querySelector('#dt-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadDecisions());
        }

        // Apply filters button
        const applyBtn = this.container.querySelector('#dt-apply-filters');
        if (applyBtn) {
            applyBtn.addEventListener('click', () => {
                this.applyFilters();
                this.loadDecisions();
            });
        }

        // Clear filters button
        const clearBtn = this.container.querySelector('#dt-clear-filters');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                this.clearFilters();
                this.loadDecisions();
            });
        }

        // Enter key in task filter
        const taskInput = this.container.querySelector('#dt-filter-task');
        if (taskInput) {
            taskInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.applyFilters();
                    this.loadDecisions();
                }
            });
        }
    }

    applyFilters() {
        const statusSelect = this.container.querySelector('#dt-filter-status');
        const taskInput = this.container.querySelector('#dt-filter-task');

        this.filters.status = statusSelect.value || null;
        this.filters.task_id = taskInput.value.trim() || null;
        this.pagination.offset = 0; // Reset to first page
    }

    clearFilters() {
        this.filters = { status: null, task_id: null };
        this.pagination.offset = 0;

        const statusSelect = this.container.querySelector('#dt-filter-status');
        const taskInput = this.container.querySelector('#dt-filter-task');

        if (statusSelect) statusSelect.value = '';
        if (taskInput) taskInput.value = '';
    }

    async loadDecisions() {
        try {
            // Build query params
            const params = new URLSearchParams({
                limit: this.pagination.limit,
                offset: this.pagination.offset
            });

            if (this.filters.status) {
                params.append('status', this.filters.status);
            }

            if (this.filters.task_id) {
                params.append('task_id', this.filters.task_id);
            }

            const response = await fetch(`/api/capability/decisions/timeline?${params}`);
            const result = await response.json();

            if (result.ok && result.data) {
                this.decisions = result.data.decisions;
                this.pagination = result.data.pagination;
                this.renderTimeline();
                this.renderPagination();
            } else {
                this.renderError(result.error || 'Failed to load decisions');
            }
        } catch (error) {
            console.error('Failed to load decisions:', error);
            this.renderError('Failed to connect to API');
        }
    }

    renderTimeline() {
        const timeline = this.container.querySelector('#dt-timeline');
        if (!timeline) return;

        if (this.decisions.length === 0) {
            timeline.innerHTML = `
                <div class="empty-state">
                    <span class="material-icons md-48">timeline</span>
                    <p>No decisions found</p>
                </div>
            `;
            return;
        }

        timeline.innerHTML = this.decisions.map(decision => {
            const statusClass = this.getStatusClass(decision.status);
            const statusIcon = this.getStatusIcon(decision.status);

            return `
                <div class="timeline-item" data-plan-id="${decision.plan_id}">
                    <div class="timeline-marker ${statusClass}">
                        <span class="material-icons md-18">${statusIcon}</span>
                    </div>
                    <div class="timeline-content">
                        <div class="timeline-header">
                            <div class="timeline-meta">
                                <span class="status-badge status-${decision.status}">${decision.status}</span>
                                <span class="timeline-time">${this.formatTimestamp(decision.created_at)}</span>
                            </div>
                            <button class="btn-icon" onclick="window.expandDecision('${decision.plan_id}')">
                                <span class="material-icons md-18">expand_more</span>
                            </button>
                        </div>

                        <div class="timeline-body">
                            <div class="plan-id">
                                <strong>Plan ID:</strong> ${decision.plan_id}
                            </div>
                            <div class="task-id">
                                <strong>Task ID:</strong> ${decision.task_id}
                            </div>
                            <div class="created-by">
                                <strong>Created By:</strong> ${decision.created_by}
                            </div>

                            ${decision.frozen_at ? `
                                <div class="freeze-info">
                                    <span class="material-icons md-18 text-blue-600">lock</span>
                                    <strong>Frozen At:</strong> ${this.formatTimestamp(decision.frozen_at)}
                                    <span class="plan-hash">${decision.plan_hash ? decision.plan_hash.substring(0, 16) + '...' : ''}</span>
                                </div>
                            ` : ''}

                            <div class="rationale">
                                <strong>Rationale:</strong>
                                <p>${this.escapeHtml(decision.rationale)}</p>
                            </div>

                            <div class="plan-steps">
                                <strong>Steps (${decision.steps.length}):</strong>
                                <ol class="steps-list">
                                    ${decision.steps.slice(0, 3).map(step => `
                                        <li>${this.escapeHtml(step.description || step.action || 'Step')}</li>
                                    `).join('')}
                                    ${decision.steps.length > 3 ? `<li class="more-steps">... and ${decision.steps.length - 3} more</li>` : ''}
                                </ol>
                            </div>

                            ${decision.related_actions_count > 0 ? `
                                <div class="related-actions">
                                    <span class="material-icons md-18">play_circle_outline</span>
                                    <strong>${decision.related_actions_count} Related Actions</strong>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    renderPagination() {
        const paginationBar = this.container.querySelector('#dt-pagination');
        if (!paginationBar) return;

        const { total, limit, offset, has_more } = this.pagination;
        const currentPage = Math.floor(offset / limit) + 1;
        const totalPages = Math.ceil(total / limit);

        paginationBar.innerHTML = `
            <div class="pagination-info">
                Showing ${offset + 1} - ${Math.min(offset + limit, total)} of ${total} decisions
            </div>
            <div class="pagination-controls">
                <button class="btn-icon" ${offset === 0 ? 'disabled' : ''} onclick="window.dtPrevPage()">
                    <span class="material-icons md-18">chevron_left</span>
                </button>
                <span class="page-info">Page ${currentPage} of ${totalPages}</span>
                <button class="btn-icon" ${!has_more ? 'disabled' : ''} onclick="window.dtNextPage()">
                    <span class="material-icons md-18">chevron_right</span>
                </button>
            </div>
        `;
    }

    renderError(message) {
        const timeline = this.container.querySelector('#dt-timeline');
        if (timeline) {
            timeline.innerHTML = `
                <div class="error-state">
                    <span class="material-icons md-48">error_outline</span>
                    <p>${message}</p>
                </div>
            `;
        }
    }

    getStatusClass(status) {
        const classes = {
            draft: 'status-draft',
            frozen: 'status-frozen',
            archived: 'status-archived',
            rolled_back: 'status-rolled-back'
        };
        return classes[status] || 'status-default';
    }

    getStatusIcon(status) {
        const icons = {
            draft: 'edit',
            frozen: 'lock',
            archived: 'archive',
            rolled_back: 'undo'
        };
        return icons[status] || 'radio_button_unchecked';
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

        const diffDays = Math.floor(diffHours / 24);
        if (diffDays < 7) return `${diffDays}d ago`;

        return date.toLocaleDateString();
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    nextPage() {
        if (this.pagination.has_more) {
            this.pagination.offset += this.pagination.limit;
            this.loadDecisions();
        }
    }

    prevPage() {
        if (this.pagination.offset > 0) {
            this.pagination.offset = Math.max(0, this.pagination.offset - this.pagination.limit);
            this.loadDecisions();
        }
    }

    destroy() {
        // Cleanup
    }
}

// Global functions for pagination (called from inline onclick)
window.dtNextPage = function() {
    if (window.currentDecisionTimelineView) {
        window.currentDecisionTimelineView.nextPage();
    }
};

window.dtPrevPage = function() {
    if (window.currentDecisionTimelineView) {
        window.currentDecisionTimelineView.prevPage();
    }
};

window.expandDecision = function(planId) {
    alert(`View details for decision: ${planId}\n\n(Details modal to be implemented)`);
};

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DecisionTimelineView;
}
