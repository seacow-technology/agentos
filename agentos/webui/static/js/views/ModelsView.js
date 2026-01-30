/**
 * Models Management View
 *
 * Provides a complete UI for managing AI models (Ollama/llama.cpp):
 * - Browse installed models
 * - Download new models from recommended list or custom name
 * - View download progress (real-time polling)
 * - View model details (size, parameters, tags)
 * - Delete models
 * - Monitor service status
 *
 * Part of Task #2: Models Management Feature
 */

class ModelsView {
    constructor() {
        this.pollIntervalId = null;
        this.activePulls = new Set();
        this.statusCheckInterval = null;
        this.cachedRecommendedModels = null;  // Cache for recommended models
    }

    /**
     * Render the view
     */
    async render(container) {
        this.container = container;
        await this.renderModelsList();
        this.startPollingPulls();
        this.startStatusCheck();
    }

    /**
     * Load and render available models
     */
    async loadAvailableModels() {
        try {
            // 1. Get recommended models list
            const response = await fetch('/api/models/available');
            const data = await response.json();

            // 2. Get installed models list
            const installedResponse = await fetch('/api/models/list');
            const installedData = await installedResponse.json();
            const installedNames = installedData.models.map(m => m.name);

            // 3. Filter out installed models
            const availableModels = data.recommended.filter(model =>
                !installedNames.includes(model.name)
            );

            // 4. Render
            const grid = document.getElementById('availableModelsGrid');
            if (!grid) return; // Grid not yet created

            if (availableModels.length === 0) {
                grid.innerHTML = `
                    <div class="empty-available">
                        <p>
                            <span class="material-icons md-18">check_circle</span>
                            All recommended models are already installed!
                        </p>
                    </div>
                `;
            } else {
                grid.innerHTML = availableModels.map(model =>
                    this.renderAvailableModelCard(model)
                ).join('');

                // Bind Install button events
                availableModels.forEach(model => {
                    const btn = document.getElementById(`install-${this.sanitizeId(model.name)}`);
                    if (btn) {
                        btn.addEventListener('click', () => this.pullModel(model.name));
                    }
                });
            }
        } catch (error) {
            console.error('Failed to load available models:', error);
            const grid = document.getElementById('availableModelsGrid');
            if (grid) {
                grid.innerHTML = `
                    <div class="empty-available">
                        <p style="color: #ef4444;">Failed to load available models</p>
                    </div>
                `;
            }
        }
    }

    /**
     * Render available model card
     */
    renderAvailableModelCard(model) {
        const safeId = this.sanitizeId(model.name);
        const tags = model.tags.map(tag =>
            `<span class="model-tag">${tag}</span>`
        ).join('');

        return `
            <div class="available-model-card">
                <div class="available-model-header">
                    <div class="model-icon-available">
                        <span class="material-icons md-48">smart_toy</span>
                    </div>
                    <div class="model-info-available">
                        <h3>${model.display_name}</h3>
                        <p class="model-size">${model.size}</p>
                    </div>
                </div>
                <div class="available-model-body">
                    <p class="model-description-available">${model.description}</p>
                    <div class="model-tags-available">${tags}</div>
                </div>
                <div class="available-model-actions">
                    <button class="btn-install-primary" id="install-${safeId}">
                        <span class="material-icons md-18">arrow_downward</span>
                        Install
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Cleanup when view is destroyed
     */
    destroy() {
        if (this.pollIntervalId) {
            clearInterval(this.pollIntervalId);
            this.pollIntervalId = null;
        }
        if (this.statusCheckInterval) {
            clearInterval(this.statusCheckInterval);
            this.statusCheckInterval = null;
        }
    }

    /**
     * Render models list view
     */
    async renderModelsList() {
        this.container.innerHTML = `
            <div class="models-view">
                <div class="view-header">
                    <div>
                        <h1>Models</h1>
                        <p class="text-sm text-gray-600 mt-1">Manage your AI models (Ollama/llama.cpp)</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-primary" id="btnDownloadModel">
                            <span class="icon"><span class="material-icons md-18">arrow_downward</span></span> Download Model
                        </button>
                    </div>
                </div>

                <div class="status-section" id="statusSection">
                    <div class="text-center py-4">
                        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto"></div>
                        <p class="mt-2 text-sm text-gray-600">Checking service status...</p>
                    </div>
                </div>

                <div id="pullProgressContainer" class="filter-section" style="display: none;"></div>

                <!-- Available Models Section -->
                <div class="available-section">
                    <div class="section-header">
                        <h2><span class="material-icons md-18">arrow_downward</span> Available Models</h2>
                        <p class="section-description">Click Install to download a model</p>
                    </div>
                    <div id="availableModelsGrid" class="available-models-grid">
                        <div class="text-center py-4">
                            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto"></div>
                            <p class="mt-2 text-sm text-gray-600">Loading available models...</p>
                        </div>
                    </div>
                </div>

                <div class="table-section">
                    <div class="section-header">
                        <h2><span class="material-icons md-18">archive</span> Installed Models</h2>
                        <p class="section-description">Manage your downloaded models</p>
                    </div>
                    <div id="modelsGrid" class="models-grid">
                        <div class="text-center py-8">
                            <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
                            <p class="mt-4 text-gray-600">Loading models...</p>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Attach event listeners
        document.getElementById('btnDownloadModel').addEventListener('click', () => this.showDownloadModal());

        // Load service status, available models, and installed models
        await this.loadServiceStatus();
        await this.loadAvailableModels();
        await this.loadModels();
    }

    /**
     * Load service status
     */
    async loadServiceStatus() {
        try {
            const response = await fetch('/api/models/status');
            if (!response.ok) {
                throw new Error('Failed to load service status');
            }

            const data = await response.json();
            const statusSection = document.getElementById('statusSection');

            let statusHtml = `
                <h2><span class="material-icons md-18">dns</span> Service Status</h2>
                <div class="service-status-grid">
            `;

            // Iterate through services array
            if (data.services && data.services.length > 0) {
                data.services.forEach(service => {
                    const statusClass = service.available ? 'status-available' : 'status-unavailable';
                    const statusText = service.available ? 'Available' : 'Not Available';
                    const statusIcon = service.available ?
                        '<span class="material-icons md-18">check</span>' :
                        '<span class="material-icons md-18">close</span>';

                    statusHtml += `
                        <div class="service-status-card ${statusClass}">
                            <div class="service-status-header">
                                <span class="service-status-icon">${statusIcon}</span>
                                <span class="service-status-name">${service.name}</span>
                            </div>
                            <div class="service-status-body">
                                <span class="service-status-badge">${statusText}</span>
                                ${service.info ? `<span class="text-xs text-gray-600">${service.info}</span>` : ''}
                            </div>
                        </div>
                    `;
                });
            }

            statusHtml += '</div></div>';
            statusSection.innerHTML = statusHtml;

        } catch (error) {
            console.error('Failed to load service status:', error);
            const statusSection = document.getElementById('statusSection');
            statusSection.innerHTML = `
                <div class="service-status-error">
                    <span class="text-red-600">Failed to check service status</span>
                </div>
            `;
        }
    }

    /**
     * Load and display models
     */
    async loadModels() {
        try {
            const response = await fetch('/api/models/list');
            if (!response.ok) {
                throw new Error('Failed to load models');
            }

            const data = await response.json();
            const models = data.models || [];

            const grid = document.getElementById('modelsGrid');

            if (models.length === 0) {
                grid.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">
                            <span class="material-icons md-48">archive</span>
                        </div>
                        <h3>No Models Installed</h3>
                        <p>Get started by downloading your first model</p>
                        <button class="btn-primary" onclick="document.getElementById('btnDownloadModel').click()">
                            Download Model
                        </button>
                    </div>
                `;
                return;
            }

            grid.innerHTML = models.map(model => this.renderModelCard(model)).join('');

            // Attach card event listeners
            models.forEach(model => {
                this.attachCardActions(model);
            });

        } catch (error) {
            console.error('Failed to load models:', error);
            const grid = document.getElementById('modelsGrid');
            grid.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">
                        <span class="material-icons md-48">error</span>
                    </div>
                    <h3>Failed to Load Models</h3>
                    <p>${error.message}</p>
                    <button class="btn-primary" onclick="location.reload()">
                        Retry
                    </button>
                </div>
            `;
        }
    }

    /**
     * Render model card
     */
    renderModelCard(model) {
        const sizeText = model.size_gb ? `${model.size_gb.toFixed(1)} GB` : model.size || 'Unknown';
        const paramsText = model.parameters || model.parameter_size || 'Unknown';

        const tags = (model.tags || [])
            .map(tag => `<span class="model-tag">${tag}</span>`)
            .join('');

        return `
            <div class="model-card" id="model-card-${this.sanitizeId(model.name)}">
                <div class="model-card-header">
                    <div class="model-icon">
                        <span class="material-icons md-48">smart_toy</span>
                    </div>
                    <div class="model-info">
                        <h3>${model.name}</h3>
                        <div class="model-meta">
                            <span class="model-provider">${model.provider || 'ollama'}</span>
                            ${model.family ? `<span class="model-family">${model.family}</span>` : ''}
                        </div>
                    </div>
                </div>
                <div class="model-card-body">
                    <div class="model-stats">
                        <div class="model-stat">
                            <span class="model-stat-label">Size</span>
                            <span class="model-stat-value">${sizeText}</span>
                        </div>
                        <div class="model-stat">
                            <span class="model-stat-label">Parameters</span>
                            <span class="model-stat-value">${paramsText}</span>
                        </div>
                    </div>
                    ${tags ? `<div class="model-tags">${tags}</div>` : ''}
                </div>
                <div class="model-card-actions">
                    <button class="btn-info" data-action="info" data-model-name="${model.name}">Info</button>
                    <button class="btn-delete" data-action="delete" data-model-name="${model.name}" data-model-provider="${model.provider || 'ollama'}">Delete</button>
                </div>
            </div>
        `;
    }

    /**
     * Sanitize ID for use in HTML element IDs
     */
    sanitizeId(str) {
        return str.replace(/[^a-zA-Z0-9-_]/g, '-');
    }

    /**
     * Attach action button event listeners
     */
    attachCardActions(model) {
        // Info button
        const infoBtn = document.querySelector(`[data-action="info"][data-model-name="${model.name}"]`);
        if (infoBtn) {
            infoBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.showModelInfo(model);
            });
        }

        // Delete button
        const deleteBtn = document.querySelector(`[data-action="delete"][data-model-name="${model.name}"]`);
        if (deleteBtn) {
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const provider = deleteBtn.getAttribute('data-model-provider');
                this.deleteModel(model.name, provider);
            });
        }
    }

    /**
     * Show download modal
     */
    async showDownloadModal() {
        // Load recommended models (use cache to improve speed)
        let recommendedModels = [];
        try {
            if (!this.cachedRecommendedModels) {
                const response = await fetch('/api/models/available');
                if (response.ok) {
                    const data = await response.json();
                    this.cachedRecommendedModels = data.recommended || [];
                }
            }
            recommendedModels = this.cachedRecommendedModels || [];
        } catch (error) {
            console.error('Failed to load recommended models:', error);
        }

        const modal = document.createElement('div');
        modal.className = 'modal active';
        modal.innerHTML = `
            <div class="modal-overlay"></div>
            <div class="modal-content modal-lg">
                <div class="modal-header">
                    <h2>Download Model</h2>
                    <button class="modal-close" id="btnCloseDownload">&times;</button>
                </div>
                <div class="modal-body">
                    ${recommendedModels.length > 0 ? `
                        <div class="form-group">
                            <label>Recommended Models</label>
                            <div class="recommended-models-grid">
                                ${recommendedModels.map(model => `
                                    <div class="recommended-model-card" data-model-name="${model.name}">
                                        <div class="recommended-model-header">
                                            <h4>${model.display_name || model.name}</h4>
                                            <span class="recommended-model-size">${model.size || 'Unknown'}</span>
                                        </div>
                                        <p class="recommended-model-description">${model.description || ''}</p>
                                        ${model.tags ? `
                                            <div class="recommended-model-tags">
                                                ${model.tags.map(tag => `<span class="model-tag">${tag}</span>`).join('')}
                                            </div>
                                        ` : ''}
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                        <div class="form-divider">
                            <span>OR</span>
                        </div>
                    ` : ''}
                    <div class="form-group">
                        <label>Custom Model Name</label>
                        <input type="text" placeholder="Enter model name (e.g., llama3.2:3b)" id="customModelInput">
                        <div class="field-hint">Enter a model name from Ollama library</div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn-secondary" id="btnCancelDownload">Cancel</button>
                    <button class="btn-primary" id="btnConfirmDownload">Download</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Selected model tracking
        let selectedModel = null;

        // Handle recommended model selection
        const recommendedCards = modal.querySelectorAll('.recommended-model-card');
        recommendedCards.forEach(card => {
            card.addEventListener('click', () => {
                recommendedCards.forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
                selectedModel = card.getAttribute('data-model-name');
                document.getElementById('customModelInput').value = '';
            });
        });

        // Handle custom input
        const customInput = document.getElementById('customModelInput');
        customInput.addEventListener('input', () => {
            if (customInput.value.trim()) {
                recommendedCards.forEach(c => c.classList.remove('selected'));
                selectedModel = null;
            }
        });

        const closeModal = () => {
            modal.remove();
        };

        document.getElementById('btnCloseDownload').addEventListener('click', closeModal);
        document.getElementById('btnCancelDownload').addEventListener('click', closeModal);
        document.getElementById('btnConfirmDownload').addEventListener('click', async () => {
            const customValue = customInput.value.trim();
            const modelName = customValue || selectedModel;

            if (!modelName) {
                this.showNotification('Please select a model or enter a custom name', 'error');
                return;
            }

            closeModal();
            await this.pullModel(modelName);
        });

        // Close on background click
        modal.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal-overlay')) {
                closeModal();
            }
        });
    }

    /**
     * Pull (download) a model
     */
    async pullModel(modelName) {
        try {
            const response = await fetch('/api/models/pull', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ model_name: modelName })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Download failed');
            }

            const data = await response.json();
            this.activePulls.add(data.pull_id);
            this.showPullProgress(data.pull_id, modelName);

        } catch (error) {
            console.error('Download failed:', error);
            this.showNotification(`Download failed: ${error.message}`, 'error');
        }
    }

    /**
     * Show pull progress
     */
    showPullProgress(pullId, modelName) {
        const container = document.getElementById('pullProgressContainer');
        container.style.display = 'block';

        const progressHtml = `
            <div class="pull-progress" id="progress-${pullId}">
                <div class="progress-header">
                    <h3>
                        <span class="material-icons md-18">refresh</span>
                        Downloading ${modelName}...
                    </h3>
                    <span class="progress-percent" id="progress-percent-${pullId}">0%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" id="progress-fill-${pullId}" style="width: 0%"></div>
                </div>
                <p class="progress-step" id="progress-step-${pullId}">Starting download...</p>
            </div>
        `;

        container.insertAdjacentHTML('beforeend', progressHtml);
    }

    /**
     * Start polling for pull progress
     */
    startPollingPulls() {
        // Poll every 500ms
        this.pollIntervalId = setInterval(async () => {
            for (const pullId of this.activePulls) {
                await this.updatePullProgress(pullId);
            }
        }, 500);
    }

    /**
     * Update pull progress
     */
    async updatePullProgress(pullId) {
        try {
            const response = await fetch(`/api/models/pull/${pullId}`);
            if (!response.ok) {
                console.error('Failed to fetch pull progress');
                return;
            }

            const data = await response.json();

            // Update progress UI
            const percentEl = document.getElementById(`progress-percent-${pullId}`);
            const fillEl = document.getElementById(`progress-fill-${pullId}`);
            const stepEl = document.getElementById(`progress-step-${pullId}`);

            if (percentEl) percentEl.textContent = `${data.progress}%`;
            if (fillEl) fillEl.style.width = `${data.progress}%`;
            if (stepEl) {
                stepEl.textContent = data.current_step || 'Processing...';
            }

            // Check if completed or failed
            if (data.status === 'COMPLETED') {
                this.activePulls.delete(pullId);
                setTimeout(() => {
                    const progressEl = document.getElementById(`progress-${pullId}`);
                    if (progressEl) {
                        progressEl.remove();
                    }
                    // Hide container if no more active pulls
                    if (this.activePulls.size === 0) {
                        document.getElementById('pullProgressContainer').style.display = 'none';
                    }
                    this.loadModels(); // Refresh installed models list
                    this.loadAvailableModels(); // Refresh available models list
                }, 2000);

                // Show success message
                if (stepEl) {
                    stepEl.innerHTML = '<span class="material-icons md-18">check_circle</span> Download completed successfully!';
                    stepEl.style.color = '#059669';
                }
                this.showNotification('Model downloaded successfully', 'success');

            } else if (data.status === 'FAILED') {
                this.activePulls.delete(pullId);

                // Show error message
                if (stepEl) {
                    stepEl.innerHTML = `<span class="material-icons md-18">error</span> Download failed: ${data.error || 'Unknown error'}`;
                    stepEl.style.color = '#dc2626';
                }
                this.showNotification(`Download failed: ${data.error || 'Unknown error'}`, 'error');
            }

        } catch (error) {
            console.error('Failed to update pull progress:', error);
        }
    }

    /**
     * Delete model
     */
    async deleteModel(modelName, provider) {
        // Create confirmation modal
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content" style="max-width: 500px;">
                <div class="modal-header">
                    <h2>Delete Model</h2>
                    <button class="modal-close" id="btnCloseDelete">&times;</button>
                </div>
                <div class="modal-body">
                    <p style="color: #374151; margin-bottom: 1rem;">
                        Are you sure you want to delete <strong>"${modelName}"</strong>?
                    </p>
                    <div style="background: #fef3c7; border: 1px solid #fbbf24; border-radius: 0.5rem; padding: 1rem; margin-bottom: 1rem;">
                        <p style="color: #92400e; font-size: 0.875rem; margin: 0;">
                            <span class="material-icons md-18">warning</span> <strong>Warning:</strong> This action cannot be undone. The model will be permanently deleted from your system.
                        </p>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn-secondary" id="btnCancelDelete">Cancel</button>
                    <button class="btn-delete" id="btnConfirmDelete">Delete</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Close handlers
        const closeModal = () => {
            modal.remove();
        };

        document.getElementById('btnCloseDelete').addEventListener('click', closeModal);
        document.getElementById('btnCancelDelete').addEventListener('click', closeModal);
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeModal();
        });

        // Confirm handler
        document.getElementById('btnConfirmDelete').addEventListener('click', async () => {
            closeModal();

            try {
                const response = await fetch(`/api/models/${provider}/${encodeURIComponent(modelName)}`, {
                    method: 'DELETE'
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || 'Failed to delete model');
                }

                this.showNotification(`${modelName} deleted successfully`, 'success');
                await this.loadModels(); // Refresh installed models list
                await this.loadAvailableModels(); // Refresh available models list

            } catch (error) {
                console.error('Failed to delete model:', error);
                this.showNotification(`Failed to delete model: ${error.message}`, 'error');
            }
        });
    }

    /**
     * Show model info
     */
    showModelInfo(model) {
        const modal = document.createElement('div');
        modal.className = 'modal active';
        modal.innerHTML = `
            <div class="modal-overlay"></div>
            <div class="modal-content modal-md">
                <div class="modal-header">
                    <h2>Model Information</h2>
                    <button class="modal-close" id="btnCloseInfo">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="model-info-section">
                        <h3>Basic Information</h3>
                        <div class="model-info-grid">
                            <div class="model-info-item">
                                <span class="model-info-label">Name</span>
                                <span class="model-info-value">${model.name}</span>
                            </div>
                            <div class="model-info-item">
                                <span class="model-info-label">Provider</span>
                                <span class="model-info-value">${model.provider || 'ollama'}</span>
                            </div>
                            ${model.family ? `
                                <div class="model-info-item">
                                    <span class="model-info-label">Family</span>
                                    <span class="model-info-value">${model.family}</span>
                                </div>
                            ` : ''}
                            <div class="model-info-item">
                                <span class="model-info-label">Size</span>
                                <span class="model-info-value">${model.size_gb ? `${model.size_gb.toFixed(1)} GB` : model.size || 'Unknown'}</span>
                            </div>
                            <div class="model-info-item">
                                <span class="model-info-label">Parameters</span>
                                <span class="model-info-value">${model.parameters || model.parameter_size || 'Unknown'}</span>
                            </div>
                            ${model.quantization_level ? `
                                <div class="model-info-item">
                                    <span class="model-info-label">Quantization</span>
                                    <span class="model-info-value">${model.quantization_level}</span>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                    ${model.tags && model.tags.length > 0 ? `
                        <div class="model-info-section">
                            <h3>Tags</h3>
                            <div class="model-tags">
                                ${model.tags.map(tag => `<span class="model-tag">${tag}</span>`).join('')}
                            </div>
                        </div>
                    ` : ''}
                    ${model.modified_at ? `
                        <div class="model-info-section">
                            <h3>Additional Details</h3>
                            <div class="model-info-item">
                                <span class="model-info-label">Last Modified</span>
                                <span class="model-info-value">${new Date(model.modified_at).toLocaleString()}</span>
                            </div>
                        </div>
                    ` : ''}
                </div>
                <div class="modal-footer">
                    <button class="btn-secondary" id="btnCloseInfoFooter">Close</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        const closeModal = () => {
            modal.remove();
        };

        document.getElementById('btnCloseInfo').addEventListener('click', closeModal);
        document.getElementById('btnCloseInfoFooter').addEventListener('click', closeModal);

        // Close on background click
        modal.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal-overlay')) {
                closeModal();
            }
        });
    }

    /**
     * Start status check interval
     */
    startStatusCheck() {
        // Check status every 5 seconds
        this.statusCheckInterval = setInterval(() => {
            this.loadServiceStatus();
        }, 5000);
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
}

// Export for use in main.js
window.ModelsView = ModelsView;
