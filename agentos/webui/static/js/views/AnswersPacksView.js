/**
 * AnswersPacksView - Answer Pack Management UI
 *
 * Part of Agent-View-Answers delivery (Wave2-E1 + Wave3-E3)
 *
 * Features:
 * - List answer packs with search/filter
 * - View pack details with Q&A list
 * - Validate pack structure
 * - Generate apply proposal (gated, not direct apply)
 * - Track related tasks/intents
 * - Create new answer pack (audited)
 *
 * API Coverage:
 * - GET /api/answers/packs
 * - POST /api/answers/packs
 * - GET /api/answers/packs/{id}
 * - POST /api/answers/packs/{id}/validate
 * - POST /api/answers/packs/{id}/apply-proposal
 * - GET /api/answers/packs/{id}/related
 */

class AnswersPacksView {
    constructor(container) {
        this.container = container;
        this.currentView = 'list'; // list, detail, create
        this.packs = [];
        this.selectedPack = null;
        this.relatedItems = [];
        this.validationResult = null;

        this.init();
    }

    init() {
        this.renderListView();
        this.loadPacks();
    }

    // ==================== List View ====================

    renderListView() {
        this.currentView = 'list';

        this.container.innerHTML = `
            <div class="answers-view">
                <div class="view-header">
                    <div>
                        <h1>Answer Packs</h1>
                        <p class="text-sm text-gray-600 mt-1">
                            Manage Q&A answer packs
                        </p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="answers-refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                        <button class="btn-primary" id="answers-create">
                            <span class="icon"><span class="material-icons md-18">add</span></span> Create New Pack
                        </button>
                    </div>
                </div>

                <div class="filter-section" style="padding: 1rem 1.5rem; background: white; border-bottom: 1px solid #e5e7eb;">
                    <div style="display: flex; gap: 0.75rem; align-items: center;">
                        <input
                            type="text"
                            id="answers-search"
                            placeholder="Search by name or description..."
                            class="form-control"
                            style="flex: 1; max-width: 400px;"
                        />
                        <select id="answers-status-filter" class="form-control" style="width: 150px;">
                            <option value="">All Status</option>
                            <option value="valid">Valid</option>
                            <option value="invalid">Invalid</option>
                        </select>
                    </div>
                </div>

                <div class="answer-pack-list" id="answers-list-container">
                    <div class="text-center py-8 text-gray-500">
                        Loading answer packs...
                    </div>
                </div>
            </div>
        `;

        this.setupListEventListeners();
    }

    setupListEventListeners() {
        // Refresh button
        const refreshBtn = this.container.querySelector('#answers-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadPacks(true));
        }

        // Create button
        const createBtn = this.container.querySelector('#answers-create');
        if (createBtn) {
            createBtn.addEventListener('click', () => this.renderCreateView());
        }

        // Search input
        const searchInput = this.container.querySelector('#answers-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.filterPacks(e.target.value, this.container.querySelector('#answers-status-filter')?.value);
            });
        }

        // Status filter
        const statusFilter = this.container.querySelector('#answers-status-filter');
        if (statusFilter) {
            statusFilter.addEventListener('change', (e) => {
                this.filterPacks(this.container.querySelector('#answers-search')?.value, e.target.value);
            });
        }
    }

    async loadPacks(forceRefresh = false) {
        try {
            const listContainer = this.container.querySelector('#answers-list-container');
            if (!listContainer) return;

            listContainer.innerHTML = '<div class="text-center py-8 text-gray-500">Loading answer packs...</div>';

            const response = await apiClient.get('/api/answers/packs?limit=100');

            if (!response.ok) {
                throw new Error(response.error || 'Failed to load answer packs');
            }

            this.packs = response.data || [];
            this.renderPacksList();

            if (forceRefresh && window.showToast) {
                window.showToast(`Loaded ${this.packs.length} answer packs`, 'success', 1500);
            }

        } catch (error) {
            console.error('Failed to load answer packs:', error);

            const listContainer = this.container.querySelector('#answers-list-container');
            if (listContainer) {
                listContainer.innerHTML = `
                    <div class="text-center py-8 text-red-600">
                        <p>Failed to load answer packs</p>
                        <p class="text-sm mt-2">${error.message}</p>
                    </div>
                `;
            }

            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    filterPacks(searchQuery = '', status = '') {
        let filteredPacks = [...this.packs];

        if (searchQuery) {
            const query = searchQuery.toLowerCase();
            filteredPacks = filteredPacks.filter(pack =>
                pack.name.toLowerCase().includes(query) ||
                pack.description.toLowerCase().includes(query)
            );
        }

        if (status) {
            filteredPacks = filteredPacks.filter(pack => pack.status === status);
        }

        this.renderPacksList(filteredPacks);
    }

    renderPacksList(packs = this.packs) {
        const listContainer = this.container.querySelector('#answers-list-container');
        if (!listContainer) return;

        if (packs.length === 0) {
            listContainer.innerHTML = `
                <div class="empty-state-answers">
                    <span class="material-icons md-18">help_outline</span>
                    <h3>No answer packs found</h3>
                    <p>Create your first answer pack to get started.</p>
                    <button class="btn-primary" id="empty-create-btn">
                        <span class="material-icons md-18">add</span> Create New Pack
                    </button>
                </div>
            `;

            const emptyCreateBtn = listContainer.querySelector('#empty-create-btn');
            if (emptyCreateBtn) {
                emptyCreateBtn.addEventListener('click', () => this.renderCreateView());
            }

            return;
        }

        listContainer.innerHTML = packs.map(pack => `
            <div class="answer-pack-card" data-pack-id="${pack.id}">
                <div class="answer-pack-card-header">
                    <div style="flex: 1;">
                        <h3 class="answer-pack-title">${this.escapeHtml(pack.name)}</h3>
                        <div class="answer-pack-meta">
                            <span class="meta-item">
                                <span class="material-icons md-16">person</span>
                                ${pack.created_by}
                            </span>
                            <span class="meta-item">
                                <span class="material-icons md-16">schedule</span>
                                ${this.formatDate(pack.created_at)}
                            </span>
                        </div>
                    </div>
                    <span class="badge badge-${pack.status === 'valid' ? 'success' : 'danger'}">
                        <span class="material-icons" style="font-size: 14px; vertical-align: middle;">${pack.status === 'valid' ? 'check' : 'cancel'}</span> ${pack.status}
                    </span>
                </div>

                <p class="answer-pack-description">${this.escapeHtml(pack.description) || '<em>No description</em>'}</p>

                <div class="answer-pack-stats">
                    <div class="stat">
                        <span class="material-icons md-18">help</span>
                        <span>${pack.question_count || pack.answers?.length || 0} questions</span>
                    </div>
                </div>

                <div class="answer-pack-actions">
                    <button class="btn-sm btn-primary pack-view-btn" data-pack-id="${pack.id}">
                        View Details
                    </button>
                    <button class="btn-sm btn-secondary pack-validate-btn" data-pack-id="${pack.id}">
                        <span class="material-icons md-16">check_circle</span> Validate
                    </button>
                </div>
            </div>
        `).join('');

        // Add event listeners to cards
        listContainer.querySelectorAll('.pack-view-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const packId = btn.dataset.packId;
                this.showPackDetail(packId);
            });
        });

        listContainer.querySelectorAll('.pack-validate-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const packId = btn.dataset.packId;
                await this.validatePack(packId);
            });
        });

        // Card click to view details
        listContainer.querySelectorAll('.answer-pack-card').forEach(card => {
            card.addEventListener('click', () => {
                const packId = card.dataset.packId;
                this.showPackDetail(packId);
            });
        });
    }

    // ==================== Detail View ====================

    async showPackDetail(packId) {
        try {
            // Fetch pack details
            const response = await apiClient.get(`/api/answers/packs/${packId}`);

            if (!response.ok) {
                throw new Error(response.error || 'Failed to load pack details');
            }

            this.selectedPack = response.data;

            // Fetch related items in parallel
            const relatedResponse = await apiClient.get(`/api/answers/packs/${packId}/related`);
            this.relatedItems = relatedResponse.ok ? (relatedResponse.data || []) : [];

            this.renderDetailView();

        } catch (error) {
            console.error('Failed to load pack details:', error);
            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    renderDetailView() {
        if (!this.selectedPack) return;

        const pack = this.selectedPack;

        this.container.innerHTML = `
            <div class="answers-view">
                <div class="view-header">
                    <div>
                        <button class="btn-secondary" id="back-to-list">
                            <span class="material-icons md-18">arrow_back</span> Back to List
                        </button>
                    </div>
                    <div class="header-actions">
                        <button class="btn-secondary" id="validate-pack">
                            <span class="material-icons md-18">check_circle</span> Validate
                        </button>
                        <button class="btn-primary" id="apply-proposal-btn">
                            <span class="material-icons md-18">send</span> Apply to Intent
                        </button>
                    </div>
                </div>

                <div class="answer-pack-detail">
                    <!-- Pack Info -->
                    <div class="answer-pack-section">
                        <div style="display: flex; justify-content: space-between; align-items: start;">
                            <div style="flex: 1;">
                                <h2 class="text-2xl font-bold text-gray-900 mb-2">${this.escapeHtml(pack.name)}</h2>
                                <p class="text-gray-600">${this.escapeHtml(pack.description) || '<em>No description</em>'}</p>
                            </div>
                            <span class="badge badge-${pack.status === 'valid' ? 'success' : 'danger'} badge-lg">
                                <span class="material-icons" style="font-size: 14px; vertical-align: middle;">${pack.status === 'valid' ? 'check' : 'cancel'}</span> ${pack.status}
                            </span>
                        </div>
                        <div class="detail-grid mt-4">
                            <div class="detail-item">
                                <span class="detail-label">Created By</span>
                                <span class="detail-value">${pack.created_by}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Created At</span>
                                <span class="detail-value">${new Date(pack.created_at).toLocaleString()}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Questions</span>
                                <span class="detail-value">${pack.question_count || pack.answers?.length || 0}</span>
                            </div>
                        </div>
                    </div>

                    <!-- Validation Results -->
                    <div id="validation-results-container"></div>

                    <!-- Q&A List -->
                    <div class="answer-pack-section">
                        <h3 class="answer-pack-section-title">
                            <span class="material-icons md-20">help</span> Questions & Answers
                        </h3>
                        <div class="qa-list">
                            ${pack.answers.map((qa, idx) => `
                                <div class="qa-item">
                                    <div class="qa-question">
                                        ${this.escapeHtml(qa.question)}
                                        ${qa.type ? `<span class="qa-type-badge">${qa.type}</span>` : ''}
                                    </div>
                                    <div class="qa-answer">
                                        ${this.escapeHtml(qa.answer)}
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>

                    <!-- Related Items -->
                    ${this.relatedItems.length > 0 ? `
                        <div class="answer-pack-section">
                            <h3 class="answer-pack-section-title">
                                <span class="material-icons md-20">link</span> Related Tasks & Intents
                            </h3>
                            <div class="related-items-list">
                                ${this.relatedItems.map(item => `
                                    <div class="related-item" data-item-id="${item.id}" data-item-type="${item.type}">
                                        <div class="related-item-info">
                                            <div class="related-item-name">${this.escapeHtml(item.name)}</div>
                                            <div class="related-item-meta">
                                                ${item.type} • ${item.status}
                                            </div>
                                        </div>
                                        <span class="material-icons md-18">arrow_forward</span>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}

                    <!-- Apply Proposal Section -->
                    <div id="apply-proposal-section" style="display: none;">
                        <!-- Will be populated dynamically -->
                    </div>
                </div>
            </div>
        `;

        this.setupDetailEventListeners();
    }

    setupDetailEventListeners() {
        // Back button
        const backBtn = this.container.querySelector('#back-to-list');
        if (backBtn) {
            backBtn.addEventListener('click', () => this.renderListView());
        }

        // Validate button
        const validateBtn = this.container.querySelector('#validate-pack');
        if (validateBtn) {
            validateBtn.addEventListener('click', () => this.validatePack(this.selectedPack.id));
        }

        // Apply proposal button
        const applyBtn = this.container.querySelector('#apply-proposal-btn');
        if (applyBtn) {
            applyBtn.addEventListener('click', () => this.showApplyProposalForm());
        }

        // Related item clicks
        this.container.querySelectorAll('.related-item').forEach(item => {
            item.addEventListener('click', () => {
                const itemId = item.dataset.itemId;
                const itemType = item.dataset.itemType;
                this.navigateToRelatedItem(itemId, itemType);
            });
        });
    }

    async validatePack(packId) {
        try {
            if (window.showToast) {
                window.showToast('Validating answer pack...', 'info', 1000);
            }

            const response = await apiClient.post(`/api/answers/packs/${packId}/validate`, {});

            if (!response.ok) {
                throw new Error(response.error || 'Validation failed');
            }

            this.validationResult = response.data;

            // If in detail view, render validation results
            if (this.currentView === 'detail') {
                this.renderValidationResults();
            }

            // Update pack status in list
            const pack = this.packs.find(p => p.id === packId);
            if (pack) {
                pack.status = this.validationResult.valid ? 'valid' : 'invalid';
            }

            if (window.showToast) {
                const message = this.validationResult.valid
                    ? '<span class="material-icons md-18">check</span> Validation passed'
                    : '<span class="material-icons md-18">cancel</span> Validation failed';
                window.showToast(message, this.validationResult.valid ? 'success' : 'error');
            }

            // If in list view, reload to show updated status
            if (this.currentView === 'list') {
                this.renderPacksList();
            }

        } catch (error) {
            console.error('Failed to validate pack:', error);
            if (window.showToast) {
                window.showToast(`Validation error: ${error.message}`, 'error');
            }
        }
    }

    renderValidationResults() {
        const container = this.container.querySelector('#validation-results-container');
        if (!container || !this.validationResult) return;

        const result = this.validationResult;

        container.innerHTML = `
            <div class="answer-pack-section">
                <h3 class="answer-pack-section-title">
                    <span class="material-icons md-20">check_circle</span> Validation Results
                </h3>
                <div class="validation-results ${result.valid ? 'valid' : 'invalid'}">
                    <div class="validation-status ${result.valid ? 'valid' : 'invalid'}">
                        <span class="material-icons">${result.valid ? 'check_circle' : 'error'}</span>
                        ${result.valid ? 'All checks passed' : 'Validation failed'}
                    </div>

                    ${result.errors && result.errors.length > 0 ? `
                        <div class="mt-3">
                            <strong class="text-sm">Errors:</strong>
                            <ul class="validation-list errors">
                                ${result.errors.map(err => `
                                    <li>
                                        <span class="material-icons md-16">error</span>
                                        ${this.escapeHtml(err)}
                                    </li>
                                `).join('')}
                            </ul>
                        </div>
                    ` : ''}

                    ${result.warnings && result.warnings.length > 0 ? `
                        <div class="mt-3">
                            <strong class="text-sm">Warnings:</strong>
                            <ul class="validation-list warnings">
                                ${result.warnings.map(warn => `
                                    <li>
                                        <span class="material-icons md-16">warning</span>
                                        ${this.escapeHtml(warn)}
                                    </li>
                                `).join('')}
                            </ul>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    showApplyProposalForm() {
        const section = this.container.querySelector('#apply-proposal-section');
        if (!section) return;

        section.style.display = 'block';
        section.innerHTML = `
            <div class="apply-proposal-section">
                <h3 class="answer-pack-section-title">
                    <span class="material-icons md-20">send</span> Apply to Intent (Proposal Mode)
                </h3>

                <div class="apply-proposal-notice">
                    <span class="material-icons md-18">info</span>
                    <p>
                        <strong>Important:</strong> This will create an apply proposal for review.
                        Changes will NOT be applied directly. The proposal must be approved before execution.
                    </p>
                </div>

                <div style="margin-bottom: 1rem;">
                    <label class="form-label">Target Intent ID *</label>
                    <input
                        type="text"
                        id="target-intent-id"
                        class="form-control"
                        placeholder="intent_001"
                        required
                    />
                    <small class="text-xs text-gray-500">Enter the intent ID where this pack should be applied</small>
                </div>

                <div style="margin-bottom: 1rem;">
                    <label class="form-label">Target Type</label>
                    <select id="target-type" class="form-control">
                        <option value="intent">Intent</option>
                        <option value="workbench">Workbench</option>
                    </select>
                </div>

                <div class="flex gap-2">
                    <button class="btn-primary" id="generate-proposal-btn">
                        <span class="material-icons md-18">send</span> Generate Apply Proposal
                    </button>
                    <button class="btn-secondary" id="cancel-apply-btn">
                        Cancel
                    </button>
                </div>

                <div id="proposal-result" class="mt-4"></div>
            </div>
        `;

        // Setup form handlers
        const generateBtn = section.querySelector('#generate-proposal-btn');
        if (generateBtn) {
            generateBtn.addEventListener('click', () => this.generateApplyProposal());
        }

        const cancelBtn = section.querySelector('#cancel-apply-btn');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => {
                section.style.display = 'none';
            });
        }
    }

    async generateApplyProposal() {
        const targetIntentId = this.container.querySelector('#target-intent-id')?.value?.trim();
        const targetType = this.container.querySelector('#target-type')?.value || 'intent';
        const resultDiv = this.container.querySelector('#proposal-result');

        if (!targetIntentId) {
            if (resultDiv) {
                resultDiv.innerHTML = '<p class="text-sm text-red-600">Target Intent ID is required</p>';
            }
            return;
        }

        try {
            if (resultDiv) {
                resultDiv.innerHTML = '<p class="text-sm text-blue-600">Generating proposal...</p>';
            }

            const response = await apiClient.post(
                `/api/answers/packs/${this.selectedPack.id}/apply-proposal`,
                {
                    target_intent_id: targetIntentId,
                    target_type: targetType
                }
            );

            if (!response.ok) {
                throw new Error(response.error || 'Failed to generate proposal');
            }

            const proposal = response.data;

            if (resultDiv) {
                resultDiv.innerHTML = `
                    <div class="proposal-preview">
                        <div class="flex items-center gap-2 mb-3">
                            <span class="material-icons md-18">check_circle</span>
                            <h4 class="proposal-preview-title">Proposal Generated Successfully</h4>
                        </div>
                        <div class="detail-grid">
                            <div class="detail-item">
                                <span class="detail-label">Proposal ID</span>
                                <span class="detail-value font-mono">${proposal.id}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Target</span>
                                <span class="detail-value">${targetIntentId}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Status</span>
                                <span class="detail-value">
                                    <span class="badge badge-warning">${proposal.status}</span>
                                </span>
                            </div>
                        </div>
                        <div class="mt-3">
                            <strong class="text-sm">Preview:</strong>
                            <ul class="proposal-changes-list mt-2">
                                ${proposal.preview.fields_to_fill?.map(field => `
                                    <li>
                                        <span class="material-icons md-16">edit</span>
                                        <span>${field.field}: <em>${field.value?.substring(0, 50)}${field.value?.length > 50 ? '...' : ''}</em></span>
                                    </li>
                                `).join('') || '<li>No preview available</li>'}
                            </ul>
                        </div>
                        <p class="text-xs text-gray-600 mt-3">
                            push_pin This proposal is now pending approval. It will not be applied until reviewed and approved.
                        </p>
                    </div>
                `;
            }

            if (window.showToast) {
                window.showToast('Apply proposal generated successfully', 'success');
            }

        } catch (error) {
            console.error('Failed to generate proposal:', error);

            if (resultDiv) {
                resultDiv.innerHTML = `<p class="text-sm text-red-600">Error: ${error.message}</p>`;
            }

            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    navigateToRelatedItem(itemId, itemType) {
        if (window.navigateToView) {
            if (itemType === 'task') {
                window.navigateToView('tasks', { task_id: itemId });
            } else if (itemType === 'intent') {
                // Navigate to intent view (if exists)
                window.showToast(`Navigate to intent: ${itemId}`, 'info');
            }
        }
    }

    // ==================== Create View ====================

    renderCreateView() {
        this.currentView = 'create';

        this.container.innerHTML = `
            <div class="answers-view">
                <div class="view-header">
                    <div>
                        <button class="btn-secondary" id="back-to-list-create">
                            <span class="material-icons md-18">arrow_back</span> Back to List
                        </button>
                    </div>
                    <div class="header-actions">
                        <button class="btn-primary" id="save-pack-btn">
                            <span class="material-icons md-18">save</span> Create Answer Pack
                        </button>
                    </div>
                </div>

                <div class="answer-pack-detail">
                    <div class="answer-pack-form">
                        <div class="answer-pack-section">
                            <h3 class="answer-pack-section-title">Pack Information</h3>

                            <div class="form-section">
                                <label class="form-label">Pack Name *</label>
                                <input
                                    type="text"
                                    id="pack-name"
                                    class="form-control"
                                    placeholder="Security Best Practices"
                                    required
                                />
                            </div>

                            <div class="form-section">
                                <label class="form-label">Description</label>
                                <textarea
                                    id="pack-description"
                                    class="form-control"
                                    rows="3"
                                    placeholder="Describe what this answer pack contains..."
                                ></textarea>
                            </div>
                        </div>

                        <div class="answer-pack-section">
                            <h3 class="answer-pack-section-title">Questions & Answers</h3>

                            <div id="qa-items-container" class="qa-form-items">
                                <!-- Q&A items will be added here -->
                            </div>

                            <button class="btn-secondary mt-3" id="add-qa-btn">
                                <span class="material-icons md-18">add</span> Add Q&A Item
                            </button>
                        </div>

                        <div class="answer-pack-section json-import-section">
                            <h4 class="text-sm font-semibold text-gray-700 mb-2">Or Import from JSON</h4>
                            <p class="text-xs text-gray-600 mb-2">
                                Upload a JSON file with answer pack data
                            </p>
                            <input type="file" id="json-import-input" accept=".json" style="display: none;" />
                            <button class="btn-secondary" id="json-import-btn">
                                <span class="material-icons md-18">send</span> Import JSON
                            </button>
                        </div>

                        <div id="create-status" class="mt-4"></div>
                    </div>
                </div>
            </div>
        `;

        this.setupCreateEventListeners();
        this.addQAItem(); // Add initial Q&A item
    }

    setupCreateEventListeners() {
        // Back button
        const backBtn = this.container.querySelector('#back-to-list-create');
        if (backBtn) {
            backBtn.addEventListener('click', () => this.renderListView());
        }

        // Save button
        const saveBtn = this.container.querySelector('#save-pack-btn');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.createAnswerPack());
        }

        // Add Q&A button
        const addQABtn = this.container.querySelector('#add-qa-btn');
        if (addQABtn) {
            addQABtn.addEventListener('click', () => this.addQAItem());
        }

        // JSON import
        const jsonImportBtn = this.container.querySelector('#json-import-btn');
        const jsonImportInput = this.container.querySelector('#json-import-input');

        if (jsonImportBtn && jsonImportInput) {
            jsonImportBtn.addEventListener('click', () => jsonImportInput.click());
            jsonImportInput.addEventListener('change', (e) => this.handleJsonImport(e));
        }
    }

    addQAItem() {
        const container = this.container.querySelector('#qa-items-container');
        if (!container) return;

        const qaCount = container.querySelectorAll('.qa-form-item').length;
        const qaId = Date.now();

        const qaHTML = `
            <div class="qa-form-item" data-qa-id="${qaId}">
                <div class="qa-form-header">
                    <span class="qa-form-number">Question #${qaCount + 1}</span>
                    <button class="qa-form-remove" data-qa-id="${qaId}">
                        <span class="material-icons md-18">delete</span>
                    </button>
                </div>

                <div class="form-section">
                    <label class="form-label">Question *</label>
                    <input
                        type="text"
                        class="form-control qa-question-input"
                        placeholder="What is the security policy?"
                        required
                    />
                </div>

                <div class="form-section">
                    <label class="form-label">Answer *</label>
                    <textarea
                        class="form-control qa-answer-input"
                        rows="3"
                        placeholder="Enter the answer..."
                        required
                    ></textarea>
                </div>

                <div class="form-section">
                    <label class="form-label">Type</label>
                    <select class="form-control qa-type-input">
                        <option value="general">General</option>
                        <option value="security_answer">Security</option>
                        <option value="config_answer">Configuration</option>
                        <option value="technical_answer">Technical</option>
                    </select>
                </div>
            </div>
        `;

        container.insertAdjacentHTML('beforeend', qaHTML);

        // Add remove handler
        const removeBtn = container.querySelector(`[data-qa-id="${qaId}"]`);
        if (removeBtn) {
            removeBtn.addEventListener('click', () => {
                const item = container.querySelector(`.qa-form-item[data-qa-id="${qaId}"]`);
                if (item) {
                    item.remove();
                    this.updateQANumbers();
                }
            });
        }
    }

    updateQANumbers() {
        const items = this.container.querySelectorAll('.qa-form-item');
        items.forEach((item, idx) => {
            const numberSpan = item.querySelector('.qa-form-number');
            if (numberSpan) {
                numberSpan.textContent = `Question #${idx + 1}`;
            }
        });
    }

    async createAnswerPack() {
        const name = this.container.querySelector('#pack-name')?.value?.trim();
        const description = this.container.querySelector('#pack-description')?.value?.trim();
        const statusDiv = this.container.querySelector('#create-status');

        // Validation
        if (!name) {
            if (statusDiv) {
                statusDiv.innerHTML = '<p class="text-sm text-red-600">Pack name is required</p>';
            }
            return;
        }

        // Collect Q&A items
        const qaItems = [];
        const qaElements = this.container.querySelectorAll('.qa-form-item');

        for (const qaEl of qaElements) {
            const question = qaEl.querySelector('.qa-question-input')?.value?.trim();
            const answer = qaEl.querySelector('.qa-answer-input')?.value?.trim();
            const type = qaEl.querySelector('.qa-type-input')?.value || 'general';

            if (!question || !answer) {
                if (statusDiv) {
                    statusDiv.innerHTML = '<p class="text-sm text-red-600">All Q&A fields must be filled</p>';
                }
                return;
            }

            qaItems.push({ question, answer, type });
        }

        if (qaItems.length === 0) {
            if (statusDiv) {
                statusDiv.innerHTML = '<p class="text-sm text-red-600">At least one Q&A item is required</p>';
            }
            return;
        }

        try {
            if (statusDiv) {
                statusDiv.innerHTML = '<p class="text-sm text-blue-600">Creating answer pack...</p>';
            }

            const response = await apiClient.post('/api/answers/packs', {
                name,
                description,
                answers: qaItems
            });

            if (!response.ok) {
                throw new Error(response.error || 'Failed to create answer pack');
            }

            if (window.showToast) {
                window.showToast('Answer pack created successfully', 'success');
            }

            // Navigate back to list
            this.loadPacks();
            this.renderListView();

        } catch (error) {
            console.error('Failed to create answer pack:', error);

            if (statusDiv) {
                statusDiv.innerHTML = `<p class="text-sm text-red-600">Error: ${error.message}</p>`;
            }

            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    handleJsonImport(event) {
        const file = event.target.files?.[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const data = JSON.parse(e.target.result);

                // Populate form with imported data
                if (data.name) {
                    this.container.querySelector('#pack-name').value = data.name;
                }
                if (data.description) {
                    this.container.querySelector('#pack-description').value = data.description;
                }

                // Clear existing Q&A items
                const container = this.container.querySelector('#qa-items-container');
                if (container) {
                    container.innerHTML = '';
                }

                // Add imported Q&A items
                if (data.answers && Array.isArray(data.answers)) {
                    data.answers.forEach(() => this.addQAItem());

                    const qaElements = this.container.querySelectorAll('.qa-form-item');
                    qaElements.forEach((qaEl, idx) => {
                        if (data.answers[idx]) {
                            const qa = data.answers[idx];
                            qaEl.querySelector('.qa-question-input').value = qa.question || '';
                            qaEl.querySelector('.qa-answer-input').value = qa.answer || '';
                            qaEl.querySelector('.qa-type-input').value = qa.type || 'general';
                        }
                    });
                }

                if (window.showToast) {
                    window.showToast('JSON imported successfully', 'success');
                }

            } catch (error) {
                console.error('Failed to parse JSON:', error);
                if (window.showToast) {
                    window.showToast('Failed to parse JSON file', 'error');
                }
            }
        };

        reader.readAsText(file);
    }

    // ==================== Utility Functions ====================

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffDays === 0) return 'Today';
        if (diffDays === 1) return 'Yesterday';
        if (diffDays < 7) return `${diffDays} days ago`;
        return date.toLocaleDateString();
    }

    destroy() {
        // Cleanup
        this.container.innerHTML = '';
    }
}
