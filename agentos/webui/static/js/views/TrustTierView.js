/**
 * TrustTierView - Trust Tier Topology
 *
 * Features:
 * - Hierarchical display of trust tiers (T0-T3)
 * - Risk levels and default quotas per tier
 * - Admin token requirements
 * - Expandable capability lists
 * - Read-only interface
 *
 * PR-2: WebUI Views - Task 3
 */

class TrustTierView {
    constructor() {
        this.container = null;
        this.expandedTiers = new Set();
        this.highlightTier = null; // Tier to highlight on load
    }

    /**
     * Render the view
     * @param {HTMLElement} container - Container element
     * @param {string} highlightTier - Tier to highlight (optional)
     */
    async render(container, highlightTier = null) {
        this.container = container;
        this.highlightTier = highlightTier;

        container.innerHTML = `
            <div class="trust-tier-view">
                <div class="view-header">
                    <div>
                        <h1>Trust Tier Topology</h1>
                        <p class="text-sm text-gray-600 mt-1">Security and quota policies by trust tier</p>
                    </div>
                    <div class="header-actions">
                        <button id="btnExpandAll" class="btn-secondary">
                            <span class="icon"><span class="material-icons md-18">unfold_more</span></span> Expand All
                        </button>
                        <button id="btnCollapseAll" class="btn-secondary">
                            <span class="icon"><span class="material-icons md-18">unfold_less</span></span> Collapse All
                        </button>
                        <button id="btnRefreshTiers" class="btn-secondary">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                    </div>
                </div>

                <div class="table-section">
                    <div id="tierContent">
                        <div class="text-center py-8">
                            <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
                            <p class="mt-4 text-gray-600">Loading trust tier data...</p>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Attach event listeners
        document.getElementById('btnExpandAll')?.addEventListener('click', () => {
            this.expandAll();
        });

        document.getElementById('btnCollapseAll')?.addEventListener('click', () => {
            this.collapseAll();
        });

        document.getElementById('btnRefreshTiers')?.addEventListener('click', () => {
            this.loadTierData();
        });

        // Load data
        await this.loadTierData();
    }

    /**
     * Load trust tier data from API
     */
    async loadTierData() {
        const contentDiv = document.getElementById('tierContent');
        if (!contentDiv) return;

        try {
            const response = await fetch('/api/governance/trust-tiers');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            this.renderTierContent(contentDiv, data.tiers);

            // Auto-expand highlighted tier
            if (this.highlightTier) {
                this.expandedTiers.add(this.highlightTier);
                const tierCard = document.getElementById(`tier-${this.highlightTier}`);
                if (tierCard) {
                    tierCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    tierCard.classList.add('tier-highlighted');
                }
            }
        } catch (error) {
            console.error('Failed to load trust tier data:', error);
            this.renderError(contentDiv, error);
        }
    }

    /**
     * Render trust tier content
     * @param {HTMLElement} container - Content container
     * @param {Array} tiers - Trust tier data array
     */
    renderTierContent(container, tiers) {
        container.innerHTML = `
            <div class="trust-tier-hierarchy">
                ${tiers.map(tier => this.renderTierCard(tier)).join('')}
            </div>
        `;

        // Attach toggle listeners
        tiers.forEach(tier => {
            const toggleBtn = document.getElementById(`toggle-${tier.id}`);
            if (toggleBtn) {
                toggleBtn.addEventListener('click', () => {
                    this.toggleTier(tier.id);
                });
            }
        });
    }

    /**
     * Render a single trust tier card
     * @param {Object} tier - Tier data
     * @returns {string} HTML string
     */
    renderTierCard(tier) {
        const isExpanded = this.expandedTiers.has(tier.tier);
        const riskColorMap = {
            'LOW': 'success',
            'MED': 'info',
            'HIGH': 'warning',
            'CRITICAL': 'danger'
        };
        const riskColor = riskColorMap[tier.default_policy.risk_level] || 'info';

        return `
            <div class="tier-card tier-${tier.tier.toLowerCase()}" id="tier-${tier.tier}">
                <div class="tier-card-header" id="toggle-${tier.tier}">
                    <div class="tier-card-title">
                        <span class="tier-icon material-icons md-24">
                            ${isExpanded ? 'expand_more' : 'chevron_right'}
                        </span>
                        <div>
                            <h3>${tier.name}</h3>
                            <span class="tier-subtitle">${tier.count} capabilities</span>
                        </div>
                    </div>
                    <div class="tier-card-badges">
                        <span class="risk-badge risk-${riskColor}">${tier.default_policy.risk_level}</span>
                    </div>
                </div>

                <div class="tier-card-body ${isExpanded ? 'expanded' : 'collapsed'}">
                    <div class="tier-info-grid">
                        <div class="tier-info-item">
                            <label>Default Quota</label>
                            <span class="info-value">${tier.default_policy.default_quota_profile.calls_per_minute} calls/min</span>
                        </div>
                        <div class="tier-info-item">
                            <label>Admin Token Required</label>
                            <span class="info-value">
                                ${tier.default_policy.requires_admin_token
                                    ? '<span class="status-badge status-warning">Yes</span>'
                                    : '<span class="status-badge status-ok">No</span>'
                                }
                            </span>
                        </div>
                        <div class="tier-info-item">
                            <label>Risk Level</label>
                            <span class="info-value">
                                <span class="risk-badge risk-${riskColor}">${tier.default_policy.risk_level}</span>
                            </span>
                        </div>
                    </div>

                    <div class="tier-capabilities">
                        <h4 class="capabilities-title">Capabilities</h4>
                        ${tier.capabilities.length > 0
                            ? `<div class="capabilities-list">
                                ${tier.capabilities.map(capId => this.renderCapabilityItem(capId)).join('')}
                               </div>`
                            : '<p class="text-muted">No capabilities in this tier</p>'
                        }
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render a single capability item
     * @param {string} capabilityId - Capability ID
     * @returns {string} HTML string
     */
    renderCapabilityItem(capabilityId) {
        return `
            <div class="capability-item">
                <button class="capability-link" onclick="window.loadView('capability-detail', '${capabilityId}')">
                    <span class="capability-name">${capabilityId}</span>
                </button>
            </div>
        `;
    }

    /**
     * Toggle tier expansion
     * @param {string} tierId - Tier ID to toggle
     */
    toggleTier(tierId) {
        if (this.expandedTiers.has(tierId)) {
            this.expandedTiers.delete(tierId);
        } else {
            this.expandedTiers.add(tierId);
        }
        this.loadTierData(); // Re-render
    }

    /**
     * Expand all tiers
     */
    expandAll() {
        this.expandedTiers = new Set(['T0', 'T1', 'T2', 'T3']);
        this.loadTierData();
    }

    /**
     * Collapse all tiers
     */
    collapseAll() {
        this.expandedTiers.clear();
        this.loadTierData();
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
                <h3>Failed to Load Trust Tier Data</h3>
                <p>${error.message}</p>
                <button class="btn-primary" onclick="window.loadView('governance-trust-tiers')">
                    Retry
                </button>
            </div>
        `;
    }

    /**
     * Destroy the view
     */
    destroy() {
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}

// Export to window
window.TrustTierView = TrustTierView;
