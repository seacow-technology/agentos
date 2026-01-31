/**
 * MarketplaceView - MCP Marketplace
 *
 * Displays MCP packages from the marketplace with:
 * - Card-based layout
 * - Search and filter
 * - Trust tier badges
 * - Connection status
 * - Quick package inspection
 *
 * PR-C: Marketplace WebUI (Frontend)
 */

class MarketplaceView {
    constructor() {
        this.container = null;
        this.packages = [];
        this.filteredPackages = [];
        this.searchTerm = '';
        this.filterStatus = 'all'; // all, connected, not-connected
    }

    /**
     * Render the view
     */
    async render(container) {
        this.container = container;

        container.innerHTML = `
            <div class="marketplace-container">
                <div class="marketplace-header">
                    <div>
                        <h1>MCP Marketplace</h1>
                        <p class="text-sm text-gray-600 mt-1">Discover and attach Model Context Protocol servers</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-secondary" id="btnRefreshMarketplace">
                            <span class="material-icons md-18">refresh</span> Refresh
                        </button>
                    </div>
                </div>

                <div class="marketplace-search">
                    <input
                        type="text"
                        id="marketplaceSearch"
                        placeholder="Search packages..."
                        class="search-input"
                    />
                    <select id="marketplaceFilter" class="filter-select">
                        <option value="all">All Packages</option>
                        <option value="connected">Connected</option>
                        <option value="not-connected">Not Connected</option>
                    </select>
                </div>

                <div id="packagesGrid" class="packages-grid">
                    <div class="text-center py-8">
                        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
                        <p class="mt-4 text-gray-600">Loading packages...</p>
                    </div>
                </div>
            </div>
        `;

        // Attach event listeners
        document.getElementById('btnRefreshMarketplace').addEventListener('click', () => this.loadPackages());
        document.getElementById('marketplaceSearch').addEventListener('input', (e) => this.handleSearch(e.target.value));
        document.getElementById('marketplaceFilter').addEventListener('change', (e) => this.handleFilter(e.target.value));

        // Load packages
        await this.loadPackages();
    }

    /**
     * Load packages from API
     */
    async loadPackages() {
        try {
            const response = await fetch('/api/mcp/marketplace/packages');
            if (!response.ok) {
                throw new Error('Failed to load packages');
            }

            const data = await response.json();
            this.packages = data.packages || [];
            this.filteredPackages = [...this.packages];
            this.renderPackages();

        } catch (error) {
            console.error('Failed to load packages:', error);
            this.renderError(error);
        }
    }

    /**
     * Handle search input
     */
    handleSearch(term) {
        this.searchTerm = term.toLowerCase();
        this.applyFilters();
    }

    /**
     * Handle filter change
     */
    handleFilter(status) {
        this.filterStatus = status;
        this.applyFilters();
    }

    /**
     * Apply search and filter
     */
    applyFilters() {
        this.filteredPackages = this.packages.filter(pkg => {
            // Apply search filter
            const matchesSearch = !this.searchTerm ||
                pkg.name.toLowerCase().includes(this.searchTerm) ||
                pkg.author.toLowerCase().includes(this.searchTerm) ||
                pkg.description.toLowerCase().includes(this.searchTerm);

            // Apply status filter
            const matchesStatus = this.filterStatus === 'all' ||
                (this.filterStatus === 'connected' && pkg.is_connected) ||
                (this.filterStatus === 'not-connected' && !pkg.is_connected);

            return matchesSearch && matchesStatus;
        });

        this.renderPackages();
    }

    /**
     * Render packages grid
     */
    renderPackages() {
        const grid = document.getElementById('packagesGrid');

        if (this.filteredPackages.length === 0) {
            grid.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">search_off</div>
                    <h3>No Packages Found</h3>
                    <p>Try adjusting your search or filter criteria</p>
                </div>
            `;
            return;
        }

        grid.innerHTML = this.filteredPackages.map(pkg => this.renderPackageCard(pkg)).join('');

        // Attach card click handlers
        this.filteredPackages.forEach(pkg => {
            const card = document.getElementById(`pkg-card-${this.sanitizeId(pkg.package_id)}`);
            if (card) {
                card.addEventListener('click', () => this.viewPackageDetail(pkg.package_id));
            }
        });
    }

    /**
     * Render a single package card
     */
    renderPackageCard(pkg) {
        const statusClass = pkg.is_connected ? 'connected' : 'not-connected';
        const statusIcon = pkg.is_connected ? 'check_circle' : 'radio_button_unchecked';
        const statusText = pkg.is_connected ? 'Connected' : 'Not Connected';

        const trustTierClass = this.getTrustTierClass(pkg.recommended_trust_tier);
        const trustTierLabel = this.getTrustTierLabel(pkg.recommended_trust_tier);

        return `
            <div class="package-card ${statusClass}" id="pkg-card-${this.sanitizeId(pkg.package_id)}">
                <div class="package-header">
                    <div>
                        <h3 class="package-name">${pkg.name}</h3>
                        <p class="package-author">${pkg.author}</p>
                    </div>
                    <span class="connection-status ${statusClass}">
                        <span class="material-icons md-16">${statusIcon}</span>
                        ${statusText}
                    </span>
                </div>

                <p class="package-description">${pkg.description}</p>

                <div class="package-meta">
                    <span class="package-tools-count">
                        <span class="material-icons md-16">build</span>
                        ${pkg.tools_count} tools
                    </span>
                    <span class="trust-tier-badge ${trustTierClass}">
                        ${trustTierLabel}
                    </span>
                </div>

                ${pkg.tags && pkg.tags.length > 0 ? `
                    <div class="package-tags">
                        ${pkg.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
                    </div>
                ` : ''}

                <div class="package-actions">
                    <button class="btn-detail">
                        View Details
                        <span class="material-icons md-16">arrow_forward</span>
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Sanitize package ID for use in HTML id attribute
     */
    sanitizeId(packageId) {
        return packageId.replace(/[^a-zA-Z0-9-_]/g, '-');
    }

    /**
     * Get trust tier CSS class
     */
    getTrustTierClass(tier) {
        const tierMap = {
            'T0': 'T0',
            'T1': 'T1',
            'T2': 'T2',
            'T3': 'T3'
        };
        return tierMap[tier] || 'T3';
    }

    /**
     * Get trust tier display label
     */
    getTrustTierLabel(tier) {
        const labelMap = {
            'T0': 'T0 - Local Extension',
            'T1': 'T1 - Local MCP',
            'T2': 'T2 - Remote MCP',
            'T3': 'T3 - Cloud MCP'
        };
        return labelMap[tier] || tier;
    }

    /**
     * Navigate to package detail view
     */
    viewPackageDetail(packageId) {
        // Navigate to detail view
        if (typeof loadView === 'function') {
            // Store package ID for detail view
            sessionStorage.setItem('mcp_package_id', packageId);
            loadView('mcp-package-detail');
        }
    }

    /**
     * Render error state
     */
    renderError(error) {
        const grid = document.getElementById('packagesGrid');
        grid.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">error</div>
                <h3>Failed to Load Packages</h3>
                <p>${error.message}</p>
                <button class="btn-primary" onclick="location.reload()">
                    Retry
                </button>
            </div>
        `;
    }

    /**
     * Cleanup
     */
    destroy() {
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}

// Export to window
window.MarketplaceView = MarketplaceView;
