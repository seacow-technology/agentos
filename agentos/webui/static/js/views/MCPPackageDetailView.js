/**
 * MCPPackageDetailView - MCP Package Details
 *
 * Displays detailed information about an MCP package:
 * - Package metadata
 * - Tools list (expandable)
 * - Governance preview (critical for security)
 * - Attach functionality with confirmation
 * - Post-attach guidance
 *
 * PR-C: Marketplace WebUI (Frontend)
 */

class MCPPackageDetailView {
    constructor() {
        this.container = null;
        this.packageId = null;
        this.package = null;
        this.governance = null;
        this.toolsExpanded = false;
        this.governanceExpanded = false;
    }

    /**
     * Render the view
     */
    async render(container) {
        this.container = container;

        // Get package ID from session storage
        this.packageId = sessionStorage.getItem('mcp_package_id');
        if (!this.packageId) {
            this.renderError(new Error('No package ID provided'));
            return;
        }

        // Show loading state
        container.innerHTML = `
            <div class="package-detail">
                <div class="text-center py-8">
                    <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
                    <p class="mt-4 text-gray-600">Loading package details...</p>
                </div>
            </div>
        `;

        try {
            // Load package details and governance preview in parallel
            const [pkgResponse, govResponse] = await Promise.all([
                fetch(`/api/mcp/marketplace/packages/${this.packageId}`),
                fetch(`/api/mcp/marketplace/governance-preview/${this.packageId}`)
            ]);

            if (!pkgResponse.ok) {
                throw new Error('Failed to load package details');
            }
            if (!govResponse.ok) {
                throw new Error('Failed to load governance preview');
            }

            const pkgData = await pkgResponse.json();
            const govData = await govResponse.json();

            this.package = pkgData.ok ? pkgData.data : pkgData;
            this.governance = govData.ok ? govData.data : govData;

            this.renderPackageDetail();

        } catch (error) {
            console.error('Failed to load package:', error);
            this.renderError(error);
        }
    }

    /**
     * Render package detail content
     */
    renderPackageDetail() {
        const pkg = this.package;
        const gov = this.governance;

        const statusClass = pkg.is_connected ? 'connected' : 'not-connected';
        const statusIcon = pkg.is_connected ? 'check_circle' : 'radio_button_unchecked';
        const statusText = pkg.is_connected ? 'Connected' : 'Not Connected';

        // Get trust tier label using helper method
        const trustTierLabel = this.getTrustTierLabel(gov.inferred_trust_tier);

        this.container.innerHTML = `
            <div class="package-detail">
                <!-- Back Button -->
                <a href="#" class="back-link" id="btnBackToMarketplace">
                    <span class="material-icons md-18">arrow_back</span>
                    Back to Marketplace
                </a>

                <!-- Package Header -->
                <div class="package-detail-header">
                    <div>
                        <h1>${pkg.name}</h1>
                        <p class="package-version">v${pkg.version}</p>
                    </div>
                    <span class="connection-status ${statusClass}">
                        <span class="material-icons">${statusIcon}</span>
                        ${statusText}
                    </span>
                </div>

                <!-- Package Metadata -->
                <div class="section">
                    <div class="package-info-grid">
                        <div class="info-item">
                            <span class="info-label">Author</span>
                            <span class="info-value">${pkg.author}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">License</span>
                            <span class="info-value">${pkg.license || 'N/A'}</span>
                        </div>
                        ${pkg.repository ? `
                            <div class="info-item">
                                <span class="info-label">Repository</span>
                                <a href="${pkg.repository}" target="_blank" class="info-link">
                                    ${pkg.repository}
                                    <span class="material-icons md-14">open_in_new</span>
                                </a>
                            </div>
                        ` : ''}
                    </div>

                    ${pkg.tags && pkg.tags.length > 0 ? `
                        <div class="package-tags" style="margin-top: 16px;">
                            ${pkg.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
                        </div>
                    ` : ''}

                    <div class="package-description-full" style="margin-top: 20px; line-height: 1.6; color: #374151;">
                        ${pkg.description}
                    </div>
                </div>

                <!-- Tools Section -->
                <div class="section">
                    <div class="section-title" id="toolsToggle" style="cursor: pointer; user-select: none;">
                        <span>Tools (${pkg.tools.length})</span>
                        <span class="material-icons">${this.toolsExpanded ? 'expand_less' : 'expand_more'}</span>
                    </div>
                    <div class="section-content" id="toolsContent" style="display: ${this.toolsExpanded ? 'block' : 'none'};">
                        ${pkg.tools.map(tool => this.renderTool(tool)).join('')}
                    </div>
                </div>

                <!-- Governance Preview Section (Critical!) -->
                <div class="section">
                    <div class="section-title" id="governanceToggle" style="cursor: pointer; user-select: none;">
                        <span>Governance Preview</span>
                        <span class="material-icons">${this.governanceExpanded ? 'expand_less' : 'expand_more'}</span>
                    </div>
                    <div class="governance-preview" id="governanceContent" style="display: ${this.governanceExpanded ? 'block' : 'none'};">
                        ${this.renderGovernancePreview(gov)}
                    </div>
                </div>

                <!-- Connection Status and Actions -->
                <div class="section">
                    ${pkg.is_connected ? this.renderConnectedState(pkg) : this.renderNotConnectedState(pkg)}
                </div>
            </div>
        `;

        // Attach event listeners
        this.attachEventListeners();
    }

    /**
     * Render a single tool
     */
    renderTool(tool) {
        return `
            <div class="tool-item">
                <div class="tool-name">${tool.name}</div>
                <div class="tool-description">${tool.description || 'No description available'}</div>
                ${tool.inputSchema ? `
                    <div class="tool-schema">
                        <strong>Input:</strong> ${this.formatSchema(tool.inputSchema)}
                    </div>
                ` : ''}
                ${tool.sideEffects && tool.sideEffects.length > 0 ? `
                    <div class="tool-side-effects">
                        ${tool.sideEffects.map(effect => `
                            <span class="side-effect-badge">${effect}</span>
                        `).join('')}
                    </div>
                ` : `
                    <div class="tool-side-effects">
                        <span class="side-effect-badge" style="background: #e8f5e9; color: #2e7d32;">No side effects</span>
                    </div>
                `}
            </div>
        `;
    }

    /**
     * Format JSON schema for display
     */
    formatSchema(schema) {
        if (typeof schema === 'object') {
            return JSON.stringify(schema, null, 2);
        }
        return schema;
    }

    /**
     * Get trust tier display label
     */
    getTrustTierLabel(tier) {
        const labels = {
            'T0': 'Local Extension',
            'T1': 'Local MCP',
            'T2': 'Remote MCP',
            'T3': 'Cloud MCP'
        };
        return labels[tier] || tier;
    }

    /**
     * Render governance preview
     */
    renderGovernancePreview(gov) {
        const tierLabel = this.getTrustTierLabel(gov.inferred_trust_tier);

        return `
            <div class="governance-item">
                <span class="governance-label">Trust Tier:</span>
                <span class="trust-tier-badge ${gov.inferred_trust_tier}">${gov.inferred_trust_tier} (${tierLabel})</span>
            </div>
            <div class="governance-item">
                <span class="governance-label">Risk Level:</span>
                <span class="risk-badge risk-${gov.inferred_risk_level.toLowerCase()}">${gov.inferred_risk_level}</span>
            </div>
            <div class="governance-item">
                <span class="governance-label">Default Quota:</span>
                <span>${gov.default_quota.calls_per_minute} calls/min, ${gov.default_quota.max_concurrent} concurrent</span>
            </div>
            <div class="governance-item">
                <span class="governance-label">Requires Admin Token:</span>
                <span>${gov.requires_admin_token_for && gov.requires_admin_token_for.length > 0 ? `Yes (${gov.requires_admin_token_for.join(', ')})` : 'No'}</span>
            </div>
            ${gov.gate_warnings && gov.gate_warnings.length > 0 ? `
                <div class="gate-warnings">
                    <strong style="display: block; margin-bottom: 8px;">Gate Warnings:</strong>
                    ${gov.gate_warnings.map(warning => `
                        <div class="warning-item">
                            <span class="material-icons md-16">warning</span>
                            ${warning}
                        </div>
                    `).join('')}
                </div>
            ` : ''}
        `;
    }

    /**
     * Render connected state
     */
    renderConnectedState(pkg) {
        return `
            <div class="success-message">
                <span class="material-icons">check_circle</span>
                <div>
                    <strong>MCP Already Connected</strong>
                    <p>This MCP server is already attached to your AgentOS instance.</p>
                </div>
            </div>
            <div class="next-steps">
                <h4>Manage MCP Server:</h4>
                <ol>
                    <li>View in Capabilities → MCP Servers</li>
                    <li>Configure settings and admin tokens</li>
                    <li>Monitor usage and governance</li>
                </ol>
                <button class="btn-secondary" onclick="loadView('capabilities')">
                    Go to Capabilities
                </button>
            </div>
        `;
    }

    /**
     * Render not connected state
     */
    renderNotConnectedState(pkg) {
        return `
            <div style="text-align: center; padding: 24px;">
                <h3 style="margin-bottom: 12px;">Ready to Attach?</h3>
                <p style="color: #6b7280; margin-bottom: 24px;">
                    This will add the MCP server to your AgentOS capabilities.
                </p>
                <button class="attach-button" id="btnAttach">
                    <span class="material-icons md-18">add_circle</span>
                    Attach to AgentOS
                </button>
            </div>
        `;
    }

    /**
     * Attach event listeners
     */
    attachEventListeners() {
        // Back button
        document.getElementById('btnBackToMarketplace')?.addEventListener('click', (e) => {
            e.preventDefault();
            if (typeof loadView === 'function') {
                loadView('marketplace');
            }
        });

        // Tools toggle
        document.getElementById('toolsToggle')?.addEventListener('click', () => {
            this.toolsExpanded = !this.toolsExpanded;
            document.getElementById('toolsContent').style.display = this.toolsExpanded ? 'block' : 'none';
            const icon = document.querySelector('#toolsToggle .material-icons');
            if (icon) {
                icon.textContent = this.toolsExpanded ? 'expand_less' : 'expand_more';
            }
        });

        // Governance toggle
        document.getElementById('governanceToggle')?.addEventListener('click', () => {
            this.governanceExpanded = !this.governanceExpanded;
            document.getElementById('governanceContent').style.display = this.governanceExpanded ? 'block' : 'none';
            const icon = document.querySelector('#governanceToggle .material-icons');
            if (icon) {
                icon.textContent = this.governanceExpanded ? 'expand_less' : 'expand_more';
            }
        });

        // Attach button
        document.getElementById('btnAttach')?.addEventListener('click', () => {
            this.showAttachConfirmation();
        });
    }

    /**
     * Show attach confirmation dialog
     */
    showAttachConfirmation() {
        const gov = this.governance;
        const pkg = this.package;

        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content" style="max-width: 600px;">
                <div class="modal-header">
                    <h2>Attach MCP to AgentOS</h2>
                    <button class="modal-close" id="btnCloseModal">&times;</button>
                </div>
                <div class="modal-body">
                    <div style="margin-bottom: 20px;">
                        <strong style="font-size: 16px;">${pkg.name}</strong>
                        <p style="color: #6b7280; font-size: 14px; margin-top: 4px;">by ${pkg.author}</p>
                    </div>

                    <div style="background: #f9fafb; padding: 16px; border-radius: 8px; margin-bottom: 20px;">
                        <h4 style="margin: 0 0 12px 0; font-size: 14px;">This will:</h4>
                        <ul style="margin: 0; padding-left: 20px; font-size: 14px; line-height: 1.8;">
                            <li>Add MCP to your AgentOS capabilities</li>
                            <li>Apply Trust Tier: <strong>${gov.inferred_trust_tier}</strong></li>
                            <li>Apply default quota profile</li>
                        </ul>
                    </div>

                    <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 16px; margin-bottom: 20px;">
                        <div style="display: flex; align-items: start; gap: 12px;">
                            <span class="material-icons" style="color: #856404;">warning</span>
                            <div style="font-size: 14px; color: #856404;">
                                <strong>Important:</strong> MCP will be <strong>DISABLED</strong> after attach
                            </div>
                        </div>
                    </div>

                    <div style="background: #e8f4fd; border-left: 4px solid #0288d1; padding: 16px; margin-bottom: 20px;">
                        <h4 style="margin: 0 0 8px 0; font-size: 14px; color: #01579b;">You will need to:</h4>
                        <ol style="margin: 0; padding-left: 20px; font-size: 14px; line-height: 1.8; color: #01579b;">
                            <li>Review in Capabilities → MCP</li>
                            <li>Enable using CLI: <code style="background: #fff; padding: 2px 6px; border-radius: 4px;">agentos mcp enable ${pkg.server_id || pkg.package_id.split('/').pop()}</code></li>
                            ${gov.requires_admin_token_for && gov.requires_admin_token_for.length > 0 ? '<li>Configure admin token if needed</li>' : ''}
                        </ol>
                    </div>

                    <div class="form-group" style="margin-bottom: 0;">
                        <label style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; display: block;">
                            Advanced: Override Trust Tier (Optional)
                        </label>
                        <select id="trustTierOverride" style="width: 100%; padding: 8px; border: 1px solid #d1d5db; border-radius: 6px;">
                            <option value="">Use Default (${gov.inferred_trust_tier})</option>
                            <option value="T0">T0 - Local Extension</option>
                            <option value="T1">T1 - Local MCP</option>
                            <option value="T2">T2 - Remote MCP</option>
                            <option value="T3">T3 - Cloud MCP</option>
                        </select>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn-secondary" id="btnCancelAttach">Cancel</button>
                    <button class="btn-primary" id="btnConfirmAttach">
                        <span class="material-icons md-18">add_circle</span>
                        Attach
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Close handlers
        const closeModal = () => modal.remove();
        document.getElementById('btnCloseModal').addEventListener('click', closeModal);
        document.getElementById('btnCancelAttach').addEventListener('click', closeModal);
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeModal();
        });

        // Confirm handler
        document.getElementById('btnConfirmAttach').addEventListener('click', async () => {
            const trustTierOverride = document.getElementById('trustTierOverride').value;
            closeModal();
            await this.attachPackage(trustTierOverride);
        });
    }

    /**
     * Attach package to AgentOS
     */
    async attachPackage(trustTierOverride) {
        try {
            // Show loading notification
            this.showNotification('Attaching MCP server...', 'info');

            const payload = {
                package_id: this.packageId
            };

            if (trustTierOverride) {
                payload.trust_tier_override = trustTierOverride;
            }

            // CSRF Fix: Use fetchWithCSRF for protected endpoint
            const response = await window.fetchWithCSRF('/api/mcp/marketplace/attach', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to attach MCP');
            }

            const result = await response.json();

            // Show success
            this.showNotification('MCP attached successfully!', 'success');

            // Update UI to show success state
            this.showAttachSuccess(result);

        } catch (error) {
            console.error('Failed to attach MCP:', error);
            this.showNotification(`Failed to attach: ${error.message}`, 'error');
        }
    }

    /**
     * Show attach success state
     */
    showAttachSuccess(result) {
        const pkg = this.package;
        const gov = this.governance;

        const successHtml = `
            <div class="success-message" style="margin-bottom: 24px;">
                <span class="material-icons" style="font-size: 48px; color: #10b981;">check_circle</span>
                <div>
                    <h2 style="margin: 0 0 8px 0;">MCP Attached Successfully</h2>
                    <p style="margin: 0; color: #6b7280;">Package: <strong>${pkg.name}</strong></p>
                    <p style="margin: 0; color: #6b7280;">Server ID: <strong>${result.server_id || pkg.server_id}</strong></p>
                    <p style="margin: 4px 0 0 0; color: #6b7280;">Status: <strong>Attached (Disabled)</strong></p>
                    <p style="margin: 0; color: #6b7280;">Trust Tier: <strong>${result.trust_tier || gov.inferred_trust_tier}</strong></p>
                </div>
            </div>

            <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 16px; margin-bottom: 24px;">
                <div style="display: flex; align-items: start; gap: 12px;">
                    <span class="material-icons" style="color: #856404;">warning</span>
                    <div style="font-size: 14px; color: #856404;">
                        <strong>Important:</strong> MCP is NOT enabled yet
                    </div>
                </div>
            </div>

            <div class="next-steps">
                <h3 style="margin-bottom: 16px;">Next Steps:</h3>
                <ol style="line-height: 2; font-size: 14px;">
                    <li>
                        <strong>Review in Capabilities → MCP</strong>
                        <br>
                        <button class="btn-secondary" onclick="loadView('capabilities')" style="margin-top: 8px;">
                            Go to Capabilities
                        </button>
                    </li>
                    <li>
                        <strong>Enable using CLI:</strong>
                        <pre style="background: #f3f4f6; padding: 12px; border-radius: 6px; margin-top: 8px; overflow-x: auto;">$ agentos mcp enable ${result.server_id || pkg.server_id}</pre>
                    </li>
                    <li>
                        <strong>Test the connection:</strong>
                        <pre style="background: #f3f4f6; padding: 12px; border-radius: 6px; margin-top: 8px; overflow-x: auto;">$ agentos mcp test ${result.server_id || pkg.server_id}</pre>
                    </li>
                </ol>
            </div>

            <div style="text-align: center; margin-top: 32px;">
                <button class="btn-secondary" onclick="loadView('marketplace')">
                    <span class="material-icons md-18">arrow_back</span>
                    Back to Marketplace
                </button>
            </div>
        `;

        // Replace the actions section
        const actionsSection = this.container.querySelector('.section:last-child');
        if (actionsSection) {
            actionsSection.innerHTML = successHtml;
        }
    }

    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        const bgColors = {
            success: '#10b981',
            error: '#ef4444',
            info: '#3b82f6'
        };

        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 16px 24px;
            background: ${bgColors[type] || bgColors.info};
            color: white;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            z-index: 10000;
            font-size: 14px;
            font-weight: 500;
            max-width: 400px;
        `;
        notification.textContent = message;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transition = 'opacity 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    /**
     * Render error state
     */
    renderError(error) {
        this.container.innerHTML = `
            <div class="package-detail">
                <a href="#" class="back-link" onclick="loadView('marketplace'); return false;">
                    <span class="material-icons md-18">arrow_back</span>
                    Back to Marketplace
                </a>
                <div class="empty-state">
                    <div class="empty-state-icon">error</div>
                    <h3>Failed to Load Package</h3>
                    <p>${error.message}</p>
                    <button class="btn-primary" onclick="loadView('marketplace')">
                        Back to Marketplace
                    </button>
                </div>
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
        sessionStorage.removeItem('mcp_package_id');
    }
}

// Export to window
window.MCPPackageDetailView = MCPPackageDetailView;
