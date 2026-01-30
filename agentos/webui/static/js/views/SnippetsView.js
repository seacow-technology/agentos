/**
 * SnippetsView - Code Snippets Management UI
 *
 * Features:
 * - Search snippets with FTS
 * - Filter by tag and language
 * - View snippet details
 * - Copy code to clipboard
 * - Insert code to chat
 * - Generate code explanation
 * - Edit and delete snippets
 *
 * Coverage: GET /api/snippets, GET /api/snippets/{id}, POST /api/snippets/{id}/explain,
 *           PATCH /api/snippets/{id}, DELETE /api/snippets/{id}
 */

class SnippetsView {
    constructor(container) {
        this.container = container;
        this.filterBar = null;
        this.dataTable = null;
        this.detailDrawer = null;
        this.currentFilters = {};
        this.snippets = [];
        this.selectedSnippet = null;
        this.availableTags = [];
        this.availableLanguages = [];

        this.init();
    }

    async init() {
        this.container.innerHTML = `
            <div class="snippets-view">
                <div class="view-header">
                    <div>
                        <h1>Code Snippets</h1>
                        <p class="text-sm text-gray-600 mt-1">Reusable code templates and snippets</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="snippets-refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                    </div>
                </div>

                <div id="snippets-filter-bar" class="filter-section"></div>

                <div id="snippets-table" class="table-section"></div>

                <div id="snippets-detail-drawer" class="drawer hidden">
                    <div class="drawer-overlay" id="snippets-drawer-overlay"></div>
                    <div class="drawer-content">
                        <div class="drawer-header">
                            <h3>Snippet Details</h3>
                            <button class="btn-close" id="snippets-drawer-close">close</button>
                        </div>
                        <div class="drawer-body" id="snippets-drawer-body">
                            <!-- Snippet details will be rendered here -->
                        </div>
                    </div>
                </div>

                <div id="snippets-edit-drawer" class="drawer hidden">
                    <div class="drawer-overlay" id="snippets-edit-overlay"></div>
                    <div class="drawer-content">
                        <div class="drawer-header">
                            <h3>Edit Snippet</h3>
                            <button class="btn-close" id="snippets-edit-close">close</button>
                        </div>
                        <div class="drawer-body" id="snippets-edit-body">
                            <!-- Edit form will be rendered here -->
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Load available tags and languages first
        await this.loadFilterOptions();

        this.setupFilterBar();
        this.setupDataTable();
        this.setupEventListeners();
        this.loadSnippets();
    }

    async loadFilterOptions() {
        try {
            this.availableTags = await SnippetsAPI.getSnippetTags();
            this.availableLanguages = await SnippetsAPI.getSnippetLanguages();
        } catch (error) {
            console.error('Failed to load filter options:', error);
        }
    }

    setupFilterBar() {
        const filterContainer = this.container.querySelector('#snippets-filter-bar');

        const tagOptions = [
            { value: '', label: 'All Tags' },
            ...this.availableTags.map(tag => ({ value: tag, label: tag }))
        ];

        const languageOptions = [
            { value: '', label: 'All Languages' },
            ...this.availableLanguages.map(lang => ({ value: lang, label: lang }))
        ];

        this.filterBar = new FilterBar(filterContainer, {
            filters: [
                {
                    type: 'text',
                    key: 'query',
                    label: 'Search',
                    placeholder: 'Search snippets by title, content, tags...'
                },
                {
                    type: 'select',
                    key: 'tag',
                    label: 'Tag',
                    options: tagOptions
                },
                {
                    type: 'select',
                    key: 'language',
                    label: 'Language',
                    options: languageOptions
                },
                {
                    type: 'button',
                    key: 'reset',
                    label: 'Reset',
                    className: 'btn-secondary'
                }
            ],
            onChange: (filters) => this.handleFilterChange(filters),
            debounceMs: 300
        });
    }

    setupDataTable() {
        const tableContainer = this.container.querySelector('#snippets-table');

        this.dataTable = new DataTable(tableContainer, {
            columns: [
                {
                    key: 'title',
                    label: 'Title',
                    width: '30%',
                    render: (value, row) => `
                        <div class="snippet-title">
                            <div class="title-text">${this.escapeHtml(value)}</div>
                            ${row.description ? `<div class="title-desc">${this.escapeHtml(row.description)}</div>` : ''}
                        </div>
                    `
                },
                {
                    key: 'language',
                    label: 'Language',
                    width: '15%',
                    render: (value) => `<span class="badge badge-language">${this.escapeHtml(value)}</span>`
                },
                {
                    key: 'tags',
                    label: 'Tags',
                    width: '25%',
                    render: (value) => {
                        if (!value || !Array.isArray(value) || value.length === 0) {
                            return '<span class="text-gray-400">No tags</span>';
                        }
                        return value.map(tag =>
                            `<span class="badge badge-tag">${this.escapeHtml(tag)}</span>`
                        ).join(' ');
                    }
                },
                {
                    key: 'created_at',
                    label: 'Created',
                    width: '15%',
                    render: (value) => this.formatTimestamp(value * 1000)  // Convert seconds to milliseconds
                },
                {
                    key: 'actions',
                    label: 'Actions',
                    width: '20%',
                    render: (_, row) => `
                        <div class="table-actions">
                            <button class="btn-sm btn-action" data-action="view" data-id="${row.id}" title="View">
                                <span class="material-icons md-18">preview</span>
                            </button>
                            <button class="btn-sm btn-action" data-action="copy" data-id="${row.id}" title="Copy">
                                <span class="material-icons md-18">content_copy</span>
                            </button>
                            <button class="btn-sm btn-action" data-action="insert" data-id="${row.id}" title="Insert to Chat">
                                <span class="material-icons md-18">add_comment</span>
                            </button>
                            <button class="btn-sm btn-action" data-action="preview" data-id="${row.id}" title="Preview">
                                <span class="material-icons md-18">play_arrow</span>
                            </button>
                            <button class="btn-sm btn-action" data-action="make-task" data-id="${row.id}" title="Create Task">
                                <span class="material-icons md-18">task</span>
                            </button>
                        </div>
                    `
                }
            ],
            data: [],
            emptyText: 'No snippets found',
            loadingText: 'Loading snippets...',
            onRowClick: (snippet, e) => {
                // Don't trigger row click if clicking action buttons
                if (e && e.target && !e.target.closest('.table-actions')) {
                    this.showSnippetDetail(snippet);
                } else if (!e) {
                    // Fallback: if no event object, show detail
                    this.showSnippetDetail(snippet);
                }
            },
            pagination: true,
            pageSize: 10
        });
    }

    setupEventListeners() {
        // Refresh button
        this.container.querySelector('#snippets-refresh').addEventListener('click', () => {
            this.loadSnippets(true);
        });

        // Detail drawer close
        this.container.querySelector('#snippets-drawer-close').addEventListener('click', () => {
            this.hideSnippetDetail();
        });

        this.container.querySelector('#snippets-drawer-overlay').addEventListener('click', () => {
            this.hideSnippetDetail();
        });

        // Edit drawer close
        this.container.querySelector('#snippets-edit-close').addEventListener('click', () => {
            this.hideEditDrawer();
        });

        this.container.querySelector('#snippets-edit-overlay').addEventListener('click', () => {
            this.hideEditDrawer();
        });

        // Event delegation for action buttons
        this.container.addEventListener('click', async (e) => {
            const actionBtn = e.target.closest('[data-action]');
            if (!actionBtn) return;

            const action = actionBtn.dataset.action;
            const snippetId = actionBtn.dataset.id;
            const snippet = this.snippets.find(s => s.id == snippetId);

            if (!snippet) return;

            switch (action) {
                case 'view':
                    this.showSnippetDetail(snippet);
                    break;
                case 'copy':
                    this.copySnippetCode(snippet);
                    break;
                case 'insert':
                    this.insertSnippetToChat(snippet);
                    break;
                case 'preview':
                    await this.previewSnippet(snippet);
                    break;
                case 'make-task':
                    await this.materializeSnippet(snippet);
                    break;
            }
        });

        // Keyboard shortcut: Escape to close drawer
        const handleKeydown = (e) => {
            if (e.key === 'Escape') {
                if (!this.container.querySelector('#snippets-detail-drawer').classList.contains('hidden')) {
                    this.hideSnippetDetail();
                } else if (!this.container.querySelector('#snippets-edit-drawer').classList.contains('hidden')) {
                    this.hideEditDrawer();
                }
            }
        };
        document.addEventListener('keydown', handleKeydown);
    }

    handleFilterChange(filters) {
        this.currentFilters = filters;
        this.loadSnippets();
    }

    async loadSnippets(forceRefresh = false) {
        this.dataTable.setLoading(true);

        try {
            const response = await SnippetsAPI.listSnippets({
                query: this.currentFilters.query,
                tag: this.currentFilters.tag,
                language: this.currentFilters.language,
                limit: 200
            });

            if (response.ok) {
                this.snippets = response.data.snippets || [];
                this.dataTable.setData(this.snippets);

                if (forceRefresh) {
                    showToast('Snippets refreshed', 'success', 2000);
                }
            } else {
                showToast(`Failed to load snippets: ${response.message}`, 'error');
                this.dataTable.setData([]);
            }
        } catch (error) {
            console.error('Failed to load snippets:', error);
            showToast('Failed to load snippets', 'error');
            this.dataTable.setData([]);
        } finally {
            this.dataTable.setLoading(false);
        }
    }

    async showSnippetDetail(snippet) {
        this.selectedSnippet = snippet;
        const drawer = this.container.querySelector('#snippets-detail-drawer');
        const drawerBody = this.container.querySelector('#snippets-drawer-body');

        // Show drawer with loading state
        drawer.classList.remove('hidden');
        drawerBody.innerHTML = '<div class="loading-spinner">Loading snippet details...</div>';

        try {
            // Fetch full snippet details
            const result = await SnippetsAPI.getSnippet(snippet.id);

            if (result.ok) {
                const snippetDetail = result.data;
                this.renderSnippetDetail(snippetDetail);
            } else {
                drawerBody.innerHTML = `
                    <div class="error-message">
                        <div class="error-icon"><span class="material-icons md-18">warning</span></div>
                        <div class="error-text">Failed to load snippet: ${result.message}</div>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Failed to load snippet detail:', error);
            drawerBody.innerHTML = `
                <div class="error-message">
                    <div class="error-icon"><span class="material-icons md-18">warning</span></div>
                    <div class="error-text">Failed to load snippet details</div>
                </div>
            `;
        }
    }

    renderSnippetDetail(snippet) {
        const drawerBody = this.container.querySelector('#snippets-drawer-body');

        drawerBody.innerHTML = `
            <div class="snippet-detail">
                <div class="detail-section">
                    <h4 class="snippet-detail-title">${this.escapeHtml(snippet.title)}</h4>
                    ${snippet.description ? `
                        <p class="snippet-detail-description">${this.escapeHtml(snippet.description)}</p>
                    ` : ''}
                </div>

                <div class="detail-section">
                    <h5>Code</h5>
                    <div class="snippet-code-container">
                        <div class="code-header">
                            <span class="code-language">${this.escapeHtml(snippet.language)}</span>
                            <div class="code-actions">
                                <button class="btn-code-action" id="snippet-copy-code" title="Copy Code">
                                    <span class="material-icons md-18">content_copy</span> Copy
                                </button>
                                <button class="btn-code-action" id="snippet-insert-code" title="Insert to Chat">
                                    <span class="material-icons md-18">add_comment</span> Insert
                                </button>
                            </div>
                        </div>
                        <pre class="code-block"><code class="language-${this.normalizeLang(snippet.language)}">${this.escapeHtml(snippet.code)}</code></pre>
                    </div>
                </div>

                <div class="detail-section">
                    <h5>Metadata</h5>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <label>Language</label>
                            <div class="detail-value">
                                <span class="badge badge-language">${this.escapeHtml(snippet.language)}</span>
                            </div>
                        </div>
                        <div class="detail-item">
                            <label>Tags</label>
                            <div class="detail-value">
                                ${snippet.tags && snippet.tags.length > 0
                                    ? snippet.tags.map(tag => `<span class="badge badge-tag">${this.escapeHtml(tag)}</span>`).join(' ')
                                    : '<span class="text-gray-400">No tags</span>'}
                            </div>
                        </div>
                        <div class="detail-item">
                            <label>Created</label>
                            <div class="detail-value">${this.formatTimestamp(snippet.created_at * 1000)}</div>
                        </div>
                        <div class="detail-item">
                            <label>Updated</label>
                            <div class="detail-value">${this.formatTimestamp(snippet.updated_at * 1000)}</div>
                        </div>
                        ${snippet.source_type ? `
                            <div class="detail-item">
                                <label>Source</label>
                                <div class="detail-value"><code>${this.escapeHtml(snippet.source_type)}</code></div>
                            </div>
                        ` : ''}
                    </div>
                </div>

                <div class="detail-section detail-section-preview-meta" id="preview-meta-${snippet.id}" style="display: none;">
                    <h5>Last Preview</h5>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <label>Preset</label>
                            <div class="detail-value"><code id="last-preset-${snippet.id}"></code></div>
                        </div>
                        <div class="detail-item">
                            <label>Dependencies</label>
                            <div class="detail-value" id="last-deps-${snippet.id}"></div>
                        </div>
                    </div>
                </div>

                <div class="detail-actions">
                    <button class="btn-primary" id="snippet-preview">
                        <span class="material-icons md-18">play_arrow</span> Preview
                    </button>
                    <button class="btn-primary" id="snippet-make-task">
                        <span class="material-icons md-18">task</span> Make Task
                    </button>
                    <button class="btn-secondary" id="snippet-explain">
                        <span class="material-icons md-18">psychology</span> Explain
                    </button>
                    <button class="btn-secondary" id="snippet-edit">
                        <span class="material-icons md-18">edit</span> Edit
                    </button>
                    <button class="btn-danger" id="snippet-delete">
                        <span class="material-icons md-18">delete</span> Delete
                    </button>
                </div>
            </div>
        `;

        // Apply syntax highlighting
        const codeBlock = drawerBody.querySelector('code');
        if (codeBlock && window.Prism) {
            Prism.highlightElement(codeBlock);
        }

        // Setup action buttons
        this.setupSnippetDetailActions(snippet);
    }

    setupSnippetDetailActions(snippet) {
        const drawerBody = this.container.querySelector('#snippets-drawer-body');

        // Copy code button
        const copyBtn = drawerBody.querySelector('#snippet-copy-code');
        if (copyBtn) {
            copyBtn.addEventListener('click', () => {
                this.copySnippetCode(snippet);
            });
        }

        // Insert code button
        const insertBtn = drawerBody.querySelector('#snippet-insert-code');
        if (insertBtn) {
            insertBtn.addEventListener('click', () => {
                this.insertSnippetToChat(snippet);
            });
        }

        // Preview button
        const previewBtn = drawerBody.querySelector('#snippet-preview');
        if (previewBtn) {
            previewBtn.addEventListener('click', async () => {
                await this.previewSnippet(snippet);
            });
        }

        // Make Task button
        const makeTaskBtn = drawerBody.querySelector('#snippet-make-task');
        if (makeTaskBtn) {
            makeTaskBtn.addEventListener('click', async () => {
                await this.materializeSnippet(snippet);
            });
        }

        // Explain button
        const explainBtn = drawerBody.querySelector('#snippet-explain');
        if (explainBtn) {
            explainBtn.addEventListener('click', () => {
                this.showExplainDialog(snippet);
            });
        }

        // Edit button
        const editBtn = drawerBody.querySelector('#snippet-edit');
        if (editBtn) {
            editBtn.addEventListener('click', () => {
                this.showEditDrawer(snippet);
            });
        }

        // Delete button
        const deleteBtn = drawerBody.querySelector('#snippet-delete');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', async () => {
                const confirmed = await Dialog.confirm(`Are you sure you want to delete snippet "${snippet.title}"?`, {
                    title: 'Delete Snippet',
                    confirmText: 'Delete',
                    danger: true
                });
                if (confirmed) {
                    await this.deleteSnippet(snippet.id);
                }
            });
        }
    }

    copySnippetCode(snippet) {
        const code = snippet.code || snippet.content;
        navigator.clipboard.writeText(code);
        showToast('Code copied to clipboard', 'success', 2000);
    }

    insertSnippetToChat(snippet) {
        // Insert code to chat input
        const chatInput = document.querySelector('#chat-input');
        if (chatInput) {
            const code = snippet.code || snippet.content;
            const codeBlock = `\`\`\`${snippet.language}\n${code}\n\`\`\``;
            const currentValue = chatInput.value;
            chatInput.value = currentValue ? `${currentValue}\n\n${codeBlock}` : codeBlock;

            // Focus on chat input
            chatInput.focus();

            // Navigate to chat view if not already there
            if (window.navigateToView) {
                window.navigateToView('chat');
            }

            showToast('Code inserted to chat', 'success', 2000);
            this.hideSnippetDetail();
        } else {
            showToast('Chat input not found', 'error');
        }
    }

    showExplainDialog(snippet) {
        // Remove existing dialog if any
        let dialog = document.getElementById('explain-dialog');
        if (dialog) {
            dialog.remove();
        }

        // Create dialog HTML
        const dialogHTML = `
            <div id="explain-dialog" class="preview-dialog">
                <div class="preview-dialog-overlay"></div>
                <div class="preview-dialog-content" style="width: 500px; height: auto;">
                    <div class="preview-dialog-header">
                        <div class="preview-dialog-title">
                            <span class="material-icons md-18">psychology</span>
                            Explain Code
                        </div>
                        <button class="preview-dialog-close" id="explain-dialog-close">
                            <span class="material-icons md-18">close</span>
                        </button>
                    </div>
                    <div class="preview-dialog-body" style="padding: 1.5rem; overflow-y: auto;">
                        <div class="form-group" style="margin-bottom: 1rem;">
                            <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">Runtime</label>
                            <select id="explain-runtime" class="form-control" style="width: 100%; padding: 0.5rem; border: 1px solid #d1d5db; border-radius: 0.375rem;">
                                <option value="local">Local</option>
                                <option value="cloud">Cloud</option>
                            </select>
                        </div>
                        <div class="form-group" style="margin-bottom: 1rem;">
                            <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">Provider</label>
                            <select id="explain-provider" class="form-control" style="width: 100%; padding: 0.5rem; border: 1px solid #d1d5db; border-radius: 0.375rem;">
                                <option value="ollama">Ollama</option>
                                <option value="lmstudio">LM Studio</option>
                                <option value="llamacpp">llama.cpp</option>
                            </select>
                        </div>
                        <div class="form-group" style="margin-bottom: 1rem;">
                            <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">Model</label>
                            <select id="explain-model" class="form-control" style="width: 100%; padding: 0.5rem; border: 1px solid #d1d5db; border-radius: 0.375rem;">
                                <option value="">Loading models...</option>
                            </select>
                        </div>
                    </div>
                    <div class="preview-dialog-footer">
                        <button class="btn-secondary" id="explain-cancel" style="padding: 0.5rem 1rem;">Cancel</button>
                        <button class="btn-primary" id="explain-confirm" style="padding: 0.5rem 1rem;">Create & Explain</button>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', dialogHTML);
        dialog = document.getElementById('explain-dialog');

        // Event listeners
        dialog.querySelector('#explain-dialog-close').addEventListener('click', () => dialog.remove());
        dialog.querySelector('.preview-dialog-overlay').addEventListener('click', () => dialog.remove());
        dialog.querySelector('#explain-cancel').addEventListener('click', () => dialog.remove());

        // Runtime change -> update provider options
        const runtimeSelect = dialog.querySelector('#explain-runtime');
        const providerSelect = dialog.querySelector('#explain-provider');
        runtimeSelect.addEventListener('change', () => {
            if (runtimeSelect.value === 'cloud') {
                providerSelect.innerHTML = '<option value="anthropic">Anthropic</option>';
            } else {
                providerSelect.innerHTML = `
                    <option value="ollama">Ollama</option>
                    <option value="lmstudio">LM Studio</option>
                    <option value="llamacpp">llama.cpp</option>
                `;
            }
            providerSelect.dispatchEvent(new Event('change'));
        });

        // Provider change -> load models
        providerSelect.addEventListener('change', async () => {
            const modelSelect = dialog.querySelector('#explain-model');
            modelSelect.innerHTML = '<option value="">Loading models...</option>';

            try {
                // Call provider models API to get available models
                const response = await fetch(`/api/providers/${providerSelect.value}/models`);
                if (response.ok) {
                    const data = await response.json();
                    if (data.models && data.models.length > 0) {
                        modelSelect.innerHTML = data.models.map(m =>
                            `<option value="${m.id}">${m.label || m.id}</option>`
                        ).join('');
                    } else {
                        // No models available - provide helpful message
                        const providerName = providerSelect.options[providerSelect.selectedIndex].text;
                        modelSelect.innerHTML = `<option value="">No models (${providerName} not running?)</option>`;
                    }
                } else if (response.status === 404) {
                    modelSelect.innerHTML = '<option value="">Provider not found</option>';
                } else {
                    modelSelect.innerHTML = `<option value="">Failed to load models (HTTP ${response.status})</option>`;
                }
            } catch (error) {
                console.error('Failed to load models:', error);
                modelSelect.innerHTML = '<option value="">Error: Network issue</option>';
            }
        });

        // Trigger initial provider load
        providerSelect.dispatchEvent(new Event('change'));

        // Confirm button
        dialog.querySelector('#explain-confirm').addEventListener('click', async () => {
            const runtime = runtimeSelect.value;
            const provider = providerSelect.value;
            const model = dialog.querySelector('#explain-model').value;

            if (!model) {
                showToast('Please select a model', 'error');
                return;
            }

            dialog.remove();
            await this.explainSnippetWithSession(snippet, { runtime, provider, model });
        });

        // Escape key to close
        const handleEscape = (e) => {
            if (e.key === 'Escape' && dialog.parentElement) {
                dialog.remove();
                document.removeEventListener('keydown', handleEscape);
            }
        };
        document.addEventListener('keydown', handleEscape);
    }

    async explainSnippetWithSession(snippet, config) {
        try {
            showToast('Creating explanation session...', 'info');

            // 1. Get language from config
            const configResponse = await fetch('/api/config');
            const configData = await configResponse.json();
            const language = configData.settings?.language || 'zh';

            // 2. Get explanation prompt
            const promptResponse = await SnippetsAPI.explainSnippet(snippet.id, { lang: language });
            if (!promptResponse.ok || !promptResponse.data?.prompt) {
                showToast('Failed to generate explanation prompt', 'error');
                return;
            }
            const prompt = promptResponse.data.prompt;

            // 3. Create new session
            const sessionResponse = await fetch('/api/sessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title: `Explain: ${snippet.title}`,
                    metadata: {
                        runtime: config.runtime,
                        provider: config.provider,
                        model: config.model,
                        snippet_id: snippet.id
                    }
                })
            });

            if (!sessionResponse.ok) {
                showToast('Failed to create session', 'error');
                return;
            }

            const session = await sessionResponse.json();
            const sessionId = session.id;

            // 4. Hide drawer before navigation (to avoid null reference)
            this.hideSnippetDetail();

            // 5. Navigate to chat view with this session
            showToast('Explanation session created', 'success');

            if (window.navigateToView) {
                window.navigateToView('chat', { session_id: sessionId });
            }

            // 6. Wait for chat view to load and WebSocket to connect, then send prompt
            setTimeout(() => {
                const chatInput = document.getElementById('chat-input');
                const sendBtn = document.getElementById('send-btn');

                if (chatInput && sendBtn) {
                    // Set the prompt in input
                    chatInput.value = prompt;

                    // Trigger send (will use WebSocket to get AI response)
                    sendBtn.click();
                } else {
                    console.warn('Chat input or send button not found, cannot auto-send explanation');
                }
            }, 800);

        } catch (error) {
            console.error('Failed to create explanation session:', error);
            showToast('Failed to create explanation session', 'error');
        }
    }

    showEditDrawer(snippet) {
        const drawer = this.container.querySelector('#snippets-edit-drawer');
        const drawerBody = this.container.querySelector('#snippets-edit-body');

        drawerBody.innerHTML = `
            <div class="edit-form">
                <div class="form-group">
                    <label for="edit-title">Title *</label>
                    <input
                        type="text"
                        id="edit-title"
                        class="form-control"
                        value="${this.escapeHtml(snippet.title)}"
                        required
                    />
                </div>

                <div class="form-group">
                    <label for="edit-description">Description</label>
                    <textarea
                        id="edit-description"
                        class="form-control"
                        rows="2"
                    >${this.escapeHtml(snippet.description || '')}</textarea>
                </div>

                <div class="form-group">
                    <label for="edit-content">Code *</label>
                    <textarea
                        id="edit-content"
                        class="form-control code-textarea"
                        rows="10"
                        required
                    >${this.escapeHtml(snippet.code)}</textarea>
                </div>

                <div class="form-group">
                    <label for="edit-tags">Tags (comma-separated)</label>
                    <input
                        type="text"
                        id="edit-tags"
                        class="form-control"
                        value="${snippet.tags ? snippet.tags.join(', ') : ''}"
                        placeholder="e.g., python, api, utility"
                    />
                </div>

                <div class="form-actions">
                    <button class="btn-primary" id="save-edit-btn">
                        <span class="material-icons md-18">save</span> Save Changes
                    </button>
                    <button class="btn-secondary" id="cancel-edit-btn">Cancel</button>
                </div>
            </div>
        `;

        drawer.classList.remove('hidden');

        // Setup form handlers
        const saveBtn = drawerBody.querySelector('#save-edit-btn');
        const cancelBtn = drawerBody.querySelector('#cancel-edit-btn');

        if (saveBtn) {
            saveBtn.addEventListener('click', async () => {
                await this.saveSnippetEdit(snippet.id);
            });
        }

        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => {
                this.hideEditDrawer();
            });
        }
    }

    async saveSnippetEdit(snippetId) {
        const title = document.getElementById('edit-title')?.value?.trim();
        const description = document.getElementById('edit-description')?.value?.trim();
        const content = document.getElementById('edit-content')?.value?.trim();
        const tagsInput = document.getElementById('edit-tags')?.value?.trim();

        if (!title || !content) {
            showToast('Title and content are required', 'error');
            return;
        }

        try {
            const updateData = {
                title,
                description: description || undefined,
                content
            };

            if (tagsInput) {
                updateData.tags = tagsInput.split(',').map(t => t.trim()).filter(t => t);
            }

            const result = await SnippetsAPI.updateSnippet(snippetId, updateData);

            if (result.ok) {
                showToast('Snippet updated successfully', 'success');
                this.hideEditDrawer();
                this.hideSnippetDetail();
                await this.loadSnippets(true);
            } else {
                showToast(`Failed to update snippet: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Failed to update snippet:', error);
            showToast('Failed to update snippet', 'error');
        }
    }

    async deleteSnippet(snippetId) {
        try {
            const result = await SnippetsAPI.deleteSnippet(snippetId);

            if (result.ok) {
                showToast('Snippet deleted successfully', 'success');
                this.hideSnippetDetail();
                await this.loadSnippets(true);
            } else {
                showToast(`Failed to delete snippet: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Failed to delete snippet:', error);
            showToast('Failed to delete snippet', 'error');
        }
    }

    hideSnippetDetail() {
        const drawer = this.container.querySelector('#snippets-detail-drawer');
        if (drawer) {
            drawer.classList.add('hidden');
        }
        this.selectedSnippet = null;
    }

    hideEditDrawer() {
        const drawer = this.container.querySelector('#snippets-edit-drawer');
        if (drawer) {
            drawer.classList.add('hidden');
        }
    }

    async previewSnippet(snippet) {
        try {
            // Auto-detect preset based on language and content
            let preset = 'html-basic';
            if (snippet.language === 'javascript' || snippet.language === 'js') {
                if (snippet.code && (snippet.code.includes('THREE.') || snippet.code.includes('FontLoader'))) {
                    preset = 'three-webgl-umd';
                }
            }

            showToast('Creating preview...', 'info', 2000);

            // Create preview via API
            const response = await fetch(`/api/snippets/${snippet.id}/preview`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ preset })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to create preview');
            }

            const data = await response.json();

            // Open preview in iframe
            this.openPreviewInDialog(data);

            // Update meta display in detail view
            this.updatePreviewMeta(snippet.id, data.preset, data.deps_injected || []);

            showToast('Preview created', 'success', 2000);

        } catch (err) {
            console.error('Preview failed:', err);
            showToast('Failed to create preview: ' + err.message, 'error', 3000);
        }
    }

    openPreviewInDialog(previewData) {
        // Create a simple preview dialog
        const existingDialog = document.getElementById('snippetPreviewDialog');
        if (existingDialog) {
            existingDialog.remove();
        }

        const dialog = document.createElement('div');
        dialog.id = 'snippetPreviewDialog';
        dialog.className = 'preview-dialog';
        dialog.innerHTML = `
            <div class="preview-dialog-overlay"></div>
            <div class="preview-dialog-content">
                <div class="preview-dialog-header">
                    <div class="preview-dialog-title">
                        <span class="material-icons md-18">play_arrow</span>
                        Preview
                        <span class="preview-preset-badge">${this.escapeHtml(previewData.preset)}</span>
                    </div>
                    <button class="preview-dialog-close" id="closeSnippetPreview">
                        <span class="material-icons md-18">close</span>
                    </button>
                </div>
                <div class="preview-dialog-body">
                    <iframe src="${previewData.url}" sandbox="allow-scripts allow-same-origin" frameborder="0"></iframe>
                </div>
                <div class="preview-dialog-footer">
                    <div class="preview-meta-info">
                        ${previewData.deps_injected && previewData.deps_injected.length > 0
                            ? `<div class="preview-deps">
                                <strong>Dependencies:</strong>
                                ${previewData.deps_injected.map(d => `<code>${this.escapeHtml(d)}</code>`).join(' ')}
                               </div>`
                            : ''}
                        <div class="preview-expiry">Expires: ${this.formatTimestamp(previewData.expires_at * 1000)}</div>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(dialog);

        // Close handlers
        const closeBtn = dialog.querySelector('#closeSnippetPreview');
        const overlay = dialog.querySelector('.preview-dialog-overlay');

        const closeDialog = () => {
            dialog.remove();
        };

        closeBtn.addEventListener('click', closeDialog);
        overlay.addEventListener('click', closeDialog);

        // Escape key
        const handleEscape = (e) => {
            if (e.key === 'Escape') {
                closeDialog();
                document.removeEventListener('keydown', handleEscape);
            }
        };
        document.addEventListener('keydown', handleEscape);
    }

    async materializeSnippet(snippet) {
        try {
            // Determine file extension
            const langExtMap = {
                'javascript': 'js',
                'typescript': 'ts',
                'python': 'py',
                'html': 'html',
                'css': 'css',
                'json': 'json',
                'markdown': 'md',
                'yaml': 'yml',
                'shell': 'sh',
                'bash': 'sh'
            };

            const extension = langExtMap[snippet.language.toLowerCase()] || 'txt';
            const safeName = (snippet.title || 'snippet').replace(/[^a-z0-9]/gi, '_').toLowerCase();
            const defaultPath = `examples/${safeName}.${extension}`;

            // Prompt for target path
            const targetPath = await Dialog.prompt('Enter target file path (relative to project root):', {
                title: 'Create Task',
                defaultValue: defaultPath,
                placeholder: 'examples/demo.html'
            });
            if (!targetPath) return;

            // Validate path
            if (targetPath.startsWith('/')) {
                showToast('Path must be relative (e.g., examples/demo.html)', 'error', 3000);
                return;
            }

            showToast('Creating task draft...', 'info', 2000);

            // Call materialize API
            const response = await fetch(`/api/snippets/${snippet.id}/materialize`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    target_path: targetPath,
                    description: `Write ${snippet.title || 'snippet'} to ${targetPath}`
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to materialize');
            }

            const data = await response.json();

            // Show task draft dialog
            this.showTaskDraftDialog(data.task_draft);

            showToast('Task draft created', 'success', 2000);

        } catch (err) {
            console.error('Materialize failed:', err);
            showToast('Failed to create task: ' + err.message, 'error', 3000);
        }
    }

    showTaskDraftDialog(taskDraft) {
        // Create task draft preview dialog
        const existingDialog = document.getElementById('taskDraftDialog');
        if (existingDialog) {
            existingDialog.remove();
        }

        const dialog = document.createElement('div');
        dialog.id = 'taskDraftDialog';
        dialog.className = 'task-draft-dialog';
        dialog.innerHTML = `
            <div class="task-draft-overlay"></div>
            <div class="task-draft-content">
                <div class="task-draft-header">
                    <div class="task-draft-title">
                        <span class="material-icons md-18">task</span>
                        Task Draft
                    </div>
                    <button class="task-draft-close" id="closeTaskDraft">
                        <span class="material-icons md-18">close</span>
                    </button>
                </div>
                <div class="task-draft-body">
                    <div class="task-draft-section">
                        <h4>${this.escapeHtml(taskDraft.title)}</h4>
                        <p>${this.escapeHtml(taskDraft.description)}</p>
                    </div>

                    <div class="task-draft-section">
                        <h5>Action</h5>
                        <div class="task-draft-info">
                            <div><strong>Type:</strong> ${this.escapeHtml(taskDraft.plan.action)}</div>
                            <div><strong>Target:</strong> <code>${this.escapeHtml(taskDraft.target_path)}</code></div>
                            <div><strong>Language:</strong> <span class="badge badge-language">${this.escapeHtml(taskDraft.language)}</span></div>
                        </div>
                    </div>

                    <div class="task-draft-section">
                        <h5>Files Affected</h5>
                        <ul class="task-draft-files">
                            ${taskDraft.files_affected.map(f => `<li><code>${this.escapeHtml(f)}</code></li>`).join('')}
                        </ul>
                    </div>

                    <div class="task-draft-section">
                        <h5>Risk Level</h5>
                        <span class="badge badge-risk-${taskDraft.risk_level.toLowerCase()}">${this.escapeHtml(taskDraft.risk_level)}</span>
                    </div>

                    ${taskDraft.requires_admin_token ? `
                        <div class="task-draft-warning">
                            <span class="material-icons md-18">warning</span>
                            This task requires admin token authorization.
                        </div>
                    ` : ''}
                </div>
                <div class="task-draft-footer">
                    <p class="task-draft-note">
                        <span class="material-icons md-18">info</span>
                        This is a task draft. To execute this task, go to the Tasks view and create a new task with the above specifications.
                    </p>
                    <button class="btn-primary" id="copyTaskDraft">
                        <span class="material-icons md-18">content_copy</span>
                        Copy Details
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(dialog);

        // Close handlers
        const closeBtn = dialog.querySelector('#closeTaskDraft');
        const overlay = dialog.querySelector('.task-draft-overlay');
        const copyBtn = dialog.querySelector('#copyTaskDraft');

        const closeDialog = () => {
            dialog.remove();
        };

        closeBtn.addEventListener('click', closeDialog);
        overlay.addEventListener('click', closeDialog);

        // Copy task draft as JSON
        copyBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(JSON.stringify(taskDraft, null, 2));
            showToast('Task draft copied to clipboard', 'success', 2000);
        });

        // Escape key
        const handleEscape = (e) => {
            if (e.key === 'Escape') {
                closeDialog();
                document.removeEventListener('keydown', handleEscape);
            }
        };
        document.addEventListener('keydown', handleEscape);
    }

    updatePreviewMeta(snippetId, preset, deps) {
        const metaSection = document.getElementById(`preview-meta-${snippetId}`);
        if (!metaSection) return;

        const presetEl = document.getElementById(`last-preset-${snippetId}`);
        const depsEl = document.getElementById(`last-deps-${snippetId}`);

        if (presetEl) presetEl.textContent = preset;
        if (depsEl) {
            if (deps && deps.length > 0) {
                depsEl.innerHTML = deps.map(d =>
                    `<code class="dep-badge">${this.escapeHtml(d)}</code>`
                ).join(' ');
            } else {
                depsEl.innerHTML = '<span class="text-gray-400">None</span>';
            }
        }

        metaSection.style.display = 'block';
    }

    // Utility functions
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatTimestamp(timestamp) {
        if (!timestamp) return 'N/A';

        try {
            const date = new Date(timestamp);
            const now = new Date();
            const diff = now - date;

            // Less than 1 minute
            if (diff < 60000) {
                return 'Just now';
            }

            // Less than 1 hour
            if (diff < 3600000) {
                const minutes = Math.floor(diff / 60000);
                return `${minutes}m ago`;
            }

            // Less than 24 hours
            if (diff < 86400000) {
                const hours = Math.floor(diff / 3600000);
                return `${hours}h ago`;
            }

            // Format as date
            return date.toLocaleString();
        } catch (e) {
            return timestamp;
        }
    }

    normalizeLang(lang) {
        if (!lang) return 'plaintext';

        const langMap = {
            'js': 'javascript',
            'ts': 'typescript',
            'py': 'python',
            'sh': 'bash',
            'shell': 'bash',
            'yml': 'yaml'
        };

        return langMap[lang.toLowerCase()] || lang.toLowerCase();
    }

    destroy() {
        // Cleanup
        if (this.filterBar && this.filterBar.destroy) {
            this.filterBar.destroy();
        }
        if (this.dataTable && this.dataTable.destroy) {
            this.dataTable.destroy();
        }
        this.container.innerHTML = '';
    }
}

// Export
window.SnippetsView = SnippetsView;
