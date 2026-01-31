/**
 * Extensions Management View
 *
 * Provides a complete UI for managing AgentOS extensions:
 * - Browse installed extensions
 * - Install new extensions (upload ZIP or from URL)
 * - View installation progress (real-time polling)
 * - Enable/disable extensions
 * - View extension details (commands, docs, permissions)
 * - Configure extensions
 * - Uninstall extensions
 * - View extension logs
 *
 * Part of PR-C: WebUI Extensions Management
 * Security: Task #36 - CSRF protection for all state-changing operations
 */

class ExtensionsView {
    constructor() {
        this.currentView = 'list'; // 'list', 'detail', 'config'
        this.selectedExtensionId = null;
        this.pollIntervalId = null;
        this.activeInstalls = new Set();
        this.selectedExtensions = new Set(); // For batch operations (L-19)
        this.bulkModeActive = false; // Track if bulk selection mode is active
    }

    /**
     * Render the view
     */
    async render(container) {
        this.container = container;
        await this.renderExtensionsList();
        this.startPollingInstalls();
        this.initKeyboardShortcuts();
    }

    /**
     * Cleanup when view is destroyed
     */
    destroy() {
        if (this.pollIntervalId) {
            clearInterval(this.pollIntervalId);
            this.pollIntervalId = null;
        }
        this.removeKeyboardShortcuts();
    }

    /**
     * Render extensions list view
     */
    async renderExtensionsList() {
        this.container.innerHTML = `
            <div class="extensions-view">
                <div class="view-header">
                    <div>
                        <h1>Extensions</h1>
                        <p class="text-sm text-gray-600 mt-1">Install and manage AgentOS extensions</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-wizard" id="btnCreateTemplate" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none;">
                            <span class="icon"><span class="material-icons md-18">auto_fix_high</span></span> Create Extension Template
                        </button>
                        <button class="btn-secondary" id="btnInstallUpload">
                            <span class="icon"><span class="material-icons md-18">arrow_upward</span></span> Upload Extension
                        </button>
                        <button class="btn-primary" id="btnInstallURL">
                            <span class="icon"><span class="material-icons md-18">link</span></span> Install from URL
                        </button>
                    </div>
                </div>

                <!-- L-20: Search Box -->
                <div class="extensions-search-bar" style="padding: 12px 24px; background: white; border-bottom: 1px solid #e5e7eb;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <div style="flex: 1; position: relative;">
                            <span class="material-icons" style="position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: #9ca3af; font-size: 20px;">search</span>
                            <input
                                type="text"
                                id="extensionSearchInput"
                                placeholder="Search extensions... (Ctrl+K)"
                                style="width: 100%; padding: 10px 12px 10px 42px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 14px;"
                            />
                        </div>
                        <button class="btn-secondary" id="btnToggleBulkMode" style="white-space: nowrap;">
                            <span class="material-icons md-18">checklist</span> Bulk Select
                        </button>
                    </div>
                </div>

                <!-- L-19: Bulk Operations Toolbar (hidden by default) -->
                <div id="bulkOperationsToolbar" class="bulk-operations-toolbar" style="display: none;">
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                        <div style="display: flex; align-items: center; gap: 16px;">
                            <span id="selectedCount" style="font-weight: 600; color: #374151;">0 selected</span>
                            <button class="btn-link" id="btnSelectAll">Select All</button>
                            <button class="btn-link" id="btnClearSelection">Clear</button>
                        </div>
                        <div style="display: flex; gap: 8px;">
                            <button class="btn-secondary" id="btnBulkEnable">
                                <span class="material-icons md-18">check_circle</span> Enable Selected
                            </button>
                            <button class="btn-secondary" id="btnBulkDisable">
                                <span class="material-icons md-18">cancel</span> Disable Selected
                            </button>
                            <button class="btn-delete" id="btnBulkUninstall">
                                <span class="material-icons md-18">delete</span> Uninstall Selected
                            </button>
                        </div>
                    </div>
                </div>

                <div id="installProgressContainer" class="filter-section" style="display: none;"></div>

                <div class="table-section">
                    <div id="extensionsGrid" class="extensions-grid">
                        <div class="text-center py-8">
                            <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
                            <p class="mt-4 text-gray-600">Loading extensions...</p>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Attach event listeners
        document.getElementById('btnCreateTemplate').addEventListener('click', () => this.showTemplateWizard());
        document.getElementById('btnInstallUpload').addEventListener('click', () => this.showInstallUploadModal());
        document.getElementById('btnInstallURL').addEventListener('click', () => this.showInstallURLModal());

        // L-20: Search functionality
        const searchInput = document.getElementById('extensionSearchInput');
        searchInput.addEventListener('input', (e) => this.filterExtensions(e.target.value));

        // L-19: Bulk operations
        document.getElementById('btnToggleBulkMode').addEventListener('click', () => this.toggleBulkMode());
        document.getElementById('btnSelectAll').addEventListener('click', () => this.selectAllExtensions());
        document.getElementById('btnClearSelection').addEventListener('click', () => this.clearSelection());
        document.getElementById('btnBulkEnable').addEventListener('click', () => this.bulkEnableExtensions());
        document.getElementById('btnBulkDisable').addEventListener('click', () => this.bulkDisableExtensions());
        document.getElementById('btnBulkUninstall').addEventListener('click', () => this.bulkUninstallExtensions());

        // Load extensions
        await this.loadExtensions();
    }

    /**
     * Load and display extensions
     */
    async loadExtensions() {
        try {
            const response = await fetch('/api/extensions');
            if (!response.ok) {
                throw new Error('Failed to load extensions');
            }

            const data = await response.json();
            const extensions = data.extensions || [];

            const grid = document.getElementById('extensionsGrid');

            if (extensions.length === 0) {
                grid.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">inventory_2</div>
                        <h3>No Extensions Installed</h3>
                        <p>Get started by installing your first extension</p>
                        <button class="btn-primary" onclick="document.getElementById('btnInstallUpload').click()">
                            Install Extension
                        </button>
                    </div>
                `;
                return;
            }

            grid.innerHTML = extensions.map(ext => this.renderExtensionCard(ext)).join('');

            // Attach card event listeners
            extensions.forEach(ext => {
                // Attach action button listeners
                this.attachCardActions(ext);

                // Attach capability tag copy listeners
                this.attachCapabilityTagCopy(ext);

                // Attach governance link listeners
                this.attachGovernanceLink(ext);
            });

            // L-18: Attach rating handlers
            this.attachRatingHandlers();

            // L-19: Attach checkbox handlers
            if (this.bulkModeActive) {
                this.attachCheckboxHandlers();
            }

            // Attach ExplainButton handlers
            if (typeof ExplainButton !== 'undefined') {
                ExplainButton.attachHandlers();
            }

        } catch (error) {
            console.error('Failed to load extensions:', error);
            const grid = document.getElementById('extensionsGrid');
            grid.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">warning</div>
                    <h3>Failed to Load Extensions</h3>
                    <p>${error.message}</p>
                    <button class="btn-primary" onclick="location.reload()">
                        Retry
                    </button>
                </div>
            `;
        }
    }

    /**
     * Render extension card
     */
    renderExtensionCard(ext) {
        const iconUrl = ext.icon_path || '/static/icons/extension-default.svg';
        const statusClass = `status-${ext.status}`;
        const disabledClass = ext.enabled ? '' : 'disabled';

        const capabilities = ext.capabilities
            .filter(cap => cap.type === 'slash_command')
            .map(cap => {
                // Remove leading slash since CSS ::before adds it
                const displayName = cap.name.startsWith('/') ? cap.name.substring(1) : cap.name;
                return `<span class="capability-tag">${displayName}</span>`;
            })
            .join('');

        const permissions = ext.permissions_required
            .map(perm => `<span class="permission-badge">${perm}</span>`)
            .join('');

        // Create Explain button for this extension
        const explainBtn = new ExplainButton('extension', ext.name, ext.name);

        // L-18: Get rating from localStorage
        const rating = this.getExtensionRating(ext.id);

        // L-19: Checkbox for bulk selection
        const checkboxHtml = this.bulkModeActive ? `
            <div class="extension-checkbox" style="position: absolute; top: 12px; left: 12px; z-index: 10;">
                <input type="checkbox" class="bulk-select-checkbox" data-ext-id="${ext.id}"
                       ${this.selectedExtensions.has(ext.id) ? 'checked' : ''}
                       style="width: 20px; height: 20px; cursor: pointer;">
            </div>
        ` : '';

        return `
            <div class="extension-card ${disabledClass}" id="ext-card-${ext.id}" data-ext-name="${ext.name.toLowerCase()}" data-ext-description="${(ext.description || '').toLowerCase()}" style="position: relative;">
                ${checkboxHtml}
                <div class="extension-card-header">
                    <img src="${iconUrl}" alt="${ext.name}" class="extension-icon" onerror="this.src='/static/icons/extension-default.svg'"
                         style="cursor: pointer;" onclick="window.extensionsView.showExtensionDetail('${ext.id}')">
                    <div class="extension-info">
                        <div class="extension-title-row">
                            <h3 style="cursor: pointer;" onclick="window.extensionsView.showExtensionDetail('${ext.id}')">${ext.name}</h3>
                            ${explainBtn.render()}
                        </div>
                        <div class="extension-meta">
                            <span class="extension-version">v${ext.version}</span>
                            <span class="extension-status ${statusClass}">${ext.status}</span>
                            ${ext.runtime ? `
                                <span class="runtime-badge runtime-${ext.runtime}" title="Runtime: ${ext.runtime.toUpperCase()} ${ext.python_version || ''}">
                                    <span class="material-icons md-14">code</span>
                                    Python ${ext.python_version || '3.8'}
                                </span>
                            ` : ''}
                            ${ext.adr_ext_002_compliant ? `
                                <span class="compliance-badge" title="Complies with ADR-EXT-002: Python-only runtime policy">
                                    <span class="material-icons md-14">verified</span>
                                    ADR-EXT-002
                                </span>
                            ` : ext.runtime ? `
                                <span class="compliance-badge non-compliant" title="Does not comply with ADR-EXT-002: May use external binaries">
                                    <span class="material-icons md-14">warning</span>
                                    Non-compliant
                                </span>
                            ` : ''}
                        </div>
                    </div>
                </div>
                <div class="extension-card-body">
                    <p class="extension-description">${ext.description || 'No description available'}</p>

                    <!-- L-18: Rating Display -->
                    <div class="extension-rating" style="margin-bottom: 12px;">
                        ${this.renderStarRating(ext.id, rating)}
                    </div>

                    ${capabilities ? `<div class="extension-capabilities">${capabilities}</div>` : ''}
                    ${permissions ? `<div class="extension-permissions">${permissions}</div>` : ''}
                    ${this.renderGovernanceInfo(ext)}
                </div>
                <div class="extension-card-actions">
                    ${ext.enabled
                        ? `<button class="btn-disable" data-action="disable" data-ext-id="${ext.id}">Disable</button>`
                        : `<button class="btn-enable" data-action="enable" data-ext-id="${ext.id}">Enable</button>`
                    }
                    <button class="btn-settings" data-action="config" data-ext-id="${ext.id}">Settings</button>
                    <button class="btn-delete" data-action="uninstall" data-ext-id="${ext.id}">Uninstall</button>
                </div>
            </div>
        `;
    }

    /**
     * Render governance information for extension
     */
    renderGovernanceInfo(ext) {
        // Check if extension has governance metadata
        const trustTier = ext.trust_tier || ext.governance?.trust_tier;
        const quotaStatus = ext.quota_status || ext.governance?.quota_status;

        // If no governance info, return empty string (graceful degradation)
        if (!trustTier && !quotaStatus) {
            return '';
        }

        const trustBadgeClass = trustTier === 'T1' ? 'success' :
                               trustTier === 'T2' ? 'warning' : 'error';
        const quotaBadgeClass = quotaStatus === 'OK' ? 'success' :
                               quotaStatus === 'WARNING' ? 'warning' : 'error';

        return `
            <div class="extension-governance" style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #e5e7eb;">
                <div style="font-size: 12px; font-weight: 600; color: #6b7280; margin-bottom: 8px;">Governance</div>
                <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
                    ${trustTier ? `
                        <div style="display: flex; align-items: center; gap: 4px;">
                            <span style="font-size: 12px; color: #6b7280;">Trust Tier:</span>
                            <span class="badge ${trustBadgeClass}" style="font-size: 11px;">${trustTier}</span>
                        </div>
                    ` : ''}
                    ${quotaStatus ? `
                        <div style="display: flex; align-items: center; gap: 4px;">
                            <span style="font-size: 12px; color: #6b7280;">Quota:</span>
                            <span class="badge ${quotaBadgeClass}" style="font-size: 11px;">${quotaStatus}</span>
                        </div>
                    ` : ''}
                    <a href="#" class="governance-link" data-ext-id="${ext.id}"
                       style="font-size: 12px; color: #3b82f6; text-decoration: none; margin-left: auto;">
                        View Details →
                    </a>
                </div>
            </div>
        `;
    }

    /**
     * Attach action button event listeners
     */
    attachCardActions(ext) {
        // Enable button
        const enableBtn = document.querySelector(`[data-action="enable"][data-ext-id="${ext.id}"]`);
        if (enableBtn) {
            enableBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.enableExtension(ext.id);
            });
        }

        // Disable button
        const disableBtn = document.querySelector(`[data-action="disable"][data-ext-id="${ext.id}"]`);
        if (disableBtn) {
            disableBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.disableExtension(ext.id);
            });
        }

        // Config button
        const configBtn = document.querySelector(`[data-action="config"][data-ext-id="${ext.id}"]`);
        if (configBtn) {
            configBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.showExtensionConfig(ext.id);
            });
        }

        // Uninstall button
        const uninstallBtn = document.querySelector(`[data-action="uninstall"][data-ext-id="${ext.id}"]`);
        if (uninstallBtn) {
            uninstallBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.uninstallExtension(ext.id, ext.name);
            });
        }
    }

    /**
     * Attach capability tag copy functionality
     */
    attachCapabilityTagCopy(ext) {
        const card = document.getElementById(`ext-card-${ext.id}`);
        if (!card) return;

        // Find all capability tags in this card
        const tags = card.querySelectorAll('.capability-tag');
        tags.forEach(tag => {
            // Add pointer cursor
            tag.style.cursor = 'pointer';
            tag.title = 'Click to copy command';

            tag.addEventListener('click', async (e) => {
                e.stopPropagation(); // Don't trigger card click

                // Get the command text (tag has the name without leading slash, add it back)
                const command = '/' + tag.textContent.trim();

                try {
                    // Copy to clipboard
                    await navigator.clipboard.writeText(command);

                    // Show success notification
                    this.showNotification(`Copied: ${command}`, 'success');

                    // Visual feedback
                    const originalBg = tag.style.backgroundColor;
                    tag.style.backgroundColor = '#10b981';
                    tag.style.color = 'white';
                    setTimeout(() => {
                        tag.style.backgroundColor = '';
                        tag.style.color = '';
                    }, 300);

                } catch (error) {
                    console.error('Failed to copy:', error);
                    this.showNotification('Copy failed', 'error');
                }
            });
        });
    }

    /**
     * Attach governance link click handler
     */
    attachGovernanceLink(ext) {
        const link = document.querySelector(`.governance-link[data-ext-id="${ext.id}"]`);
        if (!link) return;

        link.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();

            // Navigate to governance dashboard with extension filter
            // For now, just navigate to governance dashboard
            // In the future, could pass filter parameter
            if (typeof updateNavigationActive === 'function') {
                updateNavigationActive('governance-dashboard');
                loadView('governance-dashboard');
            } else {
                // Fallback: direct link
                window.location.hash = 'governance-dashboard';
            }
        });
    }

    /**
     * Show install from upload modal (L-16: With drag-and-drop support)
     */
    showInstallUploadModal() {
        const modal = document.createElement('div');
        modal.className = 'modal active';
        modal.innerHTML = `
            <div class="modal-overlay"></div>
            <div class="modal-content modal-md">
                <div class="modal-header">
                    <h2>Install Extension from ZIP</h2>
                    <button class="modal-close" id="btnCloseUpload">&times;</button>
                </div>
                <div class="modal-body">
                    <!-- L-16: Drag and Drop Area -->
                    <div id="dropZone" class="drop-zone">
                        <div class="drop-zone-content">
                            <span class="material-icons" style="font-size: 48px; color: #9ca3af; margin-bottom: 12px;">cloud_upload</span>
                            <h3 style="margin: 0 0 8px 0; font-size: 16px; font-weight: 600; color: #374151;">Drag and drop your extension here</h3>
                            <p style="margin: 0 0 16px 0; font-size: 14px; color: #6b7280;">or</p>
                            <label for="zipFileInput" class="btn-secondary" style="cursor: pointer; display: inline-block;">
                                <span class="material-icons md-18">folder_open</span> Browse Files
                            </label>
                            <input type="file" accept=".zip" id="zipFileInput" style="display: none;">
                            <p class="field-hint" style="margin-top: 12px;">Supports .zip files only</p>
                            <div id="selectedFileName" style="margin-top: 12px; font-size: 14px; color: #10b981; font-weight: 500; display: none;"></div>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn-secondary" id="btnCancelUpload">Cancel</button>
                    <button class="btn-primary" id="btnConfirmUpload" disabled>Install</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        const dropZone = document.getElementById('dropZone');
        const fileInput = document.getElementById('zipFileInput');
        const confirmBtn = document.getElementById('btnConfirmUpload');
        const fileNameDisplay = document.getElementById('selectedFileName');
        let selectedFile = null;

        // L-16: Drag and drop handlers
        const handleDragOver = (e) => {
            e.preventDefault();
            e.stopPropagation();
            e.dataTransfer.dropEffect = 'copy';
            dropZone.classList.add('drop-zone-active');
        };

        const handleDragLeave = (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('drop-zone-active');
        };

        const handleDrop = (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('drop-zone-active');

            const files = e.dataTransfer.files;
            if (files.length > 0) {
                const file = files[0];
                if (file.name.endsWith('.zip')) {
                    selectedFile = file;
                    fileNameDisplay.textContent = `Selected: ${file.name}`;
                    fileNameDisplay.style.display = 'block';
                    confirmBtn.disabled = false;
                } else {
                    this.showNotification('Please select a ZIP file', 'error');
                }
            }
        };

        dropZone.addEventListener('dragover', handleDragOver);
        dropZone.addEventListener('dragleave', handleDragLeave);
        dropZone.addEventListener('drop', handleDrop);

        // File input change handler
        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                selectedFile = file;
                fileNameDisplay.textContent = `Selected: ${file.name}`;
                fileNameDisplay.style.display = 'block';
                confirmBtn.disabled = false;
            }
        });

        const closeModal = () => {
            modal.remove();
        };

        document.getElementById('btnCloseUpload').addEventListener('click', closeModal);
        document.getElementById('btnCancelUpload').addEventListener('click', closeModal);
        document.getElementById('btnConfirmUpload').addEventListener('click', async () => {
            if (!selectedFile) {
                this.showNotification('Please select a ZIP file', 'error');
                return;
            }

            closeModal();
            await this.installFromUpload(selectedFile);
        });

        // Close on background click
        modal.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal-overlay')) {
                closeModal();
            }
        });
    }

    /**
     * Show install from URL modal
     */
    showInstallURLModal() {
        const modal = document.createElement('div');
        modal.className = 'modal active';
        modal.innerHTML = `
            <div class="modal-overlay"></div>
            <div class="modal-content modal-md">
                <div class="modal-header">
                    <h2>Install Extension from URL</h2>
                    <button class="modal-close" id="btnCloseURL">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label>Extension Package URL</label>
                        <input type="url" placeholder="https://example.com/extension.zip" id="urlInput">
                        <div class="field-hint">Enter the URL to download the extension package</div>
                    </div>
                    <div class="form-group">
                        <label>SHA256 Hash (Optional)</label>
                        <input type="text" placeholder="Enter SHA256 hash for verification" id="sha256Input">
                        <div class="field-hint">Provide the expected SHA256 hash to verify package integrity</div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn-secondary" id="btnCancelURL">Cancel</button>
                    <button class="btn-primary" id="btnConfirmURL">Install</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        const closeModal = () => {
            modal.remove();
        };

        document.getElementById('btnCloseURL').addEventListener('click', closeModal);
        document.getElementById('btnCancelURL').addEventListener('click', closeModal);
        document.getElementById('btnConfirmURL').addEventListener('click', async () => {
            const url = document.getElementById('urlInput').value.trim();
            const sha256 = document.getElementById('sha256Input').value.trim() || null;

            if (!url) {
                this.showNotification('Please enter a URL', 'error');
                return;
            }

            closeModal();
            await this.installFromURL(url, sha256);
        });

        // Close on background click
        modal.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal-overlay')) {
                closeModal();
            }
        });
    }

    /**
     * Install extension from uploaded file
     */
    async installFromUpload(file) {
        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetchWithCSRF('/api/extensions/install', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Installation failed');
            }

            const data = await response.json();
            this.activeInstalls.add(data.install_id);
            this.showInstallProgress(data.install_id, data.extension_id);

        } catch (error) {
            console.error('Installation failed:', error);
            this.showNotification(`Installation failed: ${error.message}`, 'error');
        }
    }

    /**
     * Install extension from URL
     */
    async installFromURL(url, sha256) {
        try {
            const response = await fetchWithCSRF('/api/extensions/install-url', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ url, sha256 })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Installation failed');
            }

            const data = await response.json();
            this.activeInstalls.add(data.install_id);
            this.showInstallProgress(data.install_id, data.extension_id);

        } catch (error) {
            console.error('Installation failed:', error);
            this.showNotification(`Installation failed: ${error.message}`, 'error');
        }
    }

    /**
     * Show installation progress
     */
    showInstallProgress(installId, extensionId) {
        const container = document.getElementById('installProgressContainer');

        // Show the container
        container.style.display = 'block';

        const progressHtml = `
            <div class="install-progress" id="progress-${installId}">
                <div class="progress-header">
                    <h3>Installing ${extensionId || 'extension'}...</h3>
                    <span class="progress-percent" id="progress-percent-${installId}">0%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" id="progress-fill-${installId}" style="width: 0%"></div>
                </div>
                <p class="progress-step" id="progress-step-${installId}">Starting installation...</p>
            </div>
        `;

        container.insertAdjacentHTML('beforeend', progressHtml);
    }

    /**
     * Hide progress container if no active installations
     */
    hideProgressContainerIfEmpty() {
        const container = document.getElementById('installProgressContainer');
        if (container && container.children.length === 0) {
            container.style.display = 'none';
        }
    }

    /**
     * Start polling for installation progress
     */
    startPollingInstalls() {
        // Poll every 500ms
        this.pollIntervalId = setInterval(async () => {
            for (const installId of this.activeInstalls) {
                await this.updateInstallProgress(installId);
            }
        }, 500);
    }

    /**
     * Update installation progress
     */
    async updateInstallProgress(installId) {
        try {
            const response = await fetch(`/api/extensions/install/${installId}`);
            if (!response.ok) {
                // If 404, the install record no longer exists (completed or cleaned up)
                // Stop polling this install_id
                if (response.status === 404) {
                    this.activeInstalls.delete(installId);
                    const progressEl = document.getElementById(`progress-${installId}`);
                    if (progressEl) {
                        progressEl.remove();
                    }
                    this.hideProgressContainerIfEmpty();
                    // Refresh extension list to show newly installed extension
                    this.loadExtensions();
                }
                return;
            }

            const data = await response.json();

            // Update progress UI
            const percentEl = document.getElementById(`progress-percent-${installId}`);
            const fillEl = document.getElementById(`progress-fill-${installId}`);
            const stepEl = document.getElementById(`progress-step-${installId}`);

            if (percentEl) percentEl.textContent = `${data.progress}%`;
            if (fillEl) fillEl.style.width = `${data.progress}%`;
            if (stepEl) {
                const stepText = data.current_step
                    ? `Step ${data.completed_steps}/${data.total_steps}: ${data.current_step}`
                    : 'Processing...';
                stepEl.textContent = stepText;
            }

            // Check if completed or failed
            if (data.status === 'COMPLETED') {
                this.activeInstalls.delete(installId);
                setTimeout(() => {
                    const progressEl = document.getElementById(`progress-${installId}`);
                    if (progressEl) {
                        progressEl.remove();
                    }
                    this.hideProgressContainerIfEmpty();
                    this.loadExtensions(); // Refresh list
                }, 2000);

                // Show success message
                if (stepEl) {
                    stepEl.textContent = 'check Installation completed successfully!';
                    stepEl.style.color = '#059669';
                }

                // Show notification
                this.showNotification('Extension installed successfully', 'success');

            } else if (data.status === 'FAILED') {
                this.activeInstalls.delete(installId);

                // Show error message
                if (stepEl) {
                    stepEl.textContent = `close Installation failed: ${data.error || 'Unknown error'}`;
                    stepEl.style.color = '#dc2626';
                }

                // Show notification
                this.showNotification(`Installation failed: ${data.error || 'Unknown error'}`, 'error');

                // Auto-remove failed progress after delay
                setTimeout(() => {
                    const progressEl = document.getElementById(`progress-${installId}`);
                    if (progressEl) {
                        progressEl.remove();
                    }
                    this.hideProgressContainerIfEmpty();
                }, 5000);
            }

        } catch (error) {
            console.error('Failed to update install progress:', error);
        }
    }

    /**
     * Enable extension
     */
    async enableExtension(extensionId) {
        try {
            const response = await fetchWithCSRF(`/api/extensions/${extensionId}/enable`, {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error('Failed to enable extension');
            }

            this.showNotification('Extension enabled successfully', 'success');
            await this.loadExtensions(); // Refresh list

        } catch (error) {
            console.error('Failed to enable extension:', error);
            this.showNotification(`Failed to enable extension: ${error.message}`, 'error');
        }
    }

    /**
     * Disable extension
     */
    async disableExtension(extensionId) {
        try {
            const response = await fetchWithCSRF(`/api/extensions/${extensionId}/disable`, {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error('Failed to disable extension');
            }

            this.showNotification('Extension disabled successfully', 'success');
            await this.loadExtensions(); // Refresh list

        } catch (error) {
            console.error('Failed to disable extension:', error);
            this.showNotification(`Failed to disable extension: ${error.message}`, 'error');
        }
    }

    /**
     * Uninstall extension
     */
    async uninstallExtension(extensionId, extensionName) {
        // Create confirmation modal
        const modal = document.createElement('div');
        modal.className = 'modal active';
        modal.innerHTML = `
            <div class="modal-overlay"></div>
            <div class="modal-content" style="max-width: 500px;">
                <div class="modal-header">
                    <h2>Uninstall Extension</h2>
                    <button class="modal-close" id="btnCloseUninstall">&times;</button>
                </div>
                <div class="modal-body">
                    <p style="color: #374151; margin-bottom: 1rem;">
                        Are you sure you want to uninstall <strong>"${extensionName}"</strong>?
                    </p>
                    <div style="background: #fef3c7; border: 1px solid #fbbf24; border-radius: 0.5rem; padding: 1rem; margin-bottom: 1rem;">
                        <p style="color: #92400e; font-size: 0.875rem; margin: 0;">
                            warning <strong>Warning:</strong> This action cannot be undone. All extension data and configuration will be permanently deleted.
                        </p>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn-secondary" id="btnCancelUninstall">Cancel</button>
                    <button class="btn-delete" id="btnConfirmUninstall">Uninstall</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Close handlers
        const closeModal = () => {
            modal.remove();
        };

        document.getElementById('btnCloseUninstall').addEventListener('click', closeModal);
        document.getElementById('btnCancelUninstall').addEventListener('click', closeModal);
        modal.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal-overlay')) {
                closeModal();
            }
        });

        // Confirm handler
        document.getElementById('btnConfirmUninstall').addEventListener('click', async () => {
            closeModal();

            try {
                const response = await fetchWithCSRF(`/api/extensions/${extensionId}`, {
                    method: 'DELETE'
                });

                if (!response.ok) {
                    throw new Error('Failed to uninstall extension');
                }

                this.showNotification(`${extensionName} uninstalled successfully`, 'success');
                await this.loadExtensions(); // Refresh list

            } catch (error) {
                console.error('Failed to uninstall extension:', error);
                this.showNotification(`Failed to uninstall extension: ${error.message}`, 'error');
            }
        });
    }

    /**
     * Show extension detail view
     */
    async showExtensionDetail(extensionId) {
        try {
            const response = await fetch(`/api/extensions/${extensionId}`);
            if (!response.ok) {
                throw new Error('Failed to load extension details');
            }

            const ext = await response.json();

            // Render detail view (simplified - you can expand this)
            this.container.innerHTML = `
                <div class="extensions-view">
                    <button class="btn-secondary mb-4" id="btnBack">
                        arrow_back Back to Extensions
                    </button>
                    <div class="extension-detail">
                        <div class="detail-header">
                            <img src="${ext.icon_path || '/static/icons/extension-default.svg'}" alt="${ext.name}" class="detail-icon">
                            <div>
                                <h1>${ext.name}</h1>
                                <p>${ext.description || 'No description available'}</p>
                            </div>
                        </div>

                        <!-- L-17: Screenshots -->
                        ${ext.screenshots ? this.renderScreenshotCarousel(ext.screenshots) : ''}

                        <div class="detail-section">
                            <h3>Runtime Information</h3>
                            <div class="runtime-info">
                                <div class="info-item">
                                    <label>Runtime Type:</label>
                                    <span class="runtime-badge runtime-${ext.runtime || 'unknown'}">${ext.runtime || 'Unknown'}</span>
                                </div>
                                <div class="info-item">
                                    <label>Python Version:</label>
                                    <span>${ext.python_version || 'N/A'}</span>
                                </div>
                                ${ext.python_dependencies && ext.python_dependencies.length > 0 ? `
                                    <div class="info-item">
                                        <label>Python Dependencies:</label>
                                        <div>
                                            <ul class="dependencies-list">
                                                ${ext.python_dependencies.map(dep => `<li><code>${dep}</code></li>`).join('')}
                                            </ul>
                                        </div>
                                    </div>
                                ` : ''}
                                <div class="info-item">
                                    <label>External Binaries:</label>
                                    <span class="${ext.has_external_bins ? 'text-warning' : 'text-success'}">
                                        ${ext.has_external_bins
                                            ? `⚠️ ${ext.external_bins_count} binary file(s) required`
                                            : '✓ None (Python-only)'}
                                    </span>
                                </div>
                                <div class="info-item">
                                    <label>ADR-EXT-002 Compliance:</label>
                                    ${ext.adr_ext_002_compliant ? `
                                        <span class="compliance-badge">
                                            <span class="material-icons md-18">verified</span>
                                            Compliant
                                        </span>
                                    ` : `
                                        <span class="compliance-badge non-compliant">
                                            <span class="material-icons md-18">warning</span>
                                            Non-compliant
                                        </span>
                                        ${ext.adr_ext_002_reason ? `
                                            <div style="font-size: 12px; color: #ef4444; margin-top: 4px;">
                                                ${ext.adr_ext_002_reason}
                                            </div>
                                        ` : ''}
                                    `}
                                </div>
                            </div>
                        </div>

                        ${ext.capabilities && ext.capabilities.length > 0 ? `
                            <div class="detail-section">
                                <h2>Commands</h2>
                                <div class="command-list">
                                    ${ext.capabilities
                                        .filter(cap => cap.type === 'slash_command')
                                        .map(cap => `
                                            <div class="command-item">
                                                <code>${cap.name}</code>
                                                <p>${cap.description}</p>
                                            </div>
                                        `).join('')}
                                </div>
                            </div>
                        ` : ''}

                        ${ext.usage_doc ? `
                            <div class="detail-section">
                                <h2>Usage Documentation</h2>
                                <div class="usage-doc">${this.renderMarkdown(ext.usage_doc)}</div>
                            </div>
                        ` : ''}

                        ${ext.permissions_required && ext.permissions_required.length > 0 ? `
                            <div class="detail-section">
                                <h2>Permissions</h2>
                                <ul class="permission-list">
                                    ${ext.permissions_required.map(perm => `<li><strong>${perm}</strong></li>`).join('')}
                                </ul>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;

            document.getElementById('btnBack').addEventListener('click', () => {
                this.renderExtensionsList();
            });

        } catch (error) {
            console.error('Failed to load extension details:', error);
            this.showNotification(`Failed to load extension details: ${error.message}`, 'error');
        }
    }

    /**
     * Show extension configuration view
     */
    async showExtensionConfig(extensionId) {
        try {
            // Load extension details
            const response = await fetch(`/api/extensions/${extensionId}`);
            if (!response.ok) {
                throw new Error('Failed to load extension details');
            }
            const ext = await response.json();

            // Load current configuration
            const configResponse = await fetch(`/api/extensions/${extensionId}/config`);
            if (!configResponse.ok) {
                throw new Error('Failed to load extension configuration');
            }
            const configData = await configResponse.json();
            const currentConfig = configData.config || {};

            // Create modal
            const modal = document.createElement('div');
            modal.className = 'modal active';
            modal.innerHTML = `
                <div class="modal-overlay"></div>
                <div class="modal-content" style="max-width: 600px;">
                    <div class="modal-header">
                        <h2>Configure ${ext.name}</h2>
                        <button class="modal-close" id="btnCloseConfig">&times;</button>
                    </div>
                    <div class="modal-body">
                        <p style="color: #6b7280; margin-bottom: 1.5rem; font-size: 0.875rem;">
                            Configure settings for this extension. Sensitive values (keys, tokens, passwords) will be masked when displayed.
                        </p>
                        <form id="configForm">
                            ${this.renderConfigFields(ext, currentConfig)}
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button class="btn-secondary" id="btnCancelConfig">Cancel</button>
                        <button class="btn-primary" id="btnSaveConfig">Save Configuration</button>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);

            // Close handlers
            const closeModal = () => {
                modal.remove();
            };

            document.getElementById('btnCloseConfig').addEventListener('click', closeModal);
            document.getElementById('btnCancelConfig').addEventListener('click', closeModal);
            modal.addEventListener('click', (e) => {
                if (e.target.classList.contains('modal-overlay')) {
                    closeModal();
                }
            });

            // Save handler
            document.getElementById('btnSaveConfig').addEventListener('click', async () => {
                const form = document.getElementById('configForm');
                const formData = new FormData(form);
                const config = {};

                // Collect form data
                for (const [key, value] of formData.entries()) {
                    config[key] = value;
                }

                try {
                    const saveResponse = await fetchWithCSRF(`/api/extensions/${extensionId}/config`, {
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ config })
                    });

                    if (!saveResponse.ok) {
                        throw new Error('Failed to save configuration');
                    }

                    // Show success message
                    this.showNotification('Configuration saved successfully', 'success');
                    closeModal();

                } catch (error) {
                    console.error('Failed to save configuration:', error);
                    this.showNotification('Failed to save configuration: ' + error.message, 'error');
                }
            });

        } catch (error) {
            console.error('Failed to show extension config:', error);
            this.showNotification('Failed to load configuration: ' + error.message, 'error');
        }
    }

    /**
     * Render configuration form fields
     */
    renderConfigFields(ext, currentConfig) {
        // If extension has custom config schema, use it
        // Otherwise, render generic key-value pairs
        const configKeys = Object.keys(currentConfig);

        if (configKeys.length === 0) {
            return `
                <div style="text-align: center; padding: 2rem; color: #6b7280;">
                    <p>This extension has no configuration options yet.</p>
                    <p style="font-size: 0.875rem; margin-top: 0.5rem;">
                        Configuration options will be added by the extension developer.
                    </p>
                </div>
            `;
        }

        // Render fields based on current config
        return configKeys.map(key => {
            const value = currentConfig[key];
            const isSensitive = this.isSensitiveField(key);
            const fieldType = isSensitive ? 'password' : 'text';
            const displayValue = (value === '***' || isSensitive) ? '' : value;

            return `
                <div class="form-group" style="margin-bottom: 1.5rem;">
                    <label style="display: block; font-size: 0.875rem; font-weight: 600; color: #374151; margin-bottom: 0.5rem;">
                        ${this.formatFieldName(key)}
                        ${isSensitive ? '<span style="color: #ef4444; margin-left: 0.25rem;">lock</span>' : ''}
                    </label>
                    <input
                        type="${fieldType}"
                        name="${key}"
                        value="${displayValue}"
                        placeholder="${isSensitive ? 'Enter new value to update' : 'Enter ' + this.formatFieldName(key).toLowerCase()}"
                        style="width: 100%; padding: 0.75rem; border: 1px solid #d1d5db; border-radius: 0.5rem; font-size: 0.875rem;"
                    />
                    ${isSensitive ? `
                        <p style="font-size: 0.75rem; color: #6b7280; margin-top: 0.375rem;">
                            Leave empty to keep current value
                        </p>
                    ` : ''}
                </div>
            `;
        }).join('');
    }

    /**
     * Check if field is sensitive
     */
    isSensitiveField(fieldName) {
        const lowerName = fieldName.toLowerCase();
        const sensitiveKeywords = ['key', 'secret', 'token', 'password', 'credential', 'auth'];
        return sensitiveKeywords.some(keyword => lowerName.includes(keyword));
    }

    /**
     * Format field name for display
     */
    formatFieldName(fieldName) {
        // Convert snake_case or camelCase to Title Case
        return fieldName
            .replace(/([A-Z])/g, ' $1')
            .replace(/_/g, ' ')
            .split(' ')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ')
            .trim();
    }

    /**
     * Show notification message
     */
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 1rem 1.5rem;
            background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};
            color: white;
            border-radius: 0.5rem;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            z-index: 10000;
            font-size: 0.875rem;
            font-weight: 500;
            max-width: 400px;
            animation: slideIn 0.3s ease;
        `;
        notification.textContent = message;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    /**
     * Render markdown to HTML (basic implementation)
     */
    renderMarkdown(markdown) {
        // Use marked.js if available, otherwise basic conversion
        if (typeof marked !== 'undefined') {
            return marked.parse(markdown);
        }

        // Basic markdown rendering
        return markdown
            .replace(/^### (.+)$/gm, '<h3>$1</h3>')
            .replace(/^## (.+)$/gm, '<h2>$1</h2>')
            .replace(/^# (.+)$/gm, '<h1>$1</h1>')
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            .replace(/`(.+?)`/g, '<code>$1</code>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>');
    }

    /**
     * Show extension template wizard (Task #13)
     */
    async showTemplateWizard() {
        // Load permissions and capability types
        const [permissionsData, capabilityTypesData] = await Promise.all([
            fetch('/api/extensions/templates/permissions').then(r => r.json()),
            fetch('/api/extensions/templates/capability-types').then(r => r.json())
        ]);

        const availablePermissions = permissionsData.permissions || [];
        const availableCapabilityTypes = capabilityTypesData.capability_types || [];

        // Wizard state
        const wizardState = {
            step: 1,
            maxSteps: 4,
            data: {
                extension_id: '',
                extension_name: '',
                description: '',
                author: '',
                capabilities: [],
                permissions: []
            }
        };

        // Create modal
        const modal = document.createElement('div');
        modal.className = 'modal active';
        modal.id = 'templateWizardModal';
        document.body.appendChild(modal);

        const renderWizard = () => {
            modal.innerHTML = `
                <div class="modal-overlay"></div>
                <div class="modal-content modal-lg" style="max-width: 800px;">
                    <div class="modal-header">
                        <h2>Create Extension Template</h2>
                        <button class="modal-close" id="btnCloseWizard">&times;</button>
                    </div>
                    <div class="wizard-progress" style="padding: 1rem 1.5rem; border-bottom: 1px solid #e5e7eb;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                            ${[1, 2, 3, 4].map(i => `
                                <div style="flex: 1; text-align: center;">
                                    <div style="width: 32px; height: 32px; border-radius: 50%; margin: 0 auto;
                                        background: ${i <= wizardState.step ? '#4F46E5' : '#E5E7EB'};
                                        color: ${i <= wizardState.step ? 'white' : '#9CA3AF'};
                                        display: flex; align-items: center; justify-content: center;
                                        font-weight: 600; font-size: 0.875rem;">
                                        ${i}
                                    </div>
                                    <div style="font-size: 0.75rem; margin-top: 0.5rem; color: ${i === wizardState.step ? '#4F46E5' : '#6B7280'}; font-weight: ${i === wizardState.step ? '600' : '400'};">
                                        ${['Basic Info', 'Capabilities', 'Permissions', 'Review'][i - 1]}
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    <div class="modal-body" style="min-height: 400px;">
                        ${this.renderWizardStep(wizardState, availablePermissions, availableCapabilityTypes)}
                    </div>
                    <div class="modal-footer">
                        ${wizardState.step > 1 ? `<button class="btn-secondary" id="btnWizardPrev">Previous</button>` : ''}
                        <button class="btn-secondary" id="btnWizardCancel">Cancel</button>
                        ${wizardState.step < wizardState.maxSteps
                            ? `<button class="btn-primary" id="btnWizardNext">Next</button>`
                            : `<button class="btn-primary" id="btnWizardDownload">Download Template</button>`
                        }
                    </div>
                </div>
            `;

            // Attach event listeners
            const closeModal = () => modal.remove();

            document.getElementById('btnCloseWizard')?.addEventListener('click', closeModal);
            document.getElementById('btnWizardCancel')?.addEventListener('click', closeModal);

            if (wizardState.step > 1) {
                document.getElementById('btnWizardPrev')?.addEventListener('click', () => {
                    wizardState.step--;
                    renderWizard();
                });
            }

            if (wizardState.step < wizardState.maxSteps) {
                document.getElementById('btnWizardNext')?.addEventListener('click', () => {
                    if (this.validateWizardStep(wizardState)) {
                        this.collectWizardStepData(wizardState);
                        wizardState.step++;
                        renderWizard();
                    }
                });
            } else {
                document.getElementById('btnWizardDownload')?.addEventListener('click', async () => {
                    this.collectWizardStepData(wizardState);
                    await this.downloadTemplate(wizardState.data);
                    closeModal();
                });
            }

            // Attach step-specific listeners
            this.attachWizardStepListeners(wizardState, availableCapabilityTypes);
        };

        renderWizard();
    }

    /**
     * Render wizard step content
     */
    renderWizardStep(wizardState, availablePermissions, availableCapabilityTypes) {
        const { step, data } = wizardState;

        if (step === 1) {
            return `
                <div class="wizard-step">
                    <h3 style="margin-bottom: 1.5rem; color: #111827;">Basic Information</h3>

                    <div class="policy-notice">
                        <div class="policy-notice-icon">
                            <span class="material-icons">info</span>
                        </div>
                        <div class="policy-notice-content">
                            <h4>Python-Only Runtime Policy (ADR-EXT-002)</h4>
                            <p>All AgentOS extensions must use <strong>Python runtime</strong> and cannot depend on external binary files. This policy ensures:</p>
                            <ul>
                                <li><strong>Security:</strong> All code is auditable and runs in a controlled environment</li>
                                <li><strong>Cross-platform:</strong> Extensions work consistently on Linux, macOS, and Windows</li>
                                <li><strong>Simplicity:</strong> No system-level installations or sudo permissions required</li>
                            </ul>
                            <p class="policy-note">
                                <span class="material-icons md-16">lightbulb</span>
                                The generated template will automatically include Python runtime configuration.
                            </p>
                        </div>
                    </div>

                    <div class="form-group">
                        <label>Extension ID *</label>
                        <input type="text" id="extensionId" placeholder="tools.myext" value="${data.extension_id}">
                        <p class="field-hint">Format: namespace.name (lowercase alphanumeric only, e.g., tools.myext)</p>
                    </div>

                    <div class="form-group">
                        <label>Extension Name *</label>
                        <input type="text" id="extensionName" placeholder="My Extension" value="${data.extension_name}">
                        <p class="field-hint">Human-readable name displayed in the UI</p>
                    </div>

                    <div class="form-group">
                        <label>Description *</label>
                        <textarea id="extensionDescription" placeholder="What does your extension do?" rows="3">${data.description}</textarea>
                        <p class="field-hint">Brief description of what your extension does</p>
                    </div>

                    <div class="form-group">
                        <label>Author *</label>
                        <input type="text" id="extensionAuthor" placeholder="Your Name or Organization" value="${data.author}">
                    </div>
                </div>
            `;
        } else if (step === 2) {
            return `
                <div class="wizard-step">
                    <h3 style="margin-bottom: 1rem; color: #111827;">Capabilities</h3>
                    <p style="color: #6b7280; margin-bottom: 1.5rem; font-size: 0.875rem;">
                        Define the capabilities your extension will provide. At least one capability is required.
                    </p>

                    <div id="capabilitiesList">
                        ${data.capabilities.map((cap, index) => this.renderCapabilityItem(cap, index, availableCapabilityTypes)).join('')}
                    </div>

                    <button class="btn-secondary" id="btnAddCapability" style="width: 100%; margin-top: 1rem;">
                        <span class="material-icons md-18">add</span> Add Capability
                    </button>

                    <div class="help-text" style="margin-top: 24px; padding: 16px; background: #f9fafb; border-radius: 8px;">
                        <h5 style="margin: 0 0 12px 0; color: #374151;">Python-Only Best Practices</h5>
                        <div class="best-practices">
                            <div class="practice-item">
                                <span class="material-icons md-18 text-success">check_circle</span>
                                <div>
                                    <strong>Use Python packages from PyPI</strong>
                                    <div style="font-size: 12px; color: #6b7280; margin-top: 4px;">
                                        <code>requests</code>, <code>beautifulsoup4</code>, <code>pandas</code>, etc.
                                    </div>
                                </div>
                            </div>
                            <div class="practice-item">
                                <span class="material-icons md-18 text-success">check_circle</span>
                                <div>
                                    <strong>Use Python standard library</strong>
                                    <div style="font-size: 12px; color: #6b7280; margin-top: 4px;">
                                        <code>json</code>, <code>urllib</code>, <code>os</code>, <code>pathlib</code>, etc.
                                    </div>
                                </div>
                            </div>
                            <div class="practice-item">
                                <span class="material-icons md-18 text-danger">cancel</span>
                                <div>
                                    <strong>Don't use external binaries</strong>
                                    <div style="font-size: 12px; color: #6b7280; margin-top: 4px;">
                                        Avoid: <code>curl</code>, <code>jq</code>, <code>postman</code>, system tools
                                    </div>
                                </div>
                            </div>
                        </div>
                        <p class="learn-more" style="margin-top: 12px; text-align: center;">
                            <a href="#" onclick="window.open('/store/extensions/example.python-only/QUICKSTART.md', '_blank'); return false;" style="color: #2563eb; text-decoration: none;">
                                View example.python-only for reference
                            </a>
                        </p>
                    </div>
                </div>
            `;
        } else if (step === 3) {
            return `
                <div class="wizard-step">
                    <h3 style="margin-bottom: 1rem; color: #111827;">Permissions</h3>
                    <p style="color: #6b7280; margin-bottom: 1.5rem; font-size: 0.875rem;">
                        Select the permissions your extension needs. Only request permissions you actually need.
                    </p>

                    <div id="permissionsList" style="display: grid; grid-template-columns: 1fr; gap: 0.75rem;">
                        ${availablePermissions.map(perm => `
                            <label style="display: flex; align-items: start; padding: 1rem; border: 1px solid #e5e7eb; border-radius: 0.5rem; cursor: pointer; transition: all 0.2s;"
                                onmouseover="this.style.borderColor='#4F46E5'; this.style.backgroundColor='#f9fafb';"
                                onmouseout="this.style.borderColor='#e5e7eb'; this.style.backgroundColor='white';">
                                <input type="checkbox" name="permission" value="${perm.id}"
                                    ${data.permissions.includes(perm.id) ? 'checked' : ''}
                                    style="margin-top: 0.25rem; margin-right: 0.75rem; width: 16px; height: 16px;">
                                <div style="flex: 1;">
                                    <div style="font-weight: 600; color: #111827; margin-bottom: 0.25rem;">${perm.name}</div>
                                    <div style="font-size: 0.875rem; color: #6b7280;">${perm.description}</div>
                                </div>
                            </label>
                        `).join('')}
                    </div>
                </div>
            `;
        } else if (step === 4) {
            return `
                <div class="wizard-step">
                    <h3 style="margin-bottom: 1rem; color: #111827;">Review & Download</h3>
                    <p style="color: #6b7280; margin-bottom: 1.5rem; font-size: 0.875rem;">
                        Review your extension configuration and download the template package.
                    </p>

                    <div style="background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 0.5rem; padding: 1.5rem; margin-bottom: 1.5rem;">
                        <h4 style="margin: 0 0 1rem 0; color: #111827; font-size: 1rem;">Extension Details</h4>

                        <div style="display: grid; gap: 0.75rem; font-size: 0.875rem;">
                            <div>
                                <span style="font-weight: 600; color: #6b7280;">ID:</span>
                                <span style="color: #111827; margin-left: 0.5rem;">${data.extension_id}</span>
                            </div>
                            <div>
                                <span style="font-weight: 600; color: #6b7280;">Name:</span>
                                <span style="color: #111827; margin-left: 0.5rem;">${data.extension_name}</span>
                            </div>
                            <div>
                                <span style="font-weight: 600; color: #6b7280;">Description:</span>
                                <span style="color: #111827; margin-left: 0.5rem;">${data.description}</span>
                            </div>
                            <div>
                                <span style="font-weight: 600; color: #6b7280;">Author:</span>
                                <span style="color: #111827; margin-left: 0.5rem;">${data.author}</span>
                            </div>
                        </div>
                    </div>

                    <div style="background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 0.5rem; padding: 1.5rem; margin-bottom: 1.5rem;">
                        <h4 style="margin: 0 0 1rem 0; color: #111827; font-size: 1rem;">Capabilities (${data.capabilities.length})</h4>
                        ${data.capabilities.map(cap => `
                            <div style="padding: 0.5rem 0; border-bottom: 1px solid #e5e7eb; font-size: 0.875rem;">
                                <div style="font-weight: 600; color: #111827;">${cap.name} <span style="color: #6b7280; font-weight: 400;">(${cap.type})</span></div>
                                <div style="color: #6b7280; margin-top: 0.25rem;">${cap.description}</div>
                            </div>
                        `).join('')}
                    </div>

                    <div style="background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 0.5rem; padding: 1.5rem;">
                        <h4 style="margin: 0 0 1rem 0; color: #111827; font-size: 1rem;">Permissions (${data.permissions.length})</h4>
                        ${data.permissions.length > 0
                            ? data.permissions.map(perm => `
                                <span style="display: inline-block; padding: 0.25rem 0.75rem; background: #e0e7ff; color: #4338ca; border-radius: 0.375rem; font-size: 0.75rem; margin-right: 0.5rem; margin-bottom: 0.5rem;">
                                    ${perm}
                                </span>
                            `).join('')
                            : '<span style="color: #6b7280; font-size: 0.875rem;">No permissions required</span>'
                        }
                    </div>

                    <div style="background: #eff6ff; border: 1px solid #3b82f6; border-radius: 0.5rem; padding: 1rem; margin-top: 1.5rem;">
                        <div style="display: flex; align-items: start;">
                            <span class="material-icons md-18">info</span>
                            <div style="font-size: 0.875rem; color: #1e40af;">
                                <strong>Next Steps:</strong> After downloading, extract the ZIP and customize the handlers.py file to implement your extension logic.
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }
    }

    /**
     * Render capability item in wizard
     */
    renderCapabilityItem(cap, index, availableCapabilityTypes) {
        return `
            <div class="capability-item" data-index="${index}">
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 1rem;">
                    <h4>Capability ${index + 1}</h4>
                    <button class="btn-delete-capability" data-index="${index}">
                        <span class="material-icons md-18">delete</span>
                    </button>
                </div>

                <div class="form-group">
                    <label>Type</label>
                    <select class="capability-type" data-index="${index}">
                        ${availableCapabilityTypes.map(type => `
                            <option value="${type.id}" ${cap.type === type.id ? 'selected' : ''}>${type.name}</option>
                        `).join('')}
                    </select>
                </div>

                <div class="form-group">
                    <label>Name</label>
                    <input type="text" class="capability-name" data-index="${index}"
                        placeholder="${cap.type === 'slash_command' ? '/mycommand' : 'capability_name'}"
                        value="${cap.name}">
                </div>

                <div class="form-group">
                    <label>Description</label>
                    <input type="text" class="capability-description" data-index="${index}"
                        placeholder="What does this capability do?"
                        value="${cap.description}">
                </div>
            </div>
        `;
    }

    /**
     * Attach step-specific event listeners
     */
    attachWizardStepListeners(wizardState, availableCapabilityTypes) {
        if (wizardState.step === 2) {
            // Add capability button
            document.getElementById('btnAddCapability')?.addEventListener('click', () => {
                wizardState.data.capabilities.push({
                    type: 'slash_command',
                    name: '',
                    description: '',
                    config: {}
                });
                this.showTemplateWizard(); // Re-render
            });

            // Delete capability buttons
            document.querySelectorAll('.btn-delete-capability').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const index = parseInt(e.currentTarget.dataset.index);
                    wizardState.data.capabilities.splice(index, 1);
                    this.showTemplateWizard(); // Re-render
                });
            });
        }
    }

    /**
     * Validate wizard step before proceeding
     */
    validateWizardStep(wizardState) {
        const { step, data } = wizardState;

        if (step === 1) {
            const extensionId = document.getElementById('extensionId')?.value.trim();
            const extensionName = document.getElementById('extensionName')?.value.trim();
            const description = document.getElementById('extensionDescription')?.value.trim();
            const author = document.getElementById('extensionAuthor')?.value.trim();

            if (!extensionId || !extensionName || !description || !author) {
                this.showNotification('Please fill in all required fields', 'error');
                return false;
            }

            // Validate extension ID format
            const idPattern = /^[a-z0-9]+\.[a-z0-9]+$/;
            if (!idPattern.test(extensionId)) {
                this.showNotification('Invalid Extension ID format. Use lowercase alphanumeric with one dot (e.g., tools.myext)', 'error');
                return false;
            }

            return true;
        } else if (step === 2) {
            if (data.capabilities.length === 0) {
                this.showNotification('Please add at least one capability', 'error');
                return false;
            }

            // Validate each capability
            for (let i = 0; i < data.capabilities.length; i++) {
                const cap = data.capabilities[i];
                if (!cap.name || !cap.description) {
                    this.showNotification(`Please fill in all fields for Capability ${i + 1}`, 'error');
                    return false;
                }
            }

            return true;
        }

        return true;
    }

    /**
     * Collect data from current wizard step
     */
    collectWizardStepData(wizardState) {
        const { step, data } = wizardState;

        if (step === 1) {
            data.extension_id = document.getElementById('extensionId')?.value.trim();
            data.extension_name = document.getElementById('extensionName')?.value.trim();
            data.description = document.getElementById('extensionDescription')?.value.trim();
            data.author = document.getElementById('extensionAuthor')?.value.trim();
        } else if (step === 2) {
            // Collect capability data from form
            data.capabilities.forEach((cap, index) => {
                const typeEl = document.querySelector(`.capability-type[data-index="${index}"]`);
                const nameEl = document.querySelector(`.capability-name[data-index="${index}"]`);
                const descEl = document.querySelector(`.capability-description[data-index="${index}"]`);

                if (typeEl) cap.type = typeEl.value;
                if (nameEl) cap.name = nameEl.value.trim();
                if (descEl) cap.description = descEl.value.trim();
            });
        } else if (step === 3) {
            // Collect selected permissions
            const checkboxes = document.querySelectorAll('input[name="permission"]:checked');
            data.permissions = Array.from(checkboxes).map(cb => cb.value);
        }
    }

    /**
     * Download extension template
     */
    async downloadTemplate(data) {
        try {
            this.showNotification('Generating template...', 'info');

            const response = await fetchWithCSRF('/api/extensions/templates/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to generate template');
            }

            // Download the file
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${data.extension_id}.zip`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            this.showNotification('Template downloaded successfully!', 'success');

        } catch (error) {
            console.error('Failed to download template:', error);
            this.showNotification(`Failed to download template: ${error.message}`, 'error');
        }
    }

    // ============================================
    // L-18: Rating System (localStorage-based)
    // ============================================

    /**
     * Get extension rating from localStorage
     */
    getExtensionRating(extensionId) {
        const ratings = JSON.parse(localStorage.getItem('extension_ratings') || '{}');
        return ratings[extensionId] || 0;
    }

    /**
     * Set extension rating in localStorage
     */
    setExtensionRating(extensionId, rating) {
        const ratings = JSON.parse(localStorage.getItem('extension_ratings') || '{}');
        ratings[extensionId] = rating;
        localStorage.setItem('extension_ratings', JSON.stringify(ratings));
    }

    /**
     * Render star rating component
     */
    renderStarRating(extensionId, currentRating) {
        const stars = [];
        for (let i = 1; i <= 5; i++) {
            const filled = i <= currentRating;
            stars.push(`
                <span class="star-rating" data-ext-id="${extensionId}" data-rating="${i}"
                      style="cursor: pointer; font-size: 18px; color: ${filled ? '#fbbf24' : '#d1d5db'};">
                    ${filled ? '★' : '☆'}
                </span>
            `);
        }
        return `
            <div class="rating-container" style="display: flex; align-items: center; gap: 4px;">
                ${stars.join('')}
                <span style="font-size: 12px; color: #6b7280; margin-left: 8px;">
                    ${currentRating > 0 ? `${currentRating}/5` : 'Not rated'}
                </span>
            </div>
        `;
    }

    /**
     * Attach star rating click handlers
     */
    attachRatingHandlers() {
        document.querySelectorAll('.star-rating').forEach(star => {
            star.addEventListener('click', (e) => {
                const extensionId = e.target.dataset.extId;
                const rating = parseInt(e.target.dataset.rating);
                this.setExtensionRating(extensionId, rating);
                this.showNotification(`Rated ${rating} stars`, 'success');
                // Re-render the card to update stars
                this.loadExtensions();
            });
        });
    }

    // ============================================
    // L-19: Bulk Operations
    // ============================================

    /**
     * Toggle bulk selection mode
     */
    toggleBulkMode() {
        this.bulkModeActive = !this.bulkModeActive;
        const toolbar = document.getElementById('bulkOperationsToolbar');
        const btn = document.getElementById('btnToggleBulkMode');

        if (this.bulkModeActive) {
            toolbar.style.display = 'block';
            btn.innerHTML = '<span class="material-icons md-18">close</span> Exit Bulk Mode';
        } else {
            toolbar.style.display = 'none';
            btn.innerHTML = '<span class="material-icons md-18">checklist</span> Bulk Select';
            this.clearSelection();
        }

        // Re-render to show/hide checkboxes
        this.loadExtensions();
    }

    /**
     * Handle checkbox changes
     */
    attachCheckboxHandlers() {
        document.querySelectorAll('.bulk-select-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const extId = e.target.dataset.extId;
                if (e.target.checked) {
                    this.selectedExtensions.add(extId);
                } else {
                    this.selectedExtensions.delete(extId);
                }
                this.updateSelectedCount();
            });
        });
    }

    /**
     * Update selected count display
     */
    updateSelectedCount() {
        const countEl = document.getElementById('selectedCount');
        if (countEl) {
            countEl.textContent = `${this.selectedExtensions.size} selected`;
        }
    }

    /**
     * Select all extensions
     */
    selectAllExtensions() {
        document.querySelectorAll('.bulk-select-checkbox').forEach(checkbox => {
            checkbox.checked = true;
            this.selectedExtensions.add(checkbox.dataset.extId);
        });
        this.updateSelectedCount();
    }

    /**
     * Clear selection
     */
    clearSelection() {
        this.selectedExtensions.clear();
        document.querySelectorAll('.bulk-select-checkbox').forEach(checkbox => {
            checkbox.checked = false;
        });
        this.updateSelectedCount();
    }

    /**
     * Bulk enable extensions
     */
    async bulkEnableExtensions() {
        if (this.selectedExtensions.size === 0) {
            this.showNotification('No extensions selected', 'error');
            return;
        }

        const confirmMsg = `Enable ${this.selectedExtensions.size} extension(s)?`;
        if (!confirm(confirmMsg)) return;

        let successCount = 0;
        for (const extId of this.selectedExtensions) {
            try {
                await fetchWithCSRF(`/api/extensions/${extId}/enable`, { method: 'POST' });
                successCount++;
            } catch (error) {
                console.error(`Failed to enable ${extId}:`, error);
            }
        }

        this.showNotification(`Enabled ${successCount} extension(s)`, 'success');
        this.clearSelection();
        await this.loadExtensions();
    }

    /**
     * Bulk disable extensions
     */
    async bulkDisableExtensions() {
        if (this.selectedExtensions.size === 0) {
            this.showNotification('No extensions selected', 'error');
            return;
        }

        const confirmMsg = `Disable ${this.selectedExtensions.size} extension(s)?`;
        if (!confirm(confirmMsg)) return;

        let successCount = 0;
        for (const extId of this.selectedExtensions) {
            try {
                await fetchWithCSRF(`/api/extensions/${extId}/disable`, { method: 'POST' });
                successCount++;
            } catch (error) {
                console.error(`Failed to disable ${extId}:`, error);
            }
        }

        this.showNotification(`Disabled ${successCount} extension(s)`, 'success');
        this.clearSelection();
        await this.loadExtensions();
    }

    /**
     * Bulk uninstall extensions
     */
    async bulkUninstallExtensions() {
        if (this.selectedExtensions.size === 0) {
            this.showNotification('No extensions selected', 'error');
            return;
        }

        const confirmMsg = `Are you sure you want to uninstall ${this.selectedExtensions.size} extension(s)? This action cannot be undone.`;
        if (!confirm(confirmMsg)) return;

        let successCount = 0;
        for (const extId of this.selectedExtensions) {
            try {
                await fetchWithCSRF(`/api/extensions/${extId}`, { method: 'DELETE' });
                successCount++;
            } catch (error) {
                console.error(`Failed to uninstall ${extId}:`, error);
            }
        }

        this.showNotification(`Uninstalled ${successCount} extension(s)`, 'success');
        this.clearSelection();
        await this.loadExtensions();
    }

    // ============================================
    // L-20: Keyboard Shortcuts
    // ============================================

    /**
     * Initialize keyboard shortcuts
     */
    initKeyboardShortcuts() {
        this.keyboardHandler = (e) => {
            // Ctrl+K: Focus search
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                const searchInput = document.getElementById('extensionSearchInput');
                if (searchInput) {
                    searchInput.focus();
                    searchInput.select();
                }
            }

            // Escape: Close modal or clear search
            if (e.key === 'Escape') {
                // Check if modal is open
                const modal = document.querySelector('.modal.active');
                if (modal) {
                    const closeBtn = modal.querySelector('.modal-close');
                    if (closeBtn) closeBtn.click();
                } else {
                    // Clear search
                    const searchInput = document.getElementById('extensionSearchInput');
                    if (searchInput && searchInput.value) {
                        searchInput.value = '';
                        this.filterExtensions('');
                    }
                }
            }

            // Ctrl+R: Refresh list
            if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
                e.preventDefault();
                this.loadExtensions();
                this.showNotification('Extensions list refreshed', 'info');
            }
        };

        document.addEventListener('keydown', this.keyboardHandler);
    }

    /**
     * Remove keyboard shortcuts
     */
    removeKeyboardShortcuts() {
        if (this.keyboardHandler) {
            document.removeEventListener('keydown', this.keyboardHandler);
        }
    }

    /**
     * Filter extensions based on search query
     */
    filterExtensions(query) {
        const lowerQuery = query.toLowerCase();
        document.querySelectorAll('.extension-card').forEach(card => {
            const name = card.dataset.extName || '';
            const description = card.dataset.extDescription || '';
            const matches = name.includes(lowerQuery) || description.includes(lowerQuery);
            card.style.display = matches ? '' : 'none';
        });
    }

    // ============================================
    // L-17: Screenshot Display (in detail modal)
    // ============================================

    /**
     * Render screenshot carousel
     */
    renderScreenshotCarousel(screenshots) {
        if (!screenshots || screenshots.length === 0) {
            return '';
        }

        return `
            <div class="detail-section">
                <h2>Screenshots</h2>
                <div class="screenshot-carousel">
                    <div class="screenshot-track" id="screenshotTrack">
                        ${screenshots.map((screenshot, index) => `
                            <img src="${screenshot}" alt="Screenshot ${index + 1}"
                                 class="screenshot-image"
                                 onclick="window.extensionsView.showScreenshotFullscreen('${screenshot}')">
                        `).join('')}
                    </div>
                    ${screenshots.length > 1 ? `
                        <button class="carousel-btn carousel-prev" onclick="window.extensionsView.scrollCarousel(-1)">
                            <span class="material-icons">chevron_left</span>
                        </button>
                        <button class="carousel-btn carousel-next" onclick="window.extensionsView.scrollCarousel(1)">
                            <span class="material-icons">chevron_right</span>
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    }

    /**
     * Scroll screenshot carousel
     */
    scrollCarousel(direction) {
        const track = document.getElementById('screenshotTrack');
        if (track) {
            const scrollAmount = 320; // Width of one screenshot + gap
            track.scrollBy({ left: direction * scrollAmount, behavior: 'smooth' });
        }
    }

    /**
     * Show screenshot in fullscreen
     */
    showScreenshotFullscreen(screenshotUrl) {
        const modal = document.createElement('div');
        modal.className = 'modal active';
        modal.style.backgroundColor = 'rgba(0, 0, 0, 0.9)';
        modal.innerHTML = `
            <div class="modal-overlay" style="background: rgba(0, 0, 0, 0.9);"></div>
            <div style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); z-index: 10001; max-width: 90vw; max-height: 90vh;">
                <img src="${screenshotUrl}" style="max-width: 100%; max-height: 90vh; border-radius: 8px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);">
                <button class="modal-close" id="btnCloseScreenshot" style="position: absolute; top: -40px; right: -40px; background: white; border: none; border-radius: 50%; width: 40px; height: 40px; cursor: pointer; font-size: 24px; color: #374151; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);">&times;</button>
            </div>
        `;

        document.body.appendChild(modal);

        const closeModal = () => modal.remove();
        document.getElementById('btnCloseScreenshot').addEventListener('click', closeModal);
        modal.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal-overlay')) {
                closeModal();
            }
        });
    }
}

// Export for use in main.js
window.ExtensionsView = ExtensionsView;
