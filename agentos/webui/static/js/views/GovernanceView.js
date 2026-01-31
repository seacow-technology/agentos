/**
 * GovernanceView - Governance Overview
 *
 * Features:
 * - Real-time governance overview
 * - Capabilities distribution by trust tier
 * - Quota status warnings
 * - Recent governance events
 * - Read-only interface (no modifications allowed)
 *
 * PR-2: WebUI Views - Task 1
 */

class GovernanceView {
    constructor() {
        this.container = null;
        this.refreshInterval = null;
        this.websocket = null;  // L-21: WebSocket connection
        this.searchQuery = '';  // L-22: Global search query
    }

    /**
     * Render the view
     * @param {HTMLElement} container - Container element
     */
    async render(container) {
        this.container = container;

        container.innerHTML = `
            <div class="governance-view">
                <div class="view-header">
                    <div>
                        <h1>Governance Overview</h1>
                        <p class="text-sm text-gray-600 mt-1">System-wide governance status and activity</p>
                    </div>
                    <div class="header-actions">
                        <div class="search-box" style="margin-right: 1rem;">
                            <input type="text" id="globalSearch" class="search-input"
                                   placeholder="Search governance data..."
                                   style="min-width: 250px;">
                            <span class="material-icons search-icon" style="position: absolute; right: 8px; top: 50%; transform: translateY(-50%); color: #9CA3AF;">search</span>
                        </div>
                        <button id="btnRefreshGovernance" class="btn-secondary">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                    </div>
                </div>

                <div class="table-section">
                    <div id="governanceContent">
                        <div class="text-center py-8">
                            <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
                            <p class="mt-4 text-gray-600">Loading governance data...</p>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Attach event listeners
        document.getElementById('btnRefreshGovernance')?.addEventListener('click', () => {
            this.loadGovernanceData();
        });

        // L-22: Global search listener
        const searchInput = document.getElementById('globalSearch');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.searchQuery = e.target.value.toLowerCase();
                this.applySearch();
            });
        }

        // Load data
        await this.loadGovernanceData();

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
                console.log('Governance WebSocket connected');
            };

            this.websocket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };

            this.websocket.onerror = (error) => {
                console.error('Governance WebSocket error:', error);
            };

            this.websocket.onclose = () => {
                console.log('Governance WebSocket disconnected');
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
            console.error('Failed to connect to governance WebSocket:', error);
        }
    }

    /**
     * L-21: Handle WebSocket messages
     * @param {Object} data - WebSocket message data
     */
    handleWebSocketMessage(data) {
        if (data.type === 'governance_snapshot') {
            // Initial snapshot received, update UI
            this.updateQuotaDisplay(data.data.quotas);
        } else if (data.type === 'quota_update') {
            // Single quota update
            this.updateSingleQuota(data.data);
        } else if (data.type === 'governance_event') {
            // New governance event
            this.addGovernanceEvent(data);
        }
    }

    /**
     * L-21: Update quota display from WebSocket data
     * @param {Array} quotas - Array of quota states
     */
    updateQuotaDisplay(quotas) {
        // Update the quota summary section with real-time data
        const quotaSummary = document.querySelector('.quota-summary');
        if (!quotaSummary) return;

        const warnings = quotas.filter(q => q.status === 'warning').length;
        const denied = quotas.filter(q => q.status === 'denied').length;

        // Update warning count
        const warningValue = quotaSummary.querySelector('.quota-stat:nth-child(1) .quota-value');
        if (warningValue) {
            warningValue.textContent = warnings;
            warningValue.className = `quota-value ${warnings > 0 ? 'text-warning' : ''}`;
        }

        // Update denied count
        const deniedValue = quotaSummary.querySelector('.quota-stat:nth-child(2) .quota-value');
        if (deniedValue) {
            deniedValue.textContent = denied;
            deniedValue.className = `quota-value ${denied > 0 ? 'text-danger' : ''}`;
        }
    }

    /**
     * L-21: Update a single quota in the UI
     * @param {Object} quotaData - Quota state data
     */
    updateSingleQuota(quotaData) {
        // Reload governance data to reflect changes
        // In a more sophisticated implementation, we would update just the affected quota
        this.loadGovernanceData();
    }

    /**
     * L-21: Add a new governance event to the events list
     * @param {Object} event - Governance event
     */
    addGovernanceEvent(event) {
        const eventsList = document.querySelector('.events-list');
        if (!eventsList) return;

        // Add event to the top of the list
        const eventHtml = this.renderEvent({
            timestamp: event.timestamp,
            event_type: event.event_type,
            message: event.data.message || 'Governance event',
            capability_id: event.data.capability_id
        });

        eventsList.insertAdjacentHTML('afterbegin', eventHtml);

        // Remove oldest event if more than 10
        const events = eventsList.querySelectorAll('.event-item');
        if (events.length > 10) {
            events[events.length - 1].remove();
        }
    }

    /**
     * L-22: Apply global search filter
     */
    applySearch() {
        if (!this.searchQuery) {
            // Clear search, show all
            this.clearSearchHighlights();
            return;
        }

        const searchableElements = document.querySelectorAll(
            '.governance-content .capability-tier-card, ' +
            '.governance-content .event-item, ' +
            '.governance-content .quota-stat'
        );

        searchableElements.forEach(element => {
            const text = element.textContent.toLowerCase();
            const matches = text.includes(this.searchQuery);

            if (matches) {
                element.style.display = '';
                this.highlightSearchText(element, this.searchQuery);
            } else {
                element.style.display = 'none';
            }
        });
    }

    /**
     * L-22: Highlight search text in element
     * @param {HTMLElement} element - Element to highlight
     * @param {string} query - Search query
     */
    highlightSearchText(element, query) {
        // Simple text highlighting
        const walker = document.createTreeWalker(
            element,
            NodeFilter.SHOW_TEXT,
            null,
            false
        );

        const nodesToReplace = [];
        let node;

        while (node = walker.nextNode()) {
            if (node.nodeValue.toLowerCase().includes(query)) {
                nodesToReplace.push(node);
            }
        }

        nodesToReplace.forEach(textNode => {
            const text = textNode.nodeValue;
            const lowerText = text.toLowerCase();
            const index = lowerText.indexOf(query);

            if (index !== -1) {
                const span = document.createElement('span');
                span.innerHTML = text.substring(0, index) +
                    '<mark style="background-color: #FEF3C7; padding: 0 2px;">' +
                    text.substring(index, index + query.length) +
                    '</mark>' +
                    text.substring(index + query.length);

                textNode.parentNode.replaceChild(span, textNode);
            }
        });
    }

    /**
     * L-22: Clear search highlights
     */
    clearSearchHighlights() {
        // Remove all highlights
        document.querySelectorAll('.governance-content mark').forEach(mark => {
            const text = mark.textContent;
            mark.parentNode.replaceChild(document.createTextNode(text), mark);
        });

        // Show all elements
        document.querySelectorAll('.governance-content [style*="display: none"]').forEach(el => {
            el.style.display = '';
        });
    }

    /**
     * Load governance summary data from API
     */
    async loadGovernanceData() {
        const contentDiv = document.getElementById('governanceContent');
        if (!contentDiv) return;

        try {
            const response = await fetch('/api/governance/summary');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            this.renderGovernanceContent(contentDiv, data);
        } catch (error) {
            console.error('Failed to load governance summary:', error);
            this.renderError(contentDiv, error);
        }
    }

    /**
     * Render governance content
     * @param {HTMLElement} container - Content container
     * @param {Object} data - Governance summary data
     */
    renderGovernanceContent(container, data) {
        const { capabilities, quota, recent_events } = data;

        container.innerHTML = `
            <div class="governance-content">
                <!-- Capabilities Summary -->
                <div class="governance-section">
                    <div class="section-header">
                        <h2 class="section-title">Capabilities Overview</h2>
                        <span class="section-badge">${capabilities.total} total</span>
                    </div>
                    <div class="capabilities-grid">
                        ${this.renderCapabilitiesByTier(capabilities.by_trust_tier)}
                    </div>
                </div>

                <!-- Quota Status -->
                <div class="governance-section">
                    <div class="section-header">
                        <h2 class="section-title">Quota Status</h2>
                        ${quota.warnings + quota.denied > 0 ?
                            `<span class="section-badge badge-warning">${quota.warnings + quota.denied} issues</span>` :
                            `<span class="section-badge badge-success">All OK</span>`
                        }
                    </div>
                    <div class="quota-summary">
                        <div class="quota-stat">
                            <span class="quota-label">Warnings</span>
                            <span class="quota-value ${quota.warnings > 0 ? 'text-warning' : ''}">${quota.warnings}</span>
                        </div>
                        <div class="quota-stat">
                            <span class="quota-label">Denied</span>
                            <span class="quota-value ${quota.denied > 0 ? 'text-danger' : ''}">${quota.denied}</span>
                        </div>
                        <div class="quota-actions">
                            <button class="btn-link" onclick="window.loadView('governance-quotas')">
                                View Details <span class="material-icons md-18">arrow_forward</span>
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Recent Events -->
                <div class="governance-section">
                    <div class="section-header">
                        <h2 class="section-title">Recent Events</h2>
                        <span class="section-badge">${recent_events.length} events</span>
                    </div>
                    <div class="events-list">
                        ${recent_events.length > 0
                            ? recent_events.map(event => this.renderEvent(event)).join('')
                            : '<div class="empty-state-small">No recent events</div>'
                        }
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render capabilities by trust tier
     * @param {Object} byTier - Capabilities grouped by trust tier
     * @returns {string} HTML string
     */
    renderCapabilitiesByTier(byTier) {
        const tiers = [
            { id: 'T0', name: 'T0 - Local Extension', color: 'success' },
            { id: 'T1', name: 'T1 - Local MCP', color: 'info' },
            { id: 'T2', name: 'T2 - Remote MCP', color: 'warning' },
            { id: 'T3', name: 'T3 - Cloud MCP', color: 'danger' }
        ];

        return tiers.map(tier => {
            const count = byTier[tier.id] || 0;
            return `
                <div class="capability-tier-card tier-${tier.color}" onclick="window.loadView('governance-trust-tiers', '${tier.id}')">
                    <div class="tier-header">
                        <span class="tier-label">${tier.name}</span>
                    </div>
                    <div class="tier-count">${count}</div>
                    <div class="tier-footer">
                        <span class="tier-action">View Details <span class="material-icons md-14">arrow_forward</span></span>
                    </div>
                </div>
            `;
        }).join('');
    }

    /**
     * Render a single event
     * @param {Object} event - Event data
     * @returns {string} HTML string
     */
    renderEvent(event) {
        const iconMap = {
            'quota_warning': 'warning',
            'quota_exceeded': 'block',
            'quota_denied': 'block',
            'policy_violation': 'shield',
            'gate_blocked': 'shield',
            'gate_passed': 'check_circle',
            'admin_token_required': 'lock'
        };

        const icon = iconMap[event.event_type] || 'info';
        const timeAgo = this.formatTimeAgo(event.timestamp);

        return `
            <div class="event-item event-${event.event_type}">
                <span class="event-icon material-icons md-18">${icon}</span>
                <div class="event-content">
                    <div class="event-message">${event.message}</div>
                    <div class="event-meta">
                        <span class="event-time">${timeAgo}</span>
                        ${event.capability_id ? `<span class="event-capability">${event.capability_id}</span>` : ''}
                    </div>
                </div>
            </div>
        `;
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
                <h3>Failed to Load Governance Data</h3>
                <p>${error.message}</p>
                <button class="btn-primary" onclick="window.loadView('governance')">
                    Retry
                </button>
            </div>
        `;
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
     * Destroy the view
     */
    destroy() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }

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

// Export to window
window.GovernanceView = GovernanceView;
