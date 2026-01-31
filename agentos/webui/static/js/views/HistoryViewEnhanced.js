/**
 * HistoryViewEnhanced - Command History UI with UX Improvements
 *
 * Enhancements:
 * - M-11: View state management (filters, scroll position)
 * - M-12: Virtual scrolling for performance
 * - M-13: Unified error handling with retry
 * - M-14: Form validation for filters
 *
 * v0.3.2 - M-11 to M-20 UX Improvements
 */

class HistoryViewEnhanced {
    constructor(container) {
        this.container = container;
        this.filterBar = null;
        this.virtualList = null;
        this.stateManager = null;
        this.currentFilters = {
            command_id: '',
            status: '',
            session_id: '',
            limit: 100
        };
        this.historyData = [];

        this.init();
    }

    /**
     * Initialize view
     */
    init() {
        // M-11: Setup state management
        this.stateManager = new ViewStateManager('history', {
            useUrlParams: true,
            maxAge: 3600000 // 1 hour
        });

        // Restore previous state if available
        const savedState = this.stateManager.restoreState();
        if (savedState.filters) {
            this.currentFilters = { ...this.currentFilters, ...savedState.filters };
        }

        this.render();
        this.setupEventListeners();
        this.loadHistory();
    }

    /**
     * Render view
     */
    render() {
        this.container.innerHTML = `
            <div class="history-view">
                <div class="view-header">
                    <div class="header-title">
                        <h1>Command History</h1>
                        <p class="text-sm text-gray-600 mt-1">Browse command execution history</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="history-refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                        <button class="btn-secondary" id="history-clear-filters">
                            <span class="icon"><span class="material-icons md-18">clear_all</span></span> Clear Filters
                        </button>
                    </div>
                </div>

                <div class="filter-section" id="history-filter">
                    <form id="history-filter-form" class="filter-form">
                        <div class="form-field-wrapper">
                            <label for="filter-command-id">Command ID</label>
                            <input
                                type="text"
                                id="filter-command-id"
                                name="command_id"
                                placeholder="e.g., kb:search"
                                value="${this.currentFilters.command_id}"
                                class="form-input">
                        </div>
                        <div class="form-field-wrapper">
                            <label for="filter-status">Status</label>
                            <select id="filter-status" name="status" class="form-input">
                                <option value="">All</option>
                                <option value="success" ${this.currentFilters.status === 'success' ? 'selected' : ''}>Success</option>
                                <option value="failure" ${this.currentFilters.status === 'failure' ? 'selected' : ''}>Failure</option>
                                <option value="running" ${this.currentFilters.status === 'running' ? 'selected' : ''}>Running</option>
                            </select>
                        </div>
                        <div class="form-field-wrapper">
                            <label for="filter-session-id">Session ID</label>
                            <input
                                type="text"
                                id="filter-session-id"
                                name="session_id"
                                placeholder="Filter by session"
                                value="${this.currentFilters.session_id}"
                                class="form-input">
                        </div>
                    </form>
                </div>

                <!-- Virtual List Container -->
                <div class="table-section" style="position: relative; height: calc(100vh - 300px);">
                    <div id="history-list-container" style="height: 100%;"></div>
                </div>

                <!-- Detail Drawer -->
                <div id="history-drawer" class="drawer hidden">
                    <div class="drawer-overlay"></div>
                    <div class="drawer-content">
                        <div class="drawer-header">
                            <h3>Command Details</h3>
                            <button class="btn-close">×</button>
                        </div>
                        <div class="drawer-body" id="history-drawer-body"></div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Refresh button
        const refreshBtn = document.getElementById('history-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadHistory());
        }

        // Clear filters button
        const clearBtn = document.getElementById('history-clear-filters');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearFilters());
        }

        // M-14: Form validation for filters
        const filterForm = document.getElementById('history-filter-form');
        if (filterForm) {
            // Add input event listeners with debounce
            let debounceTimer;
            filterForm.addEventListener('input', (e) => {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {
                    this.handleFilterChange(e.target.name, e.target.value);
                }, 300);
            });
        }
    }

    /**
     * Handle filter change
     */
    handleFilterChange(fieldName, value) {
        this.currentFilters[fieldName] = value;

        // M-11: Save state
        this.stateManager.updateState({
            filters: this.currentFilters
        });

        // Reload with new filters
        this.loadHistory();
    }

    /**
     * Clear filters
     */
    clearFilters() {
        this.currentFilters = {
            command_id: '',
            status: '',
            session_id: '',
            limit: 100
        };

        // Update form inputs
        document.getElementById('filter-command-id').value = '';
        document.getElementById('filter-status').value = '';
        document.getElementById('filter-session-id').value = '';

        // M-11: Clear saved state
        this.stateManager.clearState();

        // Reload
        this.loadHistory();
    }

    /**
     * Load history data
     */
    async loadHistory() {
        try {
            // Build query string
            const params = new URLSearchParams();
            if (this.currentFilters.command_id) params.append('command_id', this.currentFilters.command_id);
            if (this.currentFilters.status) params.append('status', this.currentFilters.status);
            if (this.currentFilters.session_id) params.append('session_id', this.currentFilters.session_id);
            params.append('limit', this.currentFilters.limit);

            const url = `/api/history?${params.toString()}`;

            // M-13: Use ApiClient with unified error handling
            const response = await window.apiClient.get(url);

            if (!response.ok) {
                // M-13: Show error with retry
                window.Toast.showApiError(response, () => this.loadHistory());
                return;
            }

            this.historyData = response.data.history || [];

            // M-12: Render with virtual scrolling
            this.renderVirtualList();

            // M-11: Save scroll position if exists
            const savedState = this.stateManager.getCurrentState();
            if (savedState.scrollTop && this.virtualList) {
                setTimeout(() => {
                    this.virtualList.scrollContainer.scrollTop = savedState.scrollTop;
                }, 100);
            }

        } catch (error) {
            console.error('Failed to load history:', error);
            window.Toast.error('Failed to load command history', 5000);
        }
    }

    /**
     * M-12: Render with virtual scrolling
     */
    renderVirtualList() {
        const container = document.getElementById('history-list-container');
        if (!container) return;

        // Destroy existing virtual list
        if (this.virtualList) {
            this.virtualList.destroy();
        }

        // Create virtual list
        this.virtualList = new VirtualList({
            container: container,
            itemHeight: 80, // Fixed height per item
            overscan: 5,
            renderItem: (item, index) => this.renderHistoryItem(item, index),
            onScroll: (startIndex, endIndex) => {
                // M-11: Save scroll position
                const scrollTop = this.virtualList.scrollContainer.scrollTop;
                this.stateManager.updateState({ scrollTop });
            }
        });

        this.virtualList.setItems(this.historyData);

        // Show performance indicator
        if (this.historyData.length > 100) {
            this.showStateIndicator(`Virtual scrolling enabled (${this.historyData.length} items)`);
        }
    }

    /**
     * Render single history item
     */
    renderHistoryItem(item, index) {
        const statusClass = item.status === 'success' ? 'text-green-600' :
                           item.status === 'failure' ? 'text-red-600' :
                           'text-yellow-600';

        const timestamp = item.timestamp ? new Date(item.timestamp).toLocaleString() : 'N/A';

        return `
            <div class="history-item" data-index="${index}" onclick="historyView.showDetails(${index})">
                <div class="history-item-header">
                    <span class="history-command-id">${item.command_id || 'Unknown'}</span>
                    <span class="history-status ${statusClass}">
                        <span class="material-icons md-16">${item.status === 'success' ? 'check_circle' : item.status === 'failure' ? 'error' : 'pending'}</span>
                        ${item.status || 'Unknown'}
                    </span>
                </div>
                <div class="history-item-meta">
                    <span class="text-sm text-gray-500">${timestamp}</span>
                    ${item.session_id ? `<span class="text-sm text-gray-500">Session: ${item.session_id.substring(0, 8)}</span>` : ''}
                </div>
            </div>
        `;
    }

    /**
     * Show history item details
     */
    showDetails(index) {
        const item = this.historyData[index];
        if (!item) return;

        const drawer = document.getElementById('history-drawer');
        const drawerBody = document.getElementById('history-drawer-body');

        if (drawerBody) {
            drawerBody.innerHTML = `
                <div class="history-detail">
                    <h4>Command: ${item.command_id || 'Unknown'}</h4>
                    <div class="detail-section">
                        <strong>Status:</strong> ${item.status || 'Unknown'}
                    </div>
                    <div class="detail-section">
                        <strong>Timestamp:</strong> ${item.timestamp ? new Date(item.timestamp).toLocaleString() : 'N/A'}
                    </div>
                    ${item.session_id ? `
                    <div class="detail-section">
                        <strong>Session ID:</strong> ${item.session_id}
                    </div>
                    ` : ''}
                    ${item.result ? `
                    <div class="detail-section">
                        <strong>Result:</strong>
                        <pre>${JSON.stringify(item.result, null, 2)}</pre>
                    </div>
                    ` : ''}
                </div>
            `;
        }

        drawer.classList.remove('hidden');

        // Close button
        const closeBtn = drawer.querySelector('.btn-close');
        if (closeBtn) {
            closeBtn.onclick = () => drawer.classList.add('hidden');
        }

        // Close on overlay click
        const overlay = drawer.querySelector('.drawer-overlay');
        if (overlay) {
            overlay.onclick = () => drawer.classList.add('hidden');
        }
    }

    /**
     * M-11: Show state indicator
     */
    showStateIndicator(message) {
        let indicator = document.querySelector('.view-state-indicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.className = 'view-state-indicator';
            document.body.appendChild(indicator);
        }

        indicator.innerHTML = `<span class="material-icons">info</span> ${message}`;
        indicator.classList.add('show');

        setTimeout(() => {
            indicator.classList.remove('show');
        }, 3000);
    }

    /**
     * Cleanup when view is destroyed
     */
    destroy() {
        if (this.virtualList) {
            this.virtualList.destroy();
        }

        // M-11: Save final state
        if (this.virtualList) {
            const scrollTop = this.virtualList.scrollContainer.scrollTop;
            this.stateManager.updateState({ scrollTop });
        }
    }
}

// Export for use
if (typeof window !== 'undefined') {
    window.HistoryViewEnhanced = HistoryViewEnhanced;
}
