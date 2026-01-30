/**
 * SupportView - Support & Diagnostics UI
 *
 * PR-5: Context/Runtime/Support Module
 * Coverage: GET /api/support/diagnostic-bundle
 */

class SupportView {
    constructor(container) {
        this.container = container;
        this.diagnosticData = null;
        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="support-view">
                <div class="view-header">
                    <div>
                        <h1>Support & Diagnostics</h1>
                        <p class="text-sm text-gray-600 mt-1">Generate diagnostics and support bundles</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-primary" id="support-generate">
                            <span class="icon"><span class="material-icons md-18">archive</span></span> Generate Diagnostics
                        </button>
                    </div>
                </div>

                <!-- Diagnostics Bundle -->
                <div class="detail-section">
                    <h3 class="detail-section-title">Diagnostic Bundle</h3>
                    <div class="config-card">
                        <p class="text-sm text-gray-600 mb-4">
                            Generate a comprehensive diagnostic bundle containing system information, provider status,
                            self-check results, and cache statistics. All sensitive data (API keys, tokens) are automatically masked.
                        </p>

                        <div class="flex gap-3 flex-wrap">
                            <button class="btn-primary" id="support-download-json">
                                <span class="material-icons md-18">save</span> Download as JSON
                            </button>
                            <button class="btn-secondary" id="support-view-inline">
                                <span class="material-icons md-18">preview</span> View Inline
                            </button>
                            <button class="btn-secondary" id="support-copy">
                                <span class="material-icons md-18">content_copy</span> Copy to Clipboard
                            </button>
                        </div>

                        <div id="support-status" class="mt-4"></div>
                    </div>
                </div>

                <!-- Diagnostic Data Viewer -->
                <div id="support-viewer-section" class="hidden">
                    <div class="detail-section">
                        <h3 class="detail-section-title">Diagnostic Data</h3>
                        <div class="config-card">
                            <div class="json-viewer-container-diagnostics"></div>
                        </div>
                    </div>
                </div>

                <!-- Quick Links -->
                <div class="detail-section">
                    <h3 class="detail-section-title">Quick Links</h3>
                    <div class="config-card">
                        <div class="flex gap-3 flex-wrap">
                            <button class="btn-secondary" id="support-view-health">
                                <span class="material-icons md-18">favorite</span> System Health
                            </button>
                            <button class="btn-secondary" id="support-view-providers">
                                <span class="material-icons md-18">power</span> Provider Status
                            </button>
                            <button class="btn-secondary" id="support-run-selfcheck">
                                <span class="material-icons md-18">done</span> Run Self-check
                            </button>
                            <button class="btn-secondary" id="support-view-logs">
                                <span class="material-icons md-18">description</span> View Logs
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Help & Resources -->
                <div class="detail-section">
                    <h3 class="detail-section-title">Help & Resources</h3>
                    <div class="config-card">
                        <ul class="space-y-2 text-sm">
                            <li><span class="material-icons md-18">menu_book</span> <a href="https://github.com/seacow-technology/agentos/wiki" target="_blank" class="text-blue-600 hover:underline">AgentOS Documentation</a></li>
                            <li><span class="material-icons md-18">bug_report</span> <a href="https://github.com/seacow-technology/agentos/issues" target="_blank" class="text-blue-600 hover:underline">Report an Issue</a></li>
                            <li><span class="material-icons md-18">add_comment</span> <a href="https://discord.gg/5D4E6SjU" target="_blank" class="text-blue-600 hover:underline">Community Discussions</a></li>
                            <li><span class="material-icons md-18">email</span> Support Email: <a href="mailto:support@skylinkitsolution.com" class="text-blue-600 hover:underline">support@skylinkitsolution.com</a></li>
                        </ul>
                    </div>
                </div>
            </div>
        `;

        this.setupEventListeners();
        this.autoGenerate();
    }

    setupEventListeners() {
        const generateBtn = document.getElementById('support-generate');
        const downloadBtn = document.getElementById('support-download-json');
        const viewBtn = document.getElementById('support-view-inline');
        const copyBtn = document.getElementById('support-copy');

        // Quick links
        const healthBtn = document.getElementById('support-view-health');
        const providersBtn = document.getElementById('support-view-providers');
        const selfcheckBtn = document.getElementById('support-run-selfcheck');
        const logsBtn = document.getElementById('support-view-logs');

        if (generateBtn) {
            generateBtn.addEventListener('click', () => this.generateDiagnostics());
        }

        if (downloadBtn) {
            downloadBtn.addEventListener('click', () => this.downloadDiagnostics());
        }

        if (viewBtn) {
            viewBtn.addEventListener('click', () => this.viewInline());
        }

        if (copyBtn) {
            copyBtn.addEventListener('click', () => this.copyToClipboard());
        }

        if (healthBtn) {
            healthBtn.addEventListener('click', () => {
                if (window.navigateToView) {
                    window.navigateToView('overview');
                }
            });
        }

        if (providersBtn) {
            providersBtn.addEventListener('click', () => {
                if (window.navigateToView) {
                    window.navigateToView('providers');
                }
            });
        }

        if (selfcheckBtn) {
            selfcheckBtn.addEventListener('click', () => {
                // Self-check functionality is on this page, just scroll to top or refresh
                this.autoGenerate();
                window.scrollTo({ top: 0, behavior: 'smooth' });
            });
        }

        if (logsBtn) {
            logsBtn.addEventListener('click', () => {
                if (window.navigateToView) {
                    window.navigateToView('logs');
                }
            });
        }
    }

    autoGenerate() {
        // Auto-generate on load
        setTimeout(() => this.generateDiagnostics(true), 300);
    }

    async generateDiagnostics(silent = false) {
        const statusDiv = document.getElementById('support-status');

        try {
            if (statusDiv && !silent) {
                statusDiv.innerHTML = '<p class="text-sm text-blue-600">Generating diagnostic bundle...</p>';
            }

            const response = await apiClient.get('/api/support/diagnostic-bundle');

            if (!response.ok) {
                throw new Error(response.error || 'Failed to generate diagnostic bundle');
            }

            this.diagnosticData = response.data || {};

            if (window.showToast && !silent) {
                window.showToast('Diagnostic bundle generated', 'success', 1500);
            }

            if (statusDiv) {
                const version = this.diagnosticData.version || 'Unknown';
                const timestamp = this.diagnosticData.ts ? new Date(this.diagnosticData.ts).toLocaleString() : 'N/A';
                const providersCount = this.diagnosticData.providers?.length || 0;
                const selfcheckItems = this.diagnosticData.selfcheck?.items?.length || 0;

                statusDiv.innerHTML = `
                    <div class="text-sm space-y-1">
                        <p class="text-green-600 font-semibold"><span class="material-icons md-18">check</span> Diagnostic bundle ready</p>
                        <p class="text-gray-600">
                            Version: ${version} |
                            Generated: ${timestamp} |
                            Providers: ${providersCount} |
                            Selfcheck items: ${selfcheckItems}
                        </p>
                    </div>
                `;
            }

        } catch (error) {
            console.error('Failed to generate diagnostics:', error);

            if (statusDiv) {
                statusDiv.innerHTML = `<p class="text-sm text-red-600"><span class="material-icons md-18">cancel</span> Error: ${error.message}</p>`;
            }

            if (window.showToast && !silent) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    async downloadDiagnostics() {
        if (!this.diagnosticData) {
            await this.generateDiagnostics();
            if (!this.diagnosticData) return;
        }

        try {
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
            const filename = `agentos-diagnostics-${timestamp}.json`;

            const jsonString = JSON.stringify(this.diagnosticData, null, 2);
            const blob = new Blob([jsonString], { type: 'application/json' });
            const url = URL.createObjectURL(blob);

            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            if (window.showToast) {
                window.showToast(`Downloaded: ${filename}`, 'success', 2000);
            }
        } catch (error) {
            console.error('Failed to download diagnostics:', error);
            if (window.showToast) {
                window.showToast('Download failed', 'error');
            }
        }
    }

    viewInline() {
        if (!this.diagnosticData) {
            if (window.showToast) {
                window.showToast('No diagnostic data available', 'error');
            }
            return;
        }

        const viewerSection = document.getElementById('support-viewer-section');
        const container = this.container.querySelector('.json-viewer-container-diagnostics');

        if (viewerSection) {
            viewerSection.classList.remove('hidden');
        }

        if (container) {
            new JsonViewer(container, this.diagnosticData);
        }

        // Scroll to viewer
        viewerSection?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    async copyToClipboard() {
        if (!this.diagnosticData) {
            if (window.showToast) {
                window.showToast('No diagnostic data available', 'error');
            }
            return;
        }

        try {
            const jsonString = JSON.stringify(this.diagnosticData, null, 2);
            await navigator.clipboard.writeText(jsonString);

            if (window.showToast) {
                window.showToast('Diagnostic data copied to clipboard', 'success', 1500);
            }
        } catch (error) {
            console.error('Failed to copy:', error);
            if (window.showToast) {
                window.showToast('Copy failed', 'error');
            }
        }
    }

    destroy() {
        // Cleanup
        this.container.innerHTML = '';
    }
}
