/**
 * ProvenanceView - Tool Invocation Provenance
 *
 * Features:
 * - Detailed provenance information for tool invocations
 * - Source tracking and trust tier
 * - Execution environment details
 * - Audit chain visualization
 * - Gate decision trail
 * - Read-only interface
 *
 * PR-2: WebUI Views - Task 4
 */

class ProvenanceView {
    constructor() {
        this.container = null;
        this.invocationId = null;
    }

    /**
     * Render the view
     * @param {HTMLElement} container - Container element
     * @param {string} invocationId - Invocation ID to display
     */
    async render(container, invocationId) {
        this.container = container;
        this.invocationId = invocationId;

        if (!invocationId) {
            this.renderNoInvocation(container);
            return;
        }

        container.innerHTML = `
            <div class="provenance-view">
                <div class="view-header">
                    <div>
                        <h1>Provenance Details</h1>
                        <p class="text-sm text-gray-600 mt-1">Tool invocation audit trail</p>
                    </div>
                    <div class="header-actions">
                        <button id="btnBackToAudit" class="btn-secondary">
                            <span class="icon"><span class="material-icons md-18">arrow_back</span></span> Back
                        </button>
                        <button id="btnRefreshProvenance" class="btn-secondary">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                    </div>
                </div>

                <div class="table-section">
                    <div id="provenanceContent">
                        <div class="text-center py-8">
                            <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
                            <p class="mt-4 text-gray-600">Loading provenance data...</p>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Attach event listeners
        document.getElementById('btnBackToAudit')?.addEventListener('click', () => {
            window.history.back();
        });

        document.getElementById('btnRefreshProvenance')?.addEventListener('click', () => {
            this.loadProvenanceData();
        });

        // Load data
        await this.loadProvenanceData();
    }

    /**
     * Load provenance data from API
     */
    async loadProvenanceData() {
        const contentDiv = document.getElementById('provenanceContent');
        if (!contentDiv) return;

        try {
            const response = await fetch(`/api/governance/provenance/${this.invocationId}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            this.renderProvenanceContent(contentDiv, data);
        } catch (error) {
            console.error('Failed to load provenance data:', error);
            this.renderError(contentDiv, error);
        }
    }

    /**
     * Render provenance content
     * @param {HTMLElement} container - Content container
     * @param {Object} data - Provenance data
     */
    renderProvenanceContent(container, data) {
        const { provenance, audit_chain } = data;

        container.innerHTML = `
            <div class="provenance-content">
                <!-- Invocation Header -->
                <div class="provenance-section">
                    <div class="provenance-header">
                        <div class="header-left">
                            <h2>Invocation: ${provenance.invocation_id}</h2>
                            <span class="timestamp">${new Date(provenance.timestamp).toLocaleString()}</span>
                        </div>
                        <div class="header-right">
                            <span class="trust-tier-badge tier-${provenance.trust_tier}">${provenance.trust_tier}</span>
                        </div>
                    </div>
                </div>

                <!-- Tool Information -->
                <div class="provenance-section">
                    <h3 class="section-title">Tool Information</h3>
                    <div class="info-grid">
                        <div class="info-item">
                            <label>Tool ID</label>
                            <span class="info-value">${provenance.tool_id}</span>
                        </div>
                        <div class="info-item">
                            <label>Capability ID</label>
                            <span class="info-value">${provenance.capability_id}</span>
                        </div>
                        <div class="info-item">
                            <label>Capability Type</label>
                            <span class="info-value">${provenance.capability_type}</span>
                        </div>
                        <div class="info-item">
                            <label>Source ID</label>
                            <span class="info-value">${provenance.source_id}</span>
                        </div>
                        <div class="info-item">
                            <label>Trust Tier</label>
                            <span class="info-value">
                                <span class="trust-tier-badge tier-${provenance.trust_tier}">
                                    ${provenance.trust_tier}
                                </span>
                            </span>
                        </div>
                    </div>
                </div>

                <!-- Execution Environment -->
                <div class="provenance-section">
                    <h3 class="section-title">Execution Environment</h3>
                    <div class="info-grid">
                        <div class="info-item">
                            <label>Hostname</label>
                            <span class="info-value">${provenance.execution_env.hostname || 'N/A'}</span>
                        </div>
                        <div class="info-item">
                            <label>Process ID</label>
                            <span class="info-value">${provenance.execution_env.pid || 'N/A'}</span>
                        </div>
                        <div class="info-item">
                            <label>Container ID</label>
                            <span class="info-value">${provenance.execution_env.container_id || '-'}</span>
                        </div>
                    </div>
                </div>

                <!-- Audit Chain -->
                <div class="provenance-section">
                    <h3 class="section-title">Audit Chain</h3>
                    <div class="audit-chain">
                        ${audit_chain.map(event => this.renderAuditEvent(event)).join('')}
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render a single audit event
     * @param {Object} event - Audit event data
     * @returns {string} HTML string
     */
    renderAuditEvent(event) {
        const iconMap = {
            'success': 'check_circle',
            'pending': 'schedule',
            'error': 'cancel'
        };

        const statusMap = {
            'success': 'success',
            'pending': 'muted',
            'error': 'danger'
        };

        const icon = iconMap[event.result] || 'help';
        const status = statusMap[event.result] || 'muted';

        return `
            <div class="audit-gate audit-gate-${status}">
                <span class="gate-icon material-icons md-24">${icon}</span>
                <div class="gate-content">
                    <div class="gate-header">
                        <span class="gate-name">${event.event_type}</span>
                        <span class="gate-result gate-result-${status}">${event.result}</span>
                    </div>
                    ${event.gate ? `
                        <div class="gate-message">Gate: ${event.gate}</div>
                    ` : ''}
                    <div class="gate-message">
                        <small>${new Date(event.timestamp).toLocaleString()}</small>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render no invocation state
     * @param {HTMLElement} container - Content container
     */
    renderNoInvocation(container) {
        container.innerHTML = `
            <div class="provenance-view">
                <div class="view-header">
                    <div>
                        <h1>Provenance Details</h1>
                        <p class="text-sm text-gray-600 mt-1">Tool invocation audit trail</p>
                    </div>
                </div>
                <div class="table-section">
                    <div class="empty-state">
                        <div class="empty-state-icon">info</div>
                        <h3>No Invocation Selected</h3>
                        <p>Provenance view requires an invocation ID.</p>
                        <p class="text-sm text-gray-600 mt-2">
                            Access this view from audit logs or tool invocation records.
                        </p>
                        <button class="btn-primary" onclick="window.loadView('audit')">
                            Go to Audit Logs
                        </button>
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
                <h3>Failed to Load Provenance Data</h3>
                <p>${error.message}</p>
                <button class="btn-primary" onclick="window.loadView('governance-provenance', '${this.invocationId}')">
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
window.ProvenanceView = ProvenanceView;
