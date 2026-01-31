/**
 * KnowledgePlaygroundView - Query Playground for RAG debugging
 *
 * Phase 1: Query Playground
 * Coverage: POST /api/knowledge/search
 */

class KnowledgePlaygroundView {
    constructor(container) {
        this.container = container;
        this.filterBar = null;
        this.dataTable = null;
        this.currentFilters = {};
        this.results = [];
        this.currentQuery = '';

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="knowledge-playground-view">
                <div class="view-header">
                    <div>
                        <h1>Query Playground</h1>
                        <p class="text-sm text-gray-600 mt-1">Test and explore knowledge base queries</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="kb-refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                    </div>
                </div>

                <!-- Search Bar -->
                <div class="search-section">
                    <div class="search-input-group">
                        <input
                            type="text"
                            id="kb-search-input"
                            placeholder="Search knowledge base (e.g., JWT authentication)..."
                            class="search-input"
                        />
                        <button class="btn-primary" id="kb-search-btn">
                            <span class="icon"><span class="material-icons md-18">search</span></span>
                            Search
                        </button>
                    </div>
                </div>

                <!-- Filter Bar -->
                <div id="kb-filter-bar" class="filter-section"></div>

                <!-- Results Section -->
                <div class="results-section">
                    <div class="results-header">
                        <span class="results-count" id="kb-results-count">No results</span>
                        <span class="results-duration" id="kb-results-duration"></span>
                    </div>
                    <div id="kb-results-table" class="table-section"></div>
                </div>

                <!-- Detail Drawer -->
                <div id="kb-detail-drawer" class="drawer hidden">
                    <div class="drawer-overlay" id="kb-drawer-overlay"></div>
                    <div class="drawer-content">
                        <div class="drawer-header">
                            <h3>Result Details</h3>
                            <button class="btn-close" id="kb-drawer-close">
                                <span class="material-icons">close</span>
                            </button>
                        </div>
                        <div class="drawer-body" id="kb-drawer-body">
                            <!-- Result details will be rendered here -->
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.setupFilterBar();
        this.setupDataTable();
        this.setupEventListeners();
    }

    setupFilterBar() {
        const filterContainer = this.container.querySelector('#kb-filter-bar');

        this.filterBar = new FilterBar(filterContainer, {
            filters: [
                {
                    type: 'text',
                    key: 'path_contains',
                    label: 'Path',
                    placeholder: 'Filter by path (e.g., docs/)...'
                },
                {
                    type: 'select',
                    key: 'file_type',
                    label: 'File Type',
                    options: [
                        { value: '', label: 'All Types' },
                        { value: 'md', label: 'Markdown (.md)' },
                        { value: 'py', label: 'Python (.py)' },
                        { value: 'js', label: 'JavaScript (.js)' },
                        { value: 'ts', label: 'TypeScript (.ts)' },
                        { value: 'json', label: 'JSON (.json)' },
                        { value: 'yaml', label: 'YAML (.yaml)' }
                    ]
                },
                {
                    type: 'text',
                    key: 'top_k',
                    label: 'Top K',
                    placeholder: '10',
                    defaultValue: '10'
                },
                {
                    type: 'select',
                    key: 'show_scores',
                    label: 'Show Scores',
                    options: [
                        { value: 'true', label: 'Yes' },
                        { value: 'false', label: 'No' }
                    ]
                }
            ],
            onFilterChange: (filters) => {
                this.currentFilters = filters;
                // Auto-search if query exists
                if (this.currentQuery) {
                    this.performSearch();
                }
            }
        });
    }

    setupDataTable() {
        const tableContainer = this.container.querySelector('#kb-results-table');

        this.dataTable = new DataTable(tableContainer, {
            columns: [
                { key: 'rank', label: 'Rank', width: '60px' },
                { key: 'path', label: 'Path', width: '30%' },
                { key: 'heading', label: 'Heading', width: '30%' },
                { key: 'lines', label: 'Lines', width: '100px' },
                { key: 'score', label: 'Score', width: '80px' },
                { key: 'matched_terms', label: 'Matched Terms', width: 'auto' }
            ],
            onRowClick: (row) => {
                this.showResultDetail(row);
            },
            emptyMessage: 'No search results. Try searching for something!',
            pagination: true,
            pageSize: 10
        });
    }

    setupEventListeners() {
        // Search button
        const searchBtn = this.container.querySelector('#kb-search-btn');
        const searchInput = this.container.querySelector('#kb-search-input');

        searchBtn.addEventListener('click', () => {
            this.currentQuery = searchInput.value.trim();
            if (this.currentQuery) {
                this.performSearch();
            }
        });

        // Enter key to search
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.currentQuery = searchInput.value.trim();
                if (this.currentQuery) {
                    this.performSearch();
                }
            }
        });

        // Refresh button
        const refreshBtn = this.container.querySelector('#kb-refresh');
        refreshBtn.addEventListener('click', () => {
            if (this.currentQuery) {
                this.performSearch();
            }
        });

        // Drawer close
        const drawerClose = this.container.querySelector('#kb-drawer-close');
        const drawerOverlay = this.container.querySelector('#kb-drawer-overlay');

        drawerClose.addEventListener('click', () => this.closeDrawer());
        drawerOverlay.addEventListener('click', () => this.closeDrawer());
    }

    async performSearch() {
        try {
            const topK = parseInt(this.currentFilters.top_k || '10', 10);
            const showScores = this.currentFilters.show_scores !== 'false';

            // Build filters
            const filters = {};
            if (this.currentFilters.path_contains) {
                filters.path_contains = this.currentFilters.path_contains;
            }
            if (this.currentFilters.file_type) {
                filters.file_types = [this.currentFilters.file_type];
            }

            // Build request
            const request = {
                query: this.currentQuery,
                filters: Object.keys(filters).length > 0 ? filters : null,
                top_k: topK,
                explain: true
            };

            // Call API
            // CSRF Fix: Use fetchWithCSRF for protected endpoint
            const response = await window.fetchWithCSRF('/api/knowledge/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(request)
            });

            const data = await response.json();

            if (data.ok) {
                this.results = data.data.results || [];
                this.renderResults(data.data);
            } else {
                Toast.error(`Search failed: ${data.error || 'Unknown error'}`);
                this.results = [];
                this.renderResults({ results: [], total: 0, duration_ms: 0 });
            }
        } catch (error) {
            console.error('Search error:', error);
            Toast.error(`Search error: ${error.message}`);
            this.results = [];
            this.renderResults({ results: [], total: 0, duration_ms: 0 });
        }
    }

    renderResults(data) {
        const { results, total, duration_ms } = data;

        // Update counts
        const countEl = this.container.querySelector('#kb-results-count');
        const durationEl = this.container.querySelector('#kb-results-duration');

        countEl.textContent = total === 1 ? '1 result' : `${total} results`;
        durationEl.textContent = duration_ms ? `(${duration_ms}ms)` : '';

        // Transform results for DataTable
        const showScores = this.currentFilters.show_scores !== 'false';
        const tableData = results.map((result, index) => {
            const matchedTerms = result.explanation?.matched_terms || [];

            return {
                rank: index + 1,
                path: result.path || '-',
                heading: result.heading || '(no heading)',
                lines: result.lines || '-',
                score: showScores ? result.score.toFixed(2) : '-',
                matched_terms: matchedTerms.join(', ') || '-',
                _raw: result // Store raw data for drawer
            };
        });

        this.dataTable.setData(tableData);
    }

    showResultDetail(row) {
        const result = row._raw;
        if (!result) return;

        const drawer = this.container.querySelector('#kb-detail-drawer');
        const drawerBody = this.container.querySelector('#kb-drawer-body');

        // Build detail view
        const explanation = result.explanation || {};
        const matchedTerms = explanation.matched_terms || [];
        const termFreqs = explanation.term_frequencies || {};

        drawerBody.innerHTML = `
            <div class="result-detail">
                <div class="detail-section">
                    <h4>Location</h4>
                    <div class="detail-info">
                        <div class="info-row">
                            <span class="info-label">Path:</span>
                            <span class="info-value">${result.path}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Heading:</span>
                            <span class="info-value">${result.heading || '(no heading)'}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Lines:</span>
                            <span class="info-value">${result.lines}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Chunk ID:</span>
                            <span class="info-value code">${result.chunk_id}</span>
                        </div>
                    </div>
                </div>

                <div class="detail-section">
                    <h4>Score & Explanation</h4>
                    <div class="detail-info">
                        <div class="info-row">
                            <span class="info-label">Score:</span>
                            <span class="info-value">${result.score.toFixed(2)}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Matched Terms:</span>
                            <span class="info-value">${matchedTerms.join(', ') || '-'}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Term Frequencies:</span>
                            <span class="info-value">${JSON.stringify(termFreqs)}</span>
                        </div>
                        ${explanation.document_boost ? `
                        <div class="info-row">
                            <span class="info-label">Document Boost:</span>
                            <span class="info-value">${explanation.document_boost.toFixed(2)}</span>
                        </div>
                        ` : ''}
                        ${explanation.recency_boost ? `
                        <div class="info-row">
                            <span class="info-label">Recency Boost:</span>
                            <span class="info-value">${explanation.recency_boost.toFixed(2)}</span>
                        </div>
                        ` : ''}
                    </div>
                </div>

                <div class="detail-section">
                    <h4>Content</h4>
                    <div class="content-preview">
                        <pre>${this.escapeHtml(result.content)}</pre>
                    </div>
                </div>

                <div class="detail-actions">
                    <button class="btn-secondary" id="kb-copy-context">
                        <span class="icon"><span class="material-icons md-18">content_copy</span></span>
                        Copy Context (Markdown)
                    </button>
                </div>
            </div>
        `;

        // Copy context button
        const copyBtn = drawerBody.querySelector('#kb-copy-context');
        if (copyBtn) {
            copyBtn.addEventListener('click', () => {
                this.copyContextToClipboard(result);
            });
        }

        drawer.classList.remove('hidden');
    }

    closeDrawer() {
        const drawer = this.container.querySelector('#kb-detail-drawer');
        drawer.classList.add('hidden');
    }

    copyContextToClipboard(result) {
        const markdown = `## ${result.heading || 'Content'} (${result.path}#${result.lines})

\`\`\`
${result.content}
\`\`\`

---
**Source:** ${result.path}
**Lines:** ${result.lines}
**Chunk ID:** ${result.chunk_id}
**Score:** ${result.score.toFixed(2)}
`;

        navigator.clipboard.writeText(markdown).then(() => {
            Toast.success('Context copied to clipboard!');
        }).catch(err => {
            console.error('Copy failed:', err);
            Toast.error('Failed to copy to clipboard');
        });
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    destroy() {
        // Clean up components
        if (this.filterBar && typeof this.filterBar.destroy === 'function') {
            this.filterBar.destroy();
        }
        if (this.dataTable && typeof this.dataTable.destroy === 'function') {
            this.dataTable.destroy();
        }
        // Clear container
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}

// Export for use in main.js
window.KnowledgePlaygroundView = KnowledgePlaygroundView;
