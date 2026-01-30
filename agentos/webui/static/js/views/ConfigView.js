/**
 * ConfigView - Configuration Management UI
 *
 * PR-4: Skills/Memory/Config Module (Refactored for Control Surface Consistency)
 * Coverage: GET /api/config
 *
 * 改造要点：
 * - 移除 Tab 系统，Raw JSON 改为 Modal
 * - Application Settings 改为 Property Grid
 * - Environment Variables 添加 Filter + Show all
 * - 视觉风格和 RuntimeView 对齐
 */

class ConfigView {
    constructor(container) {
        this.container = container;
        this.config = null;
        this.migrationsStatus = null;
        this.envLimit = 20; // 默认显示前 20 条环境变量
        this.envFilter = ''; // 搜索过滤器

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="config-view">
                <!-- 增强的 PageHeader -->
                <div class="view-header">
                    <div>
                        <h1>Configuration</h1>
                        <p class="text-sm text-gray-600 mt-1">
                            View runtime configuration snapshot
                        </p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="config-refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                        <button class="btn-secondary" id="config-view-raw">
                            <span class="icon"><span class="material-icons md-18">code</span></span> View Raw JSON
                        </button>
                        <button class="btn-secondary" id="config-download">
                            <span class="icon"><span class="material-icons md-18">arrow_downward</span></span> Download
                        </button>
                    </div>
                </div>

                <!-- Content Container (只有 Structured View，移除 Tab) -->
                <div id="config-content" class="config-content">
                    <div class="text-center py-8 text-gray-500">
                        Loading configuration...
                    </div>
                </div>

                <!-- Raw JSON Modal -->
                <div id="raw-json-modal" class="modal" style="display:none">
                    <div class="modal-overlay" id="raw-json-modal-overlay"></div>
                    <div class="modal-content modal-lg">
                        <div class="modal-header">
                            <h3>Full Configuration (JSON)</h3>
                            <button class="modal-close" id="raw-json-modal-close">×</button>
                        </div>
                        <div class="modal-body">
                            <div class="flex justify-end mb-3">
                                <button class="btn-sm btn-secondary" id="copy-raw-json">
                                    <span class="material-icons md-18">content_copy</span> Copy to Clipboard
                                </button>
                            </div>
                            <div class="json-viewer-container" id="raw-json-content"></div>
                            <p class="text-xs text-gray-500 mt-3">
                                info This is a read-only view of the current configuration.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.setupEventListeners();
        this.loadConfig();
    }

    setupEventListeners() {
        // Refresh button
        const refreshBtn = this.container.querySelector('#config-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadConfig(true));
        }

        // View Raw JSON button (打开 Modal)
        const viewRawBtn = this.container.querySelector('#config-view-raw');
        if (viewRawBtn) {
            viewRawBtn.addEventListener('click', () => this.showRawJsonModal());
        }

        // Download button
        const downloadBtn = this.container.querySelector('#config-download');
        if (downloadBtn) {
            downloadBtn.addEventListener('click', () => this.downloadConfig());
        }

        // Modal close handlers
        const modalOverlay = this.container.querySelector('#raw-json-modal-overlay');
        const modalClose = this.container.querySelector('#raw-json-modal-close');
        if (modalOverlay) {
            modalOverlay.addEventListener('click', () => this.hideRawJsonModal());
        }
        if (modalClose) {
            modalClose.addEventListener('click', () => this.hideRawJsonModal());
        }
    }

    async loadConfig(forceRefresh = false) {
        try {
            const contentDiv = this.container.querySelector('#config-content');
            if (!contentDiv) return;

            // Show loading state
            contentDiv.innerHTML = '<div class="text-center py-8 text-gray-500">Loading configuration...</div>';

            // Call APIs in parallel
            const [configResponse, migrationsResponse] = await Promise.all([
                apiClient.get('/api/config'),
                apiClient.get('/api/config/migrations')
            ]);

            if (!configResponse.ok) {
                throw new Error(configResponse.error || 'Failed to load configuration');
            }

            this.config = configResponse.data || {};
            this.migrationsStatus = migrationsResponse.ok ? migrationsResponse.data : null;

            // 渲染 Structured View（唯一视图）
            this.renderStructuredView(contentDiv);

            // Load budget configuration after main config is rendered
            await this.loadBudgetConfig();

            // Show success toast (only on manual refresh)
            if (forceRefresh && window.showToast) {
                window.showToast('Configuration reloaded', 'success', 1500);
            }

        } catch (error) {
            console.error('Failed to load configuration:', error);

            const contentDiv = this.container.querySelector('#config-content');
            if (contentDiv) {
                contentDiv.innerHTML = `
                    <div class="text-center py-8 text-red-600">
                        <p>Failed to load configuration</p>
                        <p class="text-sm mt-2">${error.message}</p>
                    </div>
                `;
            }

            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    renderStructuredView(container) {
        if (!this.config) return;

        const html = `
            <div class="config-structured">
                <!-- Token Budget Configuration (Task 4) -->
                ${this.renderBudgetConfig()}

                <!-- System Overview -->
                <div class="config-section">
                    <h3 class="config-section-title">System Overview</h3>
                    <div class="config-card">
                        <div class="detail-grid">
                            <div class="detail-item">
                                <span class="detail-label">AgentOS Version</span>
                                <span class="detail-value font-semibold">${this.config.version || 'Unknown'}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Python Version</span>
                                <span class="detail-value">${this.config.python_version ? this.config.python_version.split(' ')[0] : 'Unknown'}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Runtime Mode</span>
                                <span class="detail-value">Local (Open)</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Last Loaded</span>
                                <span class="detail-value">${new Date().toLocaleString()}</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Application Settings (Property Grid，不再用 JsonViewer) -->
                ${this.config.settings ? `
                    <div class="config-section">
                        <h3 class="config-section-title">Application Settings</h3>
                        <div class="config-card">
                            <div class="detail-grid">
                                ${Object.entries(this.config.settings).map(([key, value]) => `
                                    <div class="detail-item">
                                        <span class="detail-label">${this.formatLabel(key)}</span>
                                        <span class="detail-value">${this.escapeHtml(String(value))}</span>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                        <p class="text-xs text-gray-500 mt-2">
                            lock Settings are read-only. Edit the config file to make changes.
                        </p>
                    </div>
                ` : ''}

                <!-- Environment Variables (添加 Filter + Show all) -->
                ${this.config.environment && Object.keys(this.config.environment).length > 0 ?
                    this.renderEnvironmentVariables() : ''}

                <!-- Database Migrations -->
                ${this.migrationsStatus ? this.renderDatabaseMigrations() : ''}

                <!-- Quick Actions -->
                <div class="config-section">
                    <h3 class="config-section-title">Quick Actions</h3>
                    <div class="config-card">
                        <div class="flex gap-3 flex-wrap">
                            <button class="btn-secondary" id="view-providers">
                                <span class="material-icons md-18">power</span> View Providers
                            </button>
                            <button class="btn-secondary" id="view-selfcheck">
                                <span class="material-icons md-18">done</span> Run Self-check
                            </button>
                            <button class="btn-secondary" id="download-config-footer">
                                <span class="material-icons md-18">arrow_downward</span> Download Config
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        container.innerHTML = html;

        // Setup Quick Actions
        this.setupQuickActions(container);

        // Setup Environment Filter
        if (this.config.environment && Object.keys(this.config.environment).length > 0) {
            this.setupEnvironmentFilter(container);
        }
    }

    renderDatabaseMigrations() {
        if (!this.migrationsStatus) return '';

        const status = this.migrationsStatus;
        const statusBadge = status.needs_migration
            ? '<span class="badge badge-warning">Pending Migration</span>'
            : '<span class="badge badge-success">Up to Date</span>';

        return `
            <div class="config-section">
                <div class="flex items-center justify-between mb-3">
                    <h3 class="config-section-title">
                        Database Migrations
                        ${statusBadge}
                    </h3>
                </div>
                <div class="config-card">
                    <div class="detail-grid mb-4">
                        <div class="detail-item">
                            <span class="detail-label">Database Path</span>
                            <span class="detail-value font-mono text-xs">${this.escapeHtml(status.db_path)}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Current Version</span>
                            <span class="detail-value font-semibold">${status.current_version ? 'v' + status.current_version : 'Unknown'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Latest Version</span>
                            <span class="detail-value font-semibold">${status.latest_version ? 'v' + status.latest_version : 'Unknown'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Pending Migrations</span>
                            <span class="detail-value ${status.pending_count > 0 ? 'text-orange-600 font-semibold' : ''}">${status.pending_count}</span>
                        </div>
                    </div>

                    ${status.needs_migration ? `
                        <div class="bg-orange-50 border border-orange-200 rounded p-3 mb-4">
                            <div class="flex items-start gap-2">
                                <span class="material-icons md-18">warning</span>
                                <div class="flex-1">
                                    <p class="text-sm text-orange-800 font-medium">Database migration required</p>
                                    <p class="text-xs text-orange-700 mt-1">
                                        Your database is on v${status.current_version}, but v${status.latest_version} is available.
                                        ${status.pending_count} migration(s) need to be applied.
                                    </p>
                                </div>
                            </div>
                        </div>
                    ` : ''}

                    <!-- Available Migrations List -->
                    <div class="mb-4">
                        <h4 class="text-sm font-semibold text-gray-700 mb-2">Available Migrations</h4>
                        <div class="max-h-64 overflow-y-auto">
                            <table class="config-table">
                                <thead>
                                    <tr>
                                        <th>Version</th>
                                        <th>Description</th>
                                        <th>Status</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${status.migrations.map(migration => {
                                        const currentParts = status.current_version ?
                                            status.current_version.split('.').map(Number) : [0, 0, 0];
                                        const migrationParts = migration.version.split('.').map(Number);

                                        const isApplied = migrationParts[0] < currentParts[0] ||
                                                         (migrationParts[0] === currentParts[0] && migrationParts[1] < currentParts[1]) ||
                                                         (migrationParts[0] === currentParts[0] && migrationParts[1] === currentParts[1] && migrationParts[2] <= currentParts[2]);

                                        return `
                                            <tr class="${isApplied ? 'opacity-60' : ''}">
                                                <td class="font-mono text-xs">v${migration.version}</td>
                                                <td class="text-xs">${this.escapeHtml(migration.description)}</td>
                                                <td>
                                                    ${isApplied
                                                        ? '<span class="badge badge-success badge-sm">Applied</span>'
                                                        : '<span class="badge badge-warning badge-sm">Pending</span>'}
                                                </td>
                                            </tr>
                                        `;
                                    }).join('')}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- Migration Actions -->
                    <div class="flex gap-2">
                        ${status.needs_migration ? `
                            <button class="btn-primary" id="run-migrations">
                                <span class="material-icons md-18">arrow_upward</span> Run Migrations
                            </button>
                        ` : ''}
                        <button class="btn-secondary" id="refresh-migrations">
                            <span class="material-icons md-18">refresh</span> Refresh Status
                        </button>
                    </div>
                </div>
                <p class="text-xs text-gray-500 mt-2">
                    info Database migrations are applied automatically. Manual migration is only needed in special cases.
                </p>
            </div>
        `;
    }

    renderEnvironmentVariables() {
        if (!this.config.environment) return '';

        const allEnvs = Object.entries(this.config.environment).sort(([a], [b]) => a.localeCompare(b));
        const totalCount = allEnvs.length;
        const displayedEnvs = allEnvs.slice(0, this.envLimit);
        const hasMore = totalCount > this.envLimit;

        return `
            <div class="config-section">
                <div class="flex items-center justify-between mb-3">
                    <h3 class="config-section-title">
                        Environment Variables
                        <span class="badge badge-info ml-2" id="env-count">${totalCount} variables</span>
                    </h3>
                    <input
                        type="text"
                        id="env-filter"
                        placeholder="search Filter variables..."
                        class="input-sm"
                        style="width: 240px;"
                        value="${this.envFilter}"
                    />
                </div>
                <div class="config-card">
                    <div class="max-h-96 overflow-y-auto">
                        <table class="config-table" id="env-table">
                            <thead>
                                <tr>
                                    <th>Variable</th>
                                    <th>Value</th>
                                    <th style="width: 60px;"></th>
                                </tr>
                            </thead>
                            <tbody>
                                ${displayedEnvs.map(([key, value]) => `
                                    <tr data-env-key="${this.escapeHtml(key.toLowerCase())}">
                                        <td class="font-mono text-xs">${this.escapeHtml(key)}</td>
                                        <td class="font-mono text-xs text-gray-700">${this.escapeHtml(String(value))}</td>
                                        <td>
                                            <button class="btn-icon" title="Copy value" data-copy-value="${this.escapeHtml(String(value))}">
                                                <span class="material-icons md-14">content_copy</span>
                                            </button>
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
                ${hasMore ? `
                    <button class="btn-sm btn-secondary mt-2" id="env-show-all">
                        Show all (${totalCount})
                    </button>
                ` : ''}
                <p class="text-xs text-gray-500 mt-2">
                    info Sensitive values (API keys, secrets, passwords) are automatically filtered.
                </p>
            </div>
        `;
    }

    setupEnvironmentFilter(container) {
        const filterInput = container.querySelector('#env-filter');
        const showAllBtn = container.querySelector('#env-show-all');

        // Filter input
        if (filterInput) {
            filterInput.addEventListener('input', (e) => {
                this.envFilter = e.target.value.toLowerCase();
                this.filterEnvironmentTable();
            });
        }

        // Show all button
        if (showAllBtn) {
            showAllBtn.addEventListener('click', () => {
                this.envLimit = Object.keys(this.config.environment).length;
                const contentDiv = this.container.querySelector('#config-content');
                if (contentDiv) {
                    this.renderStructuredView(contentDiv);
                }
            });
        }

        // Copy value buttons
        const copyButtons = container.querySelectorAll('.btn-icon[data-copy-value]');
        copyButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const value = e.currentTarget.dataset.copyValue;
                navigator.clipboard.writeText(value).then(() => {
                    if (window.showToast) {
                        window.showToast('Value copied to clipboard', 'success', 1000);
                    }
                });
            });
        });
    }

    filterEnvironmentTable() {
        const table = this.container.querySelector('#env-table tbody');
        if (!table) return;

        const rows = table.querySelectorAll('tr');
        let visibleCount = 0;

        rows.forEach(row => {
            const key = row.dataset.envKey || '';
            if (key.includes(this.envFilter)) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        });

        // Update count badge
        const countBadge = this.container.querySelector('#env-count');
        if (countBadge) {
            const totalCount = rows.length;
            countBadge.textContent = this.envFilter
                ? `${visibleCount} of ${totalCount} variables`
                : `${totalCount} variables`;
        }
    }

    showRawJsonModal() {
        if (!this.config) {
            if (window.showToast) {
                window.showToast('No configuration loaded', 'error');
            }
            return;
        }

        const modal = this.container.querySelector('#raw-json-modal');
        const content = this.container.querySelector('#raw-json-content');

        if (modal && content) {
            // Render JSON viewer
            content.innerHTML = '';
            new JsonViewer(content, this.config);

            // Show modal
            modal.style.display = 'flex';

            // Setup copy button
            const copyBtn = this.container.querySelector('#copy-raw-json');
            if (copyBtn) {
                // Remove existing listeners
                const newCopyBtn = copyBtn.cloneNode(true);
                copyBtn.parentNode.replaceChild(newCopyBtn, copyBtn);

                newCopyBtn.addEventListener('click', () => {
                    const jsonString = JSON.stringify(this.config, null, 2);
                    navigator.clipboard.writeText(jsonString).then(() => {
                        if (window.showToast) {
                            window.showToast('Configuration copied to clipboard', 'success', 1500);
                        }
                    });
                });
            }
        }
    }

    hideRawJsonModal() {
        const modal = this.container.querySelector('#raw-json-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    setupQuickActions(container) {
        const viewProvidersBtn = container.querySelector('#view-providers');
        if (viewProvidersBtn) {
            viewProvidersBtn.addEventListener('click', () => {
                if (window.navigateToView) {
                    window.navigateToView('providers');
                }
            });
        }

        const viewSelfcheckBtn = container.querySelector('#view-selfcheck');
        if (viewSelfcheckBtn) {
            viewSelfcheckBtn.addEventListener('click', () => {
                if (window.navigateToView) {
                    window.navigateToView('support');
                }
            });
        }

        const downloadConfigBtn = container.querySelector('#download-config-footer');
        if (downloadConfigBtn) {
            downloadConfigBtn.addEventListener('click', () => this.downloadConfig());
        }

        // Database Migration actions
        const runMigrationsBtn = container.querySelector('#run-migrations');
        if (runMigrationsBtn) {
            runMigrationsBtn.addEventListener('click', () => this.runMigrations());
        }

        const refreshMigrationsBtn = container.querySelector('#refresh-migrations');
        if (refreshMigrationsBtn) {
            refreshMigrationsBtn.addEventListener('click', () => this.loadConfig(true));
        }
    }

    async runMigrations() {
        if (!this.migrationsStatus || !this.migrationsStatus.needs_migration) {
            if (window.showToast) {
                window.showToast('No migrations needed', 'info');
            }
            return;
        }

        const fromVersion = this.migrationsStatus.current_version;
        const toVersion = this.migrationsStatus.latest_version;

        const confirmed = await Dialog.confirm(
            `Run database migration from v${fromVersion} to v${toVersion}?\n\n${this.migrationsStatus.pending_count} migration(s) will be applied.\n\nThis operation cannot be undone.`,
            {
                title: 'Run Database Migration',
                confirmText: 'Run Migration',
                danger: true
            }
        );
        if (!confirmed) {
            return;
        }

        try {
            // Show loading state
            const runBtn = this.container.querySelector('#run-migrations');
            if (runBtn) {
                runBtn.disabled = true;
                runBtn.innerHTML = '<span class="material-icons md-18">hourglass_empty</span> Running...';
            }

            if (window.showToast) {
                window.showToast('Running database migrations...', 'info', 2000);
            }

            // Call migration API
            const response = await apiClient.post('/api/config/migrations/migrate', {
                target_version: null // null = latest
            });

            if (!response.ok) {
                throw new Error(response.error || 'Migration failed');
            }

            const result = response.data;

            if (window.showToast) {
                window.showToast(
                    `<span class="material-icons md-18">check</span> Migration successful: v${result.from_version} <span class="material-icons md-18">arrow_forward</span> v${result.to_version} (${result.migrations_executed} migration(s))`,
                    'success',
                    3000
                );
            }

            // Reload configuration to show updated status
            await this.loadConfig(false);

        } catch (error) {
            console.error('Failed to run migrations:', error);

            if (window.showToast) {
                window.showToast(`Migration failed: ${error.message}`, 'error', 5000);
            }

            // Re-enable button
            const runBtn = this.container.querySelector('#run-migrations');
            if (runBtn) {
                runBtn.disabled = false;
                runBtn.innerHTML = '<span class="material-icons md-18">arrow_upward</span> Run Migrations';
            }
        }
    }

    downloadConfig() {
        if (!this.config) {
            if (window.showToast) {
                window.showToast('No configuration loaded', 'error');
            }
            return;
        }

        try {
            const jsonString = JSON.stringify(this.config, null, 2);
            const blob = new Blob([jsonString], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `agentos-config-${new Date().toISOString().split('T')[0]}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            if (window.showToast) {
                window.showToast('Configuration downloaded', 'success', 1500);
            }
        } catch (error) {
            console.error('Failed to download config:', error);
            if (window.showToast) {
                window.showToast('Download failed', 'error');
            }
        }
    }

    formatLabel(key) {
        // 将 snake_case 转为 Title Case
        return key
            .split('_')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
    }

    renderBudgetConfig() {
        return `
            <div class="config-section" id="budget-config-section">
                <h3 class="config-section-title">
                    <span class="material-icons md-18">account_balance_wallet</span>
                    Token Budget Configuration
                </h3>
                <div class="config-card">
                    <div id="budget-config-content" class="budget-loading">
                        <div class="spinner"></div>
                        <span style="margin-left: 10px;">Loading budget configuration...</span>
                    </div>
                </div>

                <!-- P2-9: Budget Recommendation Card (collapsed by default) -->
                <div id="budget-recommendation-section" style="display: none; margin-top: 16px;">
                </div>
            </div>
        `;
    }

    async loadBudgetConfig() {
        try {
            const response = await apiClient.get('/api/budget/global');

            if (!response.ok) {
                throw new Error(response.error || 'Failed to load budget configuration');
            }

            this.budgetConfig = response.data || response;
            await this.loadCurrentModelInfo();
            this.renderBudgetConfigContent();

        } catch (error) {
            console.error('Failed to load budget config:', error);
            const contentDiv = this.container.querySelector('#budget-config-content');
            if (contentDiv) {
                contentDiv.innerHTML = `
                    <div class="budget-error">
                        <span class="material-icons md-18">error</span>
                        Failed to load budget configuration: ${error.message}
                    </div>
                `;
            }
        }
    }

    async loadCurrentModelInfo() {
        try {
            const response = await apiClient.get('/api/runtime/config');
            if (response.ok && response.data) {
                this.currentModelInfo = {
                    name: response.data.model || 'unknown',
                    context_window: response.data.context_window || 128000
                };
            }
        } catch (error) {
            console.warn('Failed to load current model info:', error);
            this.currentModelInfo = {
                name: 'unknown',
                context_window: 128000
            };
        }
    }

    renderBudgetConfigContent() {
        const contentDiv = this.container.querySelector('#budget-config-content');
        if (!contentDiv || !this.budgetConfig) return;

        const config = this.budgetConfig;
        const autoDeriveChecked = config.auto_derive ? 'checked' : '';

        contentDiv.innerHTML = `
            <!-- Info Banner -->
            <div class="budget-info-banner">
                <span class="material-icons md-18">info</span>
                <p>
                    Token budget controls how AgentOS allocates context space for conversations, RAG, and memory.
                    Enable auto-derive to automatically calculate optimal budgets based on your model's context window.
                </p>
            </div>

            <!-- Auto-Derive Toggle -->
            <div class="budget-auto-derive">
                <input type="checkbox" id="budget-auto-derive" ${autoDeriveChecked}>
                <label for="budget-auto-derive">Auto-derive from model (recommended)</label>
                <span class="badge badge-info">Smart</span>
            </div>

            <!-- Preview Box -->
            <div class="budget-preview-box" id="budget-preview-box">
                <h4>Current Configuration</h4>
                <div class="budget-preview-grid">
                    <div class="budget-preview-item">
                        <span class="budget-preview-label">Model</span>
                        <span class="budget-preview-value">${this.escapeHtml(this.currentModelInfo.name)}</span>
                    </div>
                    <div class="budget-preview-item">
                        <span class="budget-preview-label">Context Window</span>
                        <span class="budget-preview-value">${this.formatNumber(this.currentModelInfo.context_window)} tokens</span>
                    </div>
                    <div class="budget-preview-item">
                        <span class="budget-preview-label">Input Budget</span>
                        <span class="budget-preview-value highlight">${this.formatNumber(config.max_tokens)} tokens</span>
                    </div>
                    <div class="budget-preview-item">
                        <span class="budget-preview-label">Generation Limit</span>
                        <span class="budget-preview-value highlight">${this.formatNumber(config.generation_max_tokens)} tokens</span>
                    </div>
                </div>
            </div>

            <!-- Advanced Settings -->
            <div class="budget-advanced-section">
                <h4>Advanced Settings (Optional Override)</h4>
                <div class="budget-advanced-fields">
                    <div class="budget-field">
                        <label for="budget-max-tokens">Max Input Tokens</label>
                        <input type="number" id="budget-max-tokens"
                               value="${config.max_tokens}"
                               ${config.auto_derive ? 'disabled' : ''}>
                        <span class="field-hint">${config.auto_derive ? '(auto)' : 'Total context budget'}</span>
                    </div>
                    <div class="budget-field">
                        <label for="budget-generation">Max Generation Tokens</label>
                        <input type="number" id="budget-generation"
                               value="${config.generation_max_tokens}"
                               ${config.auto_derive ? 'disabled' : ''}>
                        <span class="field-hint">${config.auto_derive ? '(auto)' : 'Output token limit'}</span>
                    </div>
                    <div class="budget-field">
                        <label for="budget-window">Conversation Window</label>
                        <input type="number" id="budget-window"
                               value="${config.allocation.window_tokens}"
                               ${config.auto_derive ? 'disabled' : ''}>
                        <span class="field-hint">${config.auto_derive ? '(auto)' : 'Recent messages'}</span>
                    </div>
                    <div class="budget-field">
                        <label for="budget-rag">RAG Context</label>
                        <input type="number" id="budget-rag"
                               value="${config.allocation.rag_tokens}"
                               ${config.auto_derive ? 'disabled' : ''}>
                        <span class="field-hint">${config.auto_derive ? '(auto)' : 'Knowledge base results'}</span>
                    </div>
                    <div class="budget-field">
                        <label for="budget-memory">Memory Facts</label>
                        <input type="number" id="budget-memory"
                               value="${config.allocation.memory_tokens}"
                               ${config.auto_derive ? 'disabled' : ''}>
                        <span class="field-hint">${config.auto_derive ? '(auto)' : 'Pinned memories'}</span>
                    </div>
                    <div class="budget-field">
                        <label for="budget-system">System Prompt</label>
                        <input type="number" id="budget-system"
                               value="${config.allocation.system_tokens}"
                               ${config.auto_derive ? 'disabled' : ''}>
                        <span class="field-hint">${config.auto_derive ? '(auto)' : 'System instructions'}</span>
                    </div>
                </div>
            </div>

            <!-- Save Actions -->
            <div class="budget-save-actions">
                <button class="btn-secondary" id="budget-reset">
                    <span class="material-icons md-18">restart_alt</span> Reset to Defaults
                </button>
                <button class="btn-secondary" id="budget-show-recommendation">
                    <span class="material-icons md-18">lightbulb</span> Show Smart Recommendation
                </button>
                <button class="btn-primary" id="budget-save">
                    <span class="material-icons md-18">save</span> Save Configuration
                </button>
            </div>
        `;

        this.setupBudgetEventListeners();
    }

    setupBudgetEventListeners() {
        const autoDeriveCheckbox = this.container.querySelector('#budget-auto-derive');
        const saveBtn = this.container.querySelector('#budget-save');
        const resetBtn = this.container.querySelector('#budget-reset');
        const showRecommendationBtn = this.container.querySelector('#budget-show-recommendation');

        if (autoDeriveCheckbox) {
            autoDeriveCheckbox.addEventListener('change', async (e) => {
                const enabled = e.target.checked;
                await this.handleAutoDeriveToggle(enabled);
            });
        }

        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.saveBudgetConfig());
        }

        if (resetBtn) {
            resetBtn.addEventListener('click', () => this.resetBudgetConfig());
        }

        if (showRecommendationBtn) {
            showRecommendationBtn.addEventListener('click', () => this.loadBudgetRecommendation());
        }
    }

    async handleAutoDeriveToggle(enabled) {
        try {
            // Toggle field states
            const fields = this.container.querySelectorAll('.budget-field input');
            fields.forEach(field => {
                field.disabled = enabled;
                const hint = field.parentElement.querySelector('.field-hint');
                if (hint) {
                    hint.textContent = enabled ? '(auto)' : hint.dataset.originalHint || '';
                }
            });

            // If enabling auto-derive, preview the result
            if (enabled) {
                await this.previewDerivedBudget();
            }

        } catch (error) {
            console.error('Failed to toggle auto-derive:', error);
            if (window.showToast) {
                window.showToast('Failed to toggle auto-derive', 'error');
            }
        }
    }

    async previewDerivedBudget() {
        try {
            if (window.showToast) {
                window.showToast('Calculating optimal budget...', 'info', 1500);
            }

            const response = await apiClient.post('/api/budget/derive', {
                model_id: this.currentModelInfo.name,
                context_window: this.currentModelInfo.context_window
            });

            if (!response.ok) {
                throw new Error(response.error || 'Failed to derive budget');
            }

            const derived = response.data || response;

            // Update preview values
            const maxTokensInput = this.container.querySelector('#budget-max-tokens');
            const generationInput = this.container.querySelector('#budget-generation');
            const windowInput = this.container.querySelector('#budget-window');
            const ragInput = this.container.querySelector('#budget-rag');
            const memoryInput = this.container.querySelector('#budget-memory');
            const systemInput = this.container.querySelector('#budget-system');

            if (maxTokensInput) maxTokensInput.value = derived.budget.max_tokens;
            if (generationInput) generationInput.value = derived.budget.generation_max_tokens;
            if (windowInput) windowInput.value = derived.budget.allocation.window_tokens;
            if (ragInput) ragInput.value = derived.budget.allocation.rag_tokens;
            if (memoryInput) memoryInput.value = derived.budget.allocation.memory_tokens;
            if (systemInput) systemInput.value = derived.budget.allocation.system_tokens;

            // Update preview box
            const previewBox = this.container.querySelector('#budget-preview-box');
            if (previewBox) {
                const inputBudgetValue = previewBox.querySelector('.budget-preview-value.highlight');
                if (inputBudgetValue) {
                    inputBudgetValue.textContent = this.formatNumber(derived.budget.max_tokens) + ' tokens';
                }
            }

            if (window.showToast) {
                window.showToast('Budget calculated successfully', 'success', 1500);
            }

        } catch (error) {
            console.error('Failed to preview derived budget:', error);
            if (window.showToast) {
                window.showToast(`Preview failed: ${error.message}`, 'error');
            }
        }
    }

    async saveBudgetConfig() {
        try {
            const autoDeriveCheckbox = this.container.querySelector('#budget-auto-derive');
            const autoDeriveEnabled = autoDeriveCheckbox ? autoDeriveCheckbox.checked : false;

            const requestData = {
                auto_derive: autoDeriveEnabled
            };

            // If manual mode, include field values
            if (!autoDeriveEnabled) {
                const maxTokens = parseInt(this.container.querySelector('#budget-max-tokens')?.value || '8000');
                const generation = parseInt(this.container.querySelector('#budget-generation')?.value || '2000');
                const window = parseInt(this.container.querySelector('#budget-window')?.value || '4000');
                const rag = parseInt(this.container.querySelector('#budget-rag')?.value || '2000');
                const memory = parseInt(this.container.querySelector('#budget-memory')?.value || '1000');
                const system = parseInt(this.container.querySelector('#budget-system')?.value || '1000');

                requestData.max_tokens = maxTokens;
                requestData.generation_max_tokens = generation;
                requestData.window_tokens = window;
                requestData.rag_tokens = rag;
                requestData.memory_tokens = memory;
                requestData.system_tokens = system;
            }

            if (window.showToast) {
                window.showToast('Saving budget configuration...', 'info', 1500);
            }

            const response = await apiClient.put('/api/budget/global', requestData);

            if (!response.ok) {
                throw new Error(response.error || 'Failed to save budget configuration');
            }

            this.budgetConfig = response.data || response;

            if (window.showToast) {
                window.showToast('Budget configuration saved successfully', 'success', 2000);
            }

            // Reload budget config to reflect changes
            await this.loadBudgetConfig();

        } catch (error) {
            console.error('Failed to save budget config:', error);
            if (window.showToast) {
                window.showToast(`Save failed: ${error.message}`, 'error');
            }
        }
    }

    async resetBudgetConfig() {
        const confirmed = await Dialog.confirm(
            'Reset budget configuration to defaults?\n\nThis will restore the default 8k context window allocation.',
            {
                title: 'Reset Budget Configuration',
                confirmText: 'Reset',
                danger: false
            }
        );

        if (!confirmed) return;

        try {
            const defaultConfig = {
                auto_derive: false,
                max_tokens: 8000,
                generation_max_tokens: 2000,
                window_tokens: 4000,
                rag_tokens: 2000,
                memory_tokens: 1000,
                system_tokens: 1000
            };

            const response = await apiClient.put('/api/budget/global', defaultConfig);

            if (!response.ok) {
                throw new Error(response.error || 'Failed to reset budget configuration');
            }

            if (window.showToast) {
                window.showToast('Budget configuration reset to defaults', 'success', 2000);
            }

            // Reload budget config
            await this.loadBudgetConfig();

        } catch (error) {
            console.error('Failed to reset budget config:', error);
            if (window.showToast) {
                window.showToast(`Reset failed: ${error.message}`, 'error');
            }
        }
    }

    async loadBudgetRecommendation() {
        try {
            const recommendationSection = this.container.querySelector('#budget-recommendation-section');
            if (!recommendationSection) return;

            // Show loading state
            recommendationSection.style.display = 'block';
            recommendationSection.innerHTML = `
                <div class="config-card">
                    <div class="budget-loading">
                        <div class="spinner"></div>
                        <span style="margin-left: 10px;">Analyzing usage patterns...</span>
                    </div>
                </div>
            `;

            // Get current session ID (from chat or use default)
            const sessionId = window.currentSessionId || 'default';

            // Request recommendation
            const response = await apiClient.post('/api/budget/recommend', {
                session_id: sessionId,
                model_id: this.currentModelInfo.name,
                context_window: this.currentModelInfo.context_window,
                last_n: 30
            });

            if (!response.ok) {
                throw new Error(response.error || 'Failed to load recommendation');
            }

            const data = response.data || response;

            if (!data.available) {
                this.renderRecommendationUnavailable(recommendationSection, data);
            } else {
                this.renderRecommendation(recommendationSection, data);
            }

        } catch (error) {
            console.error('Failed to load budget recommendation:', error);
            const recommendationSection = this.container.querySelector('#budget-recommendation-section');
            if (recommendationSection) {
                recommendationSection.innerHTML = `
                    <div class="config-card">
                        <div class="budget-error">
                            <span class="material-icons md-18">error</span>
                            Failed to load recommendation: ${error.message}
                        </div>
                    </div>
                `;
            }
            if (window.showToast) {
                window.showToast(`Recommendation failed: ${error.message}`, 'error');
            }
        }
    }

    renderRecommendationUnavailable(container, data) {
        container.innerHTML = `
            <div class="config-card" style="background: #f9fafb; border: 1px solid #e5e7eb;">
                <div style="display: flex; align-items: start; gap: 12px;">
                    <span class="material-icons md-18">info</span>
                    <div style="flex: 1;">
                        <h4 style="margin: 0 0 8px 0; font-size: 14px; font-weight: 600; color: #374151;">
                            Smart Recommendation Not Available
                        </h4>
                        <p style="margin: 0 0 12px 0; font-size: 13px; color: #6b7280;">
                            ${this.escapeHtml(data.hint || 'Unable to generate recommendation.')}
                        </p>
                        ${data.reason === 'insufficient_data' ? `
                            <div style="display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: #f3f4f6; border-radius: 6px; font-size: 12px; color: #4b5563;">
                                <span class="material-icons md-14">analytics</span>
                                <span>Minimum ${data.min_samples} conversations needed</span>
                            </div>
                        ` : ''}
                        <button class="btn-sm btn-secondary" id="dismiss-recommendation" style="margin-top: 12px;">
                            <span class="material-icons md-14">close</span> Dismiss
                        </button>
                    </div>
                </div>
            </div>
        `;

        const dismissBtn = container.querySelector('#dismiss-recommendation');
        if (dismissBtn) {
            dismissBtn.addEventListener('click', () => {
                container.style.display = 'none';
            });
        }
    }

    renderRecommendation(container, data) {
        const current = data.current;
        const recommended = data.recommended;
        const stats = data.stats;

        // Calculate changes
        const changes = {
            window: this.calculateChange(current.window_tokens, recommended.window_tokens),
            rag: this.calculateChange(current.rag_tokens, recommended.rag_tokens),
            memory: this.calculateChange(current.memory_tokens, recommended.memory_tokens),
            system: this.calculateChange(current.system_tokens, recommended.system_tokens)
        };

        const totalSavings = recommended.metadata.estimated_savings;
        const confidenceBadge = this.getConfidenceBadge(recommended.metadata.confidence);

        container.innerHTML = `
            <div class="config-card" style="background: linear-gradient(to bottom, #fefce8, #ffffff); border: 2px solid #fbbf24;">
                <div style="display: flex; align-items: start; gap: 12px;">
                    <span class="material-icons md-18">lightbulb</span>
                    <div style="flex: 1;">
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
                            <h4 style="margin: 0; font-size: 16px; font-weight: 600; color: #374151;">
                                Smart Recommendation
                            </h4>
                            ${confidenceBadge}
                        </div>

                        <p style="margin: 0 0 16px 0; font-size: 13px; color: #4b5563; line-height: 1.5;">
                            ${this.escapeHtml(data.message || 'Based on your usage patterns, we recommend the following budget adjustments.')}
                        </p>

                        <!-- Comparison Table -->
                        <div style="overflow-x: auto; margin-bottom: 16px;">
                            <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                                <thead>
                                    <tr style="background: #f9fafb; border-bottom: 2px solid #e5e7eb;">
                                        <th style="padding: 8px 12px; text-align: left; font-weight: 600; color: #374151;">Component</th>
                                        <th style="padding: 8px 12px; text-align: right; font-weight: 600; color: #374151;">Current</th>
                                        <th style="padding: 8px 12px; text-align: right; font-weight: 600; color: #374151;">Recommended</th>
                                        <th style="padding: 8px 12px; text-align: right; font-weight: 600; color: #374151;">Change</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${this.renderComparisonRow('Window', current.window_tokens, recommended.window_tokens, changes.window)}
                                    ${this.renderComparisonRow('RAG', current.rag_tokens, recommended.rag_tokens, changes.rag)}
                                    ${this.renderComparisonRow('Memory', current.memory_tokens, recommended.memory_tokens, changes.memory)}
                                    ${this.renderComparisonRow('System', current.system_tokens, recommended.system_tokens, changes.system)}
                                    <tr style="border-top: 2px solid #e5e7eb; font-weight: 600; background: #fafafa;">
                                        <td style="padding: 10px 12px;">Total</td>
                                        <td style="padding: 10px 12px; text-align: right;">${this.formatNumber(current.window_tokens + current.rag_tokens + current.memory_tokens + current.system_tokens)}</td>
                                        <td style="padding: 10px 12px; text-align: right;">${this.formatNumber(recommended.max_tokens)}</td>
                                        <td style="padding: 10px 12px; text-align: right;">${this.formatChangePercent(totalSavings)}</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>

                        <!-- Stats Summary -->
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 16px; padding: 12px; background: #f9fafb; border-radius: 6px;">
                            <div>
                                <div style="font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em;">Based On</div>
                                <div style="font-size: 15px; font-weight: 600; color: #374151;">${stats.sample_size} conversations</div>
                            </div>
                            <div>
                                <div style="font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em;">Est. Savings</div>
                                <div style="font-size: 15px; font-weight: 600; color: ${totalSavings > 0 ? '#10b981' : '#ef4444'};">${totalSavings > 0 ? '-' : '+'}${Math.abs(totalSavings).toFixed(0)}%</div>
                            </div>
                            ${stats.truncation_rate > 0.1 ? `
                            <div>
                                <div style="font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em;">Truncation Rate</div>
                                <div style="font-size: 15px; font-weight: 600; color: #ef4444;">${(stats.truncation_rate * 100).toFixed(0)}%</div>
                            </div>
                            ` : ''}
                        </div>

                        <!-- Actions -->
                        <div style="display: flex; gap: 8px; align-items: center;">
                            <button class="btn-primary" id="apply-recommendation-btn">
                                <span class="material-icons md-18">check_circle</span> Apply Recommendation
                            </button>
                            <button class="btn-secondary" id="dismiss-recommendation-btn">
                                <span class="material-icons md-18">close</span> Dismiss
                            </button>
                            <span style="flex: 1;"></span>
                            <span style="font-size: 11px; color: #6b7280;">
                                lightbulb This is a suggestion only. You can dismiss or modify it.
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Setup event listeners
        const applyBtn = container.querySelector('#apply-recommendation-btn');
        if (applyBtn) {
            applyBtn.addEventListener('click', () => this.applyRecommendation(recommended));
        }

        const dismissBtn = container.querySelector('#dismiss-recommendation-btn');
        if (dismissBtn) {
            dismissBtn.addEventListener('click', () => {
                container.style.display = 'none';
                if (window.showToast) {
                    window.showToast('Recommendation dismissed', 'info', 1500);
                }
            });
        }
    }

    renderComparisonRow(label, current, recommended, change) {
        const changeColor = change.percent > 0 ? '#10b981' : change.percent < 0 ? '#ef4444' : '#6b7280';
        const changeIcon = change.percent > 0 ? '▼' : change.percent < 0 ? '▲' : '—';

        return `
            <tr style="border-bottom: 1px solid #f3f4f6;">
                <td style="padding: 8px 12px; color: #4b5563;">${label}</td>
                <td style="padding: 8px 12px; text-align: right; color: #6b7280; font-family: monospace;">${this.formatNumber(current)}</td>
                <td style="padding: 8px 12px; text-align: right; color: #1f2937; font-weight: 600; font-family: monospace;">${this.formatNumber(recommended)}</td>
                <td style="padding: 8px 12px; text-align: right; color: ${changeColor}; font-weight: 500; font-family: monospace;">
                    ${changeIcon} ${Math.abs(change.percent).toFixed(0)}%
                </td>
            </tr>
        `;
    }

    calculateChange(current, recommended) {
        if (current === 0) return { percent: 0, absolute: 0 };
        const absolute = recommended - current;
        const percent = (absolute / current) * 100;
        return { percent, absolute };
    }

    formatChangePercent(percent) {
        if (percent === 0) return '<span style="color: #6b7280;">—</span>';
        const sign = percent > 0 ? '▼' : '▲';
        const color = percent > 0 ? '#10b981' : '#ef4444';
        return `<span style="color: ${color}; font-weight: 600;">${sign} ${Math.abs(percent).toFixed(0)}%</span>`;
    }

    getConfidenceBadge(confidence) {
        const badges = {
            high: '<span class="badge badge-success badge-sm">High Confidence</span>',
            medium: '<span class="badge badge-info badge-sm">Medium Confidence</span>',
            low: '<span class="badge badge-warning badge-sm">Low Confidence</span>'
        };
        return badges[confidence] || badges.medium;
    }

    async applyRecommendation(recommended) {
        try {
            // Confirmation dialog
            const confirmed = await Dialog.confirm(
                'Apply this recommendation to your budget configuration?\n\n' +
                'Your current budget will be replaced with the recommended values. ' +
                'This action can be reversed by using the Reset button.',
                {
                    title: 'Apply Budget Recommendation',
                    confirmText: 'Apply',
                    danger: false
                }
            );

            if (!confirmed) {
                return;
            }

            if (window.showToast) {
                window.showToast('Applying recommendation...', 'info', 1500);
            }

            // Apply recommendation
            const sessionId = window.currentSessionId || 'default';
            const response = await apiClient.post('/api/budget/apply-recommendation', {
                recommendation: {
                    window_tokens: recommended.window_tokens,
                    rag_tokens: recommended.rag_tokens,
                    memory_tokens: recommended.memory_tokens,
                    system_tokens: recommended.system_tokens
                },
                session_id: sessionId
            });

            if (!response.ok) {
                throw new Error(response.error || 'Failed to apply recommendation');
            }

            if (window.showToast) {
                window.showToast('Recommendation applied successfully! celebration', 'success', 2500);
            }

            // Hide recommendation section
            const recommendationSection = this.container.querySelector('#budget-recommendation-section');
            if (recommendationSection) {
                recommendationSection.style.display = 'none';
            }

            // Reload budget config to show updated values
            await this.loadBudgetConfig();

        } catch (error) {
            console.error('Failed to apply recommendation:', error);
            if (window.showToast) {
                window.showToast(`Failed to apply: ${error.message}`, 'error');
            }
        }
    }

    formatNumber(num) {
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
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
