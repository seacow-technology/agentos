/**
 * ExecutionPlansView - Execution Plan Visualization View
 *
 * Displays dry-run plan/explain/validate results for tasks.
 *
 * Features:
 * - Plan Steps Timeline: Visual timeline of execution steps with dependencies
 * - Validate Report Panel: Rule checking results with actionable feedback
 * - Explain Panel: Natural language explanations with structured data
 * - Artifact Links: Related artifacts and resources
 * - Proposal/Approval workflow (no direct execution)
 *
 * Wave2-B1: Core View Implementation
 * API Integration: Connects to Agent-API-Exec endpoints
 */

class ExecutionPlansView {
    constructor(container) {
        this.container = container;
        this.currentPlan = null;
        this.taskId = null;
        this.planId = null;
        this.autoRefreshInterval = null;

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="execution-plans-view">
                <div class="view-header">
                    <div class="header-left">
                        <div>
                            <h1>Execution Plans</h1>
                            <p class="text-sm text-gray-600 mt-1">View and analyze task execution plans</p>
                        </div>
                        <div class="header-breadcrumb" id="plan-breadcrumb">
                            <!-- Breadcrumb will be rendered here -->
                        </div>
                    </div>
                    <div class="header-actions">
                        <button class="btn-secondary" id="plan-export" disabled>
                            <span class="material-icons md-18">arrow_downward</span> Export Plan
                        </button>
                        <button class="btn-secondary" id="plan-refresh">
                            <span class="material-icons md-18">refresh</span> Refresh Status
                        </button>
                        <button class="btn-primary" id="plan-generate-proposal" disabled>
                            <span class="material-icons md-18">description</span> Generate Proposal
                        </button>
                        <button class="btn-primary" id="plan-request-approval" disabled>
                            <span class="material-icons md-18">send</span> Request Approval
                        </button>
                    </div>
                </div>

                <div class="plan-content" id="plan-content">
                    <!-- Plan content will be rendered here -->
                </div>
            </div>
        `;

        this.setupEventListeners();
        this.loadInitialPlan();
    }

    setupEventListeners() {
        // Export button
        const exportBtn = this.container.querySelector('#plan-export');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportPlan());
        }

        // Refresh button
        const refreshBtn = this.container.querySelector('#plan-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshPlan());
        }

        // Generate Proposal button
        const proposalBtn = this.container.querySelector('#plan-generate-proposal');
        if (proposalBtn) {
            proposalBtn.addEventListener('click', () => this.generateProposal());
        }

        // Request Approval button
        const approvalBtn = this.container.querySelector('#plan-request-approval');
        if (approvalBtn) {
            approvalBtn.addEventListener('click', () => this.requestApproval());
        }
    }

    loadInitialPlan() {
        // Check URL parameters for task_id or plan_id
        const params = new URLSearchParams(window.location.search);
        this.taskId = params.get('task_id');
        this.planId = params.get('plan_id');

        if (this.taskId) {
            this.loadPlanForTask(this.taskId);
        } else if (this.planId) {
            this.loadPlanById(this.planId);
        } else {
            this.renderEmptyState();
        }
    }

    async loadPlanForTask(taskId) {
        const contentDiv = this.container.querySelector('#plan-content');
        contentDiv.innerHTML = '<div class="loading-state"><div class="loading-spinner"></div><p>Loading execution plan...</p></div>';

        try {
            const result = await apiClient.get(`/api/exec/tasks/${taskId}/plan`, {
                requestId: `exec-plan-task-${taskId}`
            });

            if (result.ok) {
                this.currentPlan = result.data;
                this.renderPlan(this.currentPlan);
                this.updateBreadcrumb();
                this.enableActions();
            } else {
                this.renderError(result.message, result.hint);
            }
        } catch (error) {
            console.error('Failed to load execution plan:', error);
            this.renderError('Failed to load execution plan', 'Check network connectivity and API availability');
        }
    }

    async loadPlanById(planId) {
        const contentDiv = this.container.querySelector('#plan-content');
        contentDiv.innerHTML = '<div class="loading-state"><div class="loading-spinner"></div><p>Loading execution plan...</p></div>';

        try {
            const result = await apiClient.get(`/api/exec/plans/${planId}`, {
                requestId: `exec-plan-${planId}`
            });

            if (result.ok) {
                this.currentPlan = result.data;
                this.renderPlan(this.currentPlan);
                this.updateBreadcrumb();
                this.enableActions();
            } else {
                this.renderError(result.message, result.hint);
            }
        } catch (error) {
            console.error('Failed to load execution plan:', error);
            this.renderError('Failed to load execution plan', 'Check network connectivity and API availability');
        }
    }

    renderPlan(plan) {
        const contentDiv = this.container.querySelector('#plan-content');

        contentDiv.innerHTML = `
            <div class="plan-container">
                <!-- Plan Overview -->
                <div class="plan-section plan-overview">
                    <div class="section-header">
                        <h3>Plan Overview</h3>
                        <span class="plan-status status-${plan.status || 'draft'}">${this.formatStatus(plan.status || 'draft')}</span>
                    </div>
                    <div class="overview-grid">
                        <div class="overview-item">
                            <label>Plan ID</label>
                            <div class="overview-value">
                                <code>${plan.plan_id || 'N/A'}</code>
                                ${plan.plan_id ? `<button class="btn-copy" data-copy="${plan.plan_id}"><span class="material-icons md-18">content_copy</span></button>` : ''}
                            </div>
                        </div>
                        <div class="overview-item">
                            <label>Task ID</label>
                            <div class="overview-value">
                                <code>${plan.task_id || 'N/A'}</code>
                                ${plan.task_id ? `<button class="btn-link" data-task-id="${plan.task_id}">View Task</button>` : ''}
                            </div>
                        </div>
                        <div class="overview-item">
                            <label>Created</label>
                            <div class="overview-value">${this.formatTimestamp(plan.created_at)}</div>
                        </div>
                        <div class="overview-item">
                            <label>Estimated Duration</label>
                            <div class="overview-value">${plan.estimated_duration_ms ? this.formatDuration(plan.estimated_duration_ms) : 'N/A'}</div>
                        </div>
                    </div>
                    ${plan.description ? `
                        <div class="plan-description">
                            <p>${plan.description}</p>
                        </div>
                    ` : ''}
                </div>

                <!-- Validation Results -->
                ${plan.validation ? this.renderValidation(plan.validation) : ''}

                <!-- Plan Steps Timeline -->
                ${plan.steps ? this.renderStepsTimeline(plan.steps) : ''}

                <!-- Explanation Panel -->
                ${plan.explanation ? this.renderExplanation(plan.explanation) : ''}

                <!-- Artifact Links -->
                ${plan.artifacts ? this.renderArtifacts(plan.artifacts) : ''}
            </div>
        `;

        // Setup event handlers
        this.setupPlanEventHandlers();
    }

    renderValidation(validation) {
        const allPassed = validation.rules_passed && validation.rules_passed.length > 0 &&
                         (!validation.rules_failed || validation.rules_failed.length === 0);
        const hasFailed = validation.rules_failed && validation.rules_failed.length > 0;

        return `
            <div class="plan-section validation-section ${hasFailed ? 'has-failures' : ''}">
                <div class="section-header">
                    <h3>
                        <span class="material-icons md-18">${hasFailed ? 'error' : 'check_circle'}</span>
                        Validation Report
                    </h3>
                    <span class="validation-summary ${hasFailed ? 'validation-failed' : 'validation-passed'}">
                        ${hasFailed ? `${validation.rules_failed.length} rule(s) failed` : 'All checks passed'}
                    </span>
                </div>

                <div class="validation-content">
                    ${validation.rules_passed && validation.rules_passed.length > 0 ? `
                        <div class="validation-group validation-passed-group">
                            <h4 class="validation-group-title">
                                <span class="material-icons md-18">check</span>
                                Passed Rules (${validation.rules_passed.length})
                            </h4>
                            <div class="validation-rules">
                                ${validation.rules_passed.map(rule => this.renderValidationRule(rule, 'passed')).join('')}
                            </div>
                        </div>
                    ` : ''}

                    ${validation.rules_failed && validation.rules_failed.length > 0 ? `
                        <div class="validation-group validation-failed-group">
                            <h4 class="validation-group-title">
                                <span class="material-icons md-18">close</span>
                                Failed Rules (${validation.rules_failed.length})
                            </h4>
                            <div class="validation-rules">
                                ${validation.rules_failed.map(rule => this.renderValidationRule(rule, 'failed')).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    renderValidationRule(rule, status) {
        const icon = status === 'passed' ? 'check_circle' : 'cancel';
        const ruleClass = status === 'passed' ? 'rule-passed' : 'rule-failed';

        return `
            <div class="validation-rule ${ruleClass}">
                <div class="rule-header">
                    <span class="material-icons md-18">${icon}</span>
                    <strong>${rule.rule_name || rule.name || 'Unnamed Rule'}</strong>
                </div>
                ${rule.description ? `
                    <div class="rule-description">${rule.description}</div>
                ` : ''}
                ${rule.reason ? `
                    <div class="rule-reason">
                        <span class="reason-label">Reason:</span>
                        <span class="reason-text">${rule.reason}</span>
                    </div>
                ` : ''}
                ${rule.hint ? `
                    <div class="rule-hint">
                        <span class="material-icons md-16">lightbulb</span>
                        <span>${rule.hint}</span>
                    </div>
                ` : ''}
                ${rule.fix_suggestions && rule.fix_suggestions.length > 0 ? `
                    <div class="rule-fixes">
                        <div class="fixes-label">Suggested fixes:</div>
                        <ul class="fixes-list">
                            ${rule.fix_suggestions.map(fix => `<li>${fix}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
            </div>
        `;
    }

    renderStepsTimeline(steps) {
        if (!steps || steps.length === 0) {
            return '';
        }

        return `
            <div class="plan-section steps-section">
                <div class="section-header">
                    <h3>
                        <span class="material-icons md-18">analytics</span>
                        Execution Steps (${steps.length})
                    </h3>
                    <div class="timeline-controls">
                        <button class="btn-link" id="expand-all-steps">Expand All</button>
                        <button class="btn-link" id="collapse-all-steps">Collapse All</button>
                    </div>
                </div>

                <div class="steps-timeline">
                    ${steps.map((step, index) => this.renderStep(step, index)).join('')}
                </div>
            </div>
        `;
    }

    renderStep(step, index) {
        const stepId = `step-${index}`;
        const hasRisk = step.risk_level && step.risk_level !== 'low';
        const riskClass = step.risk_level ? `risk-${step.risk_level}` : '';

        return `
            <div class="timeline-step ${riskClass}" data-step-id="${stepId}">
                <div class="step-marker">
                    <span class="step-number">${index + 1}</span>
                    ${hasRisk ? `<span class="risk-indicator" title="Risk: ${step.risk_level}">!</span>` : ''}
                </div>
                <div class="step-line"></div>
                <div class="step-content">
                    <div class="step-header" data-toggle-step="${stepId}">
                        <div class="step-title">
                            <strong>${step.name || `Step ${index + 1}`}</strong>
                            ${step.type ? `<span class="step-type-badge">${step.type}</span>` : ''}
                            ${hasRisk ? `<span class="risk-badge risk-${step.risk_level}">${step.risk_level.toUpperCase()}</span>` : ''}
                        </div>
                        <div class="step-meta">
                            ${step.estimated_duration_ms ? `
                                <span class="step-duration">
                                    <span class="material-icons md-16">schedule</span>
                                    ${this.formatDuration(step.estimated_duration_ms)}
                                </span>
                            ` : ''}
                            <span class="material-icons md-18">arrow_drop_down</span>
                        </div>
                    </div>

                    <div class="step-body collapsed" id="${stepId}-body">
                        ${step.description ? `
                            <div class="step-description">${step.description}</div>
                        ` : ''}

                        ${step.inputs && Object.keys(step.inputs).length > 0 ? `
                            <div class="step-io-section">
                                <h5>Inputs</h5>
                                <div class="step-io-list">
                                    ${Object.entries(step.inputs).map(([key, value]) => `
                                        <div class="io-item">
                                            <code class="io-key">${key}</code>
                                            <span class="io-separator">:</span>
                                            <span class="io-value">${this.formatValue(value)}</span>
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        ` : ''}

                        ${step.outputs && Object.keys(step.outputs).length > 0 ? `
                            <div class="step-io-section">
                                <h5>Expected Outputs</h5>
                                <div class="step-io-list">
                                    ${Object.entries(step.outputs).map(([key, value]) => `
                                        <div class="io-item">
                                            <code class="io-key">${key}</code>
                                            <span class="io-separator">:</span>
                                            <span class="io-value">${this.formatValue(value)}</span>
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        ` : ''}

                        ${step.depends_on && step.depends_on.length > 0 ? `
                            <div class="step-dependencies">
                                <h5>
                                    <span class="material-icons md-16">link</span>
                                    Dependencies
                                </h5>
                                <div class="dependencies-list">
                                    ${step.depends_on.map(dep => `
                                        <span class="dependency-badge">${dep}</span>
                                    `).join('')}
                                </div>
                            </div>
                        ` : ''}

                        ${step.risk_reason ? `
                            <div class="step-risk-reason">
                                <span class="material-icons md-16">warning</span>
                                <span>${step.risk_reason}</span>
                            </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    }

    renderExplanation(explanation) {
        return `
            <div class="plan-section explanation-section">
                <div class="section-header">
                    <h3>
                        <span class="material-icons md-18">info</span>
                        Plan Explanation
                    </h3>
                </div>

                <div class="explanation-content">
                    ${explanation.summary ? `
                        <div class="explanation-summary markdown-content">
                            ${this.renderMarkdown(explanation.summary)}
                        </div>
                    ` : ''}

                    ${explanation.rationale ? `
                        <div class="explanation-section-item">
                            <h4>Rationale</h4>
                            <div class="explanation-text">${explanation.rationale}</div>
                        </div>
                    ` : ''}

                    ${explanation.alternatives && explanation.alternatives.length > 0 ? `
                        <div class="explanation-section-item">
                            <h4>Alternatives Considered</h4>
                            <ul class="alternatives-list">
                                ${explanation.alternatives.map(alt => `
                                    <li>${alt}</li>
                                `).join('')}
                            </ul>
                        </div>
                    ` : ''}

                    ${explanation.risks && explanation.risks.length > 0 ? `
                        <div class="explanation-section-item">
                            <h4>Known Risks</h4>
                            <ul class="risks-list">
                                ${explanation.risks.map(risk => `
                                    <li class="risk-item">
                                        <span class="material-icons md-16">warning</span>
                                        <span>${risk}</span>
                                    </li>
                                `).join('')}
                            </ul>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    renderArtifacts(artifacts) {
        if (!artifacts || artifacts.length === 0) {
            return '';
        }

        return `
            <div class="plan-section artifacts-section">
                <div class="section-header">
                    <h3>
                        <span class="material-icons md-18">attachment</span>
                        Related Artifacts (${artifacts.length})
                    </h3>
                </div>

                <div class="artifacts-list">
                    ${artifacts.map(artifact => this.renderArtifact(artifact)).join('')}
                </div>
            </div>
        `;
    }

    renderArtifact(artifact) {
        const icon = this.getArtifactIcon(artifact.type);

        return `
            <div class="artifact-item">
                <span class="material-icons md-18">${icon}</span>
                <div class="artifact-info">
                    <div class="artifact-name">${artifact.name || artifact.path || 'Unnamed Artifact'}</div>
                    <div class="artifact-meta">
                        ${artifact.type ? `<span class="artifact-type">${artifact.type}</span>` : ''}
                        ${artifact.size ? `<span class="artifact-size">${this.formatSize(artifact.size)}</span>` : ''}
                    </div>
                </div>
                ${artifact.id ? `
                    <button class="btn-link" data-artifact-id="${artifact.id}">
                        View
                    </button>
                ` : ''}
            </div>
        `;
    }

    renderEmptyState() {
        const contentDiv = this.container.querySelector('#plan-content');
        contentDiv.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">
                    <span class="material-icons md-48">description</span>
                </div>
                <h3>No Execution Plan Available</h3>
                <p>Generate an execution plan first or select a task to view its plan.</p>
                <div class="empty-actions">
                    <button class="btn-primary" onclick="window.navigateToView('tasks')">
                        View Tasks
                    </button>
                </div>
            </div>
        `;
    }

    renderError(message, hint) {
        const contentDiv = this.container.querySelector('#plan-content');
        contentDiv.innerHTML = `
            <div class="error-state">
                <div class="error-icon">
                    <span class="material-icons md-48">error</span>
                </div>
                <h3>Failed to Load Execution Plan</h3>
                <p class="error-message">${message}</p>
                ${hint ? `
                    <div class="error-hint">
                        <span class="material-icons md-18">lightbulb</span>
                        <span>${hint}</span>
                    </div>
                ` : ''}
                <div class="error-actions">
                    <button class="btn-secondary" onclick="location.reload()">
                        Retry
                    </button>
                    <button class="btn-link" onclick="window.navigateToView('tasks')">
                        Back to Tasks
                    </button>
                </div>
            </div>
        `;
    }

    renderNoPermissionState() {
        const contentDiv = this.container.querySelector('#plan-content');
        contentDiv.innerHTML = `
            <div class="no-permission-state">
                <div class="permission-icon">
                    <span class="material-icons md-48">lock</span>
                </div>
                <h3>Permission Denied</h3>
                <p>You don't have permission to view this execution plan.</p>
                <p class="permission-hint">Contact your administrator for access.</p>
            </div>
        `;
    }

    setupPlanEventHandlers() {
        const contentDiv = this.container.querySelector('#plan-content');

        // Copy buttons
        contentDiv.querySelectorAll('.btn-copy').forEach(btn => {
            btn.addEventListener('click', () => {
                const text = btn.getAttribute('data-copy');
                navigator.clipboard.writeText(text);
                showToast('Copied to clipboard', 'success', 1500);
            });
        });

        // View task button
        const taskBtn = contentDiv.querySelector('.btn-link[data-task-id]');
        if (taskBtn) {
            taskBtn.addEventListener('click', () => {
                const taskId = taskBtn.getAttribute('data-task-id');
                window.navigateToView('tasks', { task_id: taskId });
            });
        }

        // Step toggle handlers
        contentDiv.querySelectorAll('[data-toggle-step]').forEach(header => {
            header.addEventListener('click', () => {
                const stepId = header.getAttribute('data-toggle-step');
                const body = contentDiv.querySelector(`#${stepId}-body`);
                if (body) {
                    body.classList.toggle('collapsed');
                    const icon = header.querySelector('.step-toggle-icon');
                    if (icon) {
                        icon.textContent = body.classList.contains('collapsed') ? 'expand_more' : 'expand_less';
                    }
                }
            });
        });

        // Expand/Collapse all buttons
        const expandAllBtn = contentDiv.querySelector('#expand-all-steps');
        if (expandAllBtn) {
            expandAllBtn.addEventListener('click', () => {
                contentDiv.querySelectorAll('.step-body').forEach(body => {
                    body.classList.remove('collapsed');
                });
                contentDiv.querySelectorAll('.step-toggle-icon').forEach(icon => {
                    icon.textContent = 'expand_less';
                });
            });
        }

        const collapseAllBtn = contentDiv.querySelector('#collapse-all-steps');
        if (collapseAllBtn) {
            collapseAllBtn.addEventListener('click', () => {
                contentDiv.querySelectorAll('.step-body').forEach(body => {
                    body.classList.add('collapsed');
                });
                contentDiv.querySelectorAll('.step-toggle-icon').forEach(icon => {
                    icon.textContent = 'expand_more';
                });
            });
        }

        // Artifact view buttons
        contentDiv.querySelectorAll('.btn-link[data-artifact-id]').forEach(btn => {
            btn.addEventListener('click', () => {
                const artifactId = btn.getAttribute('data-artifact-id');
                this.viewArtifact(artifactId);
            });
        });
    }

    updateBreadcrumb() {
        const breadcrumb = this.container.querySelector('#plan-breadcrumb');
        if (this.currentPlan && this.currentPlan.task_id) {
            breadcrumb.innerHTML = `
                <a href="#" onclick="window.navigateToView('tasks'); return false;">Tasks</a>
                <span class="breadcrumb-separator">/</span>
                <a href="#" onclick="window.navigateToView('tasks', {task_id: '${this.currentPlan.task_id}'}); return false;">${this.currentPlan.task_id}</a>
                <span class="breadcrumb-separator">/</span>
                <span>Execution Plan</span>
            `;
        }
    }

    enableActions() {
        const exportBtn = this.container.querySelector('#plan-export');
        const proposalBtn = this.container.querySelector('#plan-generate-proposal');
        const approvalBtn = this.container.querySelector('#plan-request-approval');

        if (exportBtn) exportBtn.disabled = false;
        if (proposalBtn) proposalBtn.disabled = false;
        if (approvalBtn) approvalBtn.disabled = false;
    }

    async exportPlan() {
        if (!this.currentPlan) return;

        try {
            const planJson = JSON.stringify(this.currentPlan, null, 2);
            const blob = new Blob([planJson], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `execution-plan-${this.currentPlan.plan_id || 'export'}.json`;
            a.click();
            URL.revokeObjectURL(url);

            showToast('Plan exported successfully', 'success');
        } catch (error) {
            console.error('Failed to export plan:', error);
            showToast('Failed to export plan', 'error');
        }
    }

    async refreshPlan() {
        if (this.taskId) {
            await this.loadPlanForTask(this.taskId);
        } else if (this.planId) {
            await this.loadPlanById(this.planId);
        }
        showToast('Plan refreshed', 'success', 2000);
    }

    async generateProposal() {
        if (!this.currentPlan) return;

        try {
            const result = await apiClient.post(`/api/exec/plans/${this.currentPlan.plan_id}/proposal`, {}, {
                requestId: `exec-proposal-${this.currentPlan.plan_id}`
            });

            if (result.ok) {
                showToast('Proposal generated successfully', 'success');
                this.refreshPlan();
            } else {
                showToast(`Failed to generate proposal: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Failed to generate proposal:', error);
            showToast('Failed to generate proposal', 'error');
        }
    }

    async requestApproval() {
        if (!this.currentPlan) return;

        try {
            const result = await apiClient.post(`/api/exec/plans/${this.currentPlan.plan_id}/request-approval`, {}, {
                requestId: `exec-approval-${this.currentPlan.plan_id}`
            });

            if (result.ok) {
                showToast('Approval request sent', 'success');
                this.refreshPlan();
            } else {
                showToast(`Failed to request approval: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Failed to request approval:', error);
            showToast('Failed to request approval', 'error');
        }
    }

    async viewArtifact(artifactId) {
        // TODO: Navigate to artifact detail view
        showToast(`Artifact view not yet implemented (ID: ${artifactId})`, 'info');
    }

    // Utility methods
    formatStatus(status) {
        const statusMap = {
            'draft': 'Draft',
            'pending': 'Pending',
            'validated': 'Validated',
            'approved': 'Approved',
            'rejected': 'Rejected',
            'executing': 'Executing',
            'completed': 'Completed',
            'failed': 'Failed'
        };
        return statusMap[status] || status;
    }

    formatTimestamp(timestamp) {
        if (!timestamp) return 'N/A';
        try {
            const date = new Date(timestamp);
            return date.toLocaleString();
        } catch (e) {
            return timestamp;
        }
    }

    formatDuration(ms) {
        if (ms < 1000) return `${ms}ms`;
        if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
        if (ms < 3600000) return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
        return `${Math.floor(ms / 3600000)}h ${Math.floor((ms % 3600000) / 60000)}m`;
    }

    formatValue(value) {
        if (value === null || value === undefined) return 'null';
        if (typeof value === 'object') return JSON.stringify(value);
        if (typeof value === 'string') return `"${value}"`;
        return String(value);
    }

    formatSize(bytes) {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / 1048576).toFixed(1)} MB`;
    }

    getArtifactIcon(type) {
        const iconMap = {
            'file': 'description',
            'config': 'settings',
            'log': 'article',
            'report': 'assessment',
            'data': 'storage',
            'code': 'code'
        };
        return iconMap[type] || 'attachment';
    }

    renderMarkdown(text) {
        // Simple markdown rendering (can be enhanced with a proper markdown library)
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }

    destroy() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
        }
        this.container.innerHTML = '';
    }
}

// Export to window
window.ExecutionPlansView = ExecutionPlansView;
