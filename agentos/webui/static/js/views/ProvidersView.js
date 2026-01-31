/**
 * Providers Management View
 *
 * Local Setup page with instance management, fingerprint detection,
 * and process lifecycle control.
 *
 * Sprint B+ WebUI Integration
 */

class ProvidersView {
    constructor(apiClient) {
        this.apiClient = apiClient;
        this.instances = [];
        this.selectedInstance = null;

        // Task #17: P0.4 - Auto-refresh configuration
        this.autoRefreshInterval = null;
        this.autoRefreshEnabled = true;  // Default to enabled
        this.autoRefreshIntervalMs = 5000;  // 5 seconds

        // Task #21: P1.8 - Debounced operations to prevent duplicate clicks
        this.debouncedOperations = new Map();
    }

    /**
     * Task #21: P1.8 - Debounce utility to prevent duplicate operations
     * @param {Function} func - Function to debounce
     * @param {number} wait - Wait time in milliseconds
     * @returns {Function} Debounced function
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func.apply(this, args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    async render() {
        return `
            <div class="providers-view">
                <div class="view-header">
                    <div>
                        <h1>Local Model Providers</h1>
                        <p class="text-sm text-gray-600 mt-1">Configure and monitor local LLM providers</p>
                    </div>
                    <div class="header-actions">
                        <label class="auto-refresh-toggle">
                            <input type="checkbox" id="auto-refresh-toggle" checked>
                            <span>Auto-refresh (5s)</span>
                        </label>
                        <button id="stop-all-instances" class="btn-warning" style="display:none">
                            <span class="material-icons md-18">stop_circle</span> Stop All
                        </button>
                        <button id="restart-all-instances" class="btn-secondary" style="display:none">
                            <span class="material-icons md-18">restart_alt</span> Restart All
                        </button>
                        <button id="refresh-all" class="btn-primary">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh All
                        </button>
                    </div>
                </div>

                <!-- Models Directory Configuration Panel -->
                <div class="models-config-panel">
                    <h2>Models Directories</h2>
                    <div id="models-directories-container">
                        <p class="loading-text">Loading configuration...</p>
                    </div>
                </div>

                <div class="providers-content">
                    <!-- Ollama Section -->
                    <div class="provider-section" data-provider="ollama">
                        <div class="section-header">
                            <h2>Ollama</h2>
                            <button class="btn-sm" data-action="add-instance" data-provider="ollama">
                                + Add Instance
                            </button>
                        </div>
                        <div class="executable-config" data-provider="ollama">
                            <h3>Executable Configuration</h3>
                            <div class="executable-path-row">
                                <input type="text"
                                       class="executable-path-input"
                                       data-provider="ollama"
                                       placeholder="Not configured"
                                       readonly>
                                <button class="btn-detect btn-sm" data-provider="ollama">
                                    <span class="material-icons md-18">search</span> Detect
                                </button>
                                <button class="btn-browse btn-sm" data-provider="ollama">
                                    <span class="material-icons md-18">folder_open</span> Browse
                                </button>
                                <button class="btn-validate btn-sm" data-provider="ollama" style="display:none">
                                    <span class="material-icons md-18">check_circle</span> Validate
                                </button>
                                <button class="btn-save btn-sm" data-provider="ollama" style="display:none">
                                    <span class="material-icons md-18">save</span> Save
                                </button>
                            </div>
                            <div class="executable-paths-info" data-provider="ollama">
                                <div class="path-info-row">
                                    <span class="path-label">Detected:</span>
                                    <span class="detected-path" data-provider="ollama">—</span>
                                </div>
                                <div class="path-info-row">
                                    <span class="path-label">Custom:</span>
                                    <span class="custom-path" data-provider="ollama">—</span>
                                </div>
                                <div class="path-info-row">
                                    <span class="path-label">Resolved:</span>
                                    <span class="resolved-path" data-provider="ollama">—</span>
                                </div>
                            </div>
                            <div class="executable-info" data-provider="ollama">
                                <span class="install-status" data-provider="ollama">Checking...</span>
                                <span class="version-info"></span>
                                <span class="platform-info"></span>
                            </div>
                            <div class="validation-message" data-provider="ollama"></div>

                        <!-- Task #19: P1.6 - Diagnostics Panel -->
                        <div class="diagnostics-section" data-provider="ollama">
                            <button class="btn-diagnostics btn-sm" data-provider="ollama">
                                <span class="material-icons md-18">assessment</span> Show Diagnostics
                            </button>
                            <div class="diagnostics-panel" data-provider="ollama" style="display:none;">
                                <div class="diagnostics-header">
                                    <strong>Diagnostics</strong>
                                    <div class="diagnostics-actions">
                                        <button class="btn-xs" data-action="health-check" data-provider="ollama" title="Run Health Check">
                                            <span class="material-icons md-18">health_and_safety</span>
                                        </button>
                                        <button class="btn-xs" data-action="copy-diagnostics" data-provider="ollama" title="Copy Diagnostics">
                                            <span class="material-icons md-18">content_copy</span>
                                        </button>
                                    </div>
                                </div>
                                <div class="diagnostics-content" data-provider="ollama">
                                    <p class="loading-text">Loading diagnostics...</p>
                                </div>
                            </div>
                        </div>

                        </div>
                        <div class="instances-container" data-provider="ollama"></div>
                    </div>

                    <!-- LM Studio Section -->
                    <div class="provider-section" data-provider="lmstudio">
                        <div class="section-header">
                            <h2>LM Studio</h2>
                            <div class="section-actions">
                                <button class="btn-sm" data-action="open-lmstudio">
                                    phone_android Open App
                                </button>
                                <button class="btn-sm" data-action="verify-lmstudio">
                                    <span class="material-icons md-18">check</span> Verify
                                </button>
                            </div>
                        </div>
                        <div class="executable-config" data-provider="lmstudio">
                            <h3>Executable Configuration</h3>
                            <div class="executable-path-row">
                                <input type="text"
                                       class="executable-path-input"
                                       data-provider="lmstudio"
                                       placeholder="Not configured"
                                       readonly>
                                <button class="btn-detect btn-sm" data-provider="lmstudio">
                                    <span class="material-icons md-18">search</span> Detect
                                </button>
                                <button class="btn-browse btn-sm" data-provider="lmstudio">
                                    <span class="material-icons md-18">folder_open</span> Browse
                                </button>
                                <button class="btn-validate btn-sm" data-provider="lmstudio" style="display:none">
                                    <span class="material-icons md-18">check_circle</span> Validate
                                </button>
                                <button class="btn-save btn-sm" data-provider="lmstudio" style="display:none">
                                    <span class="material-icons md-18">save</span> Save
                                </button>
                            </div>
                            <div class="executable-paths-info" data-provider="lmstudio">
                                <div class="path-info-row">
                                    <span class="path-label">Detected:</span>
                                    <span class="detected-path" data-provider="lmstudio">—</span>
                                </div>
                                <div class="path-info-row">
                                    <span class="path-label">Custom:</span>
                                    <span class="custom-path" data-provider="lmstudio">—</span>
                                </div>
                                <div class="path-info-row">
                                    <span class="path-label">Resolved:</span>
                                    <span class="resolved-path" data-provider="lmstudio">—</span>
                                </div>
                            </div>
                            <div class="executable-info" data-provider="lmstudio">
                                <span class="install-status" data-provider="lmstudio">Checking...</span>
                                <span class="version-info"></span>
                                <span class="platform-info"></span>
                            </div>
                            <div class="validation-message" data-provider="lmstudio"></div>

                        <!-- Task #19: P1.6 - Diagnostics Panel -->
                        <div class="diagnostics-section" data-provider="lmstudio">
                            <button class="btn-diagnostics btn-sm" data-provider="lmstudio">
                                <span class="material-icons md-18">assessment</span> Show Diagnostics
                            </button>
                            <div class="diagnostics-panel" data-provider="lmstudio" style="display:none;">
                                <div class="diagnostics-header">
                                    <strong>Diagnostics</strong>
                                    <div class="diagnostics-actions">
                                        <button class="btn-xs" data-action="health-check" data-provider="lmstudio" title="Run Health Check">
                                            <span class="material-icons md-18">health_and_safety</span>
                                        </button>
                                        <button class="btn-xs" data-action="copy-diagnostics" data-provider="lmstudio" title="Copy Diagnostics">
                                            <span class="material-icons md-18">content_copy</span>
                                        </button>
                                    </div>
                                </div>
                                <div class="diagnostics-content" data-provider="lmstudio">
                                    <p class="loading-text">Loading diagnostics...</p>
                                </div>
                            </div>
                        </div>

                        </div>
                        <div class="instances-container" data-provider="lmstudio"></div>
                    </div>

                    <!-- llamacpp Section -->
                    <div class="provider-section" data-provider="llamacpp">
                        <div class="section-header">
                            <h2>llama.cpp</h2>
                            <button class="btn-sm" data-action="add-instance" data-provider="llamacpp">
                                + Add Instance
                            </button>
                        </div>
                        <div class="executable-config" data-provider="llamacpp">
                            <h3>Executable Configuration</h3>
                            <div class="executable-path-row">
                                <input type="text"
                                       class="executable-path-input"
                                       data-provider="llamacpp"
                                       placeholder="Not configured"
                                       readonly>
                                <button class="btn-detect btn-sm" data-provider="llamacpp">
                                    <span class="material-icons md-18">search</span> Detect
                                </button>
                                <button class="btn-browse btn-sm" data-provider="llamacpp">
                                    <span class="material-icons md-18">folder_open</span> Browse
                                </button>
                                <button class="btn-validate btn-sm" data-provider="llamacpp" style="display:none">
                                    <span class="material-icons md-18">check_circle</span> Validate
                                </button>
                                <button class="btn-save btn-sm" data-provider="llamacpp" style="display:none">
                                    <span class="material-icons md-18">save</span> Save
                                </button>
                            </div>
                            <div class="executable-paths-info" data-provider="llamacpp">
                                <div class="path-info-row">
                                    <span class="path-label">Detected:</span>
                                    <span class="detected-path" data-provider="llamacpp">—</span>
                                </div>
                                <div class="path-info-row">
                                    <span class="path-label">Custom:</span>
                                    <span class="custom-path" data-provider="llamacpp">—</span>
                                </div>
                                <div class="path-info-row">
                                    <span class="path-label">Resolved:</span>
                                    <span class="resolved-path" data-provider="llamacpp">—</span>
                                </div>
                            </div>
                            <div class="executable-info" data-provider="llamacpp">
                                <span class="install-status" data-provider="llamacpp">Checking...</span>
                                <span class="version-info"></span>
                                <span class="platform-info"></span>
                            </div>
                            <div class="validation-message" data-provider="llamacpp"></div>

                        <!-- Task #19: P1.6 - Diagnostics Panel -->
                        <div class="diagnostics-section" data-provider="llamacpp">
                            <button class="btn-diagnostics btn-sm" data-provider="llamacpp">
                                <span class="material-icons md-18">assessment</span> Show Diagnostics
                            </button>
                            <div class="diagnostics-panel" data-provider="llamacpp" style="display:none;">
                                <div class="diagnostics-header">
                                    <strong>Diagnostics</strong>
                                    <div class="diagnostics-actions">
                                        <button class="btn-xs" data-action="health-check" data-provider="llamacpp" title="Run Health Check">
                                            <span class="material-icons md-18">health_and_safety</span>
                                        </button>
                                        <button class="btn-xs" data-action="copy-diagnostics" data-provider="llamacpp" title="Copy Diagnostics">
                                            <span class="material-icons md-18">content_copy</span>
                                        </button>
                                    </div>
                                </div>
                                <div class="diagnostics-content" data-provider="llamacpp">
                                    <p class="loading-text">Loading diagnostics...</p>
                                </div>
                            </div>
                        </div>

                        </div>
                        <div class="instances-container" data-provider="llamacpp"></div>
                    </div>

                    <!-- Install Section -->
                    <div class="install-section">
                        <h2>Installation</h2>
                        <div class="install-grid">
                            <div class="install-card" data-provider="ollama">
                                <h3>Ollama</h3>
                                <div class="cli-status" data-provider="ollama">
                                    <span class="status-icon"><span class="material-icons md-18">hourglass_empty</span></span>
                                    <span class="status-text">Checking...</span>
                                </div>
                                <button class="btn-install" data-provider="ollama" style="display:none">
                                    Install (brew)
                                </button>
                            </div>

                            <div class="install-card" data-provider="llamacpp">
                                <h3>llama.cpp</h3>
                                <div class="cli-status" data-provider="llamacpp">
                                    <span class="status-icon"><span class="material-icons md-18">hourglass_empty</span></span>
                                    <span class="status-text">Checking...</span>
                                </div>
                                <button class="btn-install" data-provider="llamacpp" style="display:none">
                                    Install (brew)
                                </button>
                            </div>

                            <div class="install-card" data-provider="lmstudio">
                                <h3>LM Studio</h3>
                                <div class="cli-status" data-provider="lmstudio">
                                    <span class="status-icon"><span class="material-icons md-18">hourglass_empty</span></span>
                                    <span class="status-text">Checking...</span>
                                </div>
                                <p class="install-note">Install from <a href="https://lmstudio.ai" target="_blank">lmstudio.ai</a></p>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Modals -->
                <div id="instance-modal" class="modal" style="display:none"></div>
                <div id="output-modal" class="modal" style="display:none"></div>
                <div id="model-browser-modal" class="modal" style="display:none"></div>
            </div>
        `;
    }

    async mount() {
        await this.loadInstances();
        await this.checkCLI();
        await this.loadModelsDirectories();
        await this.initExecutableConfigs();
        this.attachEventListeners();
        this.startAutoRefresh();
    }

    attachEventListeners() {
        // Task #17: P0.4 - Auto-refresh toggle
        document.getElementById('auto-refresh-toggle')?.addEventListener('change', (e) => {
            this.toggleAutoRefresh(e.target.checked);
        });

        // Refresh all
        document.getElementById('refresh-all')?.addEventListener('click', () => {
            this.refreshStatus();
        });

        // Task #21: P1.8 - Batch operations
        document.getElementById('stop-all-instances')?.addEventListener('click', () => {
            this.stopAllInstances();
        });

        document.getElementById('restart-all-instances')?.addEventListener('click', () => {
            this.restartAllInstances();
        });

        // Add instance buttons
        document.querySelectorAll('[data-action="add-instance"]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const provider = e.target.dataset.provider;
                this.showInstanceModal(provider);
            });
        });

        // LM Studio actions
        document.querySelector('[data-action="open-lmstudio"]')?.addEventListener('click', () => {
            this.openLMStudio();
        });

        document.querySelector('[data-action="verify-lmstudio"]')?.addEventListener('click', () => {
            this.verifyLMStudio();
        });

        // Install buttons
        document.querySelectorAll('.btn-install').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const provider = e.target.dataset.provider;
                this.installProvider(provider);
            });
        });

        // Executable configuration buttons
        document.querySelectorAll('.btn-detect').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const provider = e.target.closest('[data-provider]').dataset.provider;
                this.detectExecutable(provider);
            });
        });

        document.querySelectorAll('.btn-browse').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const provider = e.target.closest('[data-provider]').dataset.provider;
                this.browseExecutable(provider);
            });
        });

        // Task #21: P1.8 - Validate button event listener
        document.querySelectorAll('.btn-validate').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const provider = e.target.closest('[data-provider]').dataset.provider;
                const input = document.querySelector(`.executable-path-input[data-provider="${provider}"]`);
                if (input && input.value.trim()) {
                    this.validateExecutablePath(provider, input.value.trim());
                }
            });
        });

        document.querySelectorAll('.btn-save').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const provider = e.target.closest('[data-provider]').dataset.provider;
                this.saveExecutablePath(provider);
            });
        });

        // Task #21: P1.8 - Real-time validation on path input (show buttons)
        document.querySelectorAll('.executable-path-input').forEach(input => {
            input.addEventListener('input', (e) => {
                const provider = e.target.dataset.provider;
                const path = e.target.value.trim();

                // Task #21: P1.8 - Show validate and save buttons when input changes
                const validateBtn = document.querySelector(`.btn-validate[data-provider="${provider}"]`);
                const saveBtn = document.querySelector(`.btn-save[data-provider="${provider}"]`);

                if (validateBtn) {
                    validateBtn.style.display = path ? 'inline-flex' : 'none';
                }
                if (saveBtn) {
                    saveBtn.style.display = path ? 'inline-flex' : 'none';
                }
            });
        });

        // Instance actions (delegated)

        // Task #19: P1.6 - Diagnostics panel toggles
        document.querySelectorAll('.btn-diagnostics').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const providerId = e.currentTarget.dataset.provider;
                await this.toggleDiagnostics(providerId);
            });
        });

        // Task #19: P1.6 - Health check buttons
        document.querySelectorAll('[data-action="health-check"]').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const providerId = e.currentTarget.dataset.provider;
                await this.runHealthCheck(providerId);
            });
        });

        // Task #19: P1.6 - Copy diagnostics buttons
        document.querySelectorAll('[data-action="copy-diagnostics"]').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const providerId = e.currentTarget.dataset.provider;
                await this.copyDiagnostics(providerId);
            });
        });

        document.addEventListener('click', (e) => {
            // Find the button element (in case user clicks on icon inside button)
            const button = e.target.closest('[data-instance-action]');
            if (!button) return;

            const action = button.dataset.instanceAction;
            const instanceKey = button.dataset.instanceKey;
            const providerId = button.dataset.providerId;
            const instanceId = button.dataset.instanceId;

            switch (action) {
                case 'refresh':
                    this.refreshInstance(instanceKey);
                    break;
                case 'start':
                    this.startInstance(providerId, instanceId);
                    break;
                case 'stop':
                    this.stopInstance(providerId, instanceId);
                    break;
                case 'restart':
                    this.restartInstance(providerId, instanceId);
                    break;
                case 'output':
                    this.showOutputModal(providerId, instanceId);
                    break;
                case 'edit':
                    this.editInstance(providerId, instanceId);
                    break;
                case 'edit-routing':
                    this.editRoutingMetadata(providerId, instanceId);
                    break;
                case 'delete':
                    this.deleteInstance(providerId, instanceId);
                    break;
                case 'change-port':
                    this.changePort(providerId, instanceId);
                    break;
            }
        });
    }

    async loadInstances() {
        try {
            const response = await this.apiClient.get('/api/providers/instances');
            this.instances = response.instances;
            this.renderInstances();
        } catch (error) {
            console.error('Failed to load instances:', error);
        }
    }

    renderInstances() {
        // Group by provider
        const byProvider = {
            ollama: [],
            lmstudio: [],
            llamacpp: []
        };

        this.instances.forEach(inst => {
            if (byProvider[inst.provider_id]) {
                byProvider[inst.provider_id].push(inst);
            }
        });

        // Render each provider's instances
        Object.keys(byProvider).forEach(provider => {
            const container = document.querySelector(`.instances-container[data-provider="${provider}"]`);
            if (!container) return;

            const instances = byProvider[provider];
            if (instances.length === 0) {
                container.innerHTML = '<p class="no-instances">No instances configured</p>';
                return;
            }

            container.innerHTML = `
                <table class="instances-table">
                    <thead>
                        <tr>
                            <th>Instance ID</th>
                            <th>Endpoint</th>
                            <th>State</th>
                            <th>Fingerprint</th>
                            <th>Process</th>
                            <th>Routing Metadata</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${instances.map(inst => this.renderInstanceRow(inst)).join('')}
                    </tbody>
                </table>
            `;
        });

        // Task #21: P1.8 - Show/hide batch operation buttons based on running instances
        this.updateBatchOperationButtons();
    }

    /**
     * Task #21: P1.8 - Update batch operation buttons visibility
     */
    updateBatchOperationButtons() {
        const runningInstances = this.getAllRunningInstances();
        const stopAllBtn = document.getElementById('stop-all-instances');
        const restartAllBtn = document.getElementById('restart-all-instances');

        if (stopAllBtn) {
            stopAllBtn.style.display = runningInstances.length > 0 ? 'inline-flex' : 'none';
        }
        if (restartAllBtn) {
            restartAllBtn.style.display = runningInstances.length > 0 ? 'inline-flex' : 'none';
        }
    }

    renderInstanceRow(inst) {
        // Task #17: P0.4 - Enhanced state mapping with new states
        const stateClass = {
            'RUNNING': 'state-ready',
            'STOPPED': 'state-disconnected',
            'STARTING': 'state-starting',
            'DEGRADED': 'state-degraded',
            'ERROR': 'state-error',
            'UNKNOWN': 'state-unknown',
            // Legacy states for backward compatibility
            'READY': 'state-ready',
            'DISCONNECTED': 'state-disconnected'
        }[inst.state] || 'state-unknown';

        // Task #17: P0.4 - Enhanced process status with health check details
        let processStatus = '';
        if (inst.process_running) {
            const pidInfo = inst.pid ? ` (PID ${inst.pid})` : '';
            const healthDetails = [];
            if (inst.pid_exists !== null && inst.pid_exists !== undefined) {
                healthDetails.push(inst.pid_exists ? 'PID check' : 'PID close');
            }
            if (inst.port_listening !== null && inst.port_listening !== undefined) {
                healthDetails.push(inst.port_listening ? 'Port check' : 'Port close');
            }
            if (inst.api_responding !== null && inst.api_responding !== undefined) {
                healthDetails.push(inst.api_responding ? 'API check' : 'API close');
            }
            const healthInfo = healthDetails.length > 0 ? ` [${healthDetails.join(', ')}]` : '';
            processStatus = `<span class="process-running">Running${pidInfo}${healthInfo}</span>`;
        } else {
            processStatus = `<span class="process-stopped">Stopped</span>`;
        }

        // PR-4: Extract routing metadata
        const metadata = inst.metadata || {};
        const tags = metadata.tags || [];
        const ctx = metadata.ctx || null;
        const role = metadata.role || null;

        // Actions based on state
        let actions = `
            <button class="btn-xs" data-instance-action="refresh"
                    data-instance-key="${inst.instance_key}"><span class="material-icons md-18">refresh</span></button>
            <button class="btn-xs" data-instance-action="edit"
                    data-provider-id="${inst.provider_id}" data-instance-id="${inst.instance_id}"><span class="material-icons md-18">edit</span></button>
            <button class="btn-xs" data-instance-action="edit-routing"
                    data-provider-id="${inst.provider_id}" data-instance-id="${inst.instance_id}"
                    title="Edit routing metadata"><span class="material-icons md-18">refresh</span></button>
        `;

        // Start/Stop buttons (only for instances with launch config)
        if (inst.has_launch_config) {
            if (inst.process_running) {
                actions += `
                    <button class="btn-xs" data-instance-action="stop"
                            data-provider-id="${inst.provider_id}" data-instance-id="${inst.instance_id}"
                            title="Stop instance"><span class="material-icons md-18">stop</span></button>
                `;
            } else {
                actions += `
                    <button class="btn-xs" data-instance-action="start"
                            data-provider-id="${inst.provider_id}" data-instance-id="${inst.instance_id}"
                            title="Start instance"><span class="material-icons md-18">play_arrow</span></button>
                `;
            }
        }

        // Output log button for all instances
        actions += `
            <button class="btn-xs" data-instance-action="output"
                    data-provider-id="${inst.provider_id}" data-instance-id="${inst.instance_id}"
                    title="View logs"><span class="material-icons md-18">description</span></button>
        `;

        // Port conflict quick fix
        let errorInfo = '';
        if (inst.reason_code === 'PORT_OCCUPIED_BY_OTHER_PROVIDER') {
            errorInfo = `
                <div class="instance-error">
                    <span><span class="material-icons md-18">warning</span> ${inst.last_error}</span>
                    <button class="btn-warning btn-xs" data-instance-action="change-port"
                            data-provider-id="${inst.provider_id}" data-instance-id="${inst.instance_id}">
                        Change Port
                    </button>
                </div>
            `;
        } else if (inst.last_error) {
            errorInfo = `<div class="instance-error"><span><span class="material-icons md-18">warning</span> ${inst.last_error}</span></div>`;
        }

        // PR-4: Display routing metadata
        const tagsDisplay = tags.length > 0
            ? tags.map(t => `<span class="tag-badge">${t}</span>`).join(' ')
            : '<span class="text-muted">no tags</span>';

        const ctxDisplay = ctx
            ? `<span class="ctx-badge">${ctx}</span>`
            : '<span class="text-muted">—</span>';

        return `
            <tr class="instance-row ${stateClass}" data-instance-key="${inst.instance_key}">
                <td>${inst.instance_id}</td>
                <td>
                    <code>${inst.base_url}</code>
                    ${errorInfo}
                </td>
                <td>
                    <span class="state-badge ${stateClass}">${inst.state}</span>
                    ${inst.latency_ms ? `<span class="latency">${inst.latency_ms}ms</span>` : ''}
                </td>
                <td>
                    <span class="fingerprint-badge">${inst.detected_fingerprint || 'unknown'}</span>
                </td>
                <td>${processStatus}</td>
                <td class="routing-metadata">
                    <div class="metadata-row">
                        <label>Tags:</label>
                        <div class="metadata-value">${tagsDisplay}</div>
                    </div>
                    <div class="metadata-row">
                        <label>Ctx:</label>
                        <div class="metadata-value">${ctxDisplay}</div>
                    </div>
                    ${role ? `<div class="metadata-row"><label>Role:</label><div class="metadata-value"><span class="role-badge">${role}</span></div></div>` : ''}
                </td>
                <td class="actions">${actions}</td>
            </tr>
        `;
    }

    async checkCLI() {
        const providers = ['ollama', 'llamacpp', 'lmstudio'];

        for (const provider of providers) {
            try {
                const response = await this.apiClient.get(`/api/providers/${provider}/cli-check`);
                const statusEl = document.querySelector(`.cli-status[data-provider="${provider}"]`);
                const installBtn = document.querySelector(`.btn-install[data-provider="${provider}"]`);

                // Check if statusEl exists before accessing it
                if (!statusEl) {
                    console.warn(`CLI status element not found for provider: ${provider}`);
                    continue;
                }

                if (response.cli_found) {
                    statusEl.innerHTML = `
                        <span class="status-icon"><span class="material-icons md-18">done</span></span>
                        <span class="status-text">CLI Found</span>
                        <code class="cli-path">${response.bin_path}</code>
                    `;
                    if (installBtn) installBtn.style.display = 'none';
                } else {
                    statusEl.innerHTML = `
                        <span class="status-icon"><span class="material-icons md-18">cancel</span></span>
                        <span class="status-text">CLI Not Found</span>
                    `;
                    if (installBtn && provider !== 'lmstudio') {
                        installBtn.style.display = 'block';
                    }
                }
            } catch (error) {
                console.error(`Failed to check CLI for ${provider}:`, error);
            }
        }
    }

    showInstanceModal(provider, instance = null) {
        const modal = document.getElementById('instance-modal');
        const isEdit = instance !== null;

        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h2>${isEdit ? 'Edit' : 'Add'} ${provider} Instance</h2>
                    <button class="modal-close">&times;</button>
                </div>
                <div class="modal-body">
                    <form id="instance-form">
                        <div class="form-group">
                            <label>Instance ID</label>
                            <input type="text" name="instance_id" required
                                   value="${instance?.instance_id || ''}"
                                   ${isEdit ? 'readonly' : ''}>
                        </div>
                        <div class="form-group">
                            <label>Endpoint</label>
                            <input type="url" name="base_url" required
                                   placeholder="http://127.0.0.1:8080"
                                   value="${instance?.base_url || ''}">
                        </div>
                        ${provider === 'llamacpp' ? this.renderLaunchConfig(instance) : ''}
                        <div class="form-actions">
                            <button type="submit" class="btn-primary">Save</button>
                            <button type="button" class="btn-info" id="modal-test-btn" style="margin-right: auto;">Test Connection</button>
                            <button type="button" class="btn-secondary" id="modal-cancel-btn">Cancel</button>
                        </div>
                    </form>
                </div>
            </div>
        `;

        modal.style.display = 'flex';

        // Event listeners
        modal.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', () => modal.style.display = 'none');
        });

        // Cancel button
        const cancelBtn = modal.querySelector('#modal-cancel-btn');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => modal.style.display = 'none');
        }

        // Test button
        const testBtn = modal.querySelector('#modal-test-btn');
        if (testBtn) {
            testBtn.addEventListener('click', async () => {
                await this.testInstance(provider, document.getElementById('instance-form'));
            });
        }

        document.getElementById('instance-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.saveInstance(provider, e.target, isEdit);
        });
    }

    renderLaunchConfig(instance) {
        const launch = instance?.launch_config || {};
        const args = launch.args || {};

        return `
            <fieldset class="launch-config">
                <legend>Launch Configuration (Optional - for Start/Stop control)</legend>
                <div class="form-row">
                    <div class="form-group">
                        <label>Model Path</label>
                        <div style="display: flex; gap: 0.5rem; align-items: center;">
                            <input type="text" name="launch_model"
                                   style="flex: 1;"
                                   value="${args.model || ''}"
                                   placeholder="/path/to/model.gguf (required to start)">
                            <button type="button" class="btn-sm" id="browse-models-btn"
                                    onclick="window.providersView.showModelBrowser('llamacpp')">
                                <span class="material-icons md-18">folder_open</span> Browse
                            </button>
                        </div>
                        <small class="form-hint">Browse available model files or enter full path</small>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Host</label>
                        <input type="text" name="launch_host"
                               value="${args.host || '127.0.0.1'}">
                    </div>
                    <div class="form-group">
                        <label>Port</label>
                        <input type="number" name="launch_port"
                               value="${args.port || 8080}">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>GPU Layers (ngl)</label>
                        <input type="number" name="launch_ngl"
                               value="${args.ngl || 99}">
                    </div>
                    <div class="form-group">
                        <label>Threads</label>
                        <input type="number" name="launch_threads"
                               value="${args.threads || 8}">
                    </div>
                    <div class="form-group">
                        <label>Context Size</label>
                        <input type="number" name="launch_ctx"
                               value="${args.ctx || 8192}">
                    </div>
                </div>
                <div class="form-group">
                    <label>Extra Args</label>
                    <input type="text" name="launch_extra"
                           placeholder="--option value"
                           value="${args.extra_args || ''}">
                </div>
            </fieldset>
        `;
    }

    async testInstance(provider, form) {
        const formData = new FormData(form);
        const baseUrl = formData.get('base_url');

        if (!baseUrl) {
            Toast.error('Please enter an endpoint URL first');
            return;
        }

        const testBtn = document.getElementById('modal-test-btn');
        const originalText = testBtn.textContent;

        try {
            // Disable button and show loading state
            testBtn.disabled = true;
            testBtn.textContent = 'Testing...';

            // Record start time for latency measurement
            const startTime = Date.now();

            // Test the endpoint
            const response = await fetch(`${baseUrl}/health`, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json'
                },
                signal: AbortSignal.timeout(5000) // 5 second timeout
            });

            const latency = Date.now() - startTime;

            if (response.ok) {
                const data = await response.json();
                Toast.success(`Connection successful (${latency}ms)`);

                // Show additional info if available
                if (data.model) {
                    console.log('Model info:', data.model);
                }
            } else {
                Toast.error(`Connection failed: ${response.status} ${response.statusText}`);
            }
        } catch (error) {
            if (error.name === 'TimeoutError') {
                Toast.error('Connection timeout (>5s)');
            } else if (error.message.includes('Failed to fetch')) {
                Toast.error('Cannot reach endpoint. Check URL and network.');
            } else {
                Toast.error(`Test failed: ${error.message}`);
            }
        } finally {
            // Restore button state
            testBtn.disabled = false;
            testBtn.textContent = originalText;
        }
    }

    async saveInstance(provider, form, isEdit) {
        const formData = new FormData(form);
        const data = {
            instance_id: formData.get('instance_id'),
            base_url: formData.get('base_url'),
            enabled: true,
            metadata: {}
        };

        // Add launch config for llamacpp (always include to enable Start/Stop buttons)
        if (provider === 'llamacpp') {
            const modelPath = formData.get('launch_model') || '';
            const host = formData.get('launch_host') || '127.0.0.1';
            const port = parseInt(formData.get('launch_port')) || 8080;
            const ngl = parseInt(formData.get('launch_ngl')) || 99;
            const threads = parseInt(formData.get('launch_threads')) || 8;
            const ctx = parseInt(formData.get('launch_ctx')) || 8192;

            data.launch = {
                bin: 'llama-server',
                args: {
                    model: modelPath,
                    host: host,
                    port: port,
                    ngl: ngl,
                    threads: threads,
                    ctx: ctx
                }
            };

            const extraArgs = formData.get('launch_extra');
            if (extraArgs) {
                data.launch.args.extra_args = extraArgs;
            }
        }

        try {
            if (isEdit) {
                await this.apiClient.put(`/api/providers/instances/${provider}/${data.instance_id}`, data);
            } else {
                await this.apiClient.post(`/api/providers/instances/${provider}`, data);
            }

            Toast.success(`Instance ${provider}:${data.instance_id} saved successfully`);
            document.getElementById('instance-modal').style.display = 'none';
            await this.loadInstances();
        } catch (error) {
            console.error('Failed to save instance:', error);
            this.handleProviderError(error, `saving ${provider} instance`, provider);
        }
    }

    showOutputModal(providerId, instanceId) {
        const modal = document.getElementById('output-modal');
        modal.innerHTML = `
            <div class="modal-content output-modal">
                <div class="modal-header">
                    <h2>Process Output: ${providerId}:${instanceId}</h2>
                    <button class="modal-close">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="output-controls">
                        <select id="output-lines">
                            <option value="50">Last 50 lines</option>
                            <option value="200" selected>Last 200 lines</option>
                            <option value="1000">Last 1000 lines</option>
                        </select>
                        <input type="text" id="output-search" placeholder="Search...">
                        <button id="output-copy" class="btn-sm"><span class="material-icons md-18">content_copy</span> Copy</button>
                    </div>
                    <div class="output-tabs">
                        <button class="tab-btn active" data-stream="stdout">stdout</button>
                        <button class="tab-btn" data-stream="stderr">stderr</button>
                    </div>
                    <pre id="output-content" class="output-content">Loading...</pre>
                </div>
            </div>
        `;

        modal.style.display = 'flex';

        modal.querySelector('.modal-close').addEventListener('click', () => {
            modal.style.display = 'none';
        });

        this.loadOutput(providerId, instanceId, 'stdout', 200);

        // Tab switching
        modal.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                modal.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                const stream = e.target.dataset.stream;
                const lines = document.getElementById('output-lines').value;
                this.loadOutput(providerId, instanceId, stream, parseInt(lines));
            });
        });

        // Lines change
        document.getElementById('output-lines').addEventListener('change', (e) => {
            const stream = modal.querySelector('.tab-btn.active').dataset.stream;
            this.loadOutput(providerId, instanceId, stream, parseInt(e.target.value));
        });

        // Search
        document.getElementById('output-search').addEventListener('input', (e) => {
            this.filterOutput(e.target.value);
        });

        // Copy
        document.getElementById('output-copy').addEventListener('click', () => {
            const content = document.getElementById('output-content').textContent;
            navigator.clipboard.writeText(content);
        });
    }

    async loadOutput(providerId, instanceId, stream, lines) {
        try {
            const response = await this.apiClient.get(
                `/api/providers/${providerId}/instances/${instanceId}/output?lines=${lines}`
            );

            const content = stream === 'stdout' ? response.stdout : response.stderr;
            document.getElementById('output-content').textContent = content.join('\n') || '(empty)';
        } catch (error) {
            document.getElementById('output-content').textContent = `Error: ${error.message}`;
        }
    }

    filterOutput(query) {
        const content = document.getElementById('output-content');
        const lines = content.textContent.split('\n');

        if (!query) {
            content.textContent = lines.join('\n');
            return;
        }

        const filtered = lines.filter(line => line.toLowerCase().includes(query.toLowerCase()));
        content.textContent = filtered.join('\n');
    }

    async startInstance(providerId, instanceId) {
        // Task #21: P1.8 - Enhanced button state management
        const instanceKey = `${providerId}:${instanceId}`;
        const button = document.querySelector(`button[data-action="start-instance"][data-instance-key="${instanceKey}"]`);

        if (!button) {
            console.warn(`Start button not found for ${instanceKey}`);
        }

        const originalContent = button ? button.innerHTML : '';

        try {
            // Task #21: P1.8 - Show loading state
            if (button) {
                button.disabled = true;
                button.innerHTML = '<span class="btn-spinner"></span> Starting...';
            }

            await this.apiClient.post(`/api/providers/${providerId}/instances/start`, {
                instance_id: instanceId
            });
            Toast.success(`Instance ${providerId}:${instanceId} started successfully`);

            // Task #21: P1.8 - Auto-refresh after 1s delay
            setTimeout(() => this.refreshStatus(), 1000);
        } catch (error) {
            console.error('Failed to start instance:', error);
            this.handleProviderError(error, `starting ${providerId} instance`, providerId);
        } finally {
            // Task #21: P1.8 - Restore button state
            if (button) {
                button.disabled = false;
                button.innerHTML = originalContent || '<span class="material-icons md-18">play_arrow</span> Start';
            }
        }
    }

    async stopInstance(providerId, instanceId) {
        // Task #21: P1.8 - Confirmation dialog for destructive operation
        const confirmed = await Dialog.confirm(
            `Are you sure you want to stop ${providerId} instance?<br><br>This will terminate the running process.`,
            {
                title: 'Stop Instance',
                confirmText: 'Stop',
                danger: true
            }
        );

        if (!confirmed) {
            return;
        }

        // Task #21: P1.8 - Enhanced button state management
        const instanceKey = `${providerId}:${instanceId}`;
        const button = document.querySelector(`button[data-action="stop-instance"][data-instance-key="${instanceKey}"]`);

        const originalContent = button ? button.innerHTML : '';

        try {
            // Task #21: P1.8 - Show loading state
            if (button) {
                button.disabled = true;
                button.innerHTML = '<span class="btn-spinner"></span> Stopping...';
            }

            await this.apiClient.post(`/api/providers/${providerId}/instances/stop`, {
                instance_id: instanceId
            });
            Toast.success(`Instance ${providerId}:${instanceId} stopped successfully`);

            // Task #21: P1.8 - Auto-refresh after 1s delay
            setTimeout(() => this.refreshStatus(), 1000);
        } catch (error) {
            console.error('Failed to stop instance:', error);
            this.handleProviderError(error, `stopping ${providerId} instance`, providerId);
        } finally {
            // Task #21: P1.8 - Restore button state
            if (button) {
                button.disabled = false;
                button.innerHTML = originalContent || '<span class="material-icons md-18">stop</span> Stop';
            }
        }
    }

    async restartInstance(providerId, instanceId) {
        // Task #21: P1.8 - Confirmation dialog for destructive operation
        const confirmed = await Dialog.confirm(
            `Are you sure you want to restart ${providerId} instance?<br><br>This will stop and restart the running process.`,
            {
                title: 'Restart Instance',
                confirmText: 'Restart',
                danger: true
            }
        );

        if (!confirmed) {
            return;
        }

        // Task #16: Use dedicated restart endpoint for proper lifecycle management
        const instanceKey = `${providerId}:${instanceId}`;
        const row = document.querySelector(`tr[data-instance-key="${instanceKey}"]`);
        const button = document.querySelector(`button[data-action="restart-instance"][data-instance-key="${instanceKey}"]`);

        const originalContent = button ? button.innerHTML : '';

        try {
            // Task #21: P1.8 - Show loading state
            if (row) {
                row.classList.add('restarting');
            }
            if (button) {
                button.disabled = true;
                button.innerHTML = '<span class="btn-spinner"></span> Restarting...';
            }

            const response = await this.apiClient.post(`/api/providers/${providerId}/instances/restart`, {
                instance_id: instanceId,
                force: false
            });

            if (response.ok) {
                Toast.success(`Instance restarted: old PID ${response.old_pid || 'N/A'}, new PID ${response.new_pid || 'N/A'}`);

                // Task #21: P1.8 - Auto-refresh after 1s delay for service startup
                setTimeout(() => this.refreshStatus(), 1000);
            } else {
                Toast.error(`Failed to restart: ${response.message}`);
            }
        } catch (error) {
            console.error('Failed to restart instance:', error);
            this.handleProviderError(error, 'restarting instance', providerId);
        } finally {
            // Task #21: P1.8 - Restore button state
            if (row) {
                row.classList.remove('restarting');
            }
            if (button) {
                button.disabled = false;
                button.innerHTML = originalContent || '<span class="material-icons md-18">restart_alt</span> Restart';
            }
        }
    }

    /**
     * Task #21: P1.8 - Batch operation: Stop all running instances
     */
    async stopAllInstances() {
        const runningInstances = this.getAllRunningInstances();

        if (runningInstances.length === 0) {
            Toast.info('No running instances to stop');
            return;
        }

        // Confirmation dialog
        const confirmed = await Dialog.confirm(
            `Are you sure you want to stop ${runningInstances.length} running instance(s)?<br><br>` +
            runningInstances.map(i => `• ${i.providerId}:${i.instanceId}`).join('<br>'),
            {
                title: 'Stop All Instances',
                confirmText: 'Stop All',
                danger: true
            }
        );

        if (!confirmed) {
            return;
        }

        const stopBtn = document.getElementById('stop-all-instances');
        const originalContent = stopBtn ? stopBtn.innerHTML : '';

        try {
            if (stopBtn) {
                stopBtn.disabled = true;
                stopBtn.innerHTML = '<span class="btn-spinner"></span> Stopping...';
            }

            let successCount = 0;
            let failCount = 0;

            for (const instance of runningInstances) {
                try {
                    await this.apiClient.post(`/api/providers/${instance.providerId}/instances/stop`, {
                        instance_id: instance.instanceId
                    });
                    successCount++;
                } catch (error) {
                    console.error(`Failed to stop ${instance.providerId}:${instance.instanceId}:`, error);
                    failCount++;
                }
            }

            if (successCount > 0) {
                Toast.success(`Stopped ${successCount} instance(s)` + (failCount > 0 ? `, ${failCount} failed` : ''));
            }
            if (failCount > 0 && successCount === 0) {
                Toast.error(`Failed to stop ${failCount} instance(s)`);
            }

            // Auto-refresh after 1s
            setTimeout(() => this.refreshStatus(), 1000);
        } finally {
            if (stopBtn) {
                stopBtn.disabled = false;
                stopBtn.innerHTML = originalContent || '<span class="material-icons md-18">stop_circle</span> Stop All';
            }
        }
    }

    /**
     * Task #21: P1.8 - Batch operation: Restart all running instances
     */
    async restartAllInstances() {
        const runningInstances = this.getAllRunningInstances();

        if (runningInstances.length === 0) {
            Toast.info('No running instances to restart');
            return;
        }

        // Confirmation dialog
        const confirmed = await Dialog.confirm(
            `Are you sure you want to restart ${runningInstances.length} running instance(s)?<br><br>` +
            runningInstances.map(i => `• ${i.providerId}:${i.instanceId}`).join('<br>'),
            {
                title: 'Restart All Instances',
                confirmText: 'Restart All',
                danger: true
            }
        );

        if (!confirmed) {
            return;
        }

        const restartBtn = document.getElementById('restart-all-instances');
        const originalContent = restartBtn ? restartBtn.innerHTML : '';

        try {
            if (restartBtn) {
                restartBtn.disabled = true;
                restartBtn.innerHTML = '<span class="btn-spinner"></span> Restarting...';
            }

            let successCount = 0;
            let failCount = 0;

            for (const instance of runningInstances) {
                try {
                    await this.apiClient.post(`/api/providers/${instance.providerId}/instances/restart`, {
                        instance_id: instance.instanceId,
                        force: false
                    });
                    successCount++;
                } catch (error) {
                    console.error(`Failed to restart ${instance.providerId}:${instance.instanceId}:`, error);
                    failCount++;
                }
            }

            if (successCount > 0) {
                Toast.success(`Restarted ${successCount} instance(s)` + (failCount > 0 ? `, ${failCount} failed` : ''));
            }
            if (failCount > 0 && successCount === 0) {
                Toast.error(`Failed to restart ${failCount} instance(s)`);
            }

            // Auto-refresh after 1s
            setTimeout(() => this.refreshStatus(), 1000);
        } finally {
            if (restartBtn) {
                restartBtn.disabled = false;
                restartBtn.innerHTML = originalContent || '<span class="material-icons md-18">restart_alt</span> Restart All';
            }
        }
    }

    /**
     * Task #21: P1.8 - Helper method to get all running instances
     */
    getAllRunningInstances() {
        const runningInstances = [];

        for (const instance of this.instances) {
            if (instance.status === 'RUNNING' || instance.status === 'running') {
                runningInstances.push({
                    providerId: instance.provider_id,
                    instanceId: instance.instance_id
                });
            }
        }

        return runningInstances;
    }

    async openLMStudio() {
        try {
            await this.apiClient.post('/api/providers/lmstudio/open-app');
            Toast.success('Opening LM Studio...');
        } catch (error) {
            console.error('Failed to open LM Studio:', error);
            this.handleProviderError(error, 'opening LM Studio', 'lmstudio');
        }
    }

    async verifyLMStudio() {
        await this.refreshInstance('lmstudio');
    }

    async installProvider(provider) {
        const btn = document.querySelector(`.btn-install[data-provider="${provider}"]`);
        try {
            btn.disabled = true;
            btn.textContent = 'Installing...';

            await this.apiClient.post(`/api/providers/${provider}/install`);

            btn.innerHTML = 'Installed <span class="material-icons md-18">check</span>';
            Toast.success(`${provider} installed successfully`);
            await this.checkCLI();
        } catch (error) {
            console.error(`Failed to install ${provider}:`, error);
            if (btn) {
                btn.disabled = false;
                btn.textContent = 'Install (brew)';
            }
            this.handleProviderError(error, `installing ${provider}`, provider);
        }
    }

    async refreshInstance(instanceKey) {
        await this.loadInstances();
    }

    async editInstance(providerId, instanceId) {
        try {
            const response = await this.apiClient.get(`/api/providers/instances/${providerId}/${instanceId}`);
            // Convert config to instance format
            const instance = {
                provider_id: providerId,
                instance_id: response.config.instance_id,
                base_url: response.config.base_url,
                launch_config: response.config.launch
            };
            this.showInstanceModal(providerId, instance);
        } catch (error) {
            Dialog.alert('Failed to load instance: ' + error.message, { title: 'Load Error' });
        }
    }

    async deleteInstance(providerId, instanceId) {
        const confirmed = await Dialog.confirm(`Delete instance ${providerId}:${instanceId}?`, {
            title: 'Delete Instance',
            confirmText: 'Delete',
            danger: true
        });
        if (!confirmed) return;

        try {
            await this.apiClient.delete(`/api/providers/instances/${providerId}/${instanceId}`);
            await this.loadInstances();
        } catch (error) {
            Dialog.alert('Failed to delete: ' + error.message, { title: 'Delete Error' });
        }
    }

    changePort(providerId, instanceId) {
        // Open edit modal with port field focused
        this.editInstance(providerId, instanceId);
        setTimeout(() => {
            const portInput = document.querySelector('input[name="launch_port"]');
            if (portInput) portInput.focus();
        }, 100);
    }

    async editRoutingMetadata(providerId, instanceId) {
        try {
            const response = await this.apiClient.get(`/api/providers/instances/${providerId}/${instanceId}`);
            const instance = {
                provider_id: providerId,
                instance_id: response.config.instance_id,
                base_url: response.config.base_url,
                metadata: response.config.metadata || {}
            };
            this.showRoutingMetadataModal(instance);
        } catch (error) {
            Dialog.alert('Failed to load instance: ' + error.message, { title: 'Load Error' });
        }
    }

    showRoutingMetadataModal(instance) {
        const modal = document.getElementById('instance-modal');
        const metadata = instance.metadata || {};
        const tags = (metadata.tags || []).join(', ');
        const ctx = metadata.ctx || '';
        const role = metadata.role || '';

        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h2>Edit Routing Metadata: ${instance.instance_id}</h2>
                    <button class="modal-close">&times;</button>
                </div>
                <div class="modal-body">
                    <form id="routing-metadata-form">
                        <div class="form-group">
                            <label>Tags (comma-separated)</label>
                            <input type="text" name="tags"
                                   placeholder="e.g., coding, big_ctx, local"
                                   value="${tags}">
                            <small class="form-hint">Examples: coding, fast, big_ctx, local, vision</small>
                        </div>
                        <div class="form-group">
                            <label>Context Length (ctx)</label>
                            <input type="number" name="ctx"
                                   placeholder="e.g., 8192"
                                   value="${ctx}">
                            <small class="form-hint">Maximum context window size</small>
                        </div>
                        <div class="form-group">
                            <label>Role</label>
                            <input type="text" name="role"
                                   placeholder="e.g., coding, general, fast"
                                   value="${role}">
                            <small class="form-hint">Primary use case for this instance</small>
                        </div>
                        <div class="form-actions">
                            <button type="submit" class="btn-primary">Save Routing Metadata</button>
                            <button type="button" class="btn-secondary" id="modal-cancel-routing-btn">Cancel</button>
                        </div>
                    </form>
                </div>
            </div>
        `;

        modal.style.display = 'flex';

        modal.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', () => modal.style.display = 'none');
        });

        // Cancel button
        const cancelBtn = modal.querySelector('#modal-cancel-routing-btn');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => modal.style.display = 'none');
        }

        document.getElementById('routing-metadata-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.saveRoutingMetadata(instance.provider_id, instance.instance_id, e.target);
        });
    }

    async saveRoutingMetadata(providerId, instanceId, form) {
        const formData = new FormData(form);

        // Parse tags (comma-separated)
        const tagsStr = formData.get('tags').trim();
        const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()).filter(t => t) : [];

        // Parse ctx (optional)
        const ctxStr = formData.get('ctx').trim();
        const ctx = ctxStr ? parseInt(ctxStr) : null;

        // Parse role (optional)
        const role = formData.get('role').trim() || null;

        try {
            // Fetch current config first
            const current = await this.apiClient.get(`/api/providers/instances/${providerId}/${instanceId}`);

            // Update only metadata
            const updatedConfig = {
                ...current.config,
                metadata: {
                    ...(current.config.metadata || {}),
                    tags: tags,
                    ctx: ctx,
                    role: role
                }
            };

            await this.apiClient.put(`/api/providers/instances/${providerId}/${instanceId}`, updatedConfig);

            document.getElementById('instance-modal').style.display = 'none';
            await this.loadInstances();

            // Show success toast if available
            if (window.showToast) {
                window.showToast('Routing metadata updated', 'success');
            }
        } catch (error) {
            Dialog.alert('Failed to save routing metadata: ' + error.message, { title: 'Save Error' });
        }
    }

    async initExecutableConfigs() {
        const providers = ['ollama', 'llamacpp', 'lmstudio'];

        for (const provider of providers) {
            try {
                await this.detectExecutable(provider);
                await this.loadProviderCapabilities(provider);
            } catch (error) {
                console.error(`Failed to initialize executable config for ${provider}:`, error);
            }
        }
    }

    async loadProviderCapabilities(providerId) {
        try {
            const response = await this.apiClient.get(`/api/providers/${providerId}/capabilities`);

            // Create or update supported actions display
            const configSection = document.querySelector(`.executable-config[data-provider="${providerId}"]`);
            if (!configSection) return;

            // Check if actions display already exists
            let actionsDisplay = configSection.querySelector('.supported-actions-display');
            if (!actionsDisplay) {
                // Create new display
                actionsDisplay = document.createElement('div');
                actionsDisplay.className = 'supported-actions-display';
                configSection.appendChild(actionsDisplay);
            }

            // Render supported actions
            const actionIcons = {
                'start': 'play_arrow',
                'stop': 'stop',
                'restart': 'restart_alt',
                'open_app': 'open_in_new',
                'detect': 'search'
            };

            const actionLabels = {
                'start': 'Start',
                'stop': 'Stop',
                'restart': 'Restart',
                'open_app': 'Open App',
                'detect': 'Detect'
            };

            const allActions = ['start', 'stop', 'restart', 'open_app', 'detect'];

            const actionsHTML = allActions.map(action => {
                const supported = response.supported_actions.includes(action);
                const icon = actionIcons[action] || 'help';
                const label = actionLabels[action] || action;
                const statusIcon = supported ? 'check_circle' : 'cancel';

                return `
                    <span class="action-badge ${supported ? 'supported' : 'unsupported'}"
                          title="${supported ? 'Supported' : 'Not supported'}">
                        <span class="material-icons md-18">${icon}</span>
                        ${label} ${statusIcon}
                    </span>
                `;
            }).join('');

            actionsDisplay.innerHTML = `
                <h4>Supported Actions</h4>
                <div class="actions-matrix">
                    ${actionsHTML}
                </div>
                ${response.manual_lifecycle ? '<p class="manual-lifecycle-note">warning This provider requires manual app management</p>' : ''}
            `;

        } catch (error) {
            console.error(`Failed to load capabilities for ${providerId}:`, error);
        }
    }

    async detectExecutable(providerId) {
        const input = document.querySelector(`.executable-path-input[data-provider="${providerId}"]`);
        const statusEl = document.querySelector(`.install-status[data-provider="${providerId}"]`);
        const versionEl = document.querySelector(`.executable-info[data-provider="${providerId}"] .version-info`);
        const platformEl = document.querySelector(`.executable-info[data-provider="${providerId}"] .platform-info`);
        const validationEl = document.querySelector(`.validation-message[data-provider="${providerId}"]`);
        const detectBtn = document.querySelector(`.btn-detect[data-provider="${providerId}"]`);

        // New: Get path info elements
        const detectedPathEl = document.querySelector(`.detected-path[data-provider="${providerId}"]`);
        const customPathEl = document.querySelector(`.custom-path[data-provider="${providerId}"]`);
        const resolvedPathEl = document.querySelector(`.resolved-path[data-provider="${providerId}"]`);

        if (!input || !statusEl) return;

        try {
            // Show loading state
            if (detectBtn) {
                detectBtn.disabled = true;
                detectBtn.innerHTML = '<span class="material-icons md-18">hourglass_empty</span> Detecting...';
            }
            statusEl.textContent = 'Detecting...';
            statusEl.className = 'install-status';

            // Call detect API
            const response = await this.apiClient.get(`/api/providers/${providerId}/executable/detect`);

            // Update path info display (new fields)
            if (detectedPathEl) {
                detectedPathEl.textContent = response.path || '—';
                detectedPathEl.title = response.path || '';
            }
            if (customPathEl) {
                customPathEl.textContent = response.custom_path || '—';
                customPathEl.title = response.custom_path || '';
            }
            if (resolvedPathEl) {
                resolvedPathEl.textContent = response.resolved_path || '—';
                resolvedPathEl.title = response.resolved_path || '';

                // Add source badge
                if (response.detection_source) {
                    const sourceBadge = document.createElement('span');
                    sourceBadge.className = `source-badge source-${response.detection_source}`;
                    sourceBadge.textContent = response.detection_source;
                    sourceBadge.title = {
                        'config': 'Using custom configured path',
                        'standard': 'Found in standard installation path',
                        'path': 'Found in system PATH'
                    }[response.detection_source] || '';
                    resolvedPathEl.appendChild(document.createTextNode(' '));
                    resolvedPathEl.appendChild(sourceBadge);
                }
            }

            if (response.detected && response.resolved_path) {
                // Found
                input.value = response.resolved_path;
                input.readOnly = true;

                statusEl.textContent = 'check_circle Installed';
                statusEl.className = 'install-status installed';

                if (versionEl && response.version) {
                    versionEl.textContent = `Version: ${response.version}`;
                }

                if (platformEl && response.platform) {
                    platformEl.textContent = `Platform: ${response.platform}`;
                }

                if (validationEl) {
                    validationEl.textContent = '';
                    validationEl.className = 'validation-message';
                }

                Toast.success(`${providerId} executable detected at: ${response.resolved_path}`);
            } else {
                // Not found
                input.value = '';
                input.readOnly = false;
                input.placeholder = 'Not found - enter path manually';

                statusEl.textContent = 'warning Not found';
                statusEl.className = 'install-status not-found';

                if (versionEl) versionEl.textContent = '';
                if (platformEl && response.platform) {
                    platformEl.textContent = `Platform: ${response.platform}`;
                }

                if (validationEl && response.search_paths) {
                    validationEl.textContent = `Searched: ${response.search_paths.join(', ')}`;
                    validationEl.className = 'validation-message info';
                }

                Toast.warning(`${providerId} executable not found. Please install or configure path manually.`);
            }
        } catch (error) {
            console.error(`Failed to detect executable for ${providerId}:`, error);

            statusEl.textContent = 'cancel Error';
            statusEl.className = 'install-status error';

            if (validationEl) {
                validationEl.textContent = `Detection failed: ${error.message}`;
                validationEl.className = 'validation-message error';
            }

            this.handleProviderError(error, `detecting ${providerId} executable`, providerId);
        } finally {
            // Restore button state
            if (detectBtn) {
                detectBtn.disabled = false;
                detectBtn.innerHTML = '<span class="material-icons md-18">search</span> Detect';
            }
        }
    }

    browseExecutable(providerId) {
        // Create a file input element
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.style.display = 'none';

        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                const input = document.querySelector(`.executable-path-input[data-provider="${providerId}"]`);
                if (input) {
                    input.value = file.path || file.name;
                    input.readOnly = false;

                    // Show save button
                    const saveBtn = document.querySelector(`.btn-save[data-provider="${providerId}"]`);
                    if (saveBtn) {
                        saveBtn.style.display = 'inline-flex';
                    }

                    // Validate the selected path
                    this.validateExecutablePath(providerId, input.value);
                }
            }
            document.body.removeChild(fileInput);
        });

        document.body.appendChild(fileInput);
        fileInput.click();
    }

    async validateExecutablePath(providerId, path) {
        // Task #21: P1.8 - Enhanced validation with button state management
        const validationEl = document.querySelector(`.validation-message[data-provider="${providerId}"]`);
        const validateBtn = document.querySelector(`.btn-validate[data-provider="${providerId}"]`);

        if (!validationEl) return { is_valid: false };

        if (!path || path.trim() === '') {
            validationEl.textContent = '';
            validationEl.className = 'validation-message';
            return { is_valid: false };
        }

        const originalBtnContent = validateBtn ? validateBtn.innerHTML : '';

        try {
            // Task #21: P1.8 - Show validating state on button
            if (validateBtn) {
                validateBtn.disabled = true;
                validateBtn.innerHTML = '<span class="btn-spinner"></span> Validating...';
            }

            // Show validating state
            validationEl.textContent = 'hourglass_empty Validating...';
            validationEl.className = 'validation-message validating';

            // Call validate API
            const response = await this.apiClient.post(
                `/api/providers/${providerId}/executable/validate`,
                { path: path }
            );

            if (response.is_valid) {
                // Valid
                validationEl.textContent = 'check Valid executable';
                validationEl.className = 'validation-message valid';

                // Update version info if available
                const versionEl = document.querySelector(`.executable-info[data-provider="${providerId}"] .version-info`);
                if (versionEl && response.version) {
                    versionEl.textContent = `Version: ${response.version}`;
                }

                Toast.success(`${providerId} executable validated successfully`);
                return { is_valid: true, version: response.version };
            } else {
                // Invalid
                validationEl.textContent = `close ${response.error || 'Invalid executable'}`;
                validationEl.className = 'validation-message invalid';

                Toast.error(`Validation failed: ${response.error || 'Invalid executable'}`);
                return { is_valid: false, error: response.error };
            }
        } catch (error) {
            console.error(`Failed to validate executable path for ${providerId}:`, error);
            validationEl.textContent = `close Validation failed: ${error.message}`;
            validationEl.className = 'validation-message invalid';

            Toast.error(`Validation failed: ${error.message}`);
            return { is_valid: false, error: error.message };
        } finally {
            // Task #21: P1.8 - Restore button state
            if (validateBtn) {
                validateBtn.disabled = false;
                validateBtn.innerHTML = originalBtnContent || '<span class="material-icons md-18">check_circle</span> Validate';
            }
        }
    }

    async saveExecutablePath(providerId) {
        const input = document.querySelector(`.executable-path-input[data-provider="${providerId}"]`);
        const saveBtn = document.querySelector(`.btn-save[data-provider="${providerId}"]`);

        if (!input) return;

        const path = input.value.trim();

        // Task #21: P1.8 - Validate before saving
        if (path) {
            const validationResult = await this.validateExecutablePath(providerId, path);
            if (!validationResult.is_valid) {
                Toast.error('Please fix validation errors before saving');
                return;
            }
        }

        try {
            // Task #21: P1.8 - Show saving state
            if (saveBtn) {
                saveBtn.disabled = true;
                saveBtn.innerHTML = '<span class="btn-spinner"></span> Saving...';
            }

            // Determine if we're setting a custom path or enabling auto-detect
            const requestData = path
                ? { path: path, auto_detect: false }
                : { path: null, auto_detect: true };

            // Call save API
            const response = await this.apiClient.put(
                `/api/providers/${providerId}/executable`,
                requestData
            );

            if (response.success) {
                // Update UI
                if (response.path) {
                    input.value = response.path;
                    input.readOnly = true;

                    const statusEl = document.querySelector(`.install-status[data-provider="${providerId}"]`);
                    if (statusEl) {
                        statusEl.textContent = response.auto_detect ? 'check_circle Installed' : 'build Custom path';
                        statusEl.className = 'install-status ' + (response.auto_detect ? 'installed' : 'custom');
                    }

                    const versionEl = document.querySelector(`.executable-info[data-provider="${providerId}"] .version-info`);
                    if (versionEl && response.version) {
                        versionEl.textContent = `Version: ${response.version}`;
                    }

                    const validationEl = document.querySelector(`.validation-message[data-provider="${providerId}"]`);
                    if (validationEl) {
                        validationEl.textContent = '';
                        validationEl.className = 'validation-message';
                    }

                    Toast.success(`${providerId} executable path saved successfully`);
                } else {
                    Toast.warning(`${providerId} executable not found after saving`);
                }

                // Hide save button
                if (saveBtn) {
                    saveBtn.style.display = 'none';
                }

                // Task #21: P1.8 - Auto-refresh after save
                setTimeout(() => this.refreshStatus(), 1000);
            }
        } catch (error) {
            console.error(`Failed to save executable path for ${providerId}:`, error);
            this.handleProviderError(error, `saving ${providerId} executable path`, providerId);
        } finally {
            // Task #21: P1.8 - Restore button state
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.innerHTML = '<span class="material-icons md-18">save</span> Save';
            }
        }
    }

    /**
     * Task #17: P0.4 - Enhanced auto-refresh with configurable toggle
     *
     * Start auto-refresh timer if enabled. Refreshes provider status every 5s.
     */
    startAutoRefresh() {
        if (!this.autoRefreshEnabled) {
            return;
        }

        // Clear existing interval if any
        this.stopAutoRefresh();

        // Start new interval
        this.autoRefreshInterval = setInterval(() => {
            this.refreshStatus();
        }, this.autoRefreshIntervalMs);

        console.log(`Auto-refresh started (interval: ${this.autoRefreshIntervalMs}ms)`);
    }

    /**
     * Task #17: P0.4 - Stop auto-refresh timer
     */
    stopAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
            console.log('Auto-refresh stopped');
        }
    }

    /**
     * Task #17: P0.4 - Toggle auto-refresh on/off
     */
    toggleAutoRefresh(enabled) {
        this.autoRefreshEnabled = enabled;

        if (enabled) {
            this.startAutoRefresh();
        } else {
            this.stopAutoRefresh();
        }
    }

    /**
     * Task #17: P0.4 - Manual status refresh
     * Task #22: P0.4补充 - Updated to use /refresh endpoint
     *
     * Refreshes provider status immediately (bypasses cache if needed).
     */
    async refreshStatus() {
        try {
            // 触发后端Refresh（清除缓存）
            await this.apiClient.post('/api/providers/refresh');

            // 1seconds后重新获取Status（让后端有Time重新探测）
            setTimeout(async () => {
                await this.loadInstances();
            }, 1000);
        } catch (error) {
            console.error('Failed to refresh status:', error);
            Toast.error('Failed to refresh status');
        }
    }

    // ============================================================================
    // Models Directory Management
    // ============================================================================

    async loadModelsDirectories() {
        try {
            const response = await this.apiClient.get('/api/providers/models/directories');
            await this.renderModelsDirectories(response);
        } catch (error) {
            console.error('Failed to load models directories:', error);
            document.getElementById('models-directories-container').innerHTML = `
                <p class="error-text">Failed to load models directories configuration.</p>
            `;
        }
    }

    async renderModelsDirectories(config) {
        const container = document.getElementById('models-directories-container');

        // Get detected directories
        let detected = {};
        try {
            const detectResponse = await this.apiClient.get('/api/providers/models/directories/detect');
            detected = detectResponse.providers || {};
        } catch (error) {
            console.warn('Failed to detect directories:', error);
        }

        const html = `
            <!-- Global Models Directory -->
            <div class="models-dir-row">
                <label class="models-dir-label">Global Models Directory:</label>
                <input
                    type="text"
                    class="models-dir-input"
                    id="global-models-dir"
                    value="${config.global_dir || ''}"
                    placeholder="/path/to/models"
                />
                <button class="btn-sm" onclick="window.providersView.detectModelsDir('global')">
                    <span class="material-icons md-18">search</span> Detect
                </button>
                <button class="btn-sm" onclick="window.providersView.browseModelsDir('global')">
                    <span class="material-icons md-18">folder_open</span> Browse
                </button>
                <button class="btn-primary btn-sm" onclick="window.providersView.saveModelsDir('global')">
                    <span class="material-icons md-18">save</span> Save
                </button>
            </div>

            <div class="models-dir-separator"></div>

            <div class="models-dir-label" style="margin-bottom: 12px;">Provider-specific directories:</div>

            <!-- Ollama -->
            <div class="models-dir-row">
                <label class="provider-label">Ollama:</label>
                <select class="models-dir-select" id="ollama-dir-mode" onchange="window.providersView.handleDirModeChange('ollama', this.value)">
                    <option value="auto" ${!config.providers.ollama ? 'selected' : ''}>Auto-detect</option>
                    <option value="custom" ${config.providers.ollama ? 'selected' : ''}>Custom path</option>
                </select>
                <input
                    type="text"
                    class="models-dir-input"
                    id="ollama-models-dir"
                    value="${config.providers.ollama || ''}"
                    placeholder="/path/to/ollama/models"
                    style="${config.providers.ollama ? '' : 'display:none;'}"
                />
                <button class="btn-sm" onclick="window.providersView.browseModelsDir('ollama')"
                        style="${config.providers.ollama ? '' : 'display:none;'}" id="ollama-browse-btn">
                    <span class="material-icons md-18">folder_open</span>
                </button>
                <button class="btn-primary btn-sm" onclick="window.providersView.saveModelsDir('ollama')"
                        style="${config.providers.ollama ? '' : 'display:none;'}" id="ollama-save-btn">
                    <span class="material-icons md-18">save</span>
                </button>
                <span class="detected-path" id="ollama-detected-path" style="${config.providers.ollama ? 'display:none;' : ''}">
                    ${detected.ollama?.path ? `${detected.ollama.path} ${detected.ollama.exists ? `(${detected.ollama.model_count || 0} models)` : '(not found)'}` : 'not detected'}
                </span>
            </div>

            <!-- LlamaCpp -->
            <div class="models-dir-row">
                <label class="provider-label">LlamaCpp:</label>
                <select class="models-dir-select" id="llamacpp-dir-mode" onchange="window.providersView.handleDirModeChange('llamacpp', this.value)">
                    <option value="auto" ${!config.providers.llamacpp ? 'selected' : ''}>Auto-detect</option>
                    <option value="global" ${config.providers.llamacpp === config.global_dir ? 'selected' : ''}>Use global</option>
                    <option value="custom" ${config.providers.llamacpp && config.providers.llamacpp !== config.global_dir ? 'selected' : ''}>Custom path</option>
                </select>
                <input
                    type="text"
                    class="models-dir-input"
                    id="llamacpp-models-dir"
                    value="${config.providers.llamacpp || ''}"
                    placeholder="/path/to/llamacpp/models"
                    style="${config.providers.llamacpp ? '' : 'display:none;'}"
                />
                <button class="btn-sm" onclick="window.providersView.browseModelsDir('llamacpp')"
                        style="${config.providers.llamacpp ? '' : 'display:none;'}" id="llamacpp-browse-btn">
                    <span class="material-icons md-18">folder_open</span>
                </button>
                <button class="btn-primary btn-sm" onclick="window.providersView.saveModelsDir('llamacpp')"
                        style="${config.providers.llamacpp ? '' : 'display:none;'}" id="llamacpp-save-btn">
                    <span class="material-icons md-18">save</span>
                </button>
                <span class="detected-path" id="llamacpp-detected-path" style="${config.providers.llamacpp ? 'display:none;' : ''}">
                    ${detected.llamacpp?.path ? `${detected.llamacpp.path} ${detected.llamacpp.exists ? `(${detected.llamacpp.model_count || 0} models)` : '(not found)'}` : 'not detected'}
                </span>
            </div>

            <!-- LM Studio -->
            <div class="models-dir-row">
                <label class="provider-label">LM Studio:</label>
                <select class="models-dir-select" id="lmstudio-dir-mode" onchange="window.providersView.handleDirModeChange('lmstudio', this.value)">
                    <option value="auto" ${!config.providers.lmstudio ? 'selected' : ''}>Auto-detect</option>
                    <option value="custom" ${config.providers.lmstudio ? 'selected' : ''}>Custom path</option>
                </select>
                <input
                    type="text"
                    class="models-dir-input"
                    id="lmstudio-models-dir"
                    value="${config.providers.lmstudio || ''}"
                    placeholder="/path/to/lmstudio/models"
                    style="${config.providers.lmstudio ? '' : 'display:none;'}"
                />
                <button class="btn-sm" onclick="window.providersView.browseModelsDir('lmstudio')"
                        style="${config.providers.lmstudio ? '' : 'display:none;'}" id="lmstudio-browse-btn">
                    <span class="material-icons md-18">folder_open</span>
                </button>
                <button class="btn-primary btn-sm" onclick="window.providersView.saveModelsDir('lmstudio')"
                        style="${config.providers.lmstudio ? '' : 'display:none;'}" id="lmstudio-save-btn">
                    <span class="material-icons md-18">save</span>
                </button>
                <span class="detected-path" id="lmstudio-detected-path" style="${config.providers.lmstudio ? 'display:none;' : ''}">
                    ${detected.lmstudio?.path ? `${detected.lmstudio.path} ${detected.lmstudio.exists ? `(${detected.lmstudio.model_count || 0} models)` : '(not found)'}` : 'not detected'}
                </span>
            </div>

            <!-- Security Information -->
            <div class="security-hint" style="margin-top: 16px; padding: 12px; background: #f8f9fa; border-left: 3px solid #007bff; border-radius: 4px;">
                <div style="display: flex; align-items: flex-start; gap: 8px;">
                    <span class="material-icons md-18">lock</span>
                    <div style="flex: 1;">
                        <div style="font-weight: 600; margin-bottom: 4px;">Security Notice</div>
                        <div style="font-size: 13px; color: #6c757d; line-height: 1.5;">
                            These directories will be accessible to the WebUI for read-only browsing.
                            <strong>Do not select system-sensitive directories</strong> such as:
                            <ul style="margin: 4px 0; padding-left: 20px;">
                                <li>Windows: C:\\Windows, C:\\Program Files, C:\\Users\\[username]\\AppData\\Roaming</li>
                                <li>macOS/Linux: /etc, /var, /usr/bin, /System (macOS)</li>
                            </ul>
                            Only configured directories can be browsed. Path traversal protection is enabled.
                        </div>
                    </div>
                </div>
            </div>
        `;

        container.innerHTML = html;
    }

    handleDirModeChange(providerId, mode) {
        const input = document.getElementById(`${providerId}-models-dir`);
        const browseBtn = document.getElementById(`${providerId}-browse-btn`);
        const saveBtn = document.getElementById(`${providerId}-save-btn`);
        const detectedPath = document.getElementById(`${providerId}-detected-path`);

        if (mode === 'auto') {
            // Hide input and buttons, show detected path
            input.style.display = 'none';
            if (browseBtn) browseBtn.style.display = 'none';
            if (saveBtn) saveBtn.style.display = 'none';
            if (detectedPath) detectedPath.style.display = 'inline';
        } else if (mode === 'global') {
            // Use global directory
            const globalDir = document.getElementById('global-models-dir').value;
            input.value = globalDir;
            input.style.display = 'inline';
            if (browseBtn) browseBtn.style.display = 'inline';
            if (saveBtn) saveBtn.style.display = 'inline';
            if (detectedPath) detectedPath.style.display = 'none';
        } else {
            // Custom path
            input.style.display = 'inline';
            if (browseBtn) browseBtn.style.display = 'inline';
            if (saveBtn) saveBtn.style.display = 'inline';
            if (detectedPath) detectedPath.style.display = 'none';
        }
    }

    async detectModelsDir(providerId) {
        try {
            const response = await this.apiClient.get('/api/providers/models/directories/detect');
            const detected = response.providers[providerId];

            if (detected?.path) {
                const input = document.getElementById(`${providerId}-models-dir`);
                if (input) {
                    input.value = detected.path;
                }
                Toast.success(`Detected: ${detected.path} (${detected.model_count || 0} models)`);
            } else {
                Toast.warning(`Could not detect models directory for ${providerId}`);
            }
        } catch (error) {
            console.error('Failed to detect models directory:', error);
            this.handleProviderError(error, `detecting models directory for ${providerId}`, providerId);
        }
    }

    async browseModelsDir(providerId) {
        // Note: Directory browsing would require a file picker dialog
        // For now, we'll show a model file browser modal
        Toast.info('Opening model file browser...');
        await this.showModelBrowser(providerId);
    }

    async saveModelsDir(providerId) {
        const inputId = providerId === 'global' ? 'global-models-dir' : `${providerId}-models-dir`;
        const input = document.getElementById(inputId);

        if (!input || !input.value) {
            Toast.warning('Please enter a directory path first');
            return;
        }

        try {
            await this.apiClient.put('/api/providers/models/directories', {
                provider_id: providerId,
                path: input.value
            });

            Toast.success(`Models directory saved for ${providerId}`);
            await this.loadModelsDirectories();
        } catch (error) {
            console.error('Failed to save models directory:', error);
            this.handleProviderError(error, `saving models directory for ${providerId}`, providerId);
        }
    }

    async showModelBrowser(providerId) {
        const modal = document.getElementById('model-browser-modal');

        // Initial loading state
        modal.innerHTML = `
            <div class="modal-content model-browser-modal">
                <div class="modal-header">
                    <h2>Select Model File - ${providerId}</h2>
                    <button class="modal-close">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="model-browser-controls">
                        <input type="text" id="model-search" class="filter-input" placeholder="Search models...">
                    </div>
                    <div id="model-files-list" class="model-files-list">
                        <p class="loading-text">Loading model files...</p>
                    </div>
                </div>
            </div>
        `;

        modal.style.display = 'flex';

        // Close button
        modal.querySelector('.modal-close').addEventListener('click', () => {
            modal.style.display = 'none';
        });

        // Load model files
        try {
            const response = await this.apiClient.get('/api/providers/models/files', {
                params: { provider_id: providerId }
            });

            this.renderModelFiles(response.files, response.directory);
        } catch (error) {
            console.error('Failed to load model files:', error);
            document.getElementById('model-files-list').innerHTML = `
                <p class="error-text">Failed to load model files: ${error.message}</p>
                <p class="hint-text">Make sure the models directory is configured correctly.</p>
            `;
        }

        // Search functionality
        document.getElementById('model-search').addEventListener('input', (e) => {
            this.filterModelFiles(e.target.value);
        });
    }

    renderModelFiles(files, directory) {
        const container = document.getElementById('model-files-list');

        if (!files || files.length === 0) {
            container.innerHTML = `
                <div class="model-files-empty">
                    <span class="material-icons md-36">folder_open</span>
                    <p>No model files found in this directory</p>
                    <p class="hint-text">Directory: ${directory}</p>
                </div>
            `;
            return;
        }

        const html = files.map(file => `
            <div class="model-file-item" data-filename="${file.name}" onclick="window.providersView.selectModelFile('${file.name}')">
                <div class="model-file-info">
                    <span class="model-name">${file.name}</span>
                    <span class="model-extension">${file.extension}</span>
                </div>
                <div class="model-file-meta">
                    <span class="model-size">${file.size_human}</span>
                    <span class="model-date">${new Date(file.modified).toLocaleDateString()}</span>
                </div>
            </div>
        `).join('');

        container.innerHTML = html;
    }

    filterModelFiles(query) {
        const items = document.querySelectorAll('.model-file-item');
        const lowerQuery = query.toLowerCase();

        items.forEach(item => {
            const filename = item.dataset.filename.toLowerCase();
            if (filename.includes(lowerQuery)) {
                item.style.display = 'flex';
            } else {
                item.style.display = 'none';
            }
        });
    }

    selectModelFile(fileName) {
        // Store selected model file (this will be used when adding/editing llamacpp instances)
        this.selectedModelFile = fileName;

        // Close modal
        document.getElementById('model-browser-modal').style.display = 'none';

        Toast.success(`Selected: ${fileName}`);

        // If we have a model path input field open, fill it
        const modelPathInput = document.querySelector('input[name="launch_model"]');
        if (modelPathInput) {
            modelPathInput.value = fileName;
        }
    }

    // ============================================================================
    // Error Handling Utilities
    // ============================================================================

    /**
     * Parse and display provider errors with user-friendly messages
     * @param {Object} error - Error from API response
     * @param {string} context - Error context (e.g., "starting ollama instance")
     * @param {string} providerId - Provider identifier (ollama, llamacpp, lmstudio)
     */
    handleProviderError(error, context = '', providerId = '') {
        // Check if the error response contains structured error format
        const errorData = error.response?.data?.error || error.detail?.error;

        if (errorData) {
            // Structured error from backend (Task #8 unified format)
            const { code, message, details, suggestion } = errorData;

            // Create detailed error dialog
            const errorHtml = this.renderErrorDialog(code, message, details, suggestion, providerId);

            // Show error dialog
            this.showErrorDialog(errorHtml);
        } else {
            // Fallback to generic error handling
            const errorMsg = error.message || error.statusText || 'Unknown error';
            Toast.error(`Failed to ${context}: ${errorMsg}`);
        }
    }

    /**
     * Render error dialog HTML
     * @param {string} code - Error code
     * @param {string} message - Error message
     * @param {Object} details - Error details
     * @param {string} suggestion - Action suggestion
     * @param {string} providerId - Provider identifier
     * @returns {string} HTML string
     */
    renderErrorDialog(code, message, details, suggestion, providerId) {
        const title = this.getErrorTitle(code);
        const detailsHtml = details ? this.renderErrorDetails(details) : '';
        const suggestionHtml = suggestion ? this.renderErrorSuggestion(suggestion, code, details, providerId) : '';

        return `
            <div class="provider-error">
                <div class="error-title">${title}</div>
                <div class="error-message">${message}</div>
                ${suggestionHtml}
                ${detailsHtml}
            </div>
        `;
    }

    /**
     * Convert error code to user-friendly title
     * @param {string} errorCode - Error code constant
     * @returns {string} User-friendly title
     */
    getErrorTitle(errorCode) {
        const titles = {
            'EXECUTABLE_NOT_FOUND': 'Executable not found',
            'PORT_IN_USE': 'Port in use',
            'PROCESS_START_FAILED': 'Start failed',
            'PROCESS_STOP_FAILED': 'Stop failed',
            'INVALID_PATH': 'Invalid path',
            'MODEL_FILE_NOT_FOUND': 'Model file not found',
            'PERMISSION_DENIED': 'Permission denied',
            'TIMEOUT_ERROR': 'Operation timeout',
            'STARTUP_TIMEOUT': 'Startup timeout',
            'SHUTDOWN_TIMEOUT': 'Shutdown timeout',
            'DIRECTORY_NOT_FOUND': 'Directory not found',
            'NOT_A_DIRECTORY': 'Not a valid directory',
            'DIRECTORY_NOT_READABLE': 'Directory not readable',
            'NOT_EXECUTABLE': 'File not executable',
            'FILE_NOT_FOUND': 'File not found',
            'PROCESS_NOT_RUNNING': 'Process not running',
            'PROCESS_ALREADY_RUNNING': 'Process already running',
            'PORT_NOT_AVAILABLE': 'Port not available',
            'INVALID_MODEL_FILE': 'Invalid model file',
            'CONFIG_ERROR': 'Configuration error',
            'INVALID_CONFIG': 'Invalid configuration',
            'UNSUPPORTED_PLATFORM': 'Platform not supported',
            'PLATFORM_SPECIFIC_ERROR': 'Platform-specific error',
            'INTERNAL_ERROR': 'Internal error',
            'LAUNCH_FAILED': 'Launch failed',
            'VALIDATION_ERROR': 'Validation failed'
        };
        return titles[errorCode] || 'Actionsfailed';
    }

    /**
     * Render error details section
     * @param {Object} details - Error details object
     * @returns {string} HTML string
     */
    renderErrorDetails(details) {
        let html = '<div class="error-details">';

        // Searched paths
        if (details.searched_paths && details.searched_paths.length > 0) {
            html += '<div class="detail-section">';
            html += '<strong>Search paths:</strong>';
            html += '<ul>';
            details.searched_paths.forEach(path => {
                html += `<li><code>${this.escapeHtml(path)}</code></li>`;
            });
            html += '</ul>';
            html += '</div>';
        }

        // Platform
        if (details.platform) {
            html += `<div class="detail-section"><strong>Platform:</strong> ${this.escapeHtml(details.platform)}</div>`;
        }

        // Port
        if (details.port) {
            html += `<div class="detail-section"><strong>Port:</strong> ${details.port}</div>`;
        }

        // Occupant (for port conflicts)
        if (details.occupant) {
            html += `<div class="detail-section"><strong>Occupant:</strong> ${this.escapeHtml(details.occupant)}</div>`;
        }

        // Timeout
        if (details.timeout_seconds) {
            html += `<div class="detail-section"><strong>超时Time：</strong> ${details.timeout_seconds}seconds</div>`;
        }

        // Provider ID
        if (details.provider_id) {
            html += `<div class="detail-section"><strong>Provider：</strong> ${this.escapeHtml(details.provider_id)}</div>`;
        }

        // Instance key
        if (details.instance_key) {
            html += `<div class="detail-section"><strong>Instance:</strong> ${this.escapeHtml(details.instance_key)}</div>`;
        }

        html += '</div>';
        return html;
    }

    /**
     * Render error suggestion with actionable links
     * @param {string} suggestion - Suggestion text
     * @param {string} code - Error code
     * @param {Object} details - Error details
     * @param {string} providerId - Provider identifier
     * @returns {string} HTML string
     */
    renderErrorSuggestion(suggestion, code, details, providerId) {
        let html = `<div class="error-suggestion">${this.escapeHtml(suggestion)}`;

        // Add action links based on error type
        if (code === 'EXECUTABLE_NOT_FOUND') {
            html += `<br><br><a href="#" class="error-action-link" onclick="window.providersView.navigateToExecutableConfig('${providerId}'); return false;">
                Click to configure path →
            </a>`;
            html += ` | `;
            html += this.getProviderHelpLink(providerId);
        } else if (code === 'PORT_IN_USE' && details.port) {
            html += `<br><br>Please check if other ${providerId} instances are running, or change port configuration。`;
        } else if (code === 'MODEL_FILE_NOT_FOUND') {
            html += `<br><br><a href="#" class="error-action-link" onclick="window.providersView.showModelBrowser('${providerId}'); return false;">
                Browse available models →
            </a>`;
        } else if (code === 'PERMISSION_DENIED' && details.platform === 'windows') {
            html += '<br><br>Please try running AgentOS with administrator privileges。';
        } else if (code === 'PERMISSION_DENIED' && details.platform !== 'windows') {
            html += '<br><br>Please check file permissions or run with sudo。';
        }

        html += '</div>';
        return html;
    }

    /**
     * Get help link for provider
     * @param {string} providerId - Provider identifier
     * @returns {string} HTML anchor tag
     */
    getProviderHelpLink(providerId) {
        const links = {
            'ollama': 'https://ollama.ai',
            'llamacpp': 'https://github.com/ggerganov/llama.cpp',
            'lmstudio': 'https://lmstudio.ai'
        };

        const url = links[providerId];
        if (url) {
            return `<a href="${url}" target="_blank" class="error-action-link">Visit official website →</a>`;
        }
        return '';
    }

    /**
     * Navigate to executable configuration for provider
     * @param {string} providerId - Provider identifier
     */
    navigateToExecutableConfig(providerId) {
        // Scroll to the executable config section
        const configSection = document.querySelector(`.executable-config[data-provider="${providerId}"]`);
        if (configSection) {
            configSection.scrollIntoView({ behavior: 'smooth', block: 'center' });

            // Highlight the section temporarily
            configSection.style.transition = 'background-color 0.5s';
            configSection.style.backgroundColor = '#fff3cd';
            setTimeout(() => {
                configSection.style.backgroundColor = '';
            }, 2000);

            // Focus on the path input
            const input = document.querySelector(`.executable-path-input[data-provider="${providerId}"]`);
            if (input) {
                setTimeout(() => input.focus(), 600);
            }
        }
    }

    /**
     * Show error dialog using Dialog component or fallback to alert
     * @param {string} htmlContent - HTML content for dialog
     */
    showErrorDialog(htmlContent) {
        // Check if Dialog component is available
        if (typeof Dialog !== 'undefined' && Dialog.alert) {
            Dialog.alert(htmlContent, {
                title: 'Provider Error',
                html: true,
                width: '600px'
            });
        } else {
            // Fallback: create a simple modal
            const modal = document.createElement('div');
            modal.className = 'error-modal-overlay';
            modal.innerHTML = `
                <div class="error-modal-content">
                    <div class="error-modal-header">
                        <h3>Provider Error</h3>
                        <button class="error-modal-close" onclick="this.closest('.error-modal-overlay').remove()">×</button>
                    </div>
                    <div class="error-modal-body">
                        ${htmlContent}
                    </div>
                    <div class="error-modal-footer">
                        <button class="btn-secondary" onclick="this.closest('.error-modal-overlay').remove()">Close</button>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);

            // Click outside to close
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.remove();
                }
            });
        }
    }

    /**
     * Escape HTML to prevent XSS
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }


    // =============================================================================
    // Diagnostics Functions (Task #19: P1.6)
    // =============================================================================

    /**
     * Toggle diagnostics panel visibility for a provider
     * @param {string} providerId - Provider identifier
     */
    async toggleDiagnostics(providerId) {
        const panel = document.querySelector(`.diagnostics-panel[data-provider="${providerId}"]`);
        const button = document.querySelector(`.btn-diagnostics[data-provider="${providerId}"]`);

        if (!panel || !button) return;

        if (panel.style.display === 'none') {
            // Show panel and load diagnostics
            panel.style.display = 'block';
            button.innerHTML = '<span class="material-icons md-18">assessment</span> Hide Diagnostics';
            await this.loadDiagnostics(providerId);
        } else {
            // Hide panel
            panel.style.display = 'none';
            button.innerHTML = '<span class="material-icons md-18">assessment</span> Show Diagnostics';
        }
    }

    /**
     * Load and display diagnostics for a provider
     * @param {string} providerId - Provider identifier
     */
    async loadDiagnostics(providerId) {
        const contentDiv = document.querySelector(`.diagnostics-content[data-provider="${providerId}"]`);
        if (!contentDiv) return;

        try {
            contentDiv.innerHTML = '<p class="loading-text">Loading diagnostics...</p>';

            const diagnostics = await this.apiClient.get(`/api/providers/${providerId}/diagnostics`);

            // Store diagnostics for copy function
            if (!this.diagnosticsCache) {
                this.diagnosticsCache = {};
            }
            this.diagnosticsCache[providerId] = diagnostics;

            // Render diagnostics
            contentDiv.innerHTML = this.renderDiagnosticsContent(diagnostics);

        } catch (error) {
            console.error('Failed to load diagnostics:', error);
            contentDiv.innerHTML = `<p class="error-text">Failed to load diagnostics: ${error.message}</p>`;
        }
    }

    /**
     * Render diagnostics content HTML
     * @param {Object} diag - Diagnostics data
     * @returns {string} HTML content
     */
    renderDiagnosticsContent(diag) {
        const statusClass = {
            'RUNNING': 'status-running',
            'STOPPED': 'status-stopped',
            'ERROR': 'status-error',
            'STARTING': 'status-starting'
        }[diag.current_status] || 'status-unknown';

        return `
            <div class="diag-row">
                <span class="diag-label">Platform:</span>
                <span class="diag-value">${this.escapeHtml(diag.platform)}</span>
            </div>
            <div class="diag-row">
                <span class="diag-label">Detected Executable:</span>
                <span class="diag-value">${diag.detected_executable || '<span class="text-muted">Not found</span>'}</span>
            </div>
            <div class="diag-row">
                <span class="diag-label">Configured Executable:</span>
                <span class="diag-value">${diag.configured_executable || '<span class="text-muted">(auto)</span>'}</span>
            </div>
            <div class="diag-row">
                <span class="diag-label">Resolved Executable:</span>
                <span class="diag-value highlight">${diag.resolved_executable || '<span class="text-muted">Not resolved</span>'}</span>
            </div>
            <div class="diag-row">
                <span class="diag-label">Detection Source:</span>
                <span class="diag-value">${diag.detection_source || '<span class="text-muted">—</span>'}</span>
            </div>
            <div class="diag-row">
                <span class="diag-label">Version:</span>
                <span class="diag-value">${diag.version || '<span class="text-muted">Unknown</span>'}</span>
            </div>
            <div class="diag-row">
                <span class="diag-label">Supported Actions:</span>
                <span class="diag-value">${diag.supported_actions.join(', ')}</span>
            </div>
            <div class="diag-row">
                <span class="diag-label">Current Status:</span>
                <span class="diag-value ${statusClass}">${diag.current_status || 'UNKNOWN'}</span>
            </div>
            ${diag.pid ? `
            <div class="diag-row">
                <span class="diag-label">PID:</span>
                <span class="diag-value">${diag.pid}</span>
            </div>
            ` : ''}
            ${diag.port ? `
            <div class="diag-row">
                <span class="diag-label">Port:</span>
                <span class="diag-value">${diag.port} ${diag.port_listening ? '<span class="status-listening">(listening)</span>' : '<span class="status-not-listening">(not listening)</span>'}</span>
            </div>
            ` : ''}
            <div class="diag-row">
                <span class="diag-label">Models Directory:</span>
                <span class="diag-value">${diag.models_directory || '<span class="text-muted">Not configured</span>'}</span>
            </div>
            ${diag.models_count !== null && diag.models_count !== undefined ? `
            <div class="diag-row">
                <span class="diag-label">Models Count:</span>
                <span class="diag-value">${diag.models_count}</span>
            </div>
            ` : ''}
            ${diag.last_error ? `
            <div class="diag-row">
                <span class="diag-label">Last Error:</span>
                <span class="diag-value diag-error">${this.escapeHtml(diag.last_error)}</span>
            </div>
            ` : ''}
        `;
    }

    /**
     * Run health check for a provider (force refresh diagnostics)
     * @param {string} providerId - Provider identifier
     */
    async runHealthCheck(providerId) {
        const button = document.querySelector(`[data-action="health-check"][data-provider="${providerId}"]`);
        if (button) {
            button.disabled = true;
            button.innerHTML = '<span class="material-icons md-18">refresh</span>';
        }

        try {
            await this.loadDiagnostics(providerId);
            this.showToast('Health check completed', 'success');
        } catch (error) {
            this.showToast('Health check failed: ' + error.message, 'error');
        } finally {
            if (button) {
                button.disabled = false;
                button.innerHTML = '<span class="material-icons md-18">health_and_safety</span>';
            }
        }
    }

    /**
     * Copy diagnostics to clipboard in Markdown format
     * @param {string} providerId - Provider identifier
     */
    async copyDiagnostics(providerId) {
        const diag = this.diagnosticsCache?.[providerId];
        if (!diag) {
            this.showToast('Please load diagnostics first', 'warning');
            return;
        }

        const markdown = `## ${providerId} Diagnostics

- **Platform**: ${diag.platform}
- **Detected Executable**: ${diag.detected_executable || 'Not found'}
- **Configured Executable**: ${diag.configured_executable || '(auto)'}
- **Resolved Executable**: ${diag.resolved_executable || 'Not resolved'}
- **Detection Source**: ${diag.detection_source || '—'}
- **Version**: ${diag.version || 'Unknown'}
- **Supported Actions**: ${diag.supported_actions.join(', ')}
- **Current Status**: ${diag.current_status || 'UNKNOWN'}
${diag.pid ? `- **PID**: ${diag.pid}` : ''}
${diag.port ? `- **Port**: ${diag.port} ${diag.port_listening ? '(listening)' : '(not listening)'}` : ''}
- **Models Directory**: ${diag.models_directory || 'Not configured'}
${diag.models_count !== null && diag.models_count !== undefined ? `- **Models Count**: ${diag.models_count}` : ''}
${diag.last_error ? `- **Last Error**: ${diag.last_error}` : ''}
`;

        try {
            await navigator.clipboard.writeText(markdown);
            this.showToast('Diagnostics copied to clipboard', 'success');
        } catch (error) {
            console.error('Failed to copy to clipboard:', error);
            this.showToast('Failed to copy to clipboard', 'error');
        }
    }


    unmount() {
        // Cleanup
    }
}

// Export
window.ProvidersView = ProvidersView;
