/**
 * DecisionComparisonView - Active vs Shadow Decision Comparison Dashboard
 *
 * Displays side-by-side comparison of active (executed) and shadow (hypothetical)
 * classifier decisions to help humans evaluate which shadow version is worth migrating.
 *
 * Key Features:
 * - List view: Paginated decision comparisons with filters
 * - Detail view: Side-by-side comparison of active vs shadow decisions
 * - Summary view: Aggregated statistics for multiple shadow versions
 * - Clear distinction: Active (executed) vs Shadow (NOT EXECUTED)
 * - Score visualization: Reality Alignment Score comparison
 * - Responsive design: Adapts to different screen sizes
 *
 * Design Philosophy:
 * - Data-driven: All comparisons based on actual recorded decisions
 * - Transparent: Clear metrics for human judgment
 * - Safety: Prominent warnings that shadow decisions were not executed
 */

class DecisionComparisonView {
    constructor(container) {
        this.container = container;
        this.currentView = 'list';  // 'list', 'detail', 'summary'
        this.listData = null;
        this.detailData = null;
        this.summaryData = null;
        this.filters = {
            sessionId: null,
            activeVersion: 'v1',
            timeRange: '24h',
            infoNeedType: null,
            offset: 0,
            limit: 20,
        };

        this.init();
    }

    init() {
        this.renderLayout();
        this.setupEventListeners();
        this.loadList();
    }

    renderLayout() {
        this.container.innerHTML = `
            <div class="decision-comparison-dashboard">
                <div class="view-header">
                    <div>
                        <h1>Decision Comparison</h1>
                        <p class="text-sm text-gray-600 mt-1">Active vs Shadow Classifier Decisions</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-secondary" id="view-summary">
                            <span class="material-icons md-18">analytics</span> Summary
                        </button>
                        <button class="btn-secondary" id="view-list">
                            <span class="material-icons md-18">list</span> List
                        </button>
                        <button class="btn-refresh" id="decision-refresh">
                            <span class="material-icons md-18">refresh</span> Refresh
                        </button>
                    </div>
                </div>

                <div class="filters-section" id="filters-section">
                    <!-- Filters will be rendered here -->
                </div>

                <div class="content-section" id="content-section">
                    <!-- Main content will be rendered here -->
                </div>
            </div>
        `;

        this.renderFilters();
    }

    renderFilters() {
        const filtersSection = this.container.querySelector('#filters-section');
        if (!filtersSection) return;

        filtersSection.innerHTML = `
            <div class="filters-grid">
                <div class="filter-item">
                    <label>Time Range</label>
                    <select class="filter-select" id="filter-time-range">
                        <option value="24h" ${this.filters.timeRange === '24h' ? 'selected' : ''}>Last 24 Hours</option>
                        <option value="7d" ${this.filters.timeRange === '7d' ? 'selected' : ''}>Last 7 Days</option>
                        <option value="30d" ${this.filters.timeRange === '30d' ? 'selected' : ''}>Last 30 Days</option>
                    </select>
                </div>
                <div class="filter-item">
                    <label>Active Version</label>
                    <input type="text" class="filter-input" id="filter-active-version"
                           value="${this.filters.activeVersion}" placeholder="e.g., v1">
                </div>
                <div class="filter-item">
                    <label>Session ID (Optional)</label>
                    <input type="text" class="filter-input" id="filter-session-id"
                           value="${this.filters.sessionId || ''}" placeholder="Filter by session">
                </div>
                <div class="filter-item">
                    <label>Info Need Type (Optional)</label>
                    <select class="filter-select" id="filter-info-need-type">
                        <option value="">All Types</option>
                        <option value="EXTERNAL_FACT_UNCERTAIN">EXTERNAL_FACT_UNCERTAIN</option>
                        <option value="LOCAL_KNOWLEDGE">LOCAL_KNOWLEDGE</option>
                        <option value="AMBIENT_STATE">AMBIENT_STATE</option>
                        <option value="USER_CLARIFICATION">USER_CLARIFICATION</option>
                    </select>
                </div>
                <div class="filter-actions">
                    <button class="btn-primary" id="apply-filters">Apply Filters</button>
                    <button class="btn-secondary" id="reset-filters">Reset</button>
                </div>
            </div>
        `;
    }

    setupEventListeners() {
        // View switchers
        const summaryBtn = this.container.querySelector('#view-summary');
        if (summaryBtn) {
            summaryBtn.addEventListener('click', () => this.switchView('summary'));
        }

        const listBtn = this.container.querySelector('#view-list');
        if (listBtn) {
            listBtn.addEventListener('click', () => this.switchView('list'));
        }

        // Refresh button
        const refreshBtn = this.container.querySelector('#decision-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refresh());
        }

        // Filter actions
        const applyBtn = this.container.querySelector('#apply-filters');
        if (applyBtn) {
            applyBtn.addEventListener('click', () => this.applyFilters());
        }

        const resetBtn = this.container.querySelector('#reset-filters');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => this.resetFilters());
        }
    }

    async switchView(view) {
        this.currentView = view;

        if (view === 'list') {
            await this.loadList();
        } else if (view === 'summary') {
            await this.loadSummary();
        }
    }

    async refresh() {
        if (this.currentView === 'list') {
            await this.loadList();
        } else if (this.currentView === 'detail') {
            // Reload current detail
            if (this.detailData) {
                await this.loadDetail(this.detailData.decision_set_id);
            }
        } else if (this.currentView === 'summary') {
            await this.loadSummary();
        }
    }

    applyFilters() {
        // Read filter values
        const timeRange = this.container.querySelector('#filter-time-range')?.value;
        const activeVersion = this.container.querySelector('#filter-active-version')?.value;
        const sessionId = this.container.querySelector('#filter-session-id')?.value;
        const infoNeedType = this.container.querySelector('#filter-info-need-type')?.value;

        this.filters.timeRange = timeRange || '24h';
        this.filters.activeVersion = activeVersion || 'v1';
        this.filters.sessionId = sessionId || null;
        this.filters.infoNeedType = infoNeedType || null;
        this.filters.offset = 0;  // Reset pagination

        this.refresh();
    }

    resetFilters() {
        this.filters = {
            sessionId: null,
            activeVersion: 'v1',
            timeRange: '24h',
            infoNeedType: null,
            offset: 0,
            limit: 20,
        };

        this.renderFilters();
        this.refresh();
    }

    async loadList() {
        try {
            this.showLoading();

            // Build query parameters
            const params = new URLSearchParams({
                active_version: this.filters.activeVersion,
                time_range: this.filters.timeRange,
                limit: this.filters.limit.toString(),
                offset: this.filters.offset.toString(),
            });

            if (this.filters.sessionId) {
                params.append('session_id', this.filters.sessionId);
            }
            if (this.filters.infoNeedType) {
                params.append('info_need_type', this.filters.infoNeedType);
            }

            const response = await fetch(`/api/v3/decision-comparison/list?${params}`);
            const result = await response.json();

            if (result.ok && result.data) {
                this.listData = result.data;
                this.renderList();
            } else {
                this.renderError(result.error || 'Failed to load decision comparisons');
            }
        } catch (error) {
            console.error('Failed to load list:', error);
            this.renderError('Failed to connect to API');
        }
    }

    renderList() {
        const contentSection = this.container.querySelector('#content-section');
        if (!contentSection || !this.listData) return;

        const items = this.listData.items || [];
        const totalCount = this.listData.total_count || 0;

        if (items.length === 0) {
            contentSection.innerHTML = `
                <div class="no-data-state">
                    <span class="material-icons md-48 text-gray-400">inbox</span>
                    <h3>No Decision Comparisons Found</h3>
                    <p class="text-muted">Try adjusting your filters or time range</p>
                </div>
            `;
            return;
        }

        contentSection.innerHTML = `
            <div class="list-header">
                <span class="text-sm text-gray-600">${totalCount} decision sets found</span>
            </div>
            <div class="decision-list">
                ${items.map(item => this.renderListItem(item)).join('')}
            </div>
            <div class="pagination">
                ${this.renderPagination(totalCount)}
            </div>
        `;

        // Setup click handlers for list items
        items.forEach(item => {
            const element = contentSection.querySelector(`[data-decision-id="${item.decision_set_id}"]`);
            if (element) {
                element.addEventListener('click', () => this.loadDetail(item.decision_set_id));
            }
        });
    }

    renderListItem(item) {
        const hasEvaluation = item.has_evaluation;
        const shadowCount = item.shadow_count || 0;

        return `
            <div class="decision-list-item" data-decision-id="${item.decision_set_id}">
                <div class="item-header">
                    <div class="item-question">${this.escapeHtml(item.question_text)}</div>
                    <div class="item-meta">
                        <span class="badge badge-primary">${item.active_decision.version}</span>
                        ${hasEvaluation ? '<span class="badge badge-success">Scored</span>' : ''}
                    </div>
                </div>
                <div class="item-details">
                    <div class="detail-row">
                        <span class="label">Active Decision:</span>
                        <span class="value decision-badge ${this.getDecisionClass(item.active_decision.decision_action)}">
                            ${item.active_decision.decision_action}
                        </span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Info Need:</span>
                        <span class="value">${item.active_decision.info_need_type}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Shadow Versions:</span>
                        <span class="value">${shadowCount} version${shadowCount !== 1 ? 's' : ''} (${item.shadow_versions.join(', ')})</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Timestamp:</span>
                        <span class="value">${this.formatTime(new Date(item.timestamp))}</span>
                    </div>
                </div>
                <div class="item-action">
                    <span class="material-icons md-18">chevron_right</span>
                </div>
            </div>
        `;
    }

    renderPagination(totalCount) {
        const currentPage = Math.floor(this.filters.offset / this.filters.limit) + 1;
        const totalPages = Math.ceil(totalCount / this.filters.limit);

        const prevDisabled = currentPage === 1;
        const nextDisabled = currentPage === totalPages || totalPages === 0;

        return `
            <button class="btn-secondary" ${prevDisabled ? 'disabled' : ''} id="prev-page">
                <span class="material-icons md-18">chevron_left</span> Previous
            </button>
            <span class="pagination-info">Page ${currentPage} of ${totalPages}</span>
            <button class="btn-secondary" ${nextDisabled ? 'disabled' : ''} id="next-page">
                Next <span class="material-icons md-18">chevron_right</span>
            </button>
        `;
    }

    async loadDetail(decisionSetId) {
        try {
            this.showLoading();

            const response = await fetch(`/api/v3/decision-comparison/${decisionSetId}`);
            const result = await response.json();

            if (result.ok && result.data) {
                this.detailData = result.data;
                this.currentView = 'detail';
                this.renderDetail();
            } else {
                this.renderError(result.error || 'Failed to load decision details');
            }
        } catch (error) {
            console.error('Failed to load detail:', error);
            this.renderError('Failed to connect to API');
        }
    }

    renderDetail() {
        const contentSection = this.container.querySelector('#content-section');
        if (!contentSection || !this.detailData) return;

        const active = this.detailData.active_decision;
        const shadows = this.detailData.shadow_decisions || [];
        const comparison = this.detailData.comparison || {};

        contentSection.innerHTML = `
            <div class="detail-view">
                <div class="detail-header">
                    <button class="btn-back" id="back-to-list">
                        <span class="material-icons md-18">arrow_back</span> Back to List
                    </button>
                    <h2>Decision Comparison</h2>
                </div>

                <div class="decision-context">
                    <h3>Question</h3>
                    <p class="question-text">${this.escapeHtml(this.detailData.question_text)}</p>
                    <div class="context-meta">
                        <span><strong>Session:</strong> ${this.detailData.session_id}</span>
                        <span><strong>Message:</strong> ${this.detailData.message_id}</span>
                        <span><strong>Time:</strong> ${this.formatTime(new Date(this.detailData.timestamp))}</span>
                    </div>
                </div>

                <div class="comparison-grid">
                    <!-- Active Decision Card -->
                    <div class="decision-card active-card">
                        <div class="card-header">
                            <h3>Active Decision</h3>
                            <span class="badge badge-success">EXECUTED</span>
                        </div>
                        ${this.renderDecisionDetails(active, 'active')}
                    </div>

                    <!-- Shadow Decision Cards -->
                    ${shadows.map(shadow => `
                        <div class="decision-card shadow-card">
                            <div class="card-header">
                                <h3>Shadow Decision: ${shadow.version}</h3>
                                <span class="badge badge-warning">NOT EXECUTED</span>
                            </div>
                            <div class="shadow-warning">
                                <span class="material-icons md-18">warning</span>
                                Hypothetical evaluation only - not executed in production
                            </div>
                            ${this.renderDecisionDetails(shadow, 'shadow')}
                            <div class="version-description">
                                <strong>Change Description:</strong> ${this.escapeHtml(shadow.version_description || 'N/A')}
                            </div>
                        </div>
                    `).join('')}
                </div>

                ${this.renderComparisonSummary(comparison, active, shadows)}
            </div>
        `;

        // Setup back button
        const backBtn = contentSection.querySelector('#back-to-list');
        if (backBtn) {
            backBtn.addEventListener('click', () => {
                this.currentView = 'list';
                this.renderList();
            });
        }
    }

    renderDecisionDetails(decision, role) {
        const hasScore = decision.score !== null && decision.score !== undefined;

        return `
            <div class="decision-details">
                <div class="detail-group">
                    <div class="detail-item">
                        <span class="label">Version:</span>
                        <span class="value badge badge-primary">${decision.version}</span>
                    </div>
                    <div class="detail-item">
                        <span class="label">Decision Action:</span>
                        <span class="value decision-badge ${this.getDecisionClass(decision.decision_action)}">
                            ${decision.decision_action}
                        </span>
                    </div>
                    <div class="detail-item">
                        <span class="label">Info Need Type:</span>
                        <span class="value">${decision.info_need_type}</span>
                    </div>
                    <div class="detail-item">
                        <span class="label">Confidence:</span>
                        <span class="value">${decision.confidence_level}</span>
                    </div>
                </div>

                ${hasScore ? `
                    <div class="score-section">
                        <div class="score-label">Reality Alignment Score</div>
                        <div class="score-value ${this.getScoreClass(decision.score)}">
                            ${decision.score.toFixed(2)}
                        </div>
                        <div class="score-bar">
                            <div class="score-fill ${this.getScoreClass(decision.score)}"
                                 style="width: ${decision.score * 100}%"></div>
                        </div>
                    </div>
                ` : '<div class="no-score">No score available</div>'}

                <div class="detail-group">
                    <div class="detail-item">
                        <span class="label">Reason Codes:</span>
                        <span class="value">${decision.reason_codes.join(', ') || 'None'}</span>
                    </div>
                </div>
            </div>
        `;
    }

    renderComparisonSummary(comparison, active, shadows) {
        if (!comparison.best_shadow_version) {
            return '<div class="comparison-summary"><p>No comparison data available</p></div>';
        }

        const scoreDelta = comparison.score_delta || 0;
        const wouldChange = comparison.would_change_decision;

        return `
            <div class="comparison-summary">
                <h3>Comparison Summary</h3>
                <div class="summary-grid">
                    <div class="summary-item">
                        <span class="label">Best Shadow Version:</span>
                        <span class="value badge badge-primary">${comparison.best_shadow_version}</span>
                    </div>
                    <div class="summary-item">
                        <span class="label">Score Delta:</span>
                        <span class="value ${scoreDelta > 0 ? 'text-green-600' : 'text-red-600'}">
                            ${scoreDelta > 0 ? '+' : ''}${scoreDelta.toFixed(2)}
                        </span>
                    </div>
                    <div class="summary-item">
                        <span class="label">Would Change Decision:</span>
                        <span class="value">${wouldChange ? 'Yes' : 'No'}</span>
                    </div>
                    ${scoreDelta > 0.1 ? `
                        <div class="recommendation">
                            <span class="material-icons md-18 text-green-600">check_circle</span>
                            <span>Shadow version shows improvement - consider for migration</span>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    async loadSummary() {
        try {
            this.showLoading();

            // For now, we'll query for common shadow versions
            // In production, this could be made configurable
            const shadowVersions = 'v2-shadow-a,v2-shadow-b';

            const params = new URLSearchParams({
                active_version: this.filters.activeVersion,
                shadow_versions: shadowVersions,
                time_range: this.filters.timeRange,
            });

            if (this.filters.sessionId) {
                params.append('session_id', this.filters.sessionId);
            }
            if (this.filters.infoNeedType) {
                params.append('info_need_type', this.filters.infoNeedType);
            }

            const response = await fetch(`/api/v3/decision-comparison/summary?${params}`);
            const result = await response.json();

            if (result.ok && result.data) {
                this.summaryData = result.data;
                this.renderSummary();
            } else {
                this.renderError(result.error || 'Failed to load summary');
            }
        } catch (error) {
            console.error('Failed to load summary:', error);
            this.renderError('Failed to connect to API');
        }
    }

    renderSummary() {
        const contentSection = this.container.querySelector('#content-section');
        if (!contentSection || !this.summaryData) return;

        const comparisons = this.summaryData.shadow_comparisons || [];

        contentSection.innerHTML = `
            <div class="summary-view">
                <h2>Summary Statistics</h2>
                <p class="text-sm text-gray-600 mb-4">Active Version: ${this.summaryData.active_version}</p>

                <div class="summary-cards">
                    ${comparisons.map(comp => this.renderSummaryCard(comp)).join('')}
                </div>
            </div>
        `;
    }

    renderSummaryCard(comparison) {
        const recommendation = comparison.recommendation || 'NO_DATA';
        const improvementRate = comparison.improvement_rate;
        const hasData = improvementRate !== null && improvementRate !== undefined;

        return `
            <div class="summary-card ${this.getRecommendationClass(recommendation)}">
                <div class="card-title">
                    <h3>${comparison.shadow_version}</h3>
                    <span class="badge ${this.getRecommendationBadgeClass(recommendation)}">
                        ${this.formatRecommendation(recommendation)}
                    </span>
                </div>
                <div class="card-metrics">
                    <div class="metric-item">
                        <span class="label">Sample Count:</span>
                        <span class="value">${comparison.sample_count}</span>
                    </div>
                    <div class="metric-item">
                        <span class="label">Divergence Rate:</span>
                        <span class="value">${(comparison.divergence_rate * 100).toFixed(1)}%</span>
                    </div>
                    ${hasData ? `
                        <div class="metric-item">
                            <span class="label">Improvement Rate:</span>
                            <span class="value ${improvementRate > 0 ? 'text-green-600' : 'text-red-600'}">
                                ${improvementRate > 0 ? '+' : ''}${(improvementRate * 100).toFixed(1)}%
                            </span>
                        </div>
                        <div class="metric-item">
                            <span class="label">Better/Worse/Neutral:</span>
                            <span class="value">${comparison.better_count}/${comparison.worse_count}/${comparison.neutral_count}</span>
                        </div>
                    ` : '<div class="metric-item"><span class="text-muted">No score data available</span></div>'}
                </div>
            </div>
        `;
    }

    // Utility Methods

    showLoading() {
        const contentSection = this.container.querySelector('#content-section');
        if (!contentSection) return;

        contentSection.innerHTML = `
            <div class="loading-state">
                <span class="material-icons md-48 animate-spin">refresh</span>
                <p>Loading...</p>
            </div>
        `;
    }

    renderError(message) {
        const contentSection = this.container.querySelector('#content-section');
        if (!contentSection) return;

        contentSection.innerHTML = `
            <div class="error-state">
                <span class="material-icons md-48 text-red-600">error</span>
                <h3>Failed to Load Data</h3>
                <p class="text-muted">${this.escapeHtml(message)}</p>
                <button class="btn-primary mt-3" onclick="location.reload()">
                    Retry
                </button>
            </div>
        `;
    }

    getDecisionClass(decisionAction) {
        if (decisionAction === 'REQUIRE_COMM') return 'decision-comm';
        if (decisionAction === 'DIRECT_ANSWER') return 'decision-answer';
        return 'decision-default';
    }

    getScoreClass(score) {
        if (score >= 0.7) return 'score-good';
        if (score >= 0.4) return 'score-warning';
        return 'score-danger';
    }

    getRecommendationClass(recommendation) {
        if (recommendation.includes('STRONGLY_RECOMMEND') || recommendation.includes('CONSIDER')) {
            return 'recommendation-positive';
        }
        if (recommendation === 'DO_NOT_MIGRATE') {
            return 'recommendation-negative';
        }
        return 'recommendation-neutral';
    }

    getRecommendationBadgeClass(recommendation) {
        if (recommendation.includes('STRONGLY_RECOMMEND')) return 'badge-success';
        if (recommendation.includes('CONSIDER')) return 'badge-info';
        if (recommendation === 'DO_NOT_MIGRATE') return 'badge-danger';
        return 'badge-secondary';
    }

    formatRecommendation(recommendation) {
        return recommendation.replace(/_/g, ' ');
    }

    formatTime(date) {
        const now = new Date();
        const diff = now - date;
        const seconds = Math.floor(diff / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (seconds < 60) return 'just now';
        if (minutes < 60) return `${minutes}m ago`;
        if (hours < 24) return `${hours}h ago`;
        if (days < 7) return `${days}d ago`;

        return date.toLocaleString();
    }

    escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    destroy() {
        // Cleanup if needed
    }
}
