/**
 * RuntimeView - Runtime Management UI
 *
 * PR-5: Context/Runtime/Support Module
 * Coverage: POST /api/runtime/fix-permissions
 */

class RuntimeView {
    constructor(container) {
        this.container = container;
        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="runtime-view">
                <div class="view-header">
                    <div>
                        <h1>Runtime Management</h1>
                        <p class="text-sm text-gray-600 mt-1">System runtime management and maintenance</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="runtime-refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                    </div>
                </div>

                <!-- Runtime Status -->
                <div class="detail-section">
                    <h3 class="detail-section-title">System Status</h3>
                    <div class="config-card">
                        <div id="runtime-status-content"></div>
                    </div>
                </div>

                <!-- Runtime Actions -->
                <div class="detail-section">
                    <h3 class="detail-section-title">System Actions</h3>
                    <div class="config-card">
                        <p class="text-sm text-gray-600 mb-4">
                            Execute system maintenance operations. These operations may require elevated permissions.
                        </p>
                        <div class="flex gap-3 flex-wrap">
                            <button class="btn-primary" id="runtime-fix-permissions">
                                <span class="material-icons md-18">lock</span> Fix File Permissions
                            </button>
                            <button class="btn-secondary" id="runtime-view-providers">
                                <span class="material-icons md-18">power</span> View Providers
                            </button>
                            <button class="btn-secondary" id="runtime-run-selfcheck">
                                <span class="material-icons md-18">done</span> Run Self-check
                            </button>
                        </div>
                        <div id="runtime-action-status" class="mt-4"></div>
                    </div>
                </div>

                <!-- Provider Summary -->
                <div class="detail-section">
                    <h3 class="detail-section-title">Provider Summary</h3>
                    <div class="config-card">
                        <div id="runtime-providers-content"></div>
                    </div>
                </div>
            </div>
        `;

        this.setupEventListeners();
        this.loadRuntimeStatus();
    }

    setupEventListeners() {
        const refreshBtn = document.getElementById('runtime-refresh');
        const fixPermBtn = document.getElementById('runtime-fix-permissions');
        const viewProvidersBtn = document.getElementById('runtime-view-providers');
        const runSelfcheckBtn = document.getElementById('runtime-run-selfcheck');

        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadRuntimeStatus());
        }

        if (fixPermBtn) {
            fixPermBtn.addEventListener('click', () => this.fixPermissions());
        }

        if (viewProvidersBtn) {
            viewProvidersBtn.addEventListener('click', () => {
                if (window.navigateToView) {
                    window.navigateToView('providers');
                }
            });
        }

        if (runSelfcheckBtn) {
            runSelfcheckBtn.addEventListener('click', () => {
                if (window.navigateToView) {
                    window.navigateToView('support');
                }
            });
        }
    }

    async loadRuntimeStatus() {
        try {
            const statusDiv = document.getElementById('runtime-status-content');
            const providersDiv = document.getElementById('runtime-providers-content');

            if (statusDiv) {
                statusDiv.innerHTML = '<div class="text-center py-4 text-gray-500">Loading runtime status...</div>';
            }

            // Load health info
            const healthResponse = await apiClient.get('/api/health');
            const health = healthResponse.ok ? healthResponse.data : null;

            // Load providers status
            const providersResponse = await apiClient.get('/api/providers/status');
            const providers = providersResponse.ok ? providersResponse.data : null;

            // Load config
            const configResponse = await apiClient.get('/api/config');
            const config = configResponse.ok ? configResponse.data : null;

            // Render status
            if (statusDiv && health) {
                statusDiv.innerHTML = `
                    <div class="detail-grid">
                        <div class="detail-item">
                            <span class="detail-label">System Status</span>
                            <span class="detail-value">
                                <span class="badge badge-${health.status === 'ok' ? 'success' : health.status === 'warn' ? 'warning' : 'error'}">
                                    ${health.status?.toUpperCase() || 'UNKNOWN'}
                                </span>
                            </span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">AgentOS Version</span>
                            <span class="detail-value font-semibold">${config?.version || 'Unknown'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Python Version</span>
                            <span class="detail-value">${config?.python_version?.split(' ')[0] || 'Unknown'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Uptime</span>
                            <span class="detail-value">${this.formatUptime(health.uptime_seconds || 0)}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">CPU Usage</span>
                            <span class="detail-value">${health.metrics?.cpu_percent?.toFixed(1) || '0'}%</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Memory Usage</span>
                            <span class="detail-value">${health.metrics?.memory_mb?.toFixed(1) || '0'} MB</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Process ID</span>
                            <span class="detail-value font-mono text-xs">${health.metrics?.pid || 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Last Check</span>
                            <span class="detail-value text-sm">${new Date().toLocaleTimeString()}</span>
                        </div>
                    </div>
                `;
            }

            // Render providers summary
            if (providersDiv && providers && providers.providers) {
                const readyCount = providers.providers.filter(p => p.state === 'READY').length;
                const errorCount = providers.providers.filter(p => p.state === 'ERROR').length;

                providersDiv.innerHTML = `
                    <div class="detail-grid">
                        <div class="detail-item">
                            <span class="detail-label">Total Providers</span>
                            <span class="detail-value font-semibold">${providers.providers.length}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Ready</span>
                            <span class="detail-value">
                                <span class="badge badge-success">${readyCount}</span>
                            </span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Errors</span>
                            <span class="detail-value">
                                <span class="badge badge-error">${errorCount}</span>
                            </span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Last Updated</span>
                            <span class="detail-value text-sm">${providers.ts ? new Date(providers.ts).toLocaleString() : 'N/A'}</span>
                        </div>
                    </div>
                    <div class="mt-4">
                        <button class="btn-primary" id="runtime-goto-providers">
                            View Full Provider Status →
                        </button>
                    </div>
                `;

                const gotoBtn = providersDiv.querySelector('#runtime-goto-providers');
                if (gotoBtn) {
                    gotoBtn.addEventListener('click', () => {
                        if (window.navigateToView) {
                            window.navigateToView('providers');
                        }
                    });
                }
            }

        } catch (error) {
            console.error('Failed to load runtime status:', error);

            const statusDiv = document.getElementById('runtime-status-content');
            if (statusDiv) {
                statusDiv.innerHTML = `
                    <div class="text-center py-4 text-red-600">
                        <p>Failed to load runtime status</p>
                        <p class="text-sm mt-2">${error.message}</p>
                    </div>
                `;
            }

            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    async fixPermissions() {
        const statusDiv = document.getElementById('runtime-action-status');

        const confirmed = await Dialog.confirm('Fix file permissions on sensitive files (chmod 600)? This operation is safe and recommended.', {
            title: 'Fix Permissions',
            confirmText: 'Fix Permissions'
        });
        if (!confirmed) {
            return;
        }

        try {
            if (statusDiv) {
                statusDiv.innerHTML = '<p class="text-sm text-blue-600">Fixing file permissions...</p>';
            }

            const response = await apiClient.post('/api/runtime/fix-permissions');

            if (!response.ok) {
                throw new Error(response.error || 'Failed to fix permissions');
            }

            const result = response.data || {};

            if (window.showToast) {
                window.showToast('File permissions fixed successfully', 'success');
            }

            if (statusDiv) {
                const fixedFiles = result.fixed_files || [];
                statusDiv.innerHTML = `
                    <p class="text-sm text-green-600 font-semibold"><span class="material-icons md-18">check</span> Permissions fixed successfully</p>
                    ${fixedFiles.length > 0 ? `
                        <p class="text-xs text-gray-600 mt-2">Fixed ${fixedFiles.length} file(s):</p>
                        <ul class="text-xs text-gray-600 mt-1 ml-4 list-disc">
                            ${fixedFiles.map(f => `<li class="font-mono">${this.escapeHtml(f)}</li>`).join('')}
                        </ul>
                    ` : `
                        <p class="text-xs text-gray-600 mt-2">All files already have correct permissions.</p>
                    `}
                    <p class="text-xs text-gray-500 mt-2">${result.message || ''}</p>
                `;
            }

        } catch (error) {
            console.error('Failed to fix permissions:', error);

            if (statusDiv) {
                statusDiv.innerHTML = `<p class="text-sm text-red-600"><span class="material-icons md-18">cancel</span> Error: ${error.message}</p>`;
            }

            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    formatUptime(seconds) {
        if (seconds < 60) return `${Math.floor(seconds)}s`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        return `${hours}h ${minutes}m`;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    destroy() {
        // Cleanup
        this.container.innerHTML = '';
    }
}
