/**
 * AgentCapabilityMatrixView - AgentOS v3 Agent × Capability Matrix
 *
 * Task #29: Display and edit agent capability grants
 *
 * Features:
 * - Matrix table: Agent (rows) × Capability (columns)
 * - Cell values: ✓ (allowed), ✗ (denied), ⚠ (escalation required)
 * - Click cell to grant/revoke capability
 * - Batch operations support
 * - Grant audit trail
 */

class AgentCapabilityMatrixView {
    constructor(container) {
        this.container = container;
        this.agents = [];
        this.capabilities = [];
        this.matrix = {};
        this.selectedCells = new Set();

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="agent-capability-matrix-view">
                <div class="view-header">
                    <div>
                        <h1>Agent Capability Matrix</h1>
                        <p class="text-sm text-gray-600 mt-1">View and manage capability grants for all agents</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="acm-refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                        <button class="btn-secondary" id="acm-batch" disabled>
                            <span class="icon"><span class="material-icons md-18">edit</span></span> Batch Edit
                        </button>
                    </div>
                </div>

                <!-- Legend -->
                <div class="matrix-legend">
                    <div class="legend-item">
                        <span class="cell-preview cell-allowed">✓</span>
                        <span>Granted</span>
                    </div>
                    <div class="legend-item">
                        <span class="cell-preview cell-denied">✗</span>
                        <span>Not Granted</span>
                    </div>
                    <div class="legend-item">
                        <span class="cell-preview cell-warning">⚠</span>
                        <span>Requires Escalation</span>
                    </div>
                </div>

                <!-- Matrix Container -->
                <div class="matrix-scroll-container">
                    <div class="matrix-container" id="acm-matrix">
                        <!-- Matrix will be rendered here -->
                    </div>
                </div>

                <!-- Details Panel -->
                <div class="details-panel" id="acm-details">
                    <div class="details-placeholder">
                        <span class="material-icons md-48">grid_on</span>
                        <p>Click on a cell to view grant details</p>
                    </div>
                </div>
            </div>
        `;

        this.setupEventListeners();
        this.loadMatrix();
    }

    setupEventListeners() {
        // Refresh button
        const refreshBtn = this.container.querySelector('#acm-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadMatrix());
        }

        // Batch edit button
        const batchBtn = this.container.querySelector('#acm-batch');
        if (batchBtn) {
            batchBtn.addEventListener('click', () => this.showBatchEditModal());
        }
    }

    async loadMatrix() {
        try {
            const response = await fetch('/api/capability/agents/matrix');
            const result = await response.json();

            if (result.ok && result.data) {
                this.agents = result.data.agents;
                this.capabilities = result.data.capabilities;
                this.matrix = result.data.matrix;
                this.renderMatrix();
            } else {
                this.renderError(result.error || 'Failed to load matrix');
            }
        } catch (error) {
            console.error('Failed to load matrix:', error);
            this.renderError('Failed to connect to API');
        }
    }

    renderMatrix() {
        const container = this.container.querySelector('#acm-matrix');
        if (!container) return;

        if (this.agents.length === 0 || this.capabilities.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <span class="material-icons md-48">grid_on</span>
                    <p>No agents or capabilities found</p>
                </div>
            `;
            return;
        }

        // Group capabilities by domain
        const capsByDomain = this.groupCapabilitiesByDomain();

        // Build matrix HTML
        let html = '<table class="matrix-table">';

        // Header row with domain grouping
        html += '<thead><tr><th class="agent-header">Agent</th>';
        for (const [domain, caps] of Object.entries(capsByDomain)) {
            html += `<th colspan="${caps.length}" class="domain-header domain-${domain}">${domain}</th>`;
        }
        html += '</tr><tr><th class="agent-header"></th>';
        for (const [domain, caps] of Object.entries(capsByDomain)) {
            caps.forEach(cap => {
                const shortName = cap.split('.').pop();
                html += `<th class="capability-header" title="${cap}">
                    <div class="cap-label">${shortName}</div>
                </th>`;
            });
        }
        html += '</tr></thead>';

        // Body rows
        html += '<tbody>';
        this.agents.forEach(agent => {
            html += `<tr><td class="agent-cell">${agent}</td>`;

            for (const [domain, caps] of Object.entries(capsByDomain)) {
                caps.forEach(cap => {
                    const grant = this.matrix[agent]?.[cap];
                    const cellClass = this.getCellClass(grant);
                    const cellSymbol = this.getCellSymbol(grant);
                    const cellId = `${agent}|${cap}`;

                    html += `<td class="matrix-cell ${cellClass}"
                                 data-agent="${agent}"
                                 data-capability="${cap}"
                                 data-cell-id="${cellId}"
                                 onclick="window.handleCellClick('${agent}', '${cap}')">
                        ${cellSymbol}
                    </td>`;
                });
            }

            html += '</tr>';
        });
        html += '</tbody>';
        html += '</table>';

        container.innerHTML = html;
    }

    groupCapabilitiesByDomain() {
        const grouped = {
            state: [],
            decision: [],
            action: [],
            governance: [],
            evidence: []
        };

        this.capabilities.forEach(cap => {
            const domain = cap.split('.')[0];
            if (grouped[domain]) {
                grouped[domain].push(cap);
            }
        });

        return grouped;
    }

    getCellClass(grant) {
        if (!grant) return 'cell-denied';
        if (grant.status === 'allowed') return 'cell-allowed';
        if (grant.status === 'escalation_required') return 'cell-warning';
        return 'cell-denied';
    }

    getCellSymbol(grant) {
        if (!grant) return '✗';
        if (grant.status === 'allowed') return '✓';
        if (grant.status === 'escalation_required') return '⚠';
        return '✗';
    }

    handleCellClick(agent, capability) {
        const grant = this.matrix[agent]?.[capability];

        if (grant && grant.status === 'allowed') {
            // Show revoke confirmation
            this.showRevokeConfirmation(agent, capability, grant);
        } else {
            // Show grant form
            this.showGrantForm(agent, capability);
        }
    }

    showGrantForm(agent, capability) {
        const detailsPanel = this.container.querySelector('#acm-details');
        if (!detailsPanel) return;

        detailsPanel.innerHTML = `
            <div class="grant-form">
                <h3>Grant Capability</h3>
                <div class="form-group">
                    <label>Agent:</label>
                    <input type="text" value="${agent}" readonly class="form-input">
                </div>
                <div class="form-group">
                    <label>Capability:</label>
                    <input type="text" value="${capability}" readonly class="form-input">
                </div>
                <div class="form-group">
                    <label>Granted By:</label>
                    <input type="text" id="grant-by" class="form-input" placeholder="user:admin" value="system">
                </div>
                <div class="form-group">
                    <label>Reason:</label>
                    <textarea id="grant-reason" class="form-textarea" placeholder="Why is this grant necessary?"></textarea>
                </div>
                <div class="form-group">
                    <label>Scope (optional):</label>
                    <input type="text" id="grant-scope" class="form-input" placeholder="project:proj-123">
                </div>
                <div class="form-actions">
                    <button class="btn-primary" onclick="window.confirmGrant('${agent}', '${capability}')">
                        Grant Capability
                    </button>
                    <button class="btn-secondary" onclick="window.cancelGrantForm()">
                        Cancel
                    </button>
                </div>
            </div>
        `;
    }

    showRevokeConfirmation(agent, capability, grant) {
        const detailsPanel = this.container.querySelector('#acm-details');
        if (!detailsPanel) return;

        detailsPanel.innerHTML = `
            <div class="revoke-form">
                <h3>Revoke Capability</h3>
                <div class="warning-box">
                    <span class="material-icons md-24">warning</span>
                    <p>Are you sure you want to revoke this capability?</p>
                </div>
                <div class="grant-details">
                    <div class="detail-row">
                        <strong>Agent:</strong> ${agent}
                    </div>
                    <div class="detail-row">
                        <strong>Capability:</strong> ${capability}
                    </div>
                    <div class="detail-row">
                        <strong>Granted By:</strong> ${grant.granted_by}
                    </div>
                    <div class="detail-row">
                        <strong>Granted At:</strong> ${grant.granted_at}
                    </div>
                    <div class="detail-row">
                        <strong>Reason:</strong> ${grant.reason}
                    </div>
                </div>
                <div class="form-group">
                    <label>Revoked By:</label>
                    <input type="text" id="revoke-by" class="form-input" placeholder="user:admin" value="system">
                </div>
                <div class="form-actions">
                    <button class="btn-danger" onclick="window.confirmRevoke('${agent}', '${capability}')">
                        Revoke Capability
                    </button>
                    <button class="btn-secondary" onclick="window.cancelRevokeForm()">
                        Cancel
                    </button>
                </div>
            </div>
        `;
    }

    async grantCapability(agent, capability, grantedBy, reason, scope) {
        try {
            const response = await fetch('/api/capability/grants', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    agent_id: agent,
                    capability_id: capability,
                    granted_by: grantedBy,
                    reason: reason,
                    scope: scope || null
                })
            });

            const result = await response.json();

            if (result.ok) {
                this.showSuccess('Capability granted successfully');
                this.loadMatrix(); // Reload matrix
            } else {
                this.showError(result.error || 'Failed to grant capability');
            }
        } catch (error) {
            console.error('Failed to grant capability:', error);
            this.showError('Failed to connect to API');
        }
    }

    async revokeCapability(agent, capability, revokedBy) {
        try {
            const response = await fetch(
                `/api/capability/grants/${encodeURIComponent(agent)}/${encodeURIComponent(capability)}?revoked_by=${encodeURIComponent(revokedBy)}`,
                { method: 'DELETE' }
            );

            const result = await response.json();

            if (result.ok) {
                this.showSuccess('Capability revoked successfully');
                this.loadMatrix(); // Reload matrix
            } else {
                this.showError(result.error || 'Failed to revoke capability');
            }
        } catch (error) {
            console.error('Failed to revoke capability:', error);
            this.showError('Failed to connect to API');
        }
    }

    showSuccess(message) {
        const detailsPanel = this.container.querySelector('#acm-details');
        if (detailsPanel) {
            detailsPanel.innerHTML = `
                <div class="success-message">
                    <span class="material-icons md-48">check_circle</span>
                    <p>${message}</p>
                </div>
            `;
            setTimeout(() => {
                detailsPanel.innerHTML = `
                    <div class="details-placeholder">
                        <span class="material-icons md-48">grid_on</span>
                        <p>Click on a cell to view grant details</p>
                    </div>
                `;
            }, 2000);
        }
    }

    showError(message) {
        const detailsPanel = this.container.querySelector('#acm-details');
        if (detailsPanel) {
            detailsPanel.innerHTML = `
                <div class="error-message">
                    <span class="material-icons md-48">error_outline</span>
                    <p>${message}</p>
                </div>
            `;
        }
    }

    renderError(message) {
        const container = this.container.querySelector('#acm-matrix');
        if (container) {
            container.innerHTML = `
                <div class="error-state">
                    <span class="material-icons md-48">error_outline</span>
                    <p>${message}</p>
                </div>
            `;
        }
    }

    showBatchEditModal() {
        alert('Batch edit functionality to be implemented');
    }

    destroy() {
        // Cleanup
    }
}

// Global functions for cell interactions
window.handleCellClick = function(agent, capability) {
    if (window.currentAgentCapabilityMatrixView) {
        window.currentAgentCapabilityMatrixView.handleCellClick(agent, capability);
    }
};

window.confirmGrant = function(agent, capability) {
    if (window.currentAgentCapabilityMatrixView) {
        const grantedBy = document.getElementById('grant-by')?.value || 'system';
        const reason = document.getElementById('grant-reason')?.value || 'No reason provided';
        const scope = document.getElementById('grant-scope')?.value || null;

        window.currentAgentCapabilityMatrixView.grantCapability(agent, capability, grantedBy, reason, scope);
    }
};

window.confirmRevoke = function(agent, capability) {
    if (window.currentAgentCapabilityMatrixView) {
        const revokedBy = document.getElementById('revoke-by')?.value || 'system';
        window.currentAgentCapabilityMatrixView.revokeCapability(agent, capability, revokedBy);
    }
};

window.cancelGrantForm = function() {
    if (window.currentAgentCapabilityMatrixView) {
        const detailsPanel = document.querySelector('#acm-details');
        if (detailsPanel) {
            detailsPanel.innerHTML = `
                <div class="details-placeholder">
                    <span class="material-icons md-48">grid_on</span>
                    <p>Click on a cell to view grant details</p>
                </div>
            `;
        }
    }
};

window.cancelRevokeForm = window.cancelGrantForm;

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AgentCapabilityMatrixView;
}
