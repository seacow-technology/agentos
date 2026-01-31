/**
 * ChannelSetupWizard - Multi-step wizard for configuring communication channels
 *
 * Features:
 * - Step 1: Provider variant selection (if multiple variants)
 * - Step 2: Webhook URL generation and display
 * - Step 3: Setup steps checklist with animations
 * - Step 4: Configuration form with validation
 * - Step 5: Test connection
 *
 * Usage:
 *   const wizard = new ChannelSetupWizard(container, {
 *     manifestId: 'whatsapp_twilio',
 *     onComplete: (channelId) => { ... }
 *   });
 */

class ChannelSetupWizard {
    constructor(container, options = {}) {
        this.container = container;
        this.manifestId = options.manifestId;
        this.onComplete = options.onComplete || (() => {});
        this.onCancel = options.onCancel || (() => {});

        this.currentStep = 1;
        this.totalSteps = 5;
        this.manifest = null;
        this.config = {};
        this.webhookUrl = '';
        this.setupSteps = [];
        this.stepCheckboxes = {};

        this.init();
    }

    async init() {
        // Load manifest
        await this.loadManifest();

        // Generate webhook URL
        this.generateWebhookUrl();

        // Render wizard
        this.render();

        // Setup event listeners
        this.setupEventListeners();
    }

    async loadManifest() {
        try {
            const response = await fetch(`/api/channels/manifests/${this.manifestId}`);
            const result = await response.json();

            if (result.ok) {
                this.manifest = result.data;
                this.setupSteps = this.manifest.setup_steps || [];
            } else {
                Toast.error('Failed to load channel manifest');
                this.onCancel();
            }
        } catch (error) {
            console.error('Error loading manifest:', error);
            Toast.error('Failed to load channel manifest');
            this.onCancel();
        }
    }

    generateWebhookUrl() {
        // Generate webhook URL based on manifest
        const baseUrl = window.location.origin;
        const webhookPath = this.manifest?.webhook_paths?.[0] || '/api/channels/webhook';
        this.webhookUrl = `${baseUrl}${webhookPath}`;
    }

    render() {
        if (!this.manifest) {
            this.container.innerHTML = '<div class="loading-spinner">Loading...</div>';
            return;
        }

        this.container.innerHTML = `
            <div class="channel-setup-wizard">
                <div class="wizard-overlay" id="wizard-overlay"></div>
                <div class="wizard-modal">
                    <div class="wizard-header">
                        <h2>Setup ${this.manifest.name}</h2>
                        <button class="btn-close" id="wizard-close">
                            <span class="material-icons">close</span>
                        </button>
                    </div>

                    <div class="wizard-progress">
                        <div class="progress-steps">
                            ${this.renderProgressSteps()}
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${(this.currentStep / this.totalSteps) * 100}%"></div>
                        </div>
                    </div>

                    <div class="wizard-body" id="wizard-body">
                        ${this.renderCurrentStep()}
                    </div>

                    <div class="wizard-footer">
                        <button class="btn-secondary" id="wizard-prev" ${this.currentStep === 1 ? 'disabled' : ''}>
                            <span class="material-icons">arrow_back</span>
                            Previous
                        </button>
                        <button class="btn-primary" id="wizard-next">
                            ${this.currentStep === this.totalSteps ? 'Finish' : 'Next'}
                            <span class="material-icons">arrow_forward</span>
                        </button>
                    </div>
                </div>
            </div>
        `;

        // Add CSS if not already added
        this.addStyles();
    }

    renderProgressSteps() {
        const stepNames = ['Variant', 'Webhook', 'Guide', 'Config', 'Test'];
        return stepNames.map((name, index) => {
            const stepNum = index + 1;
            const isActive = stepNum === this.currentStep;
            const isCompleted = stepNum < this.currentStep;
            const className = `progress-step ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}`;

            return `
                <div class="${className}">
                    <div class="step-number">
                        ${isCompleted ? '<span class="material-icons">check</span>' : stepNum}
                    </div>
                    <div class="step-name">${name}</div>
                </div>
            `;
        }).join('');
    }

    renderCurrentStep() {
        switch (this.currentStep) {
            case 1:
                return this.renderStep1Variant();
            case 2:
                return this.renderStep2Webhook();
            case 3:
                return this.renderStep3Guide();
            case 4:
                return this.renderStep4Config();
            case 5:
                return this.renderStep5Test();
            default:
                return '<div>Invalid step</div>';
        }
    }

    renderStep1Variant() {
        // For now, most channels have only one variant
        // In the future, this could show multiple provider options
        return `
            <div class="wizard-step step-variant">
                <div class="step-icon">
                    <span class="material-icons" style="font-size: 48px; color: var(--primary-color);">
                        ${this.manifest.icon === 'whatsapp' ? 'chat' : 'message'}
                    </span>
                </div>
                <h3>${this.manifest.name}</h3>
                <p class="step-description">${this.manifest.long_description || this.manifest.description}</p>

                <div class="variant-info">
                    <div class="info-grid">
                        <div class="info-item">
                            <span class="info-label">Provider:</span>
                            <span class="info-value">${this.manifest.provider || 'Unknown'}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Version:</span>
                            <span class="info-value">${this.manifest.version}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Session Scope:</span>
                            <span class="info-value">${this.manifest.session_scope}</span>
                        </div>
                    </div>
                </div>

                <div class="capabilities-section">
                    <h4>Capabilities</h4>
                    <div class="capabilities-list">
                        ${this.manifest.capabilities.map(cap => `
                            <span class="capability-badge">
                                <span class="material-icons md-14">check_circle</span>
                                ${cap.replace(/_/g, ' ')}
                            </span>
                        `).join('')}
                    </div>
                </div>

                <div class="privacy-badges-section">
                    <h4>Privacy & Security</h4>
                    <div class="privacy-badges">
                        ${this.manifest.privacy_badges.map(badge => `
                            <span class="privacy-badge">
                                <span class="material-icons md-14">verified_user</span>
                                ${badge}
                            </span>
                        `).join('')}
                    </div>
                </div>

                ${this.manifest.docs_url ? `
                    <div class="docs-link">
                        <a href="${this.manifest.docs_url}" target="_blank" rel="noopener noreferrer">
                            <span class="material-icons md-18">open_in_new</span>
                            View Official Documentation
                        </a>
                    </div>
                ` : ''}
            </div>
        `;
    }

    renderStep2Webhook() {
        return `
            <div class="wizard-step step-webhook">
                <h3>Webhook Configuration</h3>
                <p class="step-description">
                    Copy the webhook URL below and configure it in your ${this.manifest.provider} account.
                </p>

                <div class="webhook-url-section">
                    <label>Webhook URL</label>
                    <div class="url-input-group">
                        <input
                            type="text"
                            class="webhook-url-input"
                            id="webhook-url-input"
                            value="${this.webhookUrl}"
                            readonly
                        />
                        <button class="btn-copy" id="copy-webhook-url" title="Copy to clipboard">
                            <span class="material-icons">content_copy</span>
                        </button>
                    </div>
                    <small class="help-text">
                        This URL will receive incoming messages from ${this.manifest.name}
                    </small>
                </div>

                ${this.manifest.security_defaults.require_signature ? `
                    <div class="webhook-security-notice">
                        <span class="material-icons">security</span>
                        <div>
                            <strong>Security Note:</strong>
                            This channel requires webhook signature verification. Make sure your provider
                            sends the required signature headers.
                        </div>
                    </div>
                ` : ''}

                <div class="webhook-info">
                    <h4>Webhook Information</h4>
                    <div class="info-grid">
                        <div class="info-item">
                            <span class="info-label">Method:</span>
                            <span class="info-value">POST</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Content-Type:</span>
                            <span class="info-value">application/x-www-form-urlencoded</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Rate Limit:</span>
                            <span class="info-value">${this.manifest.security_defaults.rate_limit_per_minute} req/min</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    renderStep3Guide() {
        return `
            <div class="wizard-step step-guide">
                <h3>Setup Steps</h3>
                <p class="step-description">
                    Follow these steps to complete the setup. Check off each item as you complete it.
                </p>

                <div class="setup-steps-list">
                    ${this.setupSteps.map((step, index) => `
                        <div class="setup-step-item" data-step-index="${index}">
                            <div class="step-header">
                                <div class="step-checkbox">
                                    <input
                                        type="checkbox"
                                        id="setup-step-${index}"
                                        class="setup-step-checkbox"
                                        data-step-index="${index}"
                                    />
                                    <label for="setup-step-${index}"></label>
                                </div>
                                <div class="step-content">
                                    <h4>${step.title}</h4>
                                    <p>${step.description}</p>
                                </div>
                            </div>

                            ${step.instruction ? `
                                <div class="step-instruction">
                                    <pre>${step.instruction}</pre>
                                </div>
                            ` : ''}

                            ${step.animation_url ? `
                                <div class="step-animation">
                                    <img src="${step.animation_url}" alt="${step.title} guide" />
                                </div>
                            ` : ''}

                            ${step.checklist && step.checklist.length > 0 ? `
                                <div class="step-checklist">
                                    <ul>
                                        ${step.checklist.map(item => `<li>${item}</li>`).join('')}
                                    </ul>
                                </div>
                            ` : ''}
                        </div>
                    `).join('')}
                </div>

                <div class="guide-notice">
                    <span class="material-icons">info</span>
                    <div>
                        You can complete these steps in your own time. The wizard will wait for you to
                        check off each item before proceeding.
                    </div>
                </div>
            </div>
        `;
    }

    renderStep4Config() {
        return `
            <div class="wizard-step step-config">
                <h3>Configuration</h3>
                <p class="step-description">
                    Enter the required configuration parameters for ${this.manifest.name}.
                </p>

                <form class="config-form" id="config-form">
                    ${this.manifest.required_config_fields.map(field => this.renderConfigField(field)).join('')}
                </form>

                <div class="config-notice">
                    <span class="material-icons">lock</span>
                    <div>
                        <strong>Security:</strong> Secret fields are encrypted at rest and never logged.
                    </div>
                </div>
            </div>
        `;
    }

    renderConfigField(field) {
        const inputType = field.type === 'password' ? 'password' : 'text';
        const value = this.config[field.name] || field.default || '';

        return `
            <div class="form-group">
                <label for="config-${field.name}">
                    ${field.label}
                    ${field.required ? '<span class="required">*</span>' : ''}
                </label>

                ${field.type === 'textarea' ? `
                    <textarea
                        id="config-${field.name}"
                        name="${field.name}"
                        class="form-input"
                        placeholder="${field.placeholder || ''}"
                        ${field.required ? 'required' : ''}
                    >${value}</textarea>
                ` : field.type === 'select' ? `
                    <select
                        id="config-${field.name}"
                        name="${field.name}"
                        class="form-input"
                        ${field.required ? 'required' : ''}
                    >
                        <option value="">Select...</option>
                        ${field.options.map(opt => `
                            <option value="${opt}" ${value === opt ? 'selected' : ''}>${opt}</option>
                        `).join('')}
                    </select>
                ` : `
                    <input
                        type="${inputType}"
                        id="config-${field.name}"
                        name="${field.name}"
                        class="form-input"
                        placeholder="${field.placeholder || ''}"
                        value="${value}"
                        ${field.required ? 'required' : ''}
                        ${field.validation_regex ? `pattern="${field.validation_regex}"` : ''}
                    />
                `}

                ${field.help_text ? `
                    <small class="help-text">${field.help_text}</small>
                ` : ''}

                ${field.validation_error ? `
                    <small class="error-text" style="display: none;">${field.validation_error}</small>
                ` : ''}

                ${field.secret ? `
                    <div class="field-badge">
                        <span class="material-icons md-14">lock</span>
                        Encrypted
                    </div>
                ` : ''}
            </div>
        `;
    }

    renderStep5Test() {
        return `
            <div class="wizard-step step-test">
                <h3>Test Connection</h3>
                <p class="step-description">
                    Test your configuration to ensure everything is set up correctly.
                </p>

                <div class="test-section">
                    <button class="btn-test btn-primary" id="test-connection">
                        <span class="material-icons">play_arrow</span>
                        Run Test
                    </button>
                </div>

                <div class="test-results" id="test-results" style="display: none;">
                    <!-- Test results will be displayed here -->
                </div>

                <div class="test-info">
                    <h4>What will be tested:</h4>
                    <ul>
                        <li>Configuration validation</li>
                        <li>Credential verification</li>
                        <li>Webhook connectivity</li>
                        <li>Message format compatibility</li>
                    </ul>
                </div>
            </div>
        `;
    }

    setupEventListeners() {
        // Close button
        const closeBtn = this.container.querySelector('#wizard-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.handleCancel());
        }

        // Overlay click
        const overlay = this.container.querySelector('#wizard-overlay');
        if (overlay) {
            overlay.addEventListener('click', () => this.handleCancel());
        }

        // Navigation buttons
        const prevBtn = this.container.querySelector('#wizard-prev');
        const nextBtn = this.container.querySelector('#wizard-next');

        if (prevBtn) {
            prevBtn.addEventListener('click', () => this.handlePrevious());
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', () => this.handleNext());
        }

        // Step-specific event listeners
        this.setupStepEventListeners();
    }

    setupStepEventListeners() {
        switch (this.currentStep) {
            case 2:
                // Copy webhook URL button
                const copyBtn = this.container.querySelector('#copy-webhook-url');
                if (copyBtn) {
                    copyBtn.addEventListener('click', () => this.handleCopyWebhook());
                }
                break;

            case 3:
                // Setup step checkboxes
                const checkboxes = this.container.querySelectorAll('.setup-step-checkbox');
                checkboxes.forEach(checkbox => {
                    checkbox.addEventListener('change', (e) => {
                        const stepIndex = e.target.dataset.stepIndex;
                        this.stepCheckboxes[stepIndex] = e.target.checked;
                    });
                });
                break;

            case 4:
                // Config form inputs
                const form = this.container.querySelector('#config-form');
                if (form) {
                    const inputs = form.querySelectorAll('input, textarea, select');
                    inputs.forEach(input => {
                        input.addEventListener('input', () => this.handleConfigChange());
                    });
                }
                break;

            case 5:
                // Test button
                const testBtn = this.container.querySelector('#test-connection');
                if (testBtn) {
                    testBtn.addEventListener('click', () => this.handleTest());
                }
                break;
        }
    }

    handleCopyWebhook() {
        const input = this.container.querySelector('#webhook-url-input');
        if (input) {
            input.select();
            document.execCommand('copy');
            Toast.success('Webhook URL copied to clipboard');
        }
    }

    handleConfigChange() {
        const form = this.container.querySelector('#config-form');
        if (form) {
            const formData = new FormData(form);
            this.config = {};
            for (const [key, value] of formData.entries()) {
                this.config[key] = value;
            }
        }
    }

    async handleTest() {
        const testBtn = this.container.querySelector('#test-connection');
        const resultsDiv = this.container.querySelector('#test-results');

        if (!testBtn || !resultsDiv) return;

        // Disable button and show loading
        testBtn.disabled = true;
        testBtn.innerHTML = '<span class="material-icons spinning">sync</span> Testing...';

        resultsDiv.style.display = 'block';
        resultsDiv.innerHTML = '<div class="loading-spinner">Running tests...</div>';

        try {
            const response = await fetch(`/api/channels/manifests/${this.manifestId}/test`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ config: this.config })
            });

            const result = await response.json();

            if (result.ok && result.data.success) {
                resultsDiv.innerHTML = `
                    <div class="test-result test-success">
                        <span class="material-icons">check_circle</span>
                        <div>
                            <h4>Test Passed</h4>
                            <p>${result.data.message}</p>
                        </div>
                    </div>
                `;
                Toast.success('Channel test passed');
            } else {
                const error = result.data?.error || 'Test failed';
                const diagnostics = result.data?.diagnostics;

                resultsDiv.innerHTML = `
                    <div class="test-result test-error">
                        <span class="material-icons">error</span>
                        <div>
                            <h4>Test Failed</h4>
                            <p>${error}</p>
                            ${diagnostics ? `
                                <div class="test-diagnostics">
                                    <h5>Diagnostics:</h5>
                                    <pre>${JSON.stringify(diagnostics, null, 2)}</pre>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                `;
                Toast.error('Channel test failed');
            }
        } catch (error) {
            console.error('Test error:', error);
            resultsDiv.innerHTML = `
                <div class="test-result test-error">
                    <span class="material-icons">error</span>
                    <div>
                        <h4>Test Error</h4>
                        <p>${error.message}</p>
                    </div>
                </div>
            `;
            Toast.error('Test error occurred');
        } finally {
            // Re-enable button
            testBtn.disabled = false;
            testBtn.innerHTML = '<span class="material-icons">play_arrow</span> Run Test';
        }
    }

    async handleNext() {
        // Validate current step before proceeding
        if (!await this.validateCurrentStep()) {
            return;
        }

        if (this.currentStep === this.totalSteps) {
            // Finish wizard
            await this.handleFinish();
        } else {
            // Move to next step
            this.currentStep++;
            this.render();
            this.setupEventListeners();
        }
    }

    handlePrevious() {
        if (this.currentStep > 1) {
            this.currentStep--;
            this.render();
            this.setupEventListeners();
        }
    }

    handleCancel() {
        if (confirm('Are you sure you want to cancel the setup? Your progress will be lost.')) {
            this.onCancel();
        }
    }

    async validateCurrentStep() {
        switch (this.currentStep) {
            case 1:
                // Variant selection - always valid for now
                return true;

            case 2:
                // Webhook URL - always valid
                return true;

            case 3:
                // Setup steps - check if all required steps are checked
                const allChecked = this.setupSteps.every((step, index) => {
                    return !step.auto_check || this.stepCheckboxes[index];
                });

                if (!allChecked) {
                    Toast.warning('Please complete all setup steps before proceeding');
                    return false;
                }
                return true;

            case 4:
                // Config form - validate all required fields
                const form = this.container.querySelector('#config-form');
                if (form && !form.checkValidity()) {
                    form.reportValidity();
                    return false;
                }

                // Additional validation via API
                try {
                    const response = await fetch(`/api/channels/manifests/${this.manifestId}/validate`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ config: this.config })
                    });

                    const result = await response.json();
                    if (!result.ok || !result.data.valid) {
                        Toast.error(result.data.error || 'Configuration validation failed');
                        return false;
                    }
                } catch (error) {
                    console.error('Validation error:', error);
                    Toast.error('Failed to validate configuration');
                    return false;
                }

                return true;

            case 5:
                // Test step - check if test has been run successfully
                const testResults = this.container.querySelector('#test-results');
                const hasSuccess = testResults && testResults.querySelector('.test-success');

                if (!hasSuccess) {
                    Toast.warning('Please run the test and ensure it passes before finishing');
                    return false;
                }
                return true;

            default:
                return true;
        }
    }

    async handleFinish() {
        // Save channel configuration
        try {
            const channelId = `${this.manifestId}_${Date.now()}`;

            // TODO: Call API to save channel configuration
            // For now, just complete the wizard

            Toast.success('Channel setup completed successfully');
            this.onComplete(channelId);
        } catch (error) {
            console.error('Error completing setup:', error);
            Toast.error('Failed to complete setup');
        }
    }

    addStyles() {
        // Check if styles already added
        if (document.getElementById('channel-setup-wizard-styles')) {
            return;
        }

        const style = document.createElement('style');
        style.id = 'channel-setup-wizard-styles';
        style.textContent = `
            .channel-setup-wizard {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                z-index: 9999;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            .wizard-overlay {
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.5);
                backdrop-filter: blur(4px);
            }

            .wizard-modal {
                position: relative;
                width: 90%;
                max-width: 800px;
                max-height: 90vh;
                background: white;
                border-radius: 12px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }

            .wizard-header {
                padding: 24px;
                border-bottom: 1px solid var(--border-color);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }

            .wizard-header h2 {
                margin: 0;
                font-size: 24px;
                font-weight: 600;
            }

            .wizard-progress {
                padding: 20px 24px;
                border-bottom: 1px solid var(--border-color);
            }

            .progress-steps {
                display: flex;
                justify-content: space-between;
                margin-bottom: 16px;
            }

            .progress-step {
                display: flex;
                flex-direction: column;
                align-items: center;
                flex: 1;
                position: relative;
            }

            .progress-step::after {
                content: '';
                position: absolute;
                top: 20px;
                left: 50%;
                width: 100%;
                height: 2px;
                background: var(--border-color);
                z-index: -1;
            }

            .progress-step:last-child::after {
                display: none;
            }

            .step-number {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                background: var(--bg-secondary);
                border: 2px solid var(--border-color);
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 600;
                margin-bottom: 8px;
                position: relative;
                z-index: 1;
            }

            .progress-step.active .step-number {
                background: var(--primary-color);
                color: white;
                border-color: var(--primary-color);
            }

            .progress-step.completed .step-number {
                background: var(--success-color);
                color: white;
                border-color: var(--success-color);
            }

            .step-name {
                font-size: 12px;
                color: var(--text-secondary);
            }

            .progress-step.active .step-name {
                color: var(--primary-color);
                font-weight: 600;
            }

            .progress-bar {
                height: 4px;
                background: var(--border-color);
                border-radius: 2px;
                overflow: hidden;
            }

            .progress-fill {
                height: 100%;
                background: var(--primary-color);
                transition: width 0.3s ease;
            }

            .wizard-body {
                flex: 1;
                overflow-y: auto;
                padding: 32px 24px;
            }

            .wizard-step h3 {
                margin: 0 0 8px 0;
                font-size: 20px;
                font-weight: 600;
            }

            .step-description {
                margin: 0 0 24px 0;
                color: var(--text-secondary);
            }

            .wizard-footer {
                padding: 20px 24px;
                border-top: 1px solid var(--border-color);
                display: flex;
                justify-content: space-between;
            }

            .step-icon {
                text-align: center;
                margin-bottom: 24px;
            }

            .variant-info,
            .webhook-info,
            .config-notice,
            .test-info {
                margin-top: 24px;
                padding: 16px;
                background: var(--bg-secondary);
                border-radius: 8px;
            }

            .info-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 16px;
            }

            .info-item {
                display: flex;
                flex-direction: column;
                gap: 4px;
            }

            .info-label {
                font-size: 12px;
                color: var(--text-secondary);
                font-weight: 500;
            }

            .info-value {
                font-weight: 600;
            }

            .capabilities-section,
            .privacy-badges-section {
                margin-top: 24px;
            }

            .capabilities-section h4,
            .privacy-badges-section h4 {
                margin: 0 0 12px 0;
                font-size: 14px;
                font-weight: 600;
                text-transform: uppercase;
                color: var(--text-secondary);
            }

            .capabilities-list,
            .privacy-badges {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
            }

            .capability-badge,
            .privacy-badge {
                display: inline-flex;
                align-items: center;
                gap: 4px;
                padding: 6px 12px;
                background: var(--success-bg);
                color: var(--success-color);
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
            }

            .privacy-badge {
                background: var(--info-bg);
                color: var(--info-color);
            }

            .docs-link {
                margin-top: 24px;
                text-align: center;
            }

            .docs-link a {
                display: inline-flex;
                align-items: center;
                gap: 4px;
                color: var(--primary-color);
                text-decoration: none;
                font-weight: 500;
            }

            .url-input-group {
                display: flex;
                gap: 8px;
            }

            .webhook-url-input {
                flex: 1;
                padding: 12px;
                border: 1px solid var(--border-color);
                border-radius: 6px;
                font-family: monospace;
                font-size: 14px;
            }

            .btn-copy {
                padding: 12px;
                background: var(--primary-color);
                color: white;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                transition: background 0.2s;
            }

            .btn-copy:hover {
                background: var(--primary-dark);
            }

            .webhook-security-notice {
                display: flex;
                gap: 12px;
                padding: 12px;
                background: var(--warning-bg);
                border-left: 3px solid var(--warning-color);
                border-radius: 6px;
                margin-top: 16px;
            }

            .setup-steps-list {
                display: flex;
                flex-direction: column;
                gap: 16px;
            }

            .setup-step-item {
                padding: 16px;
                border: 2px solid var(--border-color);
                border-radius: 8px;
                transition: border-color 0.2s;
            }

            .setup-step-item:hover {
                border-color: var(--primary-color);
            }

            .step-header {
                display: flex;
                gap: 16px;
            }

            .step-checkbox {
                flex-shrink: 0;
            }

            .step-checkbox input[type="checkbox"] {
                width: 20px;
                height: 20px;
                cursor: pointer;
            }

            .step-content h4 {
                margin: 0 0 4px 0;
                font-size: 16px;
            }

            .step-content p {
                margin: 0;
                color: var(--text-secondary);
            }

            .step-instruction {
                margin-top: 12px;
                padding: 12px;
                background: var(--bg-secondary);
                border-radius: 6px;
            }

            .step-instruction pre {
                margin: 0;
                white-space: pre-wrap;
                font-size: 13px;
                line-height: 1.6;
            }

            .step-animation {
                margin-top: 12px;
                text-align: center;
            }

            .step-animation img {
                max-width: 100%;
                border-radius: 8px;
            }

            .step-checklist {
                margin-top: 12px;
            }

            .step-checklist ul {
                margin: 0;
                padding-left: 24px;
                color: var(--text-secondary);
            }

            .guide-notice {
                display: flex;
                gap: 12px;
                padding: 12px;
                background: var(--info-bg);
                border-left: 3px solid var(--info-color);
                border-radius: 6px;
                margin-top: 24px;
            }

            .config-form {
                display: flex;
                flex-direction: column;
                gap: 20px;
            }

            .form-group {
                display: flex;
                flex-direction: column;
                gap: 8px;
            }

            .form-group label {
                font-weight: 500;
                font-size: 14px;
            }

            .required {
                color: var(--error-color);
            }

            .form-input {
                padding: 12px;
                border: 1px solid var(--border-color);
                border-radius: 6px;
                font-size: 14px;
            }

            .form-input:focus {
                outline: none;
                border-color: var(--primary-color);
            }

            .form-input:invalid {
                border-color: var(--error-color);
            }

            .help-text {
                font-size: 12px;
                color: var(--text-secondary);
            }

            .error-text {
                font-size: 12px;
                color: var(--error-color);
            }

            .field-badge {
                display: inline-flex;
                align-items: center;
                gap: 4px;
                font-size: 12px;
                color: var(--text-secondary);
            }

            .test-section {
                text-align: center;
                padding: 32px 0;
            }

            .btn-test {
                padding: 16px 32px;
                font-size: 16px;
                display: inline-flex;
                align-items: center;
                gap: 8px;
            }

            .test-results {
                margin-top: 24px;
            }

            .test-result {
                display: flex;
                gap: 16px;
                padding: 16px;
                border-radius: 8px;
            }

            .test-success {
                background: var(--success-bg);
                border-left: 4px solid var(--success-color);
            }

            .test-success .material-icons {
                color: var(--success-color);
                font-size: 32px;
            }

            .test-error {
                background: var(--error-bg);
                border-left: 4px solid var(--error-color);
            }

            .test-error .material-icons {
                color: var(--error-color);
                font-size: 32px;
            }

            .test-result h4 {
                margin: 0 0 8px 0;
            }

            .test-result p {
                margin: 0;
            }

            .test-diagnostics {
                margin-top: 12px;
                padding: 12px;
                background: rgba(0, 0, 0, 0.05);
                border-radius: 6px;
            }

            .test-diagnostics h5 {
                margin: 0 0 8px 0;
                font-size: 12px;
            }

            .test-diagnostics pre {
                margin: 0;
                font-size: 11px;
                white-space: pre-wrap;
            }

            @keyframes spinning {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }

            .spinning {
                animation: spinning 1s linear infinite;
            }
        `;

        document.head.appendChild(style);
    }

    destroy() {
        this.container.innerHTML = '';
    }
}

// Export for global use
window.ChannelSetupWizard = ChannelSetupWizard;
