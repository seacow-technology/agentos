/**
 * ContextView - Session Context Management UI
 *
 * PR-5: Context/Runtime/Support Module
 * Coverage: GET /api/context/status, POST /api/context/attach, POST /api/context/detach, POST /api/context/refresh
 */

class ContextView {
    constructor(container) {
        this.container = container;
        this.sessionId = null;
        this.contextStatus = null;
        this.currentTab = 'status';  // NEW: Track current tab

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="context-view">
                <div class="view-header">
                    <div>
                        <h1>Session Context Management</h1>
                        <p class="text-sm text-gray-600 mt-1">View and manage session context and state</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="context-refresh" disabled>
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                    </div>
                </div>

                <!-- Session Selector -->
                <div class="detail-section">
                    <h3 class="detail-section-title">Select Session</h3>
                    <div class="config-card">
                        <div class="form-group">
                            <label for="context-session-select" class="form-label">Session ID *</label>
                            <input
                                type="text"
                                id="context-session-select"
                                class="form-control"
                                placeholder="Enter session ID or select from recent..."
                            />
                            <small class="text-xs text-gray-500">Enter a session ID to view its context status</small>
                        </div>
                        <div class="flex gap-2 mt-3">
                            <button class="btn-primary" id="context-load-btn">
                                <span class="material-icons md-18">analytics</span> Load Context Status
                            </button>
                            <button class="btn-secondary" id="context-recent-btn">
                                <span class="material-icons md-18">history</span> Recent Sessions
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Context Status -->
                <div id="context-status-section" class="hidden">
                    <!-- NEW: Tab Navigation -->
                    <div class="detail-section">
                        <div class="flex gap-2 border-b border-gray-200">
                            <button class="context-tab active" data-tab="status">
                                <span class="material-icons md-18">info</span> Status
                            </button>
                            <button class="context-tab" data-tab="budget">
                                <span class="material-icons md-18">account_balance_wallet</span> Budget
                            </button>
                            <button class="context-tab" data-tab="operations">
                                <span class="material-icons md-18">settings</span> Operations
                            </button>
                            <button class="context-tab" data-tab="raw">
                                <span class="material-icons md-18">code</span> Raw Data
                            </button>
                        </div>
                    </div>

                    <!-- Tab Contents -->
                    <div id="context-tab-content">
                        <!-- Will be populated by renderTab() -->
                    </div>
                </div>
            </div>
        `;

        this.setupEventListeners();
        this.tryLoadFromCurrentSession();
    }

    setupEventListeners() {
        const loadBtn = document.getElementById('context-load-btn');
        const recentBtn = document.getElementById('context-recent-btn');
        const refreshBtn = document.getElementById('context-refresh');

        if (loadBtn) {
            loadBtn.addEventListener('click', () => this.loadContextStatus());
        }

        if (recentBtn) {
            recentBtn.addEventListener('click', () => this.showRecentSessions());
        }

        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadContextStatus());
        }

        // NEW: Tab navigation
        this.container.addEventListener('click', (e) => {
            const tab = e.target.closest('.context-tab');
            if (tab) {
                const tabName = tab.dataset.tab;
                this.switchTab(tabName);
            }

            // Operation buttons (event delegation)
            const refreshOpBtn = e.target.closest('#context-refresh-op');
            const attachOpBtn = e.target.closest('#context-attach-op');
            const detachOpBtn = e.target.closest('#context-detach-op');

            if (refreshOpBtn) {
                this.refreshContext();
            } else if (attachOpBtn) {
                this.attachContext();
            } else if (detachOpBtn) {
                this.detachContext();
            }
        });
    }

    tryLoadFromCurrentSession() {
        // Try to load from current chat session
        if (window.state && window.state.currentSession) {
            const input = document.getElementById('context-session-select');
            if (input) {
                input.value = window.state.currentSession;
                // Auto-load
                setTimeout(() => this.loadContextStatus(), 300);
            }
        }
    }

    async showRecentSessions() {
        try {
            const response = await apiClient.get('/api/sessions?limit=10');
            if (!response.ok || !response.data) {
                throw new Error('Failed to load sessions');
            }

            const sessions = response.data;
            if (sessions.length === 0) {
                if (window.showToast) {
                    window.showToast('No sessions found', 'info');
                }
                return;
            }

            // Show simple select dialog
            const sessionId = await Dialog.prompt(
                `Select a session ID:\n\n${sessions.map((s, i) => `${i + 1}. ${s.id} (${s.title || 'Untitled'})`).join('\n')}\n\nEnter the session ID:`,
                {
                    title: 'Select Session',
                    defaultValue: sessions[0].id,
                    placeholder: 'Session ID'
                }
            );

            if (sessionId) {
                const input = document.getElementById('context-session-select');
                if (input) {
                    input.value = sessionId.trim();
                    this.loadContextStatus();
                }
            }
        } catch (error) {
            console.error('Failed to load sessions:', error);
            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    async loadContextStatus() {
        const input = document.getElementById('context-session-select');
        const sessionId = input?.value?.trim();

        if (!sessionId) {
            if (window.showToast) {
                window.showToast('Please enter a session ID', 'error');
            }
            return;
        }

        this.sessionId = sessionId;

        try {
            // Show loading
            const statusSection = document.getElementById('context-status-section');
            const contentDiv = document.getElementById('context-status-content');

            if (statusSection) statusSection.classList.remove('hidden');
            if (contentDiv) contentDiv.innerHTML = '<div class="text-center py-4 text-gray-500">Loading context status...</div>';

            // Call API
            const response = await apiClient.get(`/api/context/status?session_id=${encodeURIComponent(sessionId)}`);

            if (!response.ok) {
                throw new Error(response.error || 'Failed to load context status');
            }

            this.contextStatus = response.data || {};

            // Render status
            this.renderContextStatus();

            // Enable refresh button
            const refreshBtn = document.getElementById('context-refresh');
            if (refreshBtn) {
                refreshBtn.disabled = false;
            }

        } catch (error) {
            console.error('Failed to load context status:', error);

            const contentDiv = document.getElementById('context-status-content');
            if (contentDiv) {
                contentDiv.innerHTML = `
                    <div class="text-center py-4 text-red-600">
                        <p>Failed to load context status</p>
                        <p class="text-sm mt-2">${error.message}</p>
                    </div>
                `;
            }

            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    switchTab(tabName) {
        this.currentTab = tabName;

        // Update tab active state
        this.container.querySelectorAll('.context-tab').forEach(tab => {
            if (tab.dataset.tab === tabName) {
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
            }
        });

        // Render tab content
        this.renderTab(tabName);
    }

    renderTab(tabName) {
        const contentDiv = document.getElementById('context-tab-content');
        if (!contentDiv) return;

        switch (tabName) {
            case 'status':
                this.renderStatusTab(contentDiv);
                break;
            case 'budget':
                this.renderBudgetTab(contentDiv);
                break;
            case 'operations':
                this.renderOperationsTab(contentDiv);
                break;
            case 'raw':
                this.renderRawTab(contentDiv);
                break;
        }
    }

    renderStatusTab(container) {
        if (!this.contextStatus) return;

        const status = this.contextStatus;

        // State badge color
        const stateBadge = {
            'EMPTY': 'badge-info',
            'ATTACHED': 'badge-success',
            'BUILDING': 'badge-warning',
            'STALE': 'badge-warning',
            'ERROR': 'badge-error'
        };

        // Create Explain button for this session context
        const explainBtn = new ExplainButton('file', `session:${this.sessionId}`, `Session ${this.sessionId}`);

        container.innerHTML = `
            <div class="detail-section">
                <div class="section-header-with-explain">
                    <h3 class="detail-section-title">Context Status</h3>
                    ${explainBtn.render()}
                </div>
                <div class="config-card">
                    <div class="detail-grid">
                        <div class="detail-item">
                            <span class="detail-label">Session ID</span>
                            <span class="detail-value font-mono text-xs">${this.escapeHtml(status.session_id || this.sessionId)}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">State</span>
                            <span class="detail-value">
                                <span class="badge ${stateBadge[status.state] || 'badge-info'}">${status.state || 'UNKNOWN'}</span>
                            </span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Updated At</span>
                            <span class="detail-value text-sm">
                                ${status.updated_at ? new Date(status.updated_at).toLocaleString() : 'N/A'}
                            </span>
                        </div>
                        ${status.tokens ? `
                            <div class="detail-item">
                                <span class="detail-label">Tokens</span>
                                <span class="detail-value text-sm">
                                    ${status.tokens.prompt_tokens || 0} prompt / ${status.tokens.completion_tokens || 0} completion
                                    (window: ${status.tokens.context_window || 'N/A'})
                                </span>
                            </div>
                        ` : ''}
                        ${status.rag || status.memory ? `
                            <div class="detail-item">
                                <span class="detail-label">Components</span>
                                <span class="detail-value">
                                    ${status.rag ? '<span class="badge badge-info mr-1">RAG</span>' : ''}
                                    ${status.memory ? '<span class="badge badge-info">Memory</span>' : ''}
                                </span>
                            </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    }

    renderBudgetTab(container) {
        if (!this.contextStatus) return;

        const usage = this.contextStatus.usage || {};
        const budget = this.contextStatus.budget || {};

        // Mock data if not available (for now)
        const systemTokens = budget.system_tokens || 1000;
        const windowTokens = budget.window_tokens || 4000;
        const ragTokens = budget.rag_tokens || 2000;
        const memoryTokens = budget.memory_tokens || 1000;

        const usedSystem = usage.tokens_system || 0;
        const usedWindow = usage.tokens_window || 0;
        const usedRag = usage.tokens_rag || 0;
        const usedMemory = usage.tokens_memory || 0;

        const configSource = budget.auto_derived ? 'Auto-derived' : 'Configured';

        container.innerHTML = `
            <div class="detail-section">
                <div class="budget-tab-content">
                    <h3>Configuration Source: ${configSource}</h3>

                    <table class="budget-allocation-table">
                        <thead>
                            <tr>
                                <th>Component</th>
                                <th>Budget</th>
                                <th>Used</th>
                                <th>% Used</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${this.renderBudgetRow('System', systemTokens, usedSystem)}
                            ${this.renderBudgetRow('Window', windowTokens, usedWindow)}
                            ${this.renderBudgetRow('RAG', ragTokens, usedRag)}
                            ${this.renderBudgetRow('Memory', memoryTokens, usedMemory)}
                        </tbody>
                    </table>

                    <div class="trimming-history">
                        <h4>Trimming History (last 5 operations)</h4>
                        <ul>
                            ${this.renderTrimmingLog(usage.trimming_log)}
                        </ul>
                    </div>
                </div>
            </div>
        `;
    }

    renderBudgetRow(component, budget, used) {
        const percent = budget > 0 ? ((used / budget) * 100).toFixed(1) : 0;
        return `
            <tr>
                <td>${component}</td>
                <td>${budget.toLocaleString()}</td>
                <td>${used.toLocaleString()}</td>
                <td>${percent}%</td>
            </tr>
        `;
    }

    renderTrimmingLog(log) {
        if (!log || log.length === 0) {
            return '<li>No trimming operations yet</li>';
        }

        return log.slice(-5).map(entry => `
            <li>
                ${new Date(entry.timestamp).toLocaleString()} -
                Trimmed ${entry.items_removed} ${entry.component} items
                (${(entry.tokens_saved / 1000).toFixed(1)}k tokens)
            </li>
        `).join('');
    }

    renderOperationsTab(container) {
        container.innerHTML = `
            <div class="detail-section">
                <h3 class="detail-section-title">Operations</h3>
                <div class="config-card">
                    <div class="flex gap-3 flex-wrap">
                        <button class="btn-primary" id="context-refresh-op">
                            <span class="material-icons md-18">refresh</span> Refresh Context
                        </button>
                        <button class="btn-secondary" id="context-attach-op">
                            <span class="material-icons md-18">attach_file</span> Attach Context
                        </button>
                        <button class="btn-danger" id="context-detach-op">
                            <span class="material-icons md-18">content_cut</span> Detach Context
                        </button>
                    </div>
                    <div id="context-op-status" class="mt-4"></div>
                </div>
            </div>
        `;
    }

    renderRawTab(container) {
        container.innerHTML = `
            <div class="detail-section">
                <h3 class="detail-section-title">Full Context Data</h3>
                <div class="config-card">
                    <div class="json-viewer-container-context"></div>
                </div>
            </div>
        `;

        // Render JSON viewer
        const jsonContainer = container.querySelector('.json-viewer-container-context');
        if (jsonContainer && this.contextStatus) {
            new JsonViewer(jsonContainer, this.contextStatus);
        }
    }

    renderContextStatus() {
        // NEW: Render the current tab instead of fixed content
        this.renderTab(this.currentTab);

        // Attach ExplainButton handlers
        if (typeof ExplainButton !== 'undefined') {
            ExplainButton.attachHandlers();
        }
    }


    async refreshContext() {
        if (!this.sessionId) {
            if (window.showToast) {
                window.showToast('No session selected', 'error');
            }
            return;
        }

        const statusDiv = document.getElementById('context-op-status');

        try {
            if (statusDiv) {
                statusDiv.innerHTML = '<p class="text-sm text-blue-600">Refreshing context...</p>';
            }

            const response = await apiClient.post('/api/context/refresh', {
                session_id: this.sessionId
            });

            if (!response.ok) {
                throw new Error(response.error || 'Failed to refresh context');
            }

            if (window.showToast) {
                window.showToast('Context refreshed successfully', 'success');
            }

            if (statusDiv) {
                statusDiv.innerHTML = `<p class="text-sm text-green-600"><span class="material-icons md-18">check</span> Context refreshed. New state: ${response.data?.state || 'N/A'}</p>`;
            }

            // Reload status
            setTimeout(() => this.loadContextStatus(), 500);

        } catch (error) {
            console.error('Failed to refresh context:', error);

            if (statusDiv) {
                statusDiv.innerHTML = `<p class="text-sm text-red-600"><span class="material-icons md-18">cancel</span> Error: ${error.message}</p>`;
            }

            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    async attachContext() {
        if (!this.sessionId) {
            if (window.showToast) {
                window.showToast('No session selected', 'error');
            }
            return;
        }

        // Simple attach with defaults
        const statusDiv = document.getElementById('context-op-status');

        try {
            if (statusDiv) {
                statusDiv.innerHTML = '<p class="text-sm text-blue-600">Attaching context...</p>';
            }

            const response = await apiClient.post('/api/context/attach', {
                session_id: this.sessionId,
                memory: { enabled: true, namespace: 'default' },
                rag: { enabled: true }
            });

            if (!response.ok) {
                throw new Error(response.error || 'Failed to attach context');
            }

            if (window.showToast) {
                window.showToast('Context attached successfully', 'success');
            }

            if (statusDiv) {
                statusDiv.innerHTML = '<p class="text-sm text-green-600"><span class="material-icons md-18">check</span> Context attached (Memory + RAG enabled)</p>';
            }

            // Reload status
            setTimeout(() => this.loadContextStatus(), 500);

        } catch (error) {
            console.error('Failed to attach context:', error);

            if (statusDiv) {
                statusDiv.innerHTML = `<p class="text-sm text-red-600"><span class="material-icons md-18">cancel</span> Error: ${error.message}</p>`;
            }

            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    async detachContext() {
        if (!this.sessionId) {
            if (window.showToast) {
                window.showToast('No session selected', 'error');
            }
            return;
        }

        const confirmed = await Dialog.confirm(`Are you sure you want to detach all context from session ${this.sessionId}?`, {
            title: 'Detach Context',
            confirmText: 'Detach',
            danger: true
        });
        if (!confirmed) {
            return;
        }

        const statusDiv = document.getElementById('context-op-status');

        try {
            if (statusDiv) {
                statusDiv.innerHTML = '<p class="text-sm text-blue-600">Detaching context...</p>';
            }

            const response = await apiClient.post(`/api/context/detach?session_id=${encodeURIComponent(this.sessionId)}`);

            if (!response.ok) {
                throw new Error(response.error || 'Failed to detach context');
            }

            if (window.showToast) {
                window.showToast('Context detached successfully', 'success');
            }

            if (statusDiv) {
                statusDiv.innerHTML = '<p class="text-sm text-green-600"><span class="material-icons md-18">check</span> Context detached</p>';
            }

            // Reload status
            setTimeout(() => this.loadContextStatus(), 500);

        } catch (error) {
            console.error('Failed to detach context:', error);

            if (statusDiv) {
                statusDiv.innerHTML = `<p class="text-sm text-red-600"><span class="material-icons md-18">cancel</span> Error: ${error.message}</p>`;
            }

            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
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
    }
}
