/**
 * IntentWorkbenchView - Intent Workbench UI
 *
 * Wave2-C1: Intent Workbench View
 * Coverage: /api/intent/* endpoints (builder explain, evaluator diff, merge proposal)
 *
 * Features:
 * - Builder Explain Viewer: NL → Intent transformation reasoning
 * - Evaluator Diff Viewer: Intent version comparison with field-level diffs
 * - Merge Proposal Generator: Create merge proposals without direct execution
 * - Governance Integration: Submit for Guardian review
 * - Navigation: Task → Intent → Diff flow
 *
 * Author: AgentOS Team
 * Version: 0.3.2
 */

class IntentWorkbenchView {
    constructor(container) {
        this.container = container;
        this.currentIntentId = null;
        this.currentTaskId = null;
        this.currentTab = 'explain';
        this.intentData = null;
        this.diffData = null;
        this.mergeProposal = null;
    }

    /**
     * Initialize and render the view
     * @param {Object} params - URL parameters (task_id, intent_id, tab)
     */
    async render(params = {}) {
        this.currentTaskId = params.task_id || null;
        this.currentIntentId = params.intent_id || null;
        this.currentTab = params.tab || 'explain';

        this.container.innerHTML = `
            <div class="intent-workbench">
                <div class="view-header">
                    <div class="header-left">
                        <h1>Intent Workbench</h1>
                        <p class="text-sm text-gray-600 mt-1">Test and refine intent detection</p>
                        ${this.currentTaskId ? `
                            <div class="breadcrumb">
                                <a href="#" class="breadcrumb-link" id="back-to-task">
                                    <span class="material-icons md-18">arrow_back</span>
                                    Task ${this.currentTaskId}
                                </a>
                            </div>
                        ` : ''}
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="intent-refresh">
                            <span class="material-icons md-18">refresh</span> Refresh
                        </button>
                    </div>
                </div>

                <!-- Intent Selector -->
                <div class="intent-selector-section">
                    <div class="selector-group">
                        <label for="intent-id-input">Intent ID</label>
                        <div class="input-group">
                            <input
                                type="text"
                                id="intent-id-input"
                                placeholder="Enter intent ID or select from task..."
                                value="${this.currentIntentId || ''}"
                                class="form-control"
                            />
                            <button class="btn-primary" id="load-intent-btn">Load Intent</button>
                        </div>
                    </div>
                    ${this.currentTaskId ? `
                        <div class="selector-hint">
                            <span class="material-icons md-18">info</span>
                            Loading intents for task ${this.currentTaskId}
                        </div>
                    ` : ''}
                </div>

                <!-- Tab Navigation -->
                <div class="intent-tabs">
                    <button class="tab-btn ${this.currentTab === 'explain' ? 'active' : ''}" data-tab="explain">
                        Builder Explain
                    </button>
                    <button class="tab-btn ${this.currentTab === 'diff' ? 'active' : ''}" data-tab="diff">
                        Evaluator Diff
                    </button>
                    <button class="tab-btn ${this.currentTab === 'merge' ? 'active' : ''}" data-tab="merge">
                        Merge Proposal
                    </button>
                    <button class="tab-btn ${this.currentTab === 'history' ? 'active' : ''}" data-tab="history">
                        History
                    </button>
                </div>

                <!-- Tab Content -->
                <div class="intent-tab-content">
                    <!-- Builder Explain Tab -->
                    <div class="tab-pane ${this.currentTab === 'explain' ? 'active' : ''}" data-tab-pane="explain">
                        <div id="explain-content" class="explain-loading">
                            ${this.renderEmptyState('explain')}
                        </div>
                    </div>

                    <!-- Evaluator Diff Tab -->
                    <div class="tab-pane ${this.currentTab === 'diff' ? 'active' : ''}" data-tab-pane="diff">
                        <div id="diff-content" class="diff-loading">
                            ${this.renderEmptyState('diff')}
                        </div>
                    </div>

                    <!-- Merge Proposal Tab -->
                    <div class="tab-pane ${this.currentTab === 'merge' ? 'active' : ''}" data-tab-pane="merge">
                        <div id="merge-content" class="merge-loading">
                            ${this.renderEmptyState('merge')}
                        </div>
                    </div>

                    <!-- History Tab -->
                    <div class="tab-pane ${this.currentTab === 'history' ? 'active' : ''}" data-tab-pane="history">
                        <div id="history-content" class="history-loading">
                            ${this.renderEmptyState('history')}
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.setupEventListeners();

        // Auto-load intent if ID provided
        if (this.currentIntentId) {
            await this.loadIntent(this.currentIntentId);
        } else if (this.currentTaskId) {
            await this.loadIntentsForTask(this.currentTaskId);
        }
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Back to task button
        const backBtn = this.container.querySelector('#back-to-task');
        if (backBtn) {
            backBtn.addEventListener('click', (e) => {
                e.preventDefault();
                window.navigateToView('tasks', { task_id: this.currentTaskId });
            });
        }

        // Refresh button
        const refreshBtn = this.container.querySelector('#intent-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                if (this.currentIntentId) {
                    this.loadIntent(this.currentIntentId);
                }
            });
        }

        // Load intent button
        const loadBtn = this.container.querySelector('#load-intent-btn');
        if (loadBtn) {
            loadBtn.addEventListener('click', () => {
                const input = this.container.querySelector('#intent-id-input');
                const intentId = input.value.trim();
                if (intentId) {
                    this.loadIntent(intentId);
                }
            });
        }

        // Intent ID input - Enter key
        const intentInput = this.container.querySelector('#intent-id-input');
        if (intentInput) {
            intentInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    const intentId = e.target.value.trim();
                    if (intentId) {
                        this.loadIntent(intentId);
                    }
                }
            });
        }

        // Tab switching
        const tabBtns = this.container.querySelectorAll('.tab-btn');
        tabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                this.switchTab(btn.dataset.tab);
            });
        });
    }

    /**
     * Switch active tab
     * @param {string} tabName - Tab name
     */
    switchTab(tabName) {
        this.currentTab = tabName;

        // Update tab buttons
        const tabBtns = this.container.querySelectorAll('.tab-btn');
        tabBtns.forEach(btn => {
            if (btn.dataset.tab === tabName) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // Update tab panes
        const tabPanes = this.container.querySelectorAll('.tab-pane');
        tabPanes.forEach(pane => {
            if (pane.dataset.tabPane === tabName) {
                pane.classList.add('active');
            } else {
                pane.classList.remove('active');
            }
        });

        // Load data for tab if needed
        if (this.currentIntentId) {
            switch (tabName) {
                case 'explain':
                    this.loadBuilderExplain(this.currentIntentId);
                    break;
                case 'diff':
                    this.loadEvaluatorDiff();
                    break;
                case 'merge':
                    this.loadMergeProposal();
                    break;
                case 'history':
                    this.loadIntentHistory(this.currentIntentId);
                    break;
            }
        }
    }

    /**
     * Load intent data
     * @param {string} intentId - Intent ID
     */
    async loadIntent(intentId) {
        this.currentIntentId = intentId;

        try {
            const result = await apiClient.get(`/api/intent/${intentId}`, {
                requestId: `intent-${intentId}-${Date.now()}`
            });

            if (result.ok) {
                this.intentData = result.data;
                window.showToast('Intent loaded successfully', 'success', 2000);

                // Load current tab data
                this.switchTab(this.currentTab);
            } else {
                this.renderError('explain', result.message || 'Failed to load intent');
                window.showToast(`Failed to load intent: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Failed to load intent:', error);
            this.renderError('explain', error.message);
            window.showToast('Failed to load intent', 'error');
        }
    }

    /**
     * Load intents for a task
     * @param {string} taskId - Task ID
     */
    async loadIntentsForTask(taskId) {
        try {
            const result = await apiClient.get(`/api/intent/task/${taskId}`, {
                requestId: `intent-task-${taskId}-${Date.now()}`
            });

            if (result.ok && result.data.intents && result.data.intents.length > 0) {
                // Auto-load the first/latest intent
                const latestIntent = result.data.intents[0];
                this.loadIntent(latestIntent.intent_id);
            } else {
                this.renderError('explain', 'No intents found for this task');
            }
        } catch (error) {
            console.error('Failed to load intents for task:', error);
            this.renderError('explain', error.message);
        }
    }

    /**
     * Load builder explain data
     * @param {string} intentId - Intent ID
     */
    async loadBuilderExplain(intentId) {
        const explainContent = this.container.querySelector('#explain-content');
        explainContent.innerHTML = '<div class="loading-spinner">Loading builder explanation...</div>';

        try {
            const result = await apiClient.get(`/api/intent/${intentId}/explain`, {
                requestId: `intent-explain-${intentId}-${Date.now()}`
            });

            if (result.ok) {
                this.renderBuilderExplain(result.data);
            } else {
                this.renderError('explain', result.message || 'Failed to load builder explanation');
            }
        } catch (error) {
            console.error('Failed to load builder explain:', error);
            this.renderError('explain', error.message);
        }
    }

    /**
     * Render builder explain view
     * @param {Object} data - Explain data
     */
    renderBuilderExplain(data) {
        const explainContent = this.container.querySelector('#explain-content');

        const intent = data.intent || this.intentData;
        const explanation = data.explanation || {};
        const nlRequest = data.nl_request || data.original_request || 'N/A';
        const reasoning = explanation.reasoning || data.reasoning || 'No reasoning provided';
        const alternatives = explanation.alternatives || data.alternatives || [];
        const confidence = explanation.confidence || data.confidence || null;

        explainContent.innerHTML = `
            <div class="builder-explain">
                <!-- NL Request Input -->
                <div class="explain-section">
                    <div class="section-header">
                        <h3><span class="material-icons md-18">add_comment</span> Original NL Request</h3>
                    </div>
                    <div class="nl-request-box">
                        <pre>${this.escapeHtml(nlRequest)}</pre>
                    </div>
                </div>

                <!-- Intent Structure -->
                <div class="explain-section">
                    <div class="section-header">
                        <h3><span class="material-icons md-18">account_tree</span> Intent Structure</h3>
                        <div class="section-actions">
                            <button class="btn-secondary btn-sm" id="copy-intent-btn">
                                <span class="material-icons md-18">content_copy</span> Copy
                            </button>
                            <button class="btn-secondary btn-sm" id="search-intent-btn">
                                <span class="material-icons md-18">search</span> Search
                            </button>
                        </div>
                    </div>
                    <div class="intent-json-viewer" id="intent-json-viewer"></div>
                </div>

                <!-- Reasoning & Rationale -->
                <div class="explain-section">
                    <div class="section-header">
                        <h3><span class="material-icons md-18">lightbulb</span> Transformation Reasoning</h3>
                    </div>
                    <div class="reasoning-box">
                        <div class="reasoning-content">${this.escapeHtml(reasoning)}</div>
                    </div>
                </div>

                ${confidence !== null ? `
                    <div class="explain-section">
                        <div class="section-header">
                            <h3><span class="material-icons md-18">analytics</span> Confidence Score</h3>
                        </div>
                        <div class="confidence-indicator">
                            <div class="confidence-bar">
                                <div class="confidence-fill" style="width: ${confidence * 100}%"></div>
                            </div>
                            <span class="confidence-value">${(confidence * 100).toFixed(1)}%</span>
                        </div>
                    </div>
                ` : ''}

                ${alternatives.length > 0 ? `
                    <div class="explain-section">
                        <div class="section-header">
                            <h3><span class="material-icons md-18">alt_route</span> Alternative Interpretations</h3>
                        </div>
                        <div class="alternatives-list">
                            ${alternatives.map((alt, idx) => `
                                <div class="alternative-item">
                                    <div class="alternative-header">
                                        <span class="alternative-number">#${idx + 1}</span>
                                        ${alt.confidence ? `<span class="confidence-badge">${(alt.confidence * 100).toFixed(0)}%</span>` : ''}
                                    </div>
                                    <div class="alternative-description">${this.escapeHtml(alt.description || alt.reason || JSON.stringify(alt))}</div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}

                <!-- Governance Actions -->
                <div class="explain-section governance-section">
                    <div class="section-header">
                        <h3><span class="material-icons md-18">done</span> Governance</h3>
                    </div>
                    <div class="governance-actions">
                        <button class="btn-primary" id="submit-guardian-review-btn">
                            <span class="material-icons md-18">shield</span>
                            Submit for Guardian Review
                        </button>
                        <div class="guardian-status" id="guardian-status">
                            <!-- Guardian review status will be rendered here -->
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Render JSON viewer
        const jsonContainer = explainContent.querySelector('#intent-json-viewer');
        new JsonViewer(jsonContainer, intent, {
            collapsed: false,
            maxDepth: 3,
            showToolbar: true,
            fileName: `intent-${this.currentIntentId}.json`
        });

        // Setup action buttons
        this.setupExplainActions();
    }

    /**
     * Setup builder explain actions
     */
    setupExplainActions() {
        // Copy intent button
        const copyBtn = this.container.querySelector('#copy-intent-btn');
        if (copyBtn) {
            copyBtn.addEventListener('click', async () => {
                const json = JSON.stringify(this.intentData, null, 2);
                try {
                    await navigator.clipboard.writeText(json);
                    window.showToast('Intent copied to clipboard', 'success', 1500);
                } catch (err) {
                    window.showToast('Failed to copy', 'error');
                }
            });
        }

        // Search intent button
        const searchBtn = this.container.querySelector('#search-intent-btn');
        if (searchBtn) {
            searchBtn.addEventListener('click', () => {
                const jsonViewer = this.container.querySelector('#intent-json-viewer');
                // Expand all for search
                const toggles = jsonViewer.querySelectorAll('.json-toggle');
                toggles.forEach(toggle => {
                    const container = toggle.closest('.json-object, .json-array');
                    if (container && container.classList.contains('collapsed')) {
                        toggle.click();
                    }
                });
                window.showToast('Intent structure expanded', 'info', 1500);
            });
        }

        // Submit guardian review button
        const guardianBtn = this.container.querySelector('#submit-guardian-review-btn');
        if (guardianBtn) {
            guardianBtn.addEventListener('click', () => {
                this.submitGuardianReview();
            });
        }

        // Load guardian review status
        this.loadGuardianStatus();
    }

    /**
     * Load evaluator diff
     */
    async loadEvaluatorDiff() {
        const diffContent = this.container.querySelector('#diff-content');
        diffContent.innerHTML = `
            <div class="diff-selector">
                <div class="diff-selector-header">
                    <h3>Select Intents to Compare</h3>
                </div>
                <div class="diff-selector-body">
                    <div class="selector-group">
                        <label>Intent A (Base)</label>
                        <input type="text" id="intent-a-input" placeholder="Intent ID or version" class="form-control" />
                    </div>
                    <div class="selector-group">
                        <label>Intent B (Compare)</label>
                        <input type="text" id="intent-b-input" placeholder="Intent ID or version" class="form-control" value="${this.currentIntentId || ''}" />
                    </div>
                    <button class="btn-primary" id="run-diff-btn">
                        <span class="material-icons md-18">compare</span>
                        Run Diff
                    </button>
                </div>
            </div>
        `;

        // Setup diff actions
        const runDiffBtn = diffContent.querySelector('#run-diff-btn');
        if (runDiffBtn) {
            runDiffBtn.addEventListener('click', () => {
                const intentA = diffContent.querySelector('#intent-a-input').value.trim();
                const intentB = diffContent.querySelector('#intent-b-input').value.trim();
                if (intentA && intentB) {
                    this.runDiff(intentA, intentB);
                } else {
                    window.showToast('Please provide both intent IDs', 'error');
                }
            });
        }
    }

    /**
     * Run diff between two intents
     * @param {string} intentA - Intent A ID
     * @param {string} intentB - Intent B ID
     */
    async runDiff(intentA, intentB) {
        const diffContent = this.container.querySelector('#diff-content');
        diffContent.innerHTML = '<div class="loading-spinner">Running diff analysis...</div>';

        try {
            const result = await apiClient.post('/api/intent/evaluate/diff', {
                intent_a_id: intentA,
                intent_b_id: intentB
            }, {
                requestId: `intent-diff-${Date.now()}`
            });

            if (result.ok) {
                this.diffData = result.data;
                this.renderDiffViewer(result.data);
            } else {
                this.renderError('diff', result.message || 'Failed to run diff');
            }
        } catch (error) {
            console.error('Failed to run diff:', error);
            this.renderError('diff', error.message);
        }
    }

    /**
     * Render diff viewer
     * @param {Object} data - Diff data
     */
    renderDiffViewer(data) {
        const diffContent = this.container.querySelector('#diff-content');

        const intentA = data.intent_a || {};
        const intentB = data.intent_b || {};
        const diff = data.diff || {};
        const changes = diff.changes || [];
        const riskAssessment = data.risk_assessment || {};

        diffContent.innerHTML = `
            <div class="diff-viewer">
                <!-- Diff Header -->
                <div class="diff-header">
                    <div class="diff-meta">
                        <div class="intent-label">
                            <span class="label-tag intent-a">Intent A</span>
                            <code>${intentA.intent_id || 'N/A'}</code>
                        </div>
                        <span class="material-icons md-24">compare_arrows</span>
                        <div class="intent-label">
                            <span class="label-tag intent-b">Intent B</span>
                            <code>${intentB.intent_id || 'N/A'}</code>
                        </div>
                    </div>
                    <div class="diff-summary">
                        <span class="change-count">${changes.length} changes detected</span>
                    </div>
                </div>

                ${riskAssessment.level ? `
                    <div class="risk-assessment-banner risk-${riskAssessment.level.toLowerCase()}">
                        <span class="material-icons md-18">warning</span>
                        <strong>Risk Level: ${riskAssessment.level}</strong>
                        ${riskAssessment.message ? `<span> - ${riskAssessment.message}</span>` : ''}
                    </div>
                ` : ''}

                <!-- Field-Level Diff -->
                <div class="diff-content">
                    ${changes.length > 0 ? `
                        <div class="diff-changes">
                            <div class="changes-sidebar">
                                <h4>Changes</h4>
                                <ul class="changes-nav">
                                    ${changes.map((change, idx) => `
                                        <li class="change-nav-item change-${change.type}" data-change-idx="${idx}">
                                            <span class="change-icon">${this.getChangeIcon(change.type)}</span>
                                            <span class="change-path">${change.path}</span>
                                        </li>
                                    `).join('')}
                                </ul>
                            </div>
                            <div class="changes-detail">
                                ${changes.map((change, idx) => this.renderChangeDetail(change, idx)).join('')}
                            </div>
                        </div>
                    ` : `
                        <div class="no-changes">
                            <span class="material-icons md-48">check_circle</span>
                            <p>No differences detected between the two intents</p>
                        </div>
                    `}
                </div>

                <!-- Actions -->
                <div class="diff-actions">
                    <button class="btn-secondary" id="export-diff-btn">
                        <span class="material-icons md-18">arrow_downward</span>
                        Export Diff
                    </button>
                    <button class="btn-primary" id="create-merge-proposal-btn">
                        <span class="material-icons md-18">alt_route</span>
                        Create Merge Proposal
                    </button>
                </div>
            </div>
        `;

        // Setup diff actions
        this.setupDiffActions();
    }

    /**
     * Render change detail
     * @param {Object} change - Change object
     * @param {number} idx - Index
     * @returns {string} HTML
     */
    renderChangeDetail(change, idx) {
        const typeClass = `change-${change.type}`;
        const icon = this.getChangeIcon(change.type);

        return `
            <div class="change-detail" id="change-${idx}" data-change-idx="${idx}">
                <div class="change-header ${typeClass}">
                    <span class="change-icon">${icon}</span>
                    <span class="change-type">${change.type.toUpperCase()}</span>
                    <code class="change-path">${change.path}</code>
                </div>
                <div class="change-body">
                    <div class="change-comparison">
                        ${change.type !== 'added' ? `
                            <div class="value-panel value-before">
                                <label>Before (Intent A)</label>
                                <pre>${this.escapeHtml(JSON.stringify(change.old_value, null, 2))}</pre>
                            </div>
                        ` : ''}
                        ${change.type !== 'deleted' ? `
                            <div class="value-panel value-after">
                                <label>After (Intent B)</label>
                                <pre>${this.escapeHtml(JSON.stringify(change.new_value, null, 2))}</pre>
                            </div>
                        ` : ''}
                    </div>
                    ${change.risk_note ? `
                        <div class="change-risk-note">
                            <span class="material-icons md-18">warning</span>
                            ${this.escapeHtml(change.risk_note)}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    /**
     * Get change icon
     * @param {string} type - Change type
     * @returns {string} Icon HTML
     */
    getChangeIcon(type) {
        const icons = {
            added: '<span class="material-icons md-18">add_circle</span>',
            deleted: '<span class="material-icons md-18">remove_circle</span>',
            modified: '<span class="material-icons md-18">edit</span>'
        };
        return icons[type] || '<span class="material-icons md-18">radio_button_unchecked</span>';
    }

    /**
     * Setup diff actions
     */
    setupDiffActions() {
        // Change navigation
        const changeNavItems = this.container.querySelectorAll('.change-nav-item');
        changeNavItems.forEach(item => {
            item.addEventListener('click', () => {
                const idx = item.dataset.changeIdx;
                const changeDetail = this.container.querySelector(`#change-${idx}`);
                if (changeDetail) {
                    changeDetail.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            });
        });

        // Export diff button
        const exportBtn = this.container.querySelector('#export-diff-btn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => {
                this.exportDiff();
            });
        }

        // Create merge proposal button
        const mergeBtn = this.container.querySelector('#create-merge-proposal-btn');
        if (mergeBtn) {
            mergeBtn.addEventListener('click', () => {
                this.switchTab('merge');
                this.initializeMergeProposal();
            });
        }
    }

    /**
     * Export diff as JSON
     */
    exportDiff() {
        if (!this.diffData) {
            window.showToast('No diff data to export', 'error');
            return;
        }

        const json = JSON.stringify(this.diffData, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `intent-diff-${Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        window.showToast('Diff exported successfully', 'success', 2000);
    }

    /**
     * Load merge proposal
     */
    async loadMergeProposal() {
        if (this.mergeProposal) {
            this.renderMergeProposal(this.mergeProposal);
        } else {
            this.initializeMergeProposal();
        }
    }

    /**
     * Initialize merge proposal
     */
    initializeMergeProposal() {
        const mergeContent = this.container.querySelector('#merge-content');

        if (!this.diffData) {
            mergeContent.innerHTML = `
                <div class="empty-state">
                    <span class="material-icons md-48">alt_route</span>
                    <h3>No Diff Available</h3>
                    <p>Please run a diff comparison first before creating a merge proposal.</p>
                    <button class="btn-primary" id="goto-diff-tab-btn">Go to Diff Tab</button>
                </div>
            `;

            const gotoBtn = mergeContent.querySelector('#goto-diff-tab-btn');
            if (gotoBtn) {
                gotoBtn.addEventListener('click', () => this.switchTab('diff'));
            }
            return;
        }

        mergeContent.innerHTML = `
            <div class="merge-proposal">
                <div class="merge-header">
                    <h3>Merge Proposal Generator</h3>
                    <p class="merge-hint">Select which fields to keep from each intent. The proposal will be submitted for review before execution.</p>
                </div>

                <div class="merge-selector">
                    <div class="merge-options">
                        <h4>Field Selection</h4>
                        <div id="merge-field-options">
                            ${this.renderMergeFieldOptions()}
                        </div>
                    </div>

                    <div class="merge-preview">
                        <h4>Merge Preview (Read-Only)</h4>
                        <div id="merge-preview-json"></div>
                    </div>
                </div>

                <div class="merge-actions">
                    <button class="btn-secondary" id="reset-merge-btn">
                        <span class="material-icons md-18">refresh</span>
                        Reset
                    </button>
                    <button class="btn-primary" id="generate-merge-proposal-btn">
                        <span class="material-icons md-18">alt_route</span>
                        Generate Merge Proposal
                    </button>
                </div>
            </div>
        `;

        // Setup merge actions
        this.setupMergeActions();
    }

    /**
     * Render merge field options
     * @returns {string} HTML
     */
    renderMergeFieldOptions() {
        if (!this.diffData || !this.diffData.diff || !this.diffData.diff.changes) {
            return '<p class="text-muted">No changes to merge</p>';
        }

        const changes = this.diffData.diff.changes;

        return changes.map((change, idx) => `
            <div class="merge-field-option" data-change-idx="${idx}">
                <div class="field-path">
                    <code>${change.path}</code>
                    <span class="change-type-badge change-${change.type}">${change.type}</span>
                </div>
                <div class="field-choice">
                    ${change.type !== 'added' ? `
                        <label class="choice-option">
                            <input type="radio" name="merge-field-${idx}" value="a" checked />
                            <span>Keep A</span>
                        </label>
                    ` : ''}
                    ${change.type !== 'deleted' ? `
                        <label class="choice-option">
                            <input type="radio" name="merge-field-${idx}" value="b" ${change.type === 'added' ? 'checked' : ''} />
                            <span>Keep B</span>
                        </label>
                    ` : ''}
                    ${change.type !== 'added' && change.type !== 'deleted' ? `
                        <label class="choice-option">
                            <input type="radio" name="merge-field-${idx}" value="manual" />
                            <span>Manual</span>
                        </label>
                    ` : ''}
                </div>
            </div>
        `).join('');
    }

    /**
     * Setup merge actions
     */
    setupMergeActions() {
        // Field selection change
        const mergeOptions = this.container.querySelectorAll('.merge-field-option input[type="radio"]');
        mergeOptions.forEach(radio => {
            radio.addEventListener('change', () => {
                this.updateMergePreview();
            });
        });

        // Reset button
        const resetBtn = this.container.querySelector('#reset-merge-btn');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                this.initializeMergeProposal();
            });
        }

        // Generate proposal button
        const generateBtn = this.container.querySelector('#generate-merge-proposal-btn');
        if (generateBtn) {
            generateBtn.addEventListener('click', () => {
                this.generateMergeProposal();
            });
        }

        // Initial preview
        this.updateMergePreview();
    }

    /**
     * Update merge preview
     */
    updateMergePreview() {
        const previewContainer = this.container.querySelector('#merge-preview-json');
        if (!previewContainer || !this.diffData) return;

        // Collect selections
        const selections = {};
        const changes = this.diffData.diff.changes || [];

        changes.forEach((change, idx) => {
            const selected = this.container.querySelector(`input[name="merge-field-${idx}"]:checked`);
            if (selected) {
                selections[change.path] = selected.value;
            }
        });

        // Build merged intent (simplified)
        const mergedIntent = { ...this.diffData.intent_a };

        changes.forEach(change => {
            const selection = selections[change.path];
            if (selection === 'b') {
                // Apply intent B's value
                this.setNestedValue(mergedIntent, change.path, change.new_value);
            }
            // 'a' means keep current (do nothing)
            // 'manual' would need custom input (not implemented in this version)
        });

        // Render preview
        new JsonViewer(previewContainer, mergedIntent, {
            collapsed: false,
            maxDepth: 3,
            showToolbar: false
        });
    }

    /**
     * Set nested value in object by path
     * @param {Object} obj - Object
     * @param {string} path - Dot-separated path
     * @param {*} value - Value to set
     */
    setNestedValue(obj, path, value) {
        const keys = path.split('.');
        let current = obj;

        for (let i = 0; i < keys.length - 1; i++) {
            if (!current[keys[i]]) {
                current[keys[i]] = {};
            }
            current = current[keys[i]];
        }

        current[keys[keys.length - 1]] = value;
    }

    /**
     * Generate merge proposal
     */
    async generateMergeProposal() {
        const generateBtn = this.container.querySelector('#generate-merge-proposal-btn');
        if (generateBtn) {
            generateBtn.disabled = true;
            generateBtn.innerHTML = '<span class="spinner-sm"></span> Generating...';
        }

        try {
            // Collect selections
            const selections = {};
            const changes = this.diffData.diff.changes || [];

            changes.forEach((change, idx) => {
                const selected = this.container.querySelector(`input[name="merge-field-${idx}"]:checked`);
                if (selected) {
                    selections[change.path] = selected.value;
                }
            });

            const result = await apiClient.post('/api/intent/evaluate/merge-proposal', {
                intent_a_id: this.diffData.intent_a.intent_id,
                intent_b_id: this.diffData.intent_b.intent_id,
                selections: selections
            }, {
                requestId: `intent-merge-proposal-${Date.now()}`
            });

            if (result.ok) {
                this.mergeProposal = result.data;
                window.showToast('Merge proposal generated successfully', 'success');
                this.renderMergeProposal(result.data);
            } else {
                window.showToast(`Failed to generate proposal: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Failed to generate merge proposal:', error);
            window.showToast('Failed to generate merge proposal', 'error');
        } finally {
            if (generateBtn) {
                generateBtn.disabled = false;
                generateBtn.innerHTML = '<span class="material-icons md-18">alt_route</span> Generate Merge Proposal';
            }
        }
    }

    /**
     * Render merge proposal
     * @param {Object} proposal - Proposal data
     */
    renderMergeProposal(proposal) {
        const mergeContent = this.container.querySelector('#merge-content');

        mergeContent.innerHTML = `
            <div class="merge-proposal-result">
                <div class="proposal-header">
                    <h3>Merge Proposal Generated</h3>
                    <span class="proposal-id">ID: ${proposal.proposal_id || 'N/A'}</span>
                </div>

                <div class="proposal-summary">
                    <div class="summary-card">
                        <label>Status</label>
                        <span class="status-badge status-${proposal.status || 'pending'}">${proposal.status || 'PENDING'}</span>
                    </div>
                    <div class="summary-card">
                        <label>Created</label>
                        <span>${this.formatTimestamp(proposal.created_at)}</span>
                    </div>
                    <div class="summary-card">
                        <label>Changes</label>
                        <span>${proposal.change_count || 0} fields</span>
                    </div>
                </div>

                <div class="proposal-content">
                    <h4>Merged Intent Preview</h4>
                    <div id="proposal-intent-json"></div>
                </div>

                <div class="proposal-actions">
                    <button class="btn-secondary" id="back-to-merge-btn">
                        <span class="material-icons md-18">arrow_back</span>
                        Back to Editor
                    </button>
                    <button class="btn-primary" id="submit-proposal-review-btn">
                        <span class="material-icons md-18">send</span>
                        Submit for Approval
                    </button>
                </div>
            </div>
        `;

        // Render merged intent JSON
        const jsonContainer = mergeContent.querySelector('#proposal-intent-json');
        new JsonViewer(jsonContainer, proposal.merged_intent || {}, {
            collapsed: false,
            maxDepth: 3,
            showToolbar: true,
            fileName: `merge-proposal-${proposal.proposal_id}.json`
        });

        // Setup actions
        const backBtn = mergeContent.querySelector('#back-to-merge-btn');
        if (backBtn) {
            backBtn.addEventListener('click', () => {
                this.mergeProposal = null;
                this.initializeMergeProposal();
            });
        }

        const submitBtn = mergeContent.querySelector('#submit-proposal-review-btn');
        if (submitBtn) {
            submitBtn.addEventListener('click', () => {
                this.submitProposalForReview(proposal.proposal_id);
            });
        }
    }

    /**
     * Submit proposal for review
     * @param {string} proposalId - Proposal ID
     */
    async submitProposalForReview(proposalId) {
        try {
            const result = await apiClient.post(`/api/intent/proposals/${proposalId}/submit-review`, {}, {
                requestId: `proposal-review-${proposalId}-${Date.now()}`
            });

            if (result.ok) {
                window.showToast('Proposal submitted for Guardian review', 'success');
                // Refresh proposal data
                this.loadMergeProposal();
            } else {
                window.showToast(`Failed to submit: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Failed to submit proposal:', error);
            window.showToast('Failed to submit proposal', 'error');
        }
    }

    /**
     * Load intent history
     * @param {string} intentId - Intent ID
     */
    async loadIntentHistory(intentId) {
        const historyContent = this.container.querySelector('#history-content');
        historyContent.innerHTML = '<div class="loading-spinner">Loading intent history...</div>';

        try {
            const result = await apiClient.get(`/api/intent/${intentId}/history`, {
                requestId: `intent-history-${intentId}-${Date.now()}`
            });

            if (result.ok) {
                this.renderIntentHistory(result.data);
            } else {
                this.renderError('history', result.message || 'Failed to load history');
            }
        } catch (error) {
            console.error('Failed to load intent history:', error);
            this.renderError('history', error.message);
        }
    }

    /**
     * Render intent history
     * @param {Object} data - History data
     */
    renderIntentHistory(data) {
        const historyContent = this.container.querySelector('#history-content');
        const versions = data.versions || [];

        if (versions.length === 0) {
            historyContent.innerHTML = this.renderEmptyState('history');
            return;
        }

        historyContent.innerHTML = `
            <div class="intent-history">
                <div class="history-timeline">
                    ${versions.map((version, idx) => `
                        <div class="history-item" data-version-idx="${idx}">
                            <div class="history-marker"></div>
                            <div class="history-content">
                                <div class="history-header">
                                    <span class="version-badge">v${version.version}</span>
                                    <span class="version-date">${this.formatTimestamp(version.created_at)}</span>
                                </div>
                                <div class="history-body">
                                    <div class="version-author">
                                        ${version.author ? `By ${version.author}` : 'System generated'}
                                    </div>
                                    ${version.comment ? `
                                        <div class="version-comment">${this.escapeHtml(version.comment)}</div>
                                    ` : ''}
                                    <div class="version-actions">
                                        <button class="btn-link" data-action="view" data-intent-id="${version.intent_id}">
                                            <span class="material-icons md-18">preview</span> View
                                        </button>
                                        ${idx < versions.length - 1 ? `
                                            <button class="btn-link" data-action="diff" data-intent-a="${version.intent_id}" data-intent-b="${versions[idx + 1].intent_id}">
                                                <span class="material-icons md-18">compare</span> Compare
                                            </button>
                                        ` : ''}
                                    </div>
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;

        // Setup history actions
        historyContent.querySelectorAll('[data-action]').forEach(btn => {
            btn.addEventListener('click', () => {
                const action = btn.dataset.action;
                if (action === 'view') {
                    this.loadIntent(btn.dataset.intentId);
                    this.switchTab('explain');
                } else if (action === 'diff') {
                    this.runDiff(btn.dataset.intentA, btn.dataset.intentB);
                    this.switchTab('diff');
                }
            });
        });
    }

    /**
     * Submit for Guardian review
     */
    async submitGuardianReview() {
        if (!this.currentIntentId) {
            window.showToast('No intent loaded', 'error');
            return;
        }

        try {
            const result = await apiClient.post(`/api/guardian/reviews`, {
                target_type: 'intent',
                target_id: this.currentIntentId,
                review_type: 'INTENT_VERIFICATION'
            }, {
                requestId: `guardian-review-intent-${this.currentIntentId}-${Date.now()}`
            });

            if (result.ok) {
                window.showToast('Submitted for Guardian review', 'success');
                this.loadGuardianStatus();
            } else {
                window.showToast(`Failed to submit: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Failed to submit guardian review:', error);
            window.showToast('Failed to submit for review', 'error');
        }
    }

    /**
     * Load guardian review status
     */
    async loadGuardianStatus() {
        const statusContainer = this.container.querySelector('#guardian-status');
        if (!statusContainer || !this.currentIntentId) return;

        try {
            const result = await apiClient.get(`/api/guardian/reviews?target_type=intent&target_id=${this.currentIntentId}`, {
                requestId: `guardian-status-${this.currentIntentId}-${Date.now()}`
            });

            if (result.ok && result.data.reviews && result.data.reviews.length > 0) {
                const latestReview = result.data.reviews[0];
                statusContainer.innerHTML = `
                    <div class="guardian-status-card">
                        <div class="status-header">
                            <span class="material-icons md-18">shield</span>
                            Guardian Review Status
                        </div>
                        <div class="status-body">
                            <div class="status-item">
                                <label>Verdict</label>
                                <span class="badge badge-${this.getVerdictColor(latestReview.verdict)}">${latestReview.verdict}</span>
                            </div>
                            <div class="status-item">
                                <label>Confidence</label>
                                <span>${(latestReview.confidence * 100).toFixed(0)}%</span>
                            </div>
                            <div class="status-item">
                                <label>Guardian</label>
                                <code>${latestReview.guardian_id}</code>
                            </div>
                            <div class="status-item">
                                <label>Reviewed</label>
                                <span>${this.formatTimestamp(latestReview.created_at)}</span>
                            </div>
                        </div>
                    </div>
                `;
            } else {
                statusContainer.innerHTML = `
                    <div class="guardian-status-empty">
                        <span class="material-icons md-18">info</span>
                        No Guardian reviews yet
                    </div>
                `;
            }
        } catch (error) {
            console.error('Failed to load guardian status:', error);
        }
    }

    /**
     * Get verdict color class
     * @param {string} verdict - Verdict
     * @returns {string} Color class
     */
    getVerdictColor(verdict) {
        const colors = {
            'PASS': 'success',
            'FAIL': 'danger',
            'NEEDS_REVIEW': 'warning'
        };
        return colors[verdict] || 'secondary';
    }

    /**
     * Render empty state
     * @param {string} tab - Tab name
     * @returns {string} HTML
     */
    renderEmptyState(tab) {
        const states = {
            explain: {
                icon: 'psychology',
                title: 'No Intent Loaded',
                message: 'Enter an Intent ID above to view the builder explanation and transformation reasoning.'
            },
            diff: {
                icon: 'compare_arrows',
                title: 'No Diff Available',
                message: 'Select two intents to compare and analyze field-level differences.'
            },
            merge: {
                icon: 'merge',
                title: 'No Merge Proposal',
                message: 'Run a diff comparison first, then create a merge proposal.'
            },
            history: {
                icon: 'history',
                title: 'No History Available',
                message: 'Intent version history will appear here once available.'
            }
        };

        const state = states[tab] || states.explain;

        return `
            <div class="empty-state">
                <span class="material-icons md-48">${state.icon}</span>
                <h3>${state.title}</h3>
                <p>${state.message}</p>
            </div>
        `;
    }

    /**
     * Render error state
     * @param {string} tab - Tab name
     * @param {string} message - Error message
     */
    renderError(tab, message) {
        const contentId = `${tab}-content`;
        const content = this.container.querySelector(`#${contentId}`);
        if (!content) return;

        content.innerHTML = `
            <div class="error-state">
                <span class="material-icons md-48">error</span>
                <h3>Error Loading Data</h3>
                <p>${this.escapeHtml(message)}</p>
                <button class="btn-primary" id="retry-btn-${tab}">
                    <span class="material-icons md-18">refresh</span>
                    Retry
                </button>
            </div>
        `;

        const retryBtn = content.querySelector(`#retry-btn-${tab}`);
        if (retryBtn) {
            retryBtn.addEventListener('click', () => {
                if (this.currentIntentId) {
                    this.switchTab(tab);
                }
            });
        }
    }

    /**
     * Format timestamp
     * @param {string} timestamp - ISO timestamp
     * @returns {string} Formatted string
     */
    formatTimestamp(timestamp) {
        if (!timestamp) return 'N/A';

        try {
            const date = new Date(timestamp);
            return date.toLocaleString();
        } catch (e) {
            return timestamp;
        }
    }

    /**
     * Escape HTML
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    escapeHtml(text) {
        if (typeof text !== 'string') {
            text = String(text);
        }

        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };

        return text.replace(/[&<>"']/g, m => map[m]);
    }

    /**
     * Destroy the view
     */
    destroy() {
        this.container.innerHTML = '';
        this.currentIntentId = null;
        this.currentTaskId = null;
        this.intentData = null;
        this.diffData = null;
        this.mergeProposal = null;
    }
}

// Export to window
window.IntentWorkbenchView = IntentWorkbenchView;
