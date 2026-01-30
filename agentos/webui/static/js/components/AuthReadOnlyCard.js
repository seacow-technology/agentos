/**
 * AuthReadOnlyCard - Authentication Profile Display Component (Read-Only)
 *
 * Part of Agent-View-Answers delivery (Wave2-E2)
 *
 * Features:
 * - Read-only display of auth profiles
 * - Sanitized data display (no credentials exposed)
 * - Validate connection functionality
 * - CLI-only notice for write operations
 *
 * API Coverage:
 * - GET /api/auth/profiles
 * - GET /api/auth/profiles/{id}
 * - POST /api/auth/profiles/{id}/validate
 *
 * NOTE: Add/Remove/Update operations are CLI-ONLY
 */

class AuthReadOnlyCard {
    constructor(container) {
        this.container = container;
        this.profiles = [];
        this.validationResults = new Map(); // Store validation results per profile

        this.init();
    }

    init() {
        this.render();
        this.loadProfiles();
    }

    render() {
        this.container.innerHTML = `
            <div class="auth-profiles-view">
                <!-- CLI-Only Banner -->
                <div class="cli-only-banner">
                    <span class="material-icons md-18">info</span>
                    <div class="cli-only-banner-content">
                        <h4>push_pin Authentication Configuration (Read-Only)</h4>
                        <p>
                            To add or remove auth profiles, use the CLI. WebUI provides read-only access for security reasons.
                        </p>
                        <div class="cli-code-snippet">$ agentos auth add --type ssh --key ~/.ssh/id_rsa</div>
                        <div class="cli-code-snippet">$ agentos auth add --type pat --token ghp_xxx --scopes repo,workflow</div>
                        <a href="#" class="cli-docs-link" id="auth-docs-link">View CLI Documentation →</a>
                    </div>
                </div>

                <!-- Filter Bar -->
                <div class="auth-filter-bar">
                    <select id="auth-type-filter" class="form-control">
                        <option value="">All Types</option>
                        <option value="ssh">SSH</option>
                        <option value="pat">Personal Access Token</option>
                        <option value="netrc">netrc</option>
                    </select>
                    <select id="auth-status-filter" class="form-control">
                        <option value="">All Status</option>
                        <option value="valid">Valid</option>
                        <option value="invalid">Invalid</option>
                        <option value="untested">Untested</option>
                    </select>
                    <input
                        type="text"
                        id="auth-host-filter"
                        placeholder="Filter by host..."
                        class="form-control"
                    />
                    <button class="btn-refresh" id="auth-refresh">
                        <span class="material-icons md-18">refresh</span> Refresh
                    </button>
                </div>

                <!-- Profiles Grid -->
                <div id="auth-profiles-container" class="auth-profiles-grid">
                    <div class="text-center py-8 text-gray-500">
                        Loading authentication profiles...
                    </div>
                </div>
            </div>
        `;

        this.setupEventListeners();
    }

    setupEventListeners() {
        // Refresh button
        const refreshBtn = this.container.querySelector('#auth-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadProfiles(true));
        }

        // Filters
        const typeFilter = this.container.querySelector('#auth-type-filter');
        const statusFilter = this.container.querySelector('#auth-status-filter');
        const hostFilter = this.container.querySelector('#auth-host-filter');

        if (typeFilter) {
            typeFilter.addEventListener('change', () => this.filterProfiles());
        }
        if (statusFilter) {
            statusFilter.addEventListener('change', () => this.filterProfiles());
        }
        if (hostFilter) {
            hostFilter.addEventListener('input', () => this.filterProfiles());
        }

        // Docs link
        const docsLink = this.container.querySelector('#auth-docs-link');
        if (docsLink) {
            docsLink.addEventListener('click', (e) => {
                e.preventDefault();
                window.open('https://docs.agentos.dev/cli/auth', '_blank');
            });
        }
    }

    async loadProfiles(forceRefresh = false) {
        try {
            const profilesContainer = this.container.querySelector('#auth-profiles-container');
            if (!profilesContainer) return;

            profilesContainer.innerHTML = '<div class="text-center py-8 text-gray-500">Loading authentication profiles...</div>';

            const response = await apiClient.get('/api/auth/profiles');

            if (!response.ok) {
                throw new Error(response.error || 'Failed to load auth profiles');
            }

            this.profiles = response.data || [];
            this.renderProfiles();

            if (forceRefresh && window.showToast) {
                window.showToast(`Loaded ${this.profiles.length} auth profiles`, 'success', 1500);
            }

        } catch (error) {
            console.error('Failed to load auth profiles:', error);

            const profilesContainer = this.container.querySelector('#auth-profiles-container');
            if (profilesContainer) {
                profilesContainer.innerHTML = `
                    <div class="text-center py-8 text-red-600">
                        <p>Failed to load auth profiles</p>
                        <p class="text-sm mt-2">${error.message}</p>
                    </div>
                `;
            }

            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    filterProfiles() {
        const typeValue = this.container.querySelector('#auth-type-filter')?.value || '';
        const statusValue = this.container.querySelector('#auth-status-filter')?.value || '';
        const hostValue = this.container.querySelector('#auth-host-filter')?.value?.toLowerCase() || '';

        let filteredProfiles = [...this.profiles];

        if (typeValue) {
            filteredProfiles = filteredProfiles.filter(p => p.type === typeValue);
        }

        if (statusValue) {
            filteredProfiles = filteredProfiles.filter(p => p.status === statusValue);
        }

        if (hostValue) {
            filteredProfiles = filteredProfiles.filter(p =>
                (p.host || '').toLowerCase().includes(hostValue)
            );
        }

        this.renderProfiles(filteredProfiles);
    }

    renderProfiles(profiles = this.profiles) {
        const profilesContainer = this.container.querySelector('#auth-profiles-container');
        if (!profilesContainer) return;

        if (profiles.length === 0) {
            profilesContainer.innerHTML = `
                <div class="empty-state-auth">
                    <span class="material-icons md-18">lock</span>
                    <h3>No authentication profiles configured</h3>
                    <p>Use the CLI to add your first auth profile.</p>
                    <div class="cli-code-snippet">$ agentos auth add --type ssh --key ~/.ssh/id_rsa</div>
                    <p class="text-xs text-gray-500 mt-2">
                        SSH keys, Personal Access Tokens, and netrc configurations can be added via CLI.
                    </p>
                </div>
            `;
            return;
        }

        profilesContainer.innerHTML = profiles.map(profile => this.renderProfileCard(profile)).join('');

        // Setup card event listeners
        profiles.forEach(profile => {
            const validateBtn = profilesContainer.querySelector(`#validate-${profile.id}`);
            if (validateBtn) {
                validateBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.validateProfile(profile.id);
                });
            }
        });
    }

    renderProfileCard(profile) {
        const metadata = profile.metadata || {};
        const validationResult = this.validationResults.get(profile.id);

        return `
            <div class="auth-profile-card">
                <div class="auth-profile-header">
                    <div class="auth-profile-type">
                        <span class="auth-type-badge ${profile.type}">
                            ${profile.type.toUpperCase()}
                        </span>
                    </div>
                    <span class="auth-status-badge ${profile.status}">
                        ${this.getStatusIcon(profile.status)} ${profile.status}
                    </span>
                </div>

                <div class="auth-profile-host">
                    <span class="material-icons md-18">cloud</span>
                    ${this.escapeHtml(profile.host || 'Global')}
                </div>

                <!-- Sanitized Metadata -->
                <div class="auth-metadata">
                    ${this.renderMetadata(profile)}
                </div>

                <!-- Validation Result (if exists) -->
                ${validationResult ? this.renderValidationResult(validationResult) : ''}

                <!-- Actions -->
                <div class="auth-profile-actions">
                    <button class="btn-sm btn-validate" id="validate-${profile.id}">
                        <span class="material-icons md-16">check_circle</span> Validate
                    </button>

                    <!-- Disabled Edit/Delete buttons with tooltip -->
                    <div class="auth-action-tooltip">
                        <button class="btn-sm btn-disabled" disabled>
                            <span class="material-icons md-16">edit</span> Edit
                        </button>
                        <span class="tooltip-text">Use CLI to modify</span>
                    </div>

                    <div class="auth-action-tooltip">
                        <button class="btn-sm btn-disabled" disabled>
                            <span class="material-icons md-16">delete</span> Delete
                        </button>
                        <span class="tooltip-text">Use CLI to remove</span>
                    </div>
                </div>

                <!-- CLI Hint -->
                <p class="text-xs text-gray-500 mt-2">
                    lightbulb To modify: <code class="text-xs bg-gray-100 px-1 rounded">agentos auth update ${profile.id}</code>
                </p>
            </div>
        `;
    }

    renderMetadata(profile) {
        const metadata = profile.metadata || {};
        const type = profile.type;

        if (type === 'ssh') {
            return `
                <div class="auth-metadata-item">
                    <span class="auth-metadata-label">Fingerprint</span>
                    <span class="auth-metadata-value fingerprint-display">
                        ${this.escapeHtml(metadata.fingerprint || 'N/A')}
                    </span>
                </div>
                ${metadata.key_path ? `
                    <div class="auth-metadata-item">
                        <span class="auth-metadata-label">Key Path</span>
                        <span class="auth-metadata-value">${this.escapeHtml(metadata.key_path)}</span>
                    </div>
                ` : ''}
                ${metadata.key_type ? `
                    <div class="auth-metadata-item">
                        <span class="auth-metadata-label">Key Type</span>
                        <span class="auth-metadata-value">${this.escapeHtml(metadata.key_type)}</span>
                    </div>
                ` : ''}
            `;
        } else if (type === 'pat') {
            return `
                <div class="auth-metadata-item">
                    <span class="auth-metadata-label">Token</span>
                    <span class="auth-metadata-value masked">
                        ${this.escapeHtml(metadata.token_prefix || '****')}
                    </span>
                </div>
                ${metadata.scopes && metadata.scopes.length > 0 ? `
                    <div class="auth-metadata-item" style="align-items: start;">
                        <span class="auth-metadata-label">Scopes</span>
                        <div class="auth-scopes">
                            ${metadata.scopes.map(scope => `
                                <span class="auth-scope-badge">${this.escapeHtml(scope)}</span>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
                ${metadata.expires_at ? `
                    <div class="auth-metadata-item">
                        <span class="auth-metadata-label">Expires</span>
                        <span class="auth-metadata-value">${new Date(metadata.expires_at).toLocaleDateString()}</span>
                    </div>
                ` : ''}
            `;
        } else if (type === 'netrc') {
            return `
                <div class="auth-metadata-item">
                    <span class="auth-metadata-label">Machine</span>
                    <span class="auth-metadata-value">${this.escapeHtml(metadata.machine || 'N/A')}</span>
                </div>
                ${metadata.login ? `
                    <div class="auth-metadata-item">
                        <span class="auth-metadata-label">Login</span>
                        <span class="auth-metadata-value">${this.escapeHtml(metadata.login)}</span>
                    </div>
                ` : ''}
                <div class="auth-metadata-item">
                    <span class="auth-metadata-label">Password</span>
                    <span class="auth-metadata-value masked">••••••••</span>
                </div>
            `;
        }

        return '<p class="text-xs text-gray-500">No metadata available</p>';
    }

    renderValidationResult(result) {
        const isSuccess = result.valid;
        const cssClass = isSuccess ? 'success' : 'error';
        const icon = isSuccess ? 'check_circle' : 'error';

        return `
            <div class="validation-result ${cssClass}">
                <span class="material-icons">${icon}</span>
                <div class="validation-result-content">
                    <p class="validation-result-message">${this.escapeHtml(result.message)}</p>
                    <p class="validation-result-timestamp">
                        Tested: ${new Date(result.tested_at).toLocaleString()}
                    </p>
                </div>
            </div>
        `;
    }

    async validateProfile(profileId) {
        try {
            if (window.showToast) {
                window.showToast('Testing authentication...', 'info', 1000);
            }

            const response = await apiClient.post(`/api/auth/profiles/${profileId}/validate`, {});

            if (!response.ok) {
                throw new Error(response.error || 'Validation failed');
            }

            const result = response.data;

            // Store validation result
            this.validationResults.set(profileId, result);

            // Update profile status in memory
            const profile = this.profiles.find(p => p.id === profileId);
            if (profile) {
                profile.status = result.valid ? 'valid' : 'invalid';
                profile.last_validated = result.tested_at;
            }

            // Re-render profiles to show updated status
            this.renderProfiles();

            if (window.showToast) {
                const message = result.valid
                    ? '<span class="material-icons md-18">check</span> Authentication valid'
                    : '<span class="material-icons md-18">cancel</span> Authentication failed';
                window.showToast(message, result.valid ? 'success' : 'error');
            }

        } catch (error) {
            console.error('Failed to validate profile:', error);

            if (window.showToast) {
                window.showToast(`Validation error: ${error.message}`, 'error');
            }
        }
    }

    getStatusIcon(status) {
        switch (status) {
            case 'valid':
                return '<span class="material-icons md-18">check</span>';
            case 'invalid':
                return '<span class="material-icons md-18">cancel</span>';
            case 'untested':
                return '<span class="material-icons md-18">radio_button_unchecked</span>';
            default:
                return '?';
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    destroy() {
        // Cleanup
        this.container.innerHTML = '';
        this.validationResults.clear();
    }
}


/**
 * AuthProfilesView - Standalone view for auth profiles
 * Can be used as a full-page view in the navigation
 */
class AuthProfilesView {
    constructor(container) {
        this.container = container;
        this.authCard = null;

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="auth-profiles-view">
                <div class="view-header">
                    <div>
                        <h2>Authentication Profiles</h2>
                        <p class="text-sm text-gray-600 mt-1">
                            Read-only view of Git authentication configurations
                        </p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-secondary" id="open-cli-docs">
                            <span class="material-icons md-18">help_outline</span> CLI Documentation
                        </button>
                    </div>
                </div>

                <div id="auth-card-container"></div>
            </div>
        `;

        // Setup CLI docs button
        const docsBtn = this.container.querySelector('#open-cli-docs');
        if (docsBtn) {
            docsBtn.addEventListener('click', () => {
                window.open('https://docs.agentos.dev/cli/auth', '_blank');
            });
        }

        // Initialize AuthReadOnlyCard component
        const cardContainer = this.container.querySelector('#auth-card-container');
        if (cardContainer) {
            this.authCard = new AuthReadOnlyCard(cardContainer);
        }
    }

    destroy() {
        if (this.authCard && this.authCard.destroy) {
            this.authCard.destroy();
        }
        this.container.innerHTML = '';
    }
}
