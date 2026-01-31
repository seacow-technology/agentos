/**
 * CreateTaskWizard - 4-step wizard for creating tasks with project binding
 *
 * Usage:
 *   const wizard = new CreateTaskWizard(container, {
 *     defaultProjectId: 'proj_123',
 *     onComplete: (taskId) => { ... }
 *   });
 */

class CreateTaskWizard {
    constructor(container, options = {}) {
        this.container = container;
        this.options = {
            defaultProjectId: options.defaultProjectId || null,
            onComplete: options.onComplete || (() => {}),
            onCancel: options.onCancel || (() => {})
        };

        this.step = 1;
        this.taskId = null;
        this.projects = [];
        this.repos = [];
        this.formData = {
            title: '',
            intent: '',
            project_id: this.options.defaultProjectId,
            repo_id: null,
            workdir: null,
            acceptance_criteria: []
        };

        this.init();
    }

    async init() {
        // Load projects for dropdown
        await this.loadProjects();

        this.render();
        this.setupEventListeners();
    }

    async loadProjects() {
        try {
            const result = await apiClient.get('/api/projects?limit=100');
            if (result.ok && result.data) {
                this.projects = result.data.projects || result.data || [];
            }
        } catch (err) {
            console.error('Failed to load projects:', err);
            showToast('Failed to load projects', 'error');
        }
    }

    async loadReposForProject(projectId) {
        if (!projectId) {
            this.repos = [];
            return;
        }

        try {
            const result = await apiClient.get(`/api/projects/${projectId}/repos`);
            if (result.ok && result.data) {
                this.repos = result.data.repos || result.data || [];
            }
        } catch (err) {
            console.error('Failed to load repos:', err);
            this.repos = [];
        }
    }

    render() {
        this.container.innerHTML = `
            <div class="wizard-container">
                <div class="wizard-header">
                    <h2>Create New Task</h2>
                    <div class="wizard-steps">
                        <div class="wizard-step ${this.step >= 1 ? 'active' : ''} ${this.step > 1 ? 'completed' : ''}">
                            <div class="step-number">1</div>
                            <div class="step-label">Basic Info</div>
                        </div>
                        <div class="wizard-step ${this.step >= 2 ? 'active' : ''} ${this.step > 2 ? 'completed' : ''}">
                            <div class="step-number">2</div>
                            <div class="step-label">Repository</div>
                        </div>
                        <div class="wizard-step ${this.step >= 3 ? 'active' : ''} ${this.step > 3 ? 'completed' : ''}">
                            <div class="step-number">3</div>
                            <div class="step-label">Acceptance</div>
                        </div>
                        <div class="wizard-step ${this.step >= 4 ? 'active' : ''} ${this.step > 4 ? 'completed' : ''}">
                            <div class="step-number">4</div>
                            <div class="step-label">Freeze Spec</div>
                        </div>
                    </div>
                </div>

                <div class="wizard-body">
                    ${this.renderCurrentStep()}
                </div>

                <div class="wizard-footer">
                    ${this.renderFooter()}
                </div>
            </div>
        `;
    }

    renderCurrentStep() {
        switch (this.step) {
            case 1:
                return this.renderStep1();
            case 2:
                return this.renderStep2();
            case 3:
                return this.renderStep3();
            case 4:
                return this.renderStep4();
            default:
                return '';
        }
    }

    renderStep1() {
        return `
            <div class="wizard-step-content">
                <h3>Task Basic Information</h3>
                <p class="step-description">Provide the title, intent, and project for this task.</p>

                <div class="form-group">
                    <label for="wizard-title">Task Title *</label>
                    <input type="text"
                           id="wizard-title"
                           class="form-control"
                           placeholder="e.g., Implement user authentication"
                           value="${this.escapeHtml(this.formData.title)}"
                           required>
                    <small class="form-hint">A clear, concise description of what needs to be done</small>
                </div>

                <div class="form-group">
                    <label for="wizard-intent">Intent Description (optional)</label>
                    <textarea id="wizard-intent"
                              class="form-control"
                              rows="4"
                              placeholder="Describe the goal and context of this task...">${this.escapeHtml(this.formData.intent)}</textarea>
                    <small class="form-hint">Provide context to help the agent understand the task</small>
                </div>

                <div class="form-group">
                    <label for="wizard-project">Project *</label>
                    <select id="wizard-project" class="form-control" required>
                        <option value="">-- Select Project --</option>
                        ${this.projects.map(p => `
                            <option value="${p.project_id}" ${this.formData.project_id === p.project_id ? 'selected' : ''}>
                                ${this.escapeHtml(p.name)}
                            </option>
                        `).join('')}
                    </select>
                    <small class="form-hint">Tasks must be associated with a project</small>
                </div>
            </div>
        `;
    }

    renderStep2() {
        return `
            <div class="wizard-step-content">
                <h3>Bind Repository & Working Directory</h3>
                <p class="step-description">Select the repository and working directory for this task (optional).</p>

                <div class="form-group">
                    <label for="wizard-repo">Repository (optional)</label>
                    <select id="wizard-repo" class="form-control">
                        <option value="">-- No repository --</option>
                        ${this.repos.map(r => `
                            <option value="${r.repo_id}" ${this.formData.repo_id === r.repo_id ? 'selected' : ''}>
                                ${this.escapeHtml(r.name)} (${this.escapeHtml(r.workspace_relpath || r.local_path)})
                            </option>
                        `).join('')}
                    </select>
                    <small class="form-hint">Repository where the task will operate</small>
                </div>

                <div class="form-group">
                    <label for="wizard-workdir">Working Directory (optional)</label>
                    <input type="text"
                           id="wizard-workdir"
                           class="form-control"
                           placeholder="e.g., src/auth"
                           value="${this.escapeHtml(this.formData.workdir || '')}">
                    <small class="form-hint">Relative path within the repository (use '.' for root)</small>
                </div>

                <div class="info-box">
                    <span class="material-icons md-20">info</span>
                    <div>
                        <strong>Note:</strong> You can skip this step if the task doesn't need repository access.
                        Repository and working directory can be specified later.
                    </div>
                </div>
            </div>
        `;
    }

    renderStep3() {
        return `
            <div class="wizard-step-content">
                <h3>Acceptance Criteria</h3>
                <p class="step-description">Define the conditions that must be met for this task to be considered complete.</p>

                <div class="form-group">
                    <label>Acceptance Criteria *</label>
                    <div id="criteria-list" class="criteria-list">
                        ${this.formData.acceptance_criteria.length > 0
                            ? this.formData.acceptance_criteria.map((criterion, idx) => `
                                <div class="criterion-item" data-index="${idx}">
                                    <span class="criterion-number">${idx + 1}.</span>
                                    <input type="text"
                                           class="form-control criterion-input"
                                           value="${this.escapeHtml(criterion)}"
                                           placeholder="e.g., All tests pass">
                                    <button type="button" class="btn-remove-criterion" data-index="${idx}" title="Remove">
                                        <span class="material-icons md-18">close</span>
                                    </button>
                                </div>
                            `).join('')
                            : '<div class="empty-criteria">No criteria added yet. Click "Add Criterion" to start.</div>'
                        }
                    </div>
                    <button type="button" id="add-criterion-btn" class="btn-secondary btn-sm">
                        <span class="material-icons md-16">add</span> Add Criterion
                    </button>
                    <small class="form-hint">At least one acceptance criterion is required</small>
                </div>

                <div class="info-box">
                    <span class="material-icons md-20">info</span>
                    <div>
                        <strong>Tip:</strong> Good acceptance criteria are specific, measurable, and verifiable.
                        Examples: "API returns 200 status", "Database migration completes", "All unit tests pass".
                    </div>
                </div>
            </div>
        `;
    }

    renderStep4() {
        return `
            <div class="wizard-step-content">
                <h3>Review & Freeze Specification</h3>
                <p class="step-description">Review your task details and freeze the specification to make it ready for execution.</p>

                <div class="summary-section">
                    <h4>Task Summary</h4>

                    <div class="summary-item">
                        <label>Title:</label>
                        <div class="summary-value">${this.escapeHtml(this.formData.title)}</div>
                    </div>

                    <div class="summary-item">
                        <label>Project:</label>
                        <div class="summary-value">
                            ${this.projects.find(p => p.project_id === this.formData.project_id)?.name || 'N/A'}
                        </div>
                    </div>

                    ${this.formData.intent ? `
                        <div class="summary-item">
                            <label>Intent:</label>
                            <div class="summary-value">${this.escapeHtml(this.formData.intent)}</div>
                        </div>
                    ` : ''}

                    ${this.formData.repo_id ? `
                        <div class="summary-item">
                            <label>Repository:</label>
                            <div class="summary-value">
                                ${this.repos.find(r => r.repo_id === this.formData.repo_id)?.name || 'N/A'}
                            </div>
                        </div>
                    ` : ''}

                    ${this.formData.workdir ? `
                        <div class="summary-item">
                            <label>Working Directory:</label>
                            <div class="summary-value"><code>${this.escapeHtml(this.formData.workdir)}</code></div>
                        </div>
                    ` : ''}

                    <div class="summary-item">
                        <label>Acceptance Criteria:</label>
                        <div class="summary-value">
                            <ol class="criteria-summary">
                                ${this.formData.acceptance_criteria.map(c =>
                                    `<li>${this.escapeHtml(c)}</li>`
                                ).join('')}
                            </ol>
                        </div>
                    </div>
                </div>

                ${this.taskId ? `
                    <div class="success-box">
                        <span class="material-icons md-24">check_circle</span>
                        <div>
                            <strong>Task Created!</strong>
                            <p>Task ID: <code>${this.taskId}</code></p>
                            <p>Click "Freeze Spec" to lock the specification and make the task ready for execution.</p>
                        </div>
                    </div>
                ` : `
                    <div class="info-box">
                        <span class="material-icons md-20">info</span>
                        <div>
                            <strong>What happens when you freeze?</strong>
                            <p>Freezing the specification makes it immutable. The task will transition to PLANNED state
                            and be ready for execution. This ensures consistency and prevents changes during execution.</p>
                        </div>
                    </div>
                `}
            </div>
        `;
    }

    renderFooter() {
        const canGoBack = this.step > 1 && this.step < 4;
        const canGoNext = this.step < 4;

        return `
            <button type="button" id="wizard-cancel" class="btn-secondary">
                Cancel
            </button>
            <div class="button-group">
                ${canGoBack ? `
                    <button type="button" id="wizard-back" class="btn-secondary">
                        <span class="material-icons md-18">arrow_back</span> Back
                    </button>
                ` : ''}
                ${canGoNext ? `
                    <button type="button" id="wizard-next" class="btn-primary">
                        Next <span class="material-icons md-18">arrow_forward</span>
                    </button>
                ` : ''}
                ${this.step === 4 ? `
                    <button type="button" id="wizard-freeze" class="btn-primary" ${this.taskId ? '' : 'disabled'}>
                        <span class="material-icons md-18">lock</span> Freeze Spec & Complete
                    </button>
                ` : ''}
            </div>
        `;
    }

    setupEventListeners() {
        // Cancel button
        const cancelBtn = this.container.querySelector('#wizard-cancel');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.cancel());
        }

        // Back button
        const backBtn = this.container.querySelector('#wizard-back');
        if (backBtn) {
            backBtn.addEventListener('click', () => this.goBack());
        }

        // Next button
        const nextBtn = this.container.querySelector('#wizard-next');
        if (nextBtn) {
            nextBtn.addEventListener('click', () => this.goNext());
        }

        // Freeze button
        const freezeBtn = this.container.querySelector('#wizard-freeze');
        if (freezeBtn) {
            freezeBtn.addEventListener('click', () => this.freezeSpec());
        }

        // Step-specific listeners
        this.setupStepListeners();
    }

    setupStepListeners() {
        switch (this.step) {
            case 1:
                // Project selection
                const projectSelect = this.container.querySelector('#wizard-project');
                if (projectSelect) {
                    projectSelect.addEventListener('change', async (e) => {
                        this.formData.project_id = e.target.value;
                        await this.loadReposForProject(e.target.value);
                    });
                }
                break;

            case 3:
                // Add criterion button
                const addBtn = this.container.querySelector('#add-criterion-btn');
                if (addBtn) {
                    addBtn.addEventListener('click', () => this.addCriterion());
                }

                // Remove criterion buttons
                this.container.querySelectorAll('.btn-remove-criterion').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        const index = parseInt(e.currentTarget.getAttribute('data-index'));
                        this.removeCriterion(index);
                    });
                });

                // Update criterion values
                this.container.querySelectorAll('.criterion-input').forEach((input, idx) => {
                    input.addEventListener('blur', (e) => {
                        this.formData.acceptance_criteria[idx] = e.target.value;
                    });
                });
                break;
        }
    }

    addCriterion() {
        this.formData.acceptance_criteria.push('');
        this.render();
        this.setupEventListeners();

        // Focus on the new input
        const inputs = this.container.querySelectorAll('.criterion-input');
        if (inputs.length > 0) {
            inputs[inputs.length - 1].focus();
        }
    }

    removeCriterion(index) {
        this.formData.acceptance_criteria.splice(index, 1);
        this.render();
        this.setupEventListeners();
    }

    async goNext() {
        // Validate current step
        if (!this.validateCurrentStep()) {
            return;
        }

        // Collect data from current step
        this.collectStepData();

        // Special handling for step 3: create task
        if (this.step === 3) {
            const created = await this.createTask();
            if (!created) {
                return;
            }
        }

        // Move to next step
        this.step++;
        this.render();
        this.setupEventListeners();
    }

    goBack() {
        this.collectStepData();
        this.step--;
        this.render();
        this.setupEventListeners();
    }

    validateCurrentStep() {
        switch (this.step) {
            case 1:
                const title = this.container.querySelector('#wizard-title')?.value.trim();
                const projectId = this.container.querySelector('#wizard-project')?.value;

                if (!title) {
                    showToast('Task title is required', 'error');
                    return false;
                }

                if (!projectId) {
                    showToast('Project selection is required', 'error');
                    return false;
                }

                return true;

            case 2:
                // Step 2 is optional
                return true;

            case 3:
                this.collectStepData();

                const validCriteria = this.formData.acceptance_criteria.filter(c => c.trim().length > 0);
                if (validCriteria.length === 0) {
                    showToast('At least one acceptance criterion is required', 'error');
                    return false;
                }

                this.formData.acceptance_criteria = validCriteria;
                return true;

            default:
                return true;
        }
    }

    collectStepData() {
        switch (this.step) {
            case 1:
                this.formData.title = this.container.querySelector('#wizard-title')?.value.trim() || '';
                this.formData.intent = this.container.querySelector('#wizard-intent')?.value.trim() || '';
                this.formData.project_id = this.container.querySelector('#wizard-project')?.value || null;
                break;

            case 2:
                this.formData.repo_id = this.container.querySelector('#wizard-repo')?.value || null;
                this.formData.workdir = this.container.querySelector('#wizard-workdir')?.value.trim() || null;
                break;

            case 3:
                // Criteria are updated on blur, so just validate
                const inputs = this.container.querySelectorAll('.criterion-input');
                this.formData.acceptance_criteria = Array.from(inputs)
                    .map(input => input.value.trim())
                    .filter(v => v.length > 0);
                break;
        }
    }

    async createTask() {
        try {
            showToast('Creating task...', 'info', 2000);

            // Prepare task data
            const taskData = {
                title: this.formData.title,
                intent: this.formData.intent || null,
                project_id: this.formData.project_id,
                acceptance_criteria: this.formData.acceptance_criteria
            };

            // Add optional fields
            if (this.formData.repo_id) {
                taskData.repo_id = this.formData.repo_id;
            }
            if (this.formData.workdir) {
                taskData.workdir = this.formData.workdir;
            }

            const result = await apiClient.post('/api/tasks', taskData);

            if (!result.ok) {
                showToast(`Failed to create task: ${result.message}`, 'error');
                return false;
            }

            this.taskId = result.data.task_id || result.data.task?.task_id;
            showToast('Task created successfully', 'success');
            return true;

        } catch (err) {
            console.error('Failed to create task:', err);
            showToast('Failed to create task: ' + err.message, 'error');
            return false;
        }
    }

    async freezeSpec() {
        if (!this.taskId) {
            showToast('Task not created yet', 'error');
            return;
        }

        try {
            showToast('Freezing specification...', 'info', 2000);

            const result = await apiClient.post(`/api/tasks/${this.taskId}/spec/freeze`);

            if (!result.ok) {
                showToast(`Failed to freeze spec: ${result.message}`, 'error');
                return;
            }

            showToast('Specification frozen successfully', 'success');

            // Complete the wizard
            setTimeout(() => {
                this.complete();
            }, 500);

        } catch (err) {
            console.error('Failed to freeze spec:', err);
            showToast('Failed to freeze spec: ' + err.message, 'error');
        }
    }

    complete() {
        this.options.onComplete(this.taskId);
    }

    async cancel() {
        if (this.taskId) {
            const confirmCancel = await Dialog.confirm(
                'Task has been created. Do you want to cancel the wizard?<br><br>The task will remain in draft state.',
                {
                    title: 'Cancel Wizard',
                    confirmText: 'Cancel Wizard',
                    cancelText: 'Continue Editing'
                }
            );
            if (!confirmCancel) {
                return;
            }
        }
        this.options.onCancel();
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    destroy() {
        this.container.innerHTML = '';
    }
}

// Export
window.CreateTaskWizard = CreateTaskWizard;
