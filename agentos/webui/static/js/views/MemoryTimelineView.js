/**
 * MemoryTimelineView - Memory Timeline Audit Trail
 *
 * Task #13: Read-only timeline view for memory history
 * Shows chronological history of memory items with audit trail
 * Consistent with AgentOS Logs/Audit style
 */

class MemoryTimelineView {
    constructor(container) {
        this.container = container;
        this.currentPage = 1;
        this.limit = 50;
        this.filters = {
            scope: null,
            source: null,
            type: null,
            project_id: null
        };
        this.totalItems = 0;

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="timeline-view">
                <div class="view-header">
                    <div>
                        <h1>Memory Timeline</h1>
                        <p class="text-sm text-gray-600 mt-1">Chronological audit trail of memory history</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="timeline-refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                    </div>
                </div>

                <!-- Filter Bar -->
                <div class="timeline-filters">
                    <select id="scope-filter" class="filter-select">
                        <option value="">All Scopes</option>
                        <option value="global">Global</option>
                        <option value="project">Project</option>
                        <option value="repo">Repository</option>
                        <option value="task">Task</option>
                        <option value="agent">Agent</option>
                    </select>

                    <select id="type-filter" class="filter-select">
                        <option value="">All Types</option>
                        <option value="decision">Decision</option>
                        <option value="convention">Convention</option>
                        <option value="constraint">Constraint</option>
                        <option value="known_issue">Known Issue</option>
                        <option value="playbook">Playbook</option>
                        <option value="glossary">Glossary</option>
                    </select>

                    <select id="source-filter" class="filter-select">
                        <option value="">All Sources</option>
                        <option value="rule_extraction">Rule Extraction</option>
                        <option value="explicit">User Explicit</option>
                        <option value="system">System</option>
                    </select>

                    <button class="btn-secondary btn-sm" id="reset-filters">
                        <span class="material-icons md-18">clear</span> Reset
                    </button>
                </div>

                <!-- Timeline Content -->
                <div class="timeline-content" id="timeline-content">
                    <div class="loading-state">
                        <div class="spinner"></div>
                        <p>Loading timeline...</p>
                    </div>
                </div>

                <!-- Pagination -->
                <div class="timeline-pagination" id="timeline-pagination"></div>
            </div>
        `;

        this.setupEventListeners();
        this.loadTimeline();
    }

    setupEventListeners() {
        // Refresh button
        const refreshBtn = this.container.querySelector('#timeline-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadTimeline(true));
        }

        // Filter dropdowns
        const scopeFilter = this.container.querySelector('#scope-filter');
        if (scopeFilter) {
            scopeFilter.addEventListener('change', (e) => {
                this.filters.scope = e.target.value || null;
                this.currentPage = 1;
                this.loadTimeline();
            });
        }

        const typeFilter = this.container.querySelector('#type-filter');
        if (typeFilter) {
            typeFilter.addEventListener('change', (e) => {
                this.filters.type = e.target.value || null;
                this.currentPage = 1;
                this.loadTimeline();
            });
        }

        const sourceFilter = this.container.querySelector('#source-filter');
        if (sourceFilter) {
            sourceFilter.addEventListener('change', (e) => {
                this.filters.source = e.target.value || null;
                this.currentPage = 1;
                this.loadTimeline();
            });
        }

        // Reset filters button
        const resetBtn = this.container.querySelector('#reset-filters');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                this.resetFilters();
            });
        }
    }

    resetFilters() {
        this.filters = {
            scope: null,
            source: null,
            type: null,
            project_id: null
        };
        this.currentPage = 1;

        // Reset UI
        const scopeFilter = this.container.querySelector('#scope-filter');
        const typeFilter = this.container.querySelector('#type-filter');
        const sourceFilter = this.container.querySelector('#source-filter');

        if (scopeFilter) scopeFilter.value = '';
        if (typeFilter) typeFilter.value = '';
        if (sourceFilter) sourceFilter.value = '';

        this.loadTimeline();
    }

    async loadTimeline(forceRefresh = false) {
        const timelineContent = this.container.querySelector('#timeline-content');

        try {
            // Show loading state
            if (!forceRefresh) {
                timelineContent.innerHTML = `
                    <div class="loading-state">
                        <div class="spinner"></div>
                        <p>Loading timeline...</p>
                    </div>
                `;
            }

            // Build query params
            const params = new URLSearchParams({
                limit: this.limit,
                offset: (this.currentPage - 1) * this.limit
            });

            if (this.filters.scope) {
                params.append('scope', this.filters.scope);
            }
            if (this.filters.type) {
                params.append('mem_type', this.filters.type);
            }
            if (this.filters.project_id) {
                params.append('project_id', this.filters.project_id);
            }

            // Fetch data
            const response = await apiClient.get(`/api/memory/timeline?${params}`);

            if (!response.ok) {
                throw new Error(response.error || 'Failed to load timeline');
            }

            const data = response.data;
            this.totalItems = data.total;

            // Filter by source client-side (if API doesn't support it)
            let items = data.items || [];
            if (this.filters.source) {
                items = items.filter(item => item.source === this.filters.source);
            }

            // Render timeline
            this.renderTimelineItems(items);
            this.renderPagination(data);

            // Show success toast on manual refresh
            if (forceRefresh && window.showToast) {
                window.showToast(`Loaded ${items.length} timeline items`, 'success', 1500);
            }

        } catch (error) {
            console.error('[Timeline] Failed to load:', error);
            timelineContent.innerHTML = `
                <div class="error-state">
                    <span class="material-icons md-48">error_outline</span>
                    <p>Failed to load timeline</p>
                    <p class="text-sm text-gray-600">${this.escapeHtml(error.message)}</p>
                </div>
            `;

            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    renderTimelineItems(items) {
        const timelineContent = this.container.querySelector('#timeline-content');

        if (items.length === 0) {
            timelineContent.innerHTML = `
                <div class="empty-state">
                    <span class="material-icons md-48">timeline</span>
                    <p>No memory items found</p>
                    <p class="text-sm text-gray-600">Try adjusting your filters</p>
                </div>
            `;
            return;
        }

        // Group by date
        const groupedByDate = this.groupByDate(items);

        let html = '<div class="timeline-container">';

        for (const [date, dateItems] of Object.entries(groupedByDate)) {
            html += `
                <div class="timeline-date-group">
                    <div class="timeline-date-header">${date}</div>
                    <div class="timeline-items">
            `;

            for (const item of dateItems) {
                html += this.renderTimelineItem(item);
            }

            html += `
                    </div>
                </div>
            `;
        }

        html += '</div>';

        timelineContent.innerHTML = html;
    }

    renderTimelineItem(item) {
        // Source badge color
        const sourceColors = {
            'rule_extraction': '#4caf50',
            'explicit': '#2196f3',
            'system': '#9e9e9e'
        };

        const sourceColor = sourceColors[item.source] || '#9e9e9e';

        // Active/Superseded status
        const statusBadge = item.is_active
            ? '<span class="status-badge status-active">Active</span>'
            : '<span class="status-badge status-superseded">Superseded</span>';

        // Version badge
        const versionBadge = item.version > 1
            ? `<span class="version-badge">v${item.version}</span>`
            : '';

        // Truncate long values
        const displayValue = this.truncateText(item.value, 200);

        return `
            <div class="timeline-item ${item.is_active ? 'active' : 'inactive'}">
                <div class="timeline-marker" style="background-color: ${sourceColor}"></div>

                <div class="timeline-card">
                    <div class="timeline-card-header">
                        <span class="timeline-time">${this.formatTime(item.timestamp)}</span>
                        ${statusBadge}
                        ${versionBadge}
                    </div>

                    <div class="timeline-card-body">
                        <div class="timeline-key-value">
                            <span class="timeline-key">${this.escapeHtml(item.key)}</span>
                            <span class="timeline-arrow">→</span>
                            <span class="timeline-value">${this.escapeHtml(displayValue)}</span>
                        </div>

                        <div class="timeline-meta">
                            <span class="meta-item">
                                <span class="meta-label">Type:</span>
                                <span class="meta-value">${item.type}</span>
                            </span>

                            <span class="meta-item">
                                <span class="meta-label">Source:</span>
                                <span class="meta-value" style="color: ${sourceColor}">
                                    ${this.formatSource(item.source)}
                                </span>
                            </span>

                            <span class="meta-item">
                                <span class="meta-label">Confidence:</span>
                                <span class="meta-value">${(item.confidence * 100).toFixed(0)}%</span>
                            </span>

                            <span class="meta-item">
                                <span class="meta-label">Scope:</span>
                                <span class="meta-value">${item.scope}</span>
                            </span>

                            <span class="meta-item">
                                <span class="meta-label">ID:</span>
                                <span class="meta-value font-mono text-xs">${item.id}</span>
                            </span>
                        </div>

                        ${this.renderSupersededInfo(item)}
                    </div>
                </div>
            </div>
        `;
    }

    renderSupersededInfo(item) {
        if (item.supersedes) {
            return `
                <div class="timeline-superseded-info">
                    <span class="material-icons md-18">arrow_upward</span>
                    Replaces: <code>${item.supersedes}</code>
                </div>
            `;
        }

        if (item.superseded_by) {
            return `
                <div class="timeline-superseded-info warning">
                    <span class="material-icons md-18">warning</span>
                    Superseded by: <code>${item.superseded_by}</code>
                </div>
            `;
        }

        return '';
    }

    groupByDate(items) {
        const grouped = {};

        for (const item of items) {
            const date = new Date(item.timestamp);
            const dateKey = this.formatDateKey(date);

            if (!grouped[dateKey]) {
                grouped[dateKey] = [];
            }

            grouped[dateKey].push(item);
        }

        return grouped;
    }

    formatDateKey(date) {
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);

        if (this.isSameDay(date, today)) {
            return 'Today';
        } else if (this.isSameDay(date, yesterday)) {
            return 'Yesterday';
        } else {
            return date.toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
        }
    }

    isSameDay(d1, d2) {
        return d1.getFullYear() === d2.getFullYear() &&
               d1.getMonth() === d2.getMonth() &&
               d1.getDate() === d2.getDate();
    }

    formatTime(isoString) {
        const date = new Date(isoString);
        return date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }

    formatSource(source) {
        const sourceNames = {
            'rule_extraction': 'Rule Extraction',
            'explicit': 'User Explicit',
            'system': 'System'
        };
        return sourceNames[source] || source;
    }

    renderPagination(data) {
        const paginationDiv = this.container.querySelector('#timeline-pagination');

        if (data.total <= this.limit) {
            paginationDiv.innerHTML = '';
            return;
        }

        const totalPages = Math.ceil(data.total / this.limit);

        let html = `
            <div class="pagination-controls">
                <button class="btn-secondary btn-sm" ${this.currentPage === 1 ? 'disabled' : ''}
                        id="pagination-prev">
                    <span class="material-icons md-18">chevron_left</span> Previous
                </button>

                <span class="pagination-info">
                    Page ${this.currentPage} of ${totalPages} <span class="text-gray-500">(${data.total} items)</span>
                </span>

                <button class="btn-secondary btn-sm" ${!data.has_more ? 'disabled' : ''}
                        id="pagination-next">
                    Next <span class="material-icons md-18">chevron_right</span>
                </button>
            </div>
        `;

        paginationDiv.innerHTML = html;

        // Attach pagination event listeners
        const prevBtn = paginationDiv.querySelector('#pagination-prev');
        const nextBtn = paginationDiv.querySelector('#pagination-next');

        if (prevBtn) {
            prevBtn.addEventListener('click', () => this.goToPage(this.currentPage - 1));
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', () => this.goToPage(this.currentPage + 1));
        }
    }

    goToPage(page) {
        this.currentPage = page;
        this.loadTimeline();

        // Scroll to top
        this.container.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // Utility functions
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    truncateText(text, maxLength) {
        if (text.length <= maxLength) {
            return text;
        }
        return text.substring(0, maxLength) + '...';
    }

    destroy() {
        // Cleanup
        this.container.innerHTML = '';
    }
}
