/**
 * TasksView - Task Management UI
 *
 * PR-2: Observability Module - Tasks View
 * Coverage: GET /api/tasks, GET /api/tasks/{task_id}
 */

class TasksView {
    constructor(container) {
        this.container = container;
        this.filterBar = null;
        this.dataTable = null;
        this.detailDrawer = null;
        this.currentFilters = {};
        this.tasks = [];
        this.selectedTask = null;
        this.decisionTraceLoaded = false;
        this.currentDecisionTrace = [];
        this.nextTraceCursor = null;
        this.planLoaded = false;
        this.reposLoaded = false;
        this.dependenciesLoaded = false;
        this.guardianReviewsLoaded = false;

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="tasks-view">
                <div class="view-header">
                    <div>
                        <h1>Task Management</h1>
                        <p class="text-sm text-gray-600 mt-1">Manage and monitor task lifecycle and execution</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="tasks-refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                        <button class="btn-secondary" id="tasks-batch-create">
                            <span class="icon"><span class="material-icons md-18">add</span></span> Batch Create
                        </button>
                        <button class="btn-primary" id="tasks-create">
                            <span class="icon"><span class="material-icons md-18">add</span></span> Create Task
                        </button>
                    </div>
                </div>

                <div id="tasks-filter-bar" class="filter-section"></div>

                <div id="tasks-table" class="table-section"></div>

                <div id="tasks-detail-drawer" class="drawer hidden">
                    <div class="drawer-overlay" id="tasks-drawer-overlay"></div>
                    <div class="drawer-content">
                        <div class="drawer-header">
                            <h3>Task Details</h3>
                            <button class="btn-close" id="tasks-drawer-close">close</button>
                        </div>
                        <div class="drawer-body" id="tasks-drawer-body">
                            <!-- Task details will be rendered here -->
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.setupFilterBar();
        this.setupDataTable();
        this.setupEventListeners();
        this.parseURLParameters();  // Parse URL params for initial filters
        this.loadProjects();  // Load projects for filter dropdown
        this.loadTasks();
    }

    parseURLParameters() {
        // Parse URL hash parameters (e.g., #/tasks?project=abc123)
        const hash = window.location.hash;
        if (hash.includes('?')) {
            const queryString = hash.split('?')[1];
            const params = new URLSearchParams(queryString);

            // Set initial filters from URL
            if (params.has('project')) {
                this.currentFilters.project_id = params.get('project');
            }
            if (params.has('status')) {
                this.currentFilters.status = params.get('status');
            }
            if (params.has('session')) {
                this.currentFilters.session_id = params.get('session');
            }
        }
    }

    setupFilterBar() {
        const filterContainer = this.container.querySelector('#tasks-filter-bar');

        this.filterBar = new FilterBar(filterContainer, {
            filters: [
                {
                    type: 'text',
                    key: 'task_id',
                    label: 'Task ID',
                    placeholder: 'Filter by task ID...'
                },
                {
                    type: 'select',
                    key: 'status',
                    label: 'Status',
                    options: [
                        { value: '', label: 'All Status' },
                        { value: 'pending', label: 'Pending' },
                        { value: 'running', label: 'Running' },
                        { value: 'completed', label: 'Completed' },
                        { value: 'failed', label: 'Failed' },
                        { value: 'cancelled', label: 'Cancelled' }
                    ]
                },
                {
                    type: 'select',
                    key: 'project_id',
                    label: 'Project',
                    options: [
                        { value: '', label: 'All Projects' }
                    ],
                    dynamic: true  // Will be populated from API
                },
                {
                    type: 'text',
                    key: 'session_id',
                    label: 'Session ID',
                    placeholder: 'Filter by session...'
                },
                {
                    type: 'time-range',
                    key: 'time_range',
                    label: 'Time Range',
                    placeholder: 'Select time range'
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
        const tableContainer = this.container.querySelector('#tasks-table');

        this.dataTable = new DataTable(tableContainer, {
            columns: [
                {
                    key: 'task_id',
                    label: 'Task ID',
                    width: '200px',
                    render: (value) => `<code class="code-inline">${value}</code>`
                },
                {
                    key: 'project_id',
                    label: 'Project',
                    width: '160px',
                    render: (value, row) => this.renderProjectBadge(value, row)
                },
                {
                    key: 'status',
                    label: 'Status',
                    width: '120px',
                    render: (value) => this.renderStatus(value)
                },
                {
                    key: 'type',
                    label: 'Type',
                    width: '150px',
                    render: (value) => value || 'N/A'
                },
                {
                    key: 'session_id',
                    label: 'Session',
                    width: '200px',
                    render: (value) => value ? `<code class="code-inline">${value}</code>` : 'N/A'
                },
                {
                    key: 'created_at',
                    label: 'Created',
                    width: '180px',
                    render: (value) => this.formatTimestamp(value)
                },
                {
                    key: 'updated_at',
                    label: 'Updated',
                    width: '180px',
                    render: (value) => this.formatTimestamp(value)
                }
            ],
            data: [],
            emptyText: 'No tasks found',
            loadingText: 'Loading tasks...',
            onRowClick: (task) => this.showTaskDetail(task),
            pagination: true,
            pageSize: 10
        });
    }

    setupEventListeners() {
        // Refresh button
        this.container.querySelector('#tasks-refresh').addEventListener('click', () => {
            this.loadTasks(true);
        });

        // Create button
        this.container.querySelector('#tasks-create').addEventListener('click', () => {
            this.createTask();
        });

        // Batch create button
        this.container.querySelector('#tasks-batch-create').addEventListener('click', () => {
            this.showBatchCreateDialog();
        });

        // Drawer close
        this.container.querySelector('#tasks-drawer-close').addEventListener('click', () => {
            this.hideTaskDetail();
        });

        this.container.querySelector('#tasks-drawer-overlay').addEventListener('click', () => {
            this.hideTaskDetail();
        });

        // Keyboard shortcut: Escape to close drawer
        const handleKeydown = (e) => {
            if (e.key === 'Escape' && !this.container.querySelector('#tasks-detail-drawer').classList.contains('hidden')) {
                this.hideTaskDetail();
            }
        };
        document.addEventListener('keydown', handleKeydown);
    }

    handleFilterChange(filters) {
        this.currentFilters = filters;
        this.loadTasks();
    }

    setupProjectBadgeHandlers() {
        // Use event delegation for project badge clicks
        const tableContainer = this.container.querySelector('#tasks-table');
        if (!tableContainer) return;

        // Remove old listener if exists
        if (this._projectBadgeHandler) {
            tableContainer.removeEventListener('click', this._projectBadgeHandler);
        }

        // Create new handler
        this._projectBadgeHandler = (e) => {
            const badge = e.target.closest('.project-badge');
            if (!badge) return;

            e.stopPropagation(); // Prevent row click

            const projectId = badge.getAttribute('data-project-id');
            if (projectId && window.projectContext) {
                // Filter by this project
                window.projectContext.setCurrentProject(projectId);
            }
        };

        tableContainer.addEventListener('click', this._projectBadgeHandler);
    }

    async loadProjects() {
        try {
            const result = await apiClient.get('/api/projects', {
                requestId: `projects-for-filter-${Date.now()}`
            });

            if (result.ok && result.data && result.data.projects) {
                const projects = result.data.projects;

                // Update the project filter dropdown (only if filterBar is initialized)
                if (this.filterBar && this.filterBar.filters) {
                    const projectFilter = this.filterBar.filters.find(f => f.key === 'project_id');
                    if (projectFilter) {
                        projectFilter.options = [
                            { value: '', label: 'All Projects' },
                            ...projects.map(p => ({
                                value: p.project_id,
                                label: p.name
                            }))
                        ];

                        // Re-render the filter bar to show updated options
                        this.filterBar.render();
                    }
                }
            }
        } catch (error) {
            console.error('Failed to load projects for filter:', error);
        }
    }

    async loadTasks(forceRefresh = false) {
        this.dataTable.setLoading(true);

        try {
            // Build query parameters
            const params = new URLSearchParams();

            if (this.currentFilters.task_id) {
                params.append('task_id', this.currentFilters.task_id);
            }
            if (this.currentFilters.status) {
                params.append('status', this.currentFilters.status);
            }
            if (this.currentFilters.project_id) {
                params.append('project_id', this.currentFilters.project_id);
            }
            if (this.currentFilters.session_id) {
                params.append('session_id', this.currentFilters.session_id);
            }
            if (this.currentFilters.time_range) {
                const { start, end } = this.currentFilters.time_range;
                if (start) params.append('start_time', start);
                if (end) params.append('end_time', end);
            }

            const url = `/api/tasks${params.toString() ? '?' + params.toString() : ''}`;
            const result = await apiClient.get(url, {
                requestId: `tasks-list-${Date.now()}`
            });

            if (result.ok) {
                this.tasks = result.data.tasks || result.data || [];
                this.dataTable.setData(this.tasks);

                // Setup project badge click handlers
                this.setupProjectBadgeHandlers();

                if (forceRefresh) {
                    showToast('Tasks refreshed', 'success', 2000);
                }
            } else {
                showToast(`Failed to load tasks: ${result.message}`, 'error');
                this.dataTable.setData([]);
            }
        } catch (error) {
            console.error('Failed to load tasks:', error);
            showToast('Failed to load tasks', 'error');
            this.dataTable.setData([]);
        } finally {
            this.dataTable.setLoading(false);
        }
    }

    async showTaskDetail(task) {
        this.selectedTask = task;
        const drawer = this.container.querySelector('#tasks-detail-drawer');
        const drawerBody = this.container.querySelector('#tasks-drawer-body');

        // Show drawer with loading state
        drawer.classList.remove('hidden');
        drawerBody.innerHTML = '<div class="loading-spinner">Loading task details...</div>';

        try {
            // Fetch full task details
            const result = await apiClient.get(`/api/tasks/${task.task_id}`, {
                requestId: `task-detail-${task.task_id}`
            });

            if (result.ok) {
                const taskDetail = result.data;
                this.renderTaskDetail(taskDetail);
            } else {
                drawerBody.innerHTML = `
                    <div class="error-message">
                        <div class="error-icon"><span class="material-icons md-18">warning</span></div>
                        <div class="error-text">Failed to load task details: ${result.message}</div>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Failed to load task detail:', error);
            drawerBody.innerHTML = `
                <div class="error-message">
                    <div class="error-icon"><span class="material-icons md-18">warning</span></div>
                    <div class="error-text">Failed to load task details</div>
                </div>
            `;
        }
    }

    renderTaskDetail(task) {
        const drawerBody = this.container.querySelector('#tasks-drawer-body');

        // Create Explain button for this task
        const explainBtn = new ExplainButton('task', task.task_id, task.title || task.task_id);

        drawerBody.innerHTML = `
            <div class="task-detail">
                <!-- Task Header with Explain Button -->
                <div class="task-detail-header">
                    <div class="task-title-section">
                        <h3>${this.escapeHtml(task.title || task.task_id)}</h3>
                        ${explainBtn.render()}
                    </div>
                </div>

                <!-- Tab Navigation -->
                <div class="task-detail-tabs">
                    <button class="tab-btn active" data-tab="overview">Overview</button>
                    <button class="tab-btn" data-tab="plan">Execution Plan</button>
                    <button class="tab-btn" data-tab="repos">Repos & Changes</button>
                    <button class="tab-btn" data-tab="dependencies">Dependencies</button>
                    <button class="tab-btn" data-tab="decision-trace">Decision Trace</button>
                    <button class="tab-btn" data-tab="guardian-reviews">Guardian Reviews</button>
                    <button class="tab-btn" data-tab="audit">Audit</button>
                    <button class="tab-btn" data-tab="history">History</button>
                </div>

                <!-- Tab Content -->
                <div class="task-detail-tab-content">
                    <!-- Overview Tab -->
                    <div class="tab-pane active" data-tab-pane="overview">
                        <div class="detail-section">
                            <h4>Basic Information</h4>
                            <div class="detail-grid">
                                <div class="detail-item">
                                    <label>Task ID</label>
                                    <div class="detail-value">
                                        <code>${task.task_id}</code>
                                        <button class="btn-copy" data-copy="${task.task_id}" title="Copy Task ID">
                                            <span class="material-icons md-18">content_copy</span>
                                        </button>
                                    </div>
                                </div>
                                <div class="detail-item">
                                    <label>Status</label>
                                    <div class="detail-value">${this.renderStatus(task.status)}</div>
                                </div>
                                <div class="detail-item">
                                    <label>Type</label>
                                    <div class="detail-value">${task.type || 'N/A'}</div>
                                </div>
                                <div class="detail-item">
                                    <label>Session ID</label>
                                    <div class="detail-value">
                                        ${task.session_id ? `
                                            <code>${task.session_id}</code>
                                            <button class="btn-link" data-session="${task.session_id}">View Session</button>
                                        ` : 'N/A'}
                                    </div>
                                </div>
                                <div class="detail-item">
                                    <label>Created</label>
                                    <div class="detail-value">${this.formatTimestamp(task.created_at)}</div>
                                </div>
                                <div class="detail-item">
                                    <label>Updated</label>
                                    <div class="detail-value">${this.formatTimestamp(task.updated_at)}</div>
                                </div>
                            </div>
                        </div>

                        <!-- Project & Spec Information (v0.4) -->
                        ${task.project_id || task.spec_version ? `
                            <div class="detail-section">
                                <h4>Project & Specification</h4>
                                <div class="project-info-box">
                                    ${task.project_id ? `
                                        <div class="project-info-item">
                                            <label>Project:</label>
                                            <div class="value">
                                                <a href="#/projects" class="project-link" data-project-id="${task.project_id}">
                                                    ${task.project_name || task.project_id}
                                                </a>
                                            </div>
                                        </div>
                                    ` : ''}
                                    ${task.repo_id ? `
                                        <div class="project-info-item">
                                            <label>Repository:</label>
                                            <div class="value">${task.repo_name || task.repo_id}</div>
                                        </div>
                                    ` : ''}
                                    ${task.workdir ? `
                                        <div class="project-info-item">
                                            <label>Working Directory:</label>
                                            <div class="value"><code>${task.workdir}</code></div>
                                        </div>
                                    ` : ''}
                                    ${task.spec_version !== undefined ? `
                                        <div class="project-info-item">
                                            <label>Spec Version:</label>
                                            <div class="value">
                                                v${task.spec_version}
                                                ${task.spec_frozen_at ? `
                                                    <span class="spec-status-badge frozen">
                                                        <span class="material-icons md-18">lock</span>
                                                        Frozen
                                                    </span>
                                                ` : `
                                                    <span class="spec-status-badge draft">
                                                        <span class="material-icons md-18">edit</span>
                                                        Draft
                                                    </span>
                                                `}
                                            </div>
                                        </div>
                                    ` : ''}
                                    ${task.spec_frozen_at ? `
                                        <div class="project-info-item">
                                            <label>Spec Frozen At:</label>
                                            <div class="value">${this.formatTimestamp(task.spec_frozen_at)}</div>
                                        </div>
                                    ` : ''}
                                </div>

                                <!-- Spec Actions -->
                                ${!task.spec_frozen_at && task.status === 'draft' ? `
                                    <div class="spec-actions">
                                        <button class="btn-freeze-spec" id="btn-freeze-spec" data-task-id="${task.task_id}">
                                            <span class="material-icons md-18">lock</span>
                                            Freeze Specification
                                        </button>
                                    </div>
                                ` : ''}
                                ${task.spec_frozen_at && task.status === 'planned' ? `
                                    <div class="spec-actions">
                                        <button class="btn-mark-ready" id="btn-mark-ready" data-task-id="${task.task_id}">
                                            <span class="material-icons md-18">play_arrow</span>
                                            Mark as Ready
                                        </button>
                                    </div>
                                ` : ''}
                            </div>
                        ` : ''}

                        <!-- Acceptance Criteria (v0.4) -->
                        ${task.acceptance_criteria && task.acceptance_criteria.length > 0 ? `
                            <div class="detail-section">
                                <h4>Acceptance Criteria</h4>
                                <ol class="criteria-summary">
                                    ${task.acceptance_criteria.map(criterion => `
                                        <li>${this.escapeHtml(criterion)}</li>
                                    `).join('')}
                                </ol>
                            </div>
                        ` : ''}

                        ${task.description ? `
                            <div class="detail-section">
                                <h4>Description</h4>
                                <div class="detail-description">${task.description}</div>
                            </div>
                        ` : ''}

                        ${this.renderRouteTimeline(task)}

                        ${task.error ? `
                            <div class="detail-section">
                                <h4>Error</h4>
                                <div class="error-box">${task.error}</div>
                            </div>
                        ` : ''}

                        <div class="detail-section">
                            <h4>Full Task Data</h4>
                            <div id="task-json-viewer"></div>
                        </div>

                        <div class="detail-actions">
                            <button class="btn-secondary" id="task-view-events">View Related Events</button>
                            <button class="btn-secondary" id="task-view-logs">View Related Logs</button>
                            ${task.status === 'running' ? `
                                <button class="btn-danger" id="task-cancel">Cancel Task</button>
                            ` : ''}
                        </div>

                        <!-- Wave4-X1: Integration Links to New Views -->
                        <div class="detail-section">
                            <h4>Execution & Governance</h4>
                            <div class="execution-links">
                                <button class="btn-link" id="task-view-plan">
                                    <span class="material-icons md-18">content_copy</span> View Execution Plan
                                </button>
                                <button class="btn-link" id="task-view-intent">
                                    <span class="material-icons md-18">edit</span> View Intent Workbench
                                </button>
                                <button class="btn-link" id="task-view-content">
                                    <span class="material-icons md-18">archive</span> View Content Assets
                                </button>
                                <button class="btn-link" id="task-view-answers">
                                    <span class="material-icons md-18">add_comment</span> View Answer Packs
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- Execution Plan Tab -->
                    <div class="tab-pane" data-tab-pane="plan">
                        <div id="task-plan-content" class="plan-loading">
                            <div class="loading-spinner">Loading execution plan...</div>
                        </div>
                    </div>

                    <!-- Repos & Changes Tab -->
                    <div class="tab-pane" data-tab-pane="repos">
                        <div id="task-repos-content" class="repos-loading">
                            <div class="loading-spinner">Loading repository information...</div>
                        </div>
                    </div>

                    <!-- Dependencies Tab -->
                    <div class="tab-pane" data-tab-pane="dependencies">
                        <div id="task-dependencies-content" class="dependencies-loading">
                            <div class="loading-spinner">Loading dependencies...</div>
                        </div>
                    </div>

                    <!-- Decision Trace Tab -->
                    <div class="tab-pane" data-tab-pane="decision-trace">
                        <div class="decision-trace-container">
                            <div class="trace-header">
                                <h4>Decision Trace Timeline</h4>
                                <div class="trace-filters">
                                    <input type="text" class="trace-search" placeholder="Search in trace..." id="trace-search">
                                    <select class="trace-filter" id="trace-filter-type">
                                        <option value="">All Decisions</option>
                                        <option value="ALLOWED">ALLOWED</option>
                                        <option value="BLOCKED">BLOCKED</option>
                                        <option value="PAUSED">PAUSED</option>
                                        <option value="RETRY">RETRY</option>
                                    </select>
                                </div>
                            </div>
                            <div id="decision-trace-content" class="trace-loading">
                                <div class="loading-spinner">Loading decision trace...</div>
                            </div>
                        </div>
                    </div>

                    <!-- Guardian Reviews Tab -->
                    <div class="tab-pane" data-tab-pane="guardian-reviews">
                        <div id="guardian-reviews-container" class="guardian-loading">
                            <div class="loading-spinner"></div>
                            <span>Loading Guardian reviews...</span>
                        </div>
                    </div>

                    <!-- Audit Tab (Placeholder) -->
                    <div class="tab-pane" data-tab-pane="audit">
                        <div class="detail-section">
                            <h4>Audit Log</h4>
                            <p class="text-muted">Audit log view coming soon...</p>
                        </div>
                    </div>

                    <!-- History Tab (Placeholder) -->
                    <div class="tab-pane" data-tab-pane="history">
                        <div class="detail-section">
                            <h4>Task History</h4>
                            <p class="text-muted">Task history view coming soon...</p>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Render JSON viewer
        const jsonContainer = drawerBody.querySelector('#task-json-viewer');
        new JsonViewer(jsonContainer, task, {
            collapsed: true,
            maxDepth: 2,
            showToolbar: true,
            fileName: `task-${task.task_id}.json`
        });

        // Setup tab switching
        this.setupTabSwitching(task);

        // Setup action buttons
        this.setupTaskDetailActions(task);

        // Attach ExplainButton handlers
        if (typeof ExplainButton !== 'undefined') {
            ExplainButton.attachHandlers();
        }
    }

    renderRouteTimeline(task) {
        // PR-4: Extract routing information from task data
        const routePlan = task.route_plan_json ? JSON.parse(task.route_plan_json) : task.route_plan;
        const requirements = task.requirements_json ? JSON.parse(task.requirements_json) : task.requirements;
        const selectedInstance = task.selected_instance_id || routePlan?.selected;

        // Check if there's any routing info
        if (!routePlan && !selectedInstance && !requirements) {
            return '';
        }

        // Build route timeline from events (if available)
        const routeEvents = (task.events || []).filter(e =>
            e.event_type === 'TASK_ROUTED' ||
            e.event_type === 'TASK_ROUTE_VERIFIED' ||
            e.event_type === 'TASK_REROUTED' ||
            e.event_type === 'TASK_ROUTE_OVERRIDDEN'
        );

        return `
            <div class="detail-section route-section">
                <h4>Routing Information</h4>

                ${selectedInstance ? `
                    <div class="route-selected">
                        <div class="route-label">Selected Instance</div>
                        <div class="route-instance">${selectedInstance}</div>
                    </div>
                ` : ''}

                ${requirements ? `
                    <div class="route-requirements">
                        <div class="route-label">Requirements</div>
                        <div class="requirements-list">
                            ${requirements.needs ? requirements.needs.map(n => `<span class="requirement-badge">${n}</span>`).join(' ') : ''}
                            ${requirements.min_ctx ? `<span class="requirement-badge">min_ctx: ${requirements.min_ctx}</span>` : ''}
                        </div>
                    </div>
                ` : ''}

                ${routePlan ? this.renderRoutePlan(routePlan) : ''}

                ${routeEvents.length > 0 ? this.renderRouteEventsTimeline(routeEvents) : ''}
            </div>
        `;
    }

    renderRoutePlan(routePlan) {
        const scores = routePlan.scores || {};
        const reasons = routePlan.reasons || [];
        const fallback = routePlan.fallback || [];

        return `
            <div class="route-plan">
                ${reasons.length > 0 ? `
                    <div class="route-reasons">
                        <div class="route-label">Routing Reasons</div>
                        <ul class="reasons-list">
                            ${reasons.map(r => `<li>${r}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}

                ${Object.keys(scores).length > 0 ? `
                    <div class="route-scores">
                        <div class="route-label">Instance Scores</div>
                        <div class="scores-chart">
                            ${Object.entries(scores).map(([instance, score]) => `
                                <div class="score-item">
                                    <div class="score-bar-container">
                                        <div class="score-bar" style="width: ${score * 100}%"></div>
                                    </div>
                                    <div class="score-label">
                                        <span class="score-instance">${instance}</span>
                                        <span class="score-value">${(score * 100).toFixed(1)}%</span>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}

                ${fallback.length > 0 ? `
                    <div class="route-fallback">
                        <div class="route-label">Fallback Chain</div>
                        <div class="fallback-chain">
                            ${fallback.map((inst, idx) => `
                                <span class="fallback-instance">
                                    ${idx + 1}. ${inst}
                                </span>
                            `).join(' <span class="material-icons md-18">arrow_forward</span> ')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
    }

    renderRouteEventsTimeline(events) {
        return `
            <div class="route-timeline">
                <div class="route-label">Route Timeline</div>
                <div class="timeline-container">
                    ${events.map(event => this.renderRouteEvent(event)).join('')}
                </div>
            </div>
        `;
    }

    renderRouteEvent(event) {
        const eventIcons = {
            'TASK_ROUTED': '<span class="material-icons md-18">refresh</span>',
            'TASK_ROUTE_VERIFIED': '<span class="material-icons md-18">done</span>',
            'TASK_REROUTED': '<span class="material-icons md-18">refresh</span>',
            'TASK_ROUTE_OVERRIDDEN': '<span class="material-icons md-18">edit</span>'
        };

        const eventLabels = {
            'TASK_ROUTED': 'Initial Route',
            'TASK_ROUTE_VERIFIED': 'Route Verified',
            'TASK_REROUTED': 'Rerouted',
            'TASK_ROUTE_OVERRIDDEN': 'Manual Override'
        };

        const icon = eventIcons[event.event_type] || 'push_pin';
        const label = eventLabels[event.event_type] || event.event_type;

        // Extract routing info from event data
        const eventData = event.data || {};
        const instance = eventData.selected || eventData.instance || 'unknown';
        const reason = eventData.reason || eventData.reason_code || '';
        const score = eventData.score;

        return `
            <div class="timeline-event">
                <div class="event-icon">${icon}</div>
                <div class="event-content">
                    <div class="event-header">
                        <span class="event-type">${label}</span>
                        <span class="event-time">${this.formatTimestamp(event.timestamp || event.created_at)}</span>
                    </div>
                    <div class="event-details">
                        <div class="event-instance">Instance: <code>${instance}</code></div>
                        ${reason ? `<div class="event-reason">Reason: ${reason}</div>` : ''}
                        ${score !== undefined ? `<div class="event-score">Score: ${(score * 100).toFixed(1)}%</div>` : ''}
                    </div>
                </div>
            </div>
        `;
    }

    setupTabSwitching(task) {
        const drawerBody = this.container.querySelector('#tasks-drawer-body');
        const tabBtns = drawerBody.querySelectorAll('.tab-btn');
        const tabPanes = drawerBody.querySelectorAll('.tab-pane');

        tabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const tabName = btn.getAttribute('data-tab');

                // Update active tab button
                tabBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                // Update active tab pane
                tabPanes.forEach(pane => {
                    if (pane.getAttribute('data-tab-pane') === tabName) {
                        pane.classList.add('active');
                    } else {
                        pane.classList.remove('active');
                    }
                });

                // Load execution plan when tab is activated
                if (tabName === 'plan' && !this.planLoaded) {
                    this.loadTaskPlan(task.task_id);
                    this.planLoaded = true;
                }

                // Load decision trace when tab is activated
                if (tabName === 'decision-trace' && !this.decisionTraceLoaded) {
                    this.loadDecisionTrace(task.task_id);
                    this.decisionTraceLoaded = true;
                }

                // Load repos when tab is activated
                if (tabName === 'repos' && !this.reposLoaded) {
                    this.loadTaskRepos(task.task_id);
                    this.reposLoaded = true;
                }

                // Load dependencies when tab is activated
                if (tabName === 'dependencies' && !this.dependenciesLoaded) {
                    this.loadTaskDependencies(task.task_id);
                    this.dependenciesLoaded = true;
                }

                // Load Guardian reviews when tab is activated
                if (tabName === 'guardian-reviews' && !this.guardianReviewsLoaded) {
                    this.loadGuardianReviews(task.task_id);
                    this.guardianReviewsLoaded = true;
                }
            });
        });

        // Setup decision trace filters
        const searchInput = drawerBody.querySelector('#trace-search');
        const filterSelect = drawerBody.querySelector('#trace-filter-type');

        if (searchInput) {
            searchInput.addEventListener('input', () => {
                this.filterDecisionTrace();
            });
        }

        if (filterSelect) {
            filterSelect.addEventListener('change', () => {
                this.filterDecisionTrace();
            });
        }
    }

    async loadDecisionTrace(taskId, cursor = null) {
        const traceContent = this.container.querySelector('#decision-trace-content');

        try {
            // Build URL with parameters
            const params = new URLSearchParams();
            params.append('limit', '50');
            if (cursor) {
                params.append('cursor', cursor);
            }

            const url = `/api/governance/tasks/${taskId}/decision-trace?${params.toString()}`;
            const result = await apiClient.get(url, {
                requestId: `decision-trace-${taskId}-${Date.now()}`
            });

            if (result.ok) {
                this.currentDecisionTrace = result.data.trace_items || [];
                this.nextTraceCursor = result.data.next_cursor;
                this.renderDecisionTrace(this.currentDecisionTrace, cursor === null);
            } else {
                traceContent.innerHTML = `
                    <div class="error-message">
                        <div class="error-icon"><span class="material-icons md-18">warning</span></div>
                        <div class="error-text">Failed to load decision trace: ${result.message}</div>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Failed to load decision trace:', error);
            traceContent.innerHTML = `
                <div class="error-message">
                    <div class="error-icon"><span class="material-icons md-18">warning</span></div>
                    <div class="error-text">Failed to load decision trace</div>
                </div>
            `;
        }
    }

    renderDecisionTrace(traceItems, isInitial = true) {
        const traceContent = this.container.querySelector('#decision-trace-content');

        if (traceItems.length === 0) {
            traceContent.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon"><span class="material-icons md-36">analytics</span></div>
                    <div class="empty-text">No decision trace available</div>
                </div>
            `;
            return;
        }

        const timelineHtml = `
            <div class="decision-trace-timeline" id="decision-trace-timeline">
                ${traceItems.map(item => this.renderTraceItem(item)).join('')}
            </div>
            ${this.nextTraceCursor ? `
                <div class="trace-load-more">
                    <button class="btn-secondary" id="trace-load-more">Load More</button>
                </div>
            ` : ''}
        `;

        if (isInitial) {
            traceContent.innerHTML = timelineHtml;
        } else {
            // Append to existing timeline
            const timeline = traceContent.querySelector('#decision-trace-timeline');
            const loadMoreBtn = traceContent.querySelector('.trace-load-more');
            if (loadMoreBtn) loadMoreBtn.remove();

            timeline.insertAdjacentHTML('beforeend', traceItems.map(item => this.renderTraceItem(item)).join(''));

            if (this.nextTraceCursor) {
                timeline.insertAdjacentHTML('afterend', `
                    <div class="trace-load-more">
                        <button class="btn-secondary" id="trace-load-more">Load More</button>
                    </div>
                `);
            }
        }

        // Setup load more button
        const loadMoreBtn = traceContent.querySelector('#trace-load-more');
        if (loadMoreBtn) {
            loadMoreBtn.addEventListener('click', () => {
                this.loadDecisionTrace(this.selectedTask.task_id, this.nextTraceCursor);
            });
        }

        // Setup toggle buttons
        traceContent.querySelectorAll('.trace-toggle-json').forEach(btn => {
            btn.addEventListener('click', () => {
                const itemId = btn.getAttribute('data-item-id');
                const jsonContainer = traceContent.querySelector(`#trace-json-${itemId}`);
                if (jsonContainer) {
                    jsonContainer.classList.toggle('hidden');
                    btn.textContent = jsonContainer.classList.contains('hidden') ? 'Show JSON' : 'Hide JSON';
                }
            });
        });
    }

    renderTraceItem(item) {
        const timestamp = this.formatTimestamp(item.ts);
        const itemId = `${item.kind}-${item.audit_id || item.event_id || Math.random()}`;

        if (item.kind === 'audit') {
            return this.renderAuditTraceItem(item, timestamp, itemId);
        } else if (item.kind === 'event') {
            return this.renderEventTraceItem(item, timestamp, itemId);
        } else {
            return this.renderGenericTraceItem(item, timestamp, itemId);
        }
    }

    renderAuditTraceItem(item, timestamp, itemId) {
        const decisionSnapshot = item.decision_snapshot || {};
        const decisionType = this.extractDecisionType(item.event_type, decisionSnapshot);
        const decisionBadge = this.renderDecisionBadge(decisionType);
        const details = this.extractDecisionDetails(decisionSnapshot);

        return `
            <div class="trace-item" data-decision-type="${decisionType}">
                <div class="trace-timestamp">${timestamp}</div>
                <div class="trace-line"></div>
                <div class="trace-content">
                    <div class="trace-event">
                        <span class="event-type-badge event-audit">SUPERVISOR AUDIT</span>
                        <span class="event-source">${item.event_type}</span>
                    </div>
                    <div class="trace-decision">
                        ${decisionBadge}
                        ${details.reason ? `<div class="decision-reason">${details.reason}</div>` : ''}
                    </div>
                    ${details.rules.length > 0 ? `
                        <div class="trace-rules">
                            <div class="rules-label">Rules Applied:</div>
                            <div class="rules-list">
                                ${details.rules.map(rule => `<span class="rule-badge">${rule}</span>`).join('')}
                            </div>
                        </div>
                    ` : ''}
                    ${details.riskScore !== null ? `
                        <div class="trace-risk">
                            <span class="risk-label">Risk Score:</span>
                            <span class="risk-value ${this.getRiskClass(details.riskScore)}">${details.riskScore}/100</span>
                        </div>
                    ` : ''}
                    ${decisionSnapshot && Object.keys(decisionSnapshot).length > 0 ? `
                        <div class="trace-json-toggle">
                            <button class="btn-link trace-toggle-json" data-item-id="${itemId}">Show JSON</button>
                        </div>
                        <div class="trace-json hidden" id="trace-json-${itemId}">
                            <pre>${JSON.stringify(decisionSnapshot, null, 2)}</pre>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    renderEventTraceItem(item, timestamp, itemId) {
        const payload = item.payload || {};
        const eventSource = payload.source || 'unknown';

        return `
            <div class="trace-item" data-decision-type="">
                <div class="trace-timestamp">${timestamp}</div>
                <div class="trace-line"></div>
                <div class="trace-content">
                    <div class="trace-event">
                        <span class="event-type-badge event-task">TASK EVENT</span>
                        <span class="event-source">${item.event_type}</span>
                    </div>
                    ${eventSource !== 'unknown' ? `
                        <div class="event-metadata">
                            <span class="metadata-label">Source:</span>
                            <span class="metadata-value">${eventSource}</span>
                        </div>
                    ` : ''}
                    ${payload && Object.keys(payload).length > 0 ? `
                        <div class="trace-json-toggle">
                            <button class="btn-link trace-toggle-json" data-item-id="${itemId}">Show JSON</button>
                        </div>
                        <div class="trace-json hidden" id="trace-json-${itemId}">
                            <pre>${JSON.stringify(payload, null, 2)}</pre>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    renderGenericTraceItem(item, timestamp, itemId) {
        return `
            <div class="trace-item" data-decision-type="">
                <div class="trace-timestamp">${timestamp}</div>
                <div class="trace-line"></div>
                <div class="trace-content">
                    <div class="trace-event">
                        <span class="event-type-badge">${item.kind.toUpperCase()}</span>
                    </div>
                    <div class="trace-json-toggle">
                        <button class="btn-link trace-toggle-json" data-item-id="${itemId}">Show JSON</button>
                    </div>
                    <div class="trace-json hidden" id="trace-json-${itemId}">
                        <pre>${JSON.stringify(item.data, null, 2)}</pre>
                    </div>
                </div>
            </div>
        `;
    }

    extractDecisionType(eventType, decisionSnapshot) {
        // Try to extract from event_type first
        if (eventType.includes('ALLOWED')) return 'ALLOWED';
        if (eventType.includes('BLOCKED')) return 'BLOCKED';
        if (eventType.includes('PAUSED')) return 'PAUSED';
        if (eventType.includes('RETRY')) return 'RETRY';

        // Try from decision_snapshot
        if (decisionSnapshot.decision_type) {
            return decisionSnapshot.decision_type.toUpperCase();
        }

        return 'UNKNOWN';
    }

    extractDecisionDetails(decisionSnapshot) {
        const details = {
            reason: null,
            rules: [],
            riskScore: null,
        };

        if (!decisionSnapshot) return details;

        // Extract reason
        if (decisionSnapshot.blocked_reason_code) {
            details.reason = `Blocked: ${decisionSnapshot.blocked_reason_code}`;
        } else if (decisionSnapshot.reason) {
            details.reason = decisionSnapshot.reason;
        } else if (decisionSnapshot.metadata && decisionSnapshot.metadata.reason) {
            details.reason = decisionSnapshot.metadata.reason;
        }

        // Extract rules
        if (decisionSnapshot.rules_applied) {
            details.rules = Array.isArray(decisionSnapshot.rules_applied)
                ? decisionSnapshot.rules_applied
                : [decisionSnapshot.rules_applied];
        } else if (decisionSnapshot.policies_evaluated) {
            details.rules = Array.isArray(decisionSnapshot.policies_evaluated)
                ? decisionSnapshot.policies_evaluated
                : [decisionSnapshot.policies_evaluated];
        }

        // Extract risk score
        if (decisionSnapshot.metadata && typeof decisionSnapshot.metadata.risk_score === 'number') {
            details.riskScore = decisionSnapshot.metadata.risk_score;
        } else if (typeof decisionSnapshot.risk_score === 'number') {
            details.riskScore = decisionSnapshot.risk_score;
        }

        return details;
    }

    renderDecisionBadge(decisionType) {
        const badges = {
            'ALLOWED': '<span class="decision-badge decision-allowed"><span class="material-icons md-18">check_circle</span> ALLOWED</span>',
            'BLOCKED': '<span class="decision-badge decision-blocked"><span class="material-icons md-18">block</span> BLOCKED</span>',
            'PAUSED': '<span class="decision-badge decision-paused"><span class="material-icons md-18">pause_circle</span> PAUSED</span>',
            'RETRY': '<span class="decision-badge decision-retry"><span class="material-icons md-18">refresh</span> RETRY</span>',
            'UNKNOWN': '<span class="decision-badge decision-unknown"><span class="material-icons md-18">help</span> UNKNOWN</span>',
        };

        return badges[decisionType] || badges['UNKNOWN'];
    }

    getRiskClass(score) {
        if (score >= 80) return 'risk-high';
        if (score >= 50) return 'risk-medium';
        return 'risk-low';
    }

    filterDecisionTrace() {
        const drawerBody = this.container.querySelector('#tasks-drawer-body');
        const searchInput = drawerBody.querySelector('#trace-search');
        const filterSelect = drawerBody.querySelector('#trace-filter-type');
        const traceItems = drawerBody.querySelectorAll('.trace-item');

        if (!searchInput || !filterSelect) return;

        const searchTerm = searchInput.value.toLowerCase();
        const filterType = filterSelect.value;

        traceItems.forEach(item => {
            const text = item.textContent.toLowerCase();
            const decisionType = item.getAttribute('data-decision-type');

            const matchesSearch = !searchTerm || text.includes(searchTerm);
            const matchesFilter = !filterType || decisionType === filterType;

            if (matchesSearch && matchesFilter) {
                item.style.display = '';
            } else {
                item.style.display = 'none';
            }
        });
    }

    setupTaskDetailActions(task) {
        const drawerBody = this.container.querySelector('#tasks-drawer-body');

        // Copy buttons
        drawerBody.querySelectorAll('.btn-copy').forEach(btn => {
            btn.addEventListener('click', () => {
                const text = btn.getAttribute('data-copy');
                navigator.clipboard.writeText(text);
                showToast('Copied to clipboard', 'success', 1500);
            });
        });

        // View session button
        const sessionBtn = drawerBody.querySelector('.btn-link[data-session]');
        if (sessionBtn) {
            sessionBtn.addEventListener('click', () => {
                const sessionId = sessionBtn.getAttribute('data-session');
                window.navigateToView('chat', { session_id: sessionId });
                this.hideTaskDetail();
            });
        }

        // View events button
        const eventsBtn = drawerBody.querySelector('#task-view-events');
        if (eventsBtn) {
            eventsBtn.addEventListener('click', () => {
                window.navigateToView('events', { task_id: task.task_id });
                this.hideTaskDetail();
            });
        }

        // View logs button
        const logsBtn = drawerBody.querySelector('#task-view-logs');
        if (logsBtn) {
            logsBtn.addEventListener('click', () => {
                window.navigateToView('logs', { task_id: task.task_id });
                this.hideTaskDetail();
            });
        }

        // Cancel button
        const cancelBtn = drawerBody.querySelector('#task-cancel');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', async () => {
                const confirmed = await Dialog.confirm(`Are you sure you want to cancel task ${task.task_id}?`, {
                    title: 'Cancel Task',
                    confirmText: 'Cancel Task',
                    danger: true
                });
                if (confirmed) {
                    await this.cancelTask(task.task_id);
                }
            });
        }

        // Wave4-X1: Navigation to new execution views
        const planBtn = drawerBody.querySelector('#task-view-plan');
        if (planBtn) {
            planBtn.addEventListener('click', () => {
                // Switch to plan tab instead of navigating away
                const tabBtn = drawerBody.querySelector('.tab-btn[data-tab="plan"]');
                if (tabBtn) {
                    tabBtn.click();
                }
            });
        }

        const intentBtn = drawerBody.querySelector('#task-view-intent');
        if (intentBtn) {
            intentBtn.addEventListener('click', () => {
                this.hideTaskDetail();
                loadView('intent-workbench');
                // TODO: Pass task's intent_id context when IntentWorkbenchView is implemented
            });
        }

        const contentBtn = drawerBody.querySelector('#task-view-content');
        if (contentBtn) {
            contentBtn.addEventListener('click', () => {
                this.hideTaskDetail();
                loadView('content-registry');
                // TODO: Filter by task's content assets when ContentRegistryView is implemented
            });
        }

        const answersBtn = drawerBody.querySelector('#task-view-answers');
        if (answersBtn) {
            answersBtn.addEventListener('click', () => {
                this.hideTaskDetail();
                loadView('answer-packs');
                // TODO: Filter by task's answer packs when AnswerPacksView is implemented
            });
        }

        // v0.4: Freeze spec button
        const freezeSpecBtn = drawerBody.querySelector('#btn-freeze-spec');
        if (freezeSpecBtn) {
            freezeSpecBtn.addEventListener('click', async () => {
                const taskId = freezeSpecBtn.getAttribute('data-task-id');
                await this.freezeTaskSpec(taskId);
            });
        }

        // v0.4: Mark ready button
        const markReadyBtn = drawerBody.querySelector('#btn-mark-ready');
        if (markReadyBtn) {
            markReadyBtn.addEventListener('click', async () => {
                const taskId = markReadyBtn.getAttribute('data-task-id');
                await this.markTaskReady(taskId);
            });
        }

        // v0.4: Project link
        const projectLink = drawerBody.querySelector('.project-link');
        if (projectLink) {
            projectLink.addEventListener('click', (e) => {
                e.preventDefault();
                const projectId = projectLink.getAttribute('data-project-id');
                window.navigateToView('projects');
                this.hideTaskDetail();
                // TODO: Open project detail when ProjectsView supports direct navigation
            });
        }
    }

    hideTaskDetail() {
        const drawer = this.container.querySelector('#tasks-detail-drawer');
        drawer.classList.add('hidden');
        this.selectedTask = null;
        this.decisionTraceLoaded = false;
        this.currentDecisionTrace = [];
        this.nextTraceCursor = null;
        this.planLoaded = false;
        this.reposLoaded = false;
        this.dependenciesLoaded = false;
        this.guardianReviewsLoaded = false;
    }

    async createTask() {
        // Create backdrop for wizard modal
        const backdrop = document.createElement('div');
        backdrop.className = 'modal-wizard-overlay';

        // Create dialog container for wizard
        const wizardContainer = document.createElement('div');
        wizardContainer.className = 'modal-wizard-content';

        // Append to body
        backdrop.appendChild(wizardContainer);
        document.body.appendChild(backdrop);

        // Trigger animation
        requestAnimationFrame(() => {
            backdrop.style.display = 'flex';
        });

        // Get default project from current filter
        const defaultProjectId = this.currentFilters.project_id || null;

        // Initialize wizard
        const wizard = new CreateTaskWizard(wizardContainer, {
            defaultProjectId: defaultProjectId,
            onComplete: (taskId) => {
                showToast('Task created and spec frozen successfully', 'success');
                backdrop.remove();
                this.loadTasks(true);

                // Optionally open the task detail
                if (taskId) {
                    setTimeout(() => {
                        this.showTaskDetail(taskId);
                    }, 500);
                }
            },
            onCancel: () => {
                backdrop.remove();
            }
        });

        // Close on backdrop click
        backdrop.addEventListener('click', (e) => {
            if (e.target === backdrop) {
                wizard.cancel();
            }
        });

        // Close on Escape key
        const handleKeyDown = (e) => {
            if (e.key === 'Escape') {
                wizard.cancel();
                document.removeEventListener('keydown', handleKeyDown);
            }
        };
        document.addEventListener('keydown', handleKeyDown);
    }

    renderCreateTaskForm() {
        return `
            <form id="create-task-form" class="create-task-form">
                <div class="form-group">
                    <label for="task-title" class="required">Title</label>
                    <input
                        type="text"
                        id="task-title"
                        class="form-control"
                        placeholder="Enter task title"
                        maxlength="500"
                        required
                    />
                    <span class="form-error" id="task-title-error"></span>
                </div>

                <div class="form-group">
                    <label for="task-created-by">Created By</label>
                    <input
                        type="text"
                        id="task-created-by"
                        class="form-control"
                        placeholder="Your identifier"
                    />
                    <small class="form-hint">Optional: Your name or identifier</small>
                    <span class="form-error" id="task-created-by-error"></span>
                </div>

                <div class="form-group">
                    <label for="task-metadata">Metadata</label>
                    <textarea
                        id="task-metadata"
                        class="form-control"
                        placeholder='{"key": "value"}'
                        rows="4"
                    ></textarea>
                    <small class="form-hint">Optional: JSON format metadata</small>
                    <span class="form-error" id="task-metadata-error"></span>
                </div>
            </form>
        `;
    }

    async handleCreateTaskSubmit(backdrop, closeDialog) {
        // Step A: Clear previous errors
        const form = document.getElementById('create-task-form');
        form.querySelectorAll('.form-error').forEach(el => el.textContent = '');
        form.querySelectorAll('.form-control').forEach(el => el.classList.remove('error'));

        // Step B: Get and validate form data
        const title = document.getElementById('task-title').value.trim();
        const createdBy = document.getElementById('task-created-by').value.trim();
        const metadataStr = document.getElementById('task-metadata').value.trim();

        // Validate title
        if (!title) {
            this.showFieldError('task-title', 'task-title-error', 'Title is required');
            return;
        }

        // Validate metadata JSON if provided
        let metadata = null;
        if (metadataStr) {
            try {
                metadata = JSON.parse(metadataStr);
            } catch (e) {
                this.showFieldError('task-metadata', 'task-metadata-error', 'Invalid JSON format');
                return;
            }
        }

        // Build request data
        const requestData = {
            title: title
        };

        if (createdBy) {
            requestData.created_by = createdBy;
        }

        if (metadata) {
            requestData.metadata = metadata;
        }

        // Step E: Show loading state
        const submitBtn = document.getElementById('create-task-submit');
        const originalBtnText = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner"></span> Creating...';

        try {
            // Step C: Call API
            const result = await apiClient.post('/api/tasks', requestData, {
                requestId: 'create-task-' + Date.now()
            });

            // Step D: Handle response
            if (result.ok) {
                showToast('Task created successfully', 'success');
                closeDialog();
                this.loadTasks(true);
            } else {
                showToast(`Failed to create task: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Failed to create task:', error);
            showToast('Failed to create task', 'error');
        } finally {
            // Restore button state
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtnText;
        }
    }

    showFieldError(fieldId, errorId, message) {
        const field = document.getElementById(fieldId);
        const error = document.getElementById(errorId);
        field.classList.add('error');
        error.textContent = message;
    }

    async cancelTask(taskId) {
        try {
            const result = await apiClient.post(`/api/tasks/${taskId}/cancel`, {}, {
                requestId: `task-cancel-${taskId}`
            });

            if (result.ok) {
                showToast('Task cancelled successfully', 'success');
                this.hideTaskDetail();
                this.loadTasks(true);
            } else {
                showToast(`Failed to cancel task: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Failed to cancel task:', error);
            showToast('Failed to cancel task', 'error');
        }
    }

    async loadTaskPlan(taskId) {
        const planContent = this.container.querySelector('#task-plan-content');

        try {
            const result = await apiClient.get(`/api/exec/tasks/${taskId}/plan`, {
                requestId: `task-plan-${taskId}-${Date.now()}`
            });

            if (result.ok) {
                const plan = result.data;
                this.renderTaskPlan(plan);
            } else {
                planContent.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon"><span class="material-icons md-36">description</span></div>
                        <div class="empty-text">No execution plan available for this task</div>
                        <p class="text-muted">Generate a plan first or check if the API is available.</p>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Failed to load task plan:', error);
            planContent.innerHTML = `
                <div class="error-message">
                    <div class="error-icon"><span class="material-icons md-18">warning</span></div>
                    <div class="error-text">Failed to load execution plan</div>
                    <p class="text-muted">The execution plan API may not be available yet.</p>
                </div>
            `;
        }
    }

    renderTaskPlan(plan) {
        const planContent = this.container.querySelector('#task-plan-content');

        // Create a mini embedded version of the plan
        planContent.innerHTML = `
            <div class="task-plan-embedded">
                <div class="plan-header">
                    <div class="plan-info">
                        <h4>Execution Plan</h4>
                        ${plan.plan_id ? `<code class="code-inline">${plan.plan_id}</code>` : ''}
                    </div>
                    <span class="plan-status status-${plan.status || 'draft'}">${this.formatPlanStatus(plan.status || 'draft')}</span>
                </div>

                ${plan.description ? `
                    <div class="plan-description">
                        <p>${plan.description}</p>
                    </div>
                ` : ''}

                ${plan.validation ? this.renderPlanValidationSummary(plan.validation) : ''}

                ${plan.steps && plan.steps.length > 0 ? `
                    <div class="plan-steps-summary">
                        <h5>Steps (${plan.steps.length})</h5>
                        <div class="steps-list">
                            ${plan.steps.slice(0, 5).map((step, idx) => `
                                <div class="step-item">
                                    <span class="step-number">${idx + 1}</span>
                                    <span class="step-name">${step.name || `Step ${idx + 1}`}</span>
                                    ${step.risk_level && step.risk_level !== 'low' ? `
                                        <span class="risk-badge risk-${step.risk_level}">${step.risk_level.toUpperCase()}</span>
                                    ` : ''}
                                </div>
                            `).join('')}
                            ${plan.steps.length > 5 ? `
                                <div class="text-muted">... and ${plan.steps.length - 5} more steps</div>
                            ` : ''}
                        </div>
                    </div>
                ` : ''}

                <div class="plan-actions">
                    <button class="btn-secondary" onclick="window.open('#execution-plans?task_id=${plan.task_id}', '_blank')">
                        <span class="material-icons md-18">open_in_new</span>
                        View Full Plan
                    </button>
                </div>
            </div>
        `;
    }

    renderPlanValidationSummary(validation) {
        const hasFailed = validation.rules_failed && validation.rules_failed.length > 0;
        const passedCount = validation.rules_passed ? validation.rules_passed.length : 0;
        const failedCount = validation.rules_failed ? validation.rules_failed.length : 0;

        return `
            <div class="plan-validation-summary ${hasFailed ? 'has-failures' : 'all-passed'}">
                <h5>
                    <span class="material-icons md-18">${hasFailed ? 'error' : 'check_circle'}</span>
                    Validation
                </h5>
                <div class="validation-stats">
                    ${passedCount > 0 ? `<span class="stat-passed">${passedCount} passed</span>` : ''}
                    ${failedCount > 0 ? `<span class="stat-failed">${failedCount} failed</span>` : ''}
                </div>
            </div>
        `;
    }

    formatPlanStatus(status) {
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

    renderStatus(status) {
        const statusMap = {
            'pending': { label: 'Pending', class: 'status-pending', icon: '<span class="material-icons md-18">hourglass_empty</span>' },
            'running': { label: 'Running', class: 'status-running', icon: '<span class="material-icons md-18">play_arrow</span>' },
            'completed': { label: 'Completed', class: 'status-success', icon: '<span class="material-icons md-18">done</span>' },
            'failed': { label: 'Failed', class: 'status-error', icon: '<span class="material-icons md-18">cancel</span>' },
            'cancelled': { label: 'Cancelled', class: 'status-cancelled', icon: '<span class="material-icons md-18">block</span>' }
        };

        const config = statusMap[status] || { label: status, class: 'status-unknown', icon: '<span class="material-icons md-18">help</span>' };
        return `<span class="status-badge ${config.class}">${config.icon} ${config.label}</span>`;
    }

    renderProjectBadge(projectId, task) {
        if (!projectId) {
            return `<span class="project-badge project-badge-no-project">
                <span class="material-icons md-14">folder_open</span>
                <span>No Project</span>
            </span>`;
        }

        // Get project name from context if available
        let projectName = projectId;
        if (window.projectContext && typeof window.projectContext.getProjectName === 'function') {
            projectName = window.projectContext.getProjectName(projectId);
        }

        // Truncate long names
        if (projectName.length > 20) {
            projectName = projectName.substring(0, 17) + '...';
        }

        return `<span class="project-badge" data-project-id="${this.escapeHtml(projectId)}" title="${this.escapeHtml(projectId)}">
            <span class="material-icons md-14">folder</span>
            <span>${this.escapeHtml(projectName)}</span>
        </span>`;
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

    async loadTaskRepos(taskId) {
        const reposContent = this.container.querySelector('#task-repos-content');

        try {
            const result = await apiClient.get(`/api/tasks/${taskId}/repos?detailed=true`, {
                requestId: `task-repos-${taskId}-${Date.now()}`
            });

            if (result.ok) {
                const repos = result.data || [];
                this.renderTaskRepos(repos);
            } else {
                reposContent.innerHTML = `
                    <div class="error-message">
                        <div class="error-icon"><span class="material-icons md-18">warning</span></div>
                        <div class="error-text">Failed to load repositories: ${result.message}</div>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Failed to load task repos:', error);
            reposContent.innerHTML = `
                <div class="error-message">
                    <div class="error-icon"><span class="material-icons md-18">warning</span></div>
                    <div class="error-text">Failed to load repositories</div>
                </div>
            `;
        }
    }

    renderTaskRepos(repos) {
        const reposContent = this.container.querySelector('#task-repos-content');

        if (repos.length === 0) {
            reposContent.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon"><span class="material-icons md-36">code</span></div>
                    <div class="empty-text">No repositories associated with this task</div>
                </div>
            `;
            return;
        }

        reposContent.innerHTML = `
            <div class="repos-section">
                <h4>Repositories (${repos.length})</h4>
                ${repos.map(repo => this.renderRepoCard(repo)).join('')}
            </div>
        `;

        // Setup expand/collapse handlers
        reposContent.querySelectorAll('.repo-card-header').forEach(header => {
            header.addEventListener('click', () => {
                const card = header.parentElement;
                card.classList.toggle('expanded');
            });
        });
    }

    renderRepoCard(repo) {
        const accessBadge = repo.writable
            ? '<span class="badge-success">FULL access</span>'
            : '<span class="badge-muted">READ_ONLY</span>';

        const hasChanges = repo.files && repo.files.length > 0;
        const changesSummary = hasChanges
            ? `<span class="text-success">+${repo.total_lines_added}</span>, <span class="text-danger">-${repo.total_lines_deleted}</span>`
            : 'No changes';

        return `
            <div class="repo-card ${hasChanges ? '' : 'no-changes'}">
                <div class="repo-card-header">
                    <div class="repo-info">
                        <span class="material-icons md-18">folder</span>
                        <strong>${repo.name}</strong>
                        ${accessBadge}
                        <span class="role-badge role-${repo.role}">${repo.role}</span>
                    </div>
                    <div class="repo-stats">
                        ${hasChanges ? `
                            <span class="material-icons md-18">check</span>
                            <span>${repo.files.length} files changed (${changesSummary})</span>
                        ` : '<span class="text-muted">No changes</span>'}
                    </div>
                </div>
                ${hasChanges ? `
                    <div class="repo-card-body">
                        <div class="files-list">
                            ${repo.files.slice(0, 10).map(file => `
                                <div class="file-item">
                                    <span class="material-icons md-16">description</span>
                                    <code class="file-path">${file.path}</code>
                                    <span class="file-stats">
                                        <span class="text-success">+${file.lines_added || 0}</span>
                                        <span class="text-danger">-${file.lines_deleted || 0}</span>
                                    </span>
                                </div>
                            `).join('')}
                            ${repo.files.length > 10 ? `
                                <div class="text-muted">... and ${repo.files.length - 10} more files</div>
                            ` : ''}
                        </div>
                        ${repo.commit_hash ? `
                            <div class="repo-commit">
                                <span class="material-icons md-16">commit</span>
                                <span>Commit:</span>
                                <code class="code-inline">${repo.commit_hash}</code>
                            </div>
                        ` : ''}
                    </div>
                ` : ''}
            </div>
        `;
    }

    async loadTaskDependencies(taskId) {
        const depsContent = this.container.querySelector('#task-dependencies-content');

        try {
            const result = await apiClient.get(`/api/tasks/${taskId}/dependencies?include_reverse=true`, {
                requestId: `task-deps-${taskId}-${Date.now()}`
            });

            if (result.ok) {
                const data = result.data || {};
                this.renderTaskDependencies(data.depends_on || [], data.depended_by || []);
            } else {
                depsContent.innerHTML = `
                    <div class="error-message">
                        <div class="error-icon"><span class="material-icons md-18">warning</span></div>
                        <div class="error-text">Failed to load dependencies: ${result.message}</div>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Failed to load task dependencies:', error);
            depsContent.innerHTML = `
                <div class="error-message">
                    <div class="error-icon"><span class="material-icons md-18">warning</span></div>
                    <div class="error-text">Failed to load dependencies</div>
                </div>
            `;
        }
    }

    renderTaskDependencies(dependsOn, dependedBy) {
        const depsContent = this.container.querySelector('#task-dependencies-content');

        if (dependsOn.length === 0 && dependedBy.length === 0) {
            depsContent.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon"><span class="material-icons md-36">link</span></div>
                    <div class="empty-text">No dependencies found</div>
                </div>
            `;
            return;
        }

        depsContent.innerHTML = `
            <div class="dependencies-section">
                ${dependsOn.length > 0 ? `
                    <div class="deps-group">
                        <h4>
                            <span class="material-icons md-18">arrow_downward</span>
                            Depends on (${dependsOn.length})
                        </h4>
                        <div class="deps-list">
                            ${dependsOn.map(dep => this.renderDependencyItem(dep, 'depends-on')).join('')}
                        </div>
                    </div>
                ` : ''}

                ${dependedBy.length > 0 ? `
                    <div class="deps-group">
                        <h4>
                            <span class="material-icons md-18">arrow_upward</span>
                            Depended by (${dependedBy.length})
                        </h4>
                        <div class="deps-list">
                            ${dependedBy.map(dep => this.renderDependencyItem(dep, 'depended-by')).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;

        // Setup click handlers for viewing tasks
        depsContent.querySelectorAll('.btn-view-task').forEach(btn => {
            btn.addEventListener('click', async () => {
                const targetTaskId = btn.getAttribute('data-task-id');
                // Close current drawer and show the dependency task
                this.hideTaskDetail();
                // Fetch and show the dependency task
                const task = this.tasks.find(t => t.task_id === targetTaskId);
                if (task) {
                    await this.showTaskDetail(task);
                } else {
                    // Fetch task details if not in current list
                    try {
                        const result = await apiClient.get(`/api/tasks/${targetTaskId}`);
                        if (result.ok) {
                            await this.showTaskDetail(result.data);
                        }
                    } catch (error) {
                        showToast('Failed to load dependency task', 'error');
                    }
                }
            });
        });
    }

    renderDependencyItem(dep, direction) {
        const typeColors = {
            'requires': 'dep-requires',
            'suggests': 'dep-suggests',
            'blocks': 'dep-blocks'
        };

        const typeIcons = {
            'requires': 'link',
            'suggests': 'info',
            'blocks': 'block'
        };

        const typeClass = typeColors[dep.dependency_type] || 'dep-default';
        const typeIcon = typeIcons[dep.dependency_type] || 'link';
        const targetTaskId = direction === 'depends-on' ? dep.depends_on_task_id : dep.task_id;

        return `
            <div class="dependency-item ${typeClass}">
                <div class="dep-icon">
                    <span class="material-icons md-18">${typeIcon}</span>
                </div>
                <div class="dep-content">
                    <div class="dep-header">
                        <code class="code-inline">${targetTaskId}</code>
                        <span class="dep-type-badge dep-type-${dep.dependency_type}">${dep.dependency_type}</span>
                    </div>
                    ${dep.reason ? `
                        <div class="dep-reason">${dep.reason}</div>
                    ` : ''}
                    <div class="dep-meta">
                        <span>${this.formatTimestamp(dep.created_at)}</span>
                    </div>
                </div>
                <div class="dep-actions">
                    <button class="btn-link btn-view-task" data-task-id="${targetTaskId}">
                        View Task
                    </button>
                </div>
            </div>
        `;
    }

    async loadGuardianReviews(taskId) {
        const container = this.container.querySelector('#guardian-reviews-container');

        // Show loading state
        container.innerHTML = `
            <div class="guardian-loading">
                <div class="loading-spinner"></div>
                <span>Loading Guardian reviews...</span>
            </div>
        `;

        try {
            // Fetch verdict summary
            const verdictResp = await apiClient.get(`/api/guardian/targets/task/${taskId}/verdict`, {
                requestId: `guardian-verdict-${taskId}-${Date.now()}`
            });

            // Fetch full reviews
            const reviewsResp = await apiClient.get(`/api/guardian/reviews?target_type=task&target_id=${taskId}`, {
                requestId: `guardian-reviews-${taskId}-${Date.now()}`
            });

            if (verdictResp.ok && reviewsResp.ok) {
                const verdictData = verdictResp.data;
                const reviewsData = reviewsResp.data;

                // Render Guardian Reviews Panel
                this.renderGuardianReviewsPanel(container, verdictData, reviewsData.reviews || []);
            } else {
                const errorMsg = verdictResp.message || reviewsResp.message || 'Unknown error';
                container.innerHTML = `
                    <div class="error-message">
                        <div class="error-icon"><span class="material-icons md-18">warning</span></div>
                        <div class="error-text">Failed to load Guardian reviews: ${errorMsg}</div>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Failed to load Guardian reviews:', error);
            container.innerHTML = `
                <div class="error-message">
                    <div class="error-icon"><span class="material-icons md-18">warning</span></div>
                    <div class="error-text">Failed to load Guardian reviews: ${error.message}</div>
                </div>
            `;
        }
    }

    renderGuardianReviewsPanel(container, verdictData, reviews) {
        const panel = new GuardianReviewPanel({
            container,
            verdictData,
            reviews
        });
        panel.render();
    }

    showBatchCreateDialog() {
        // Create backdrop
        const backdrop = document.createElement('div');
        backdrop.className = 'dialog-backdrop';

        // Create dialog container
        const dialog = document.createElement('div');
        dialog.className = 'dialog-container dialog-container--large';

        // Build dialog HTML
        dialog.innerHTML = `
            <div class="dialog-content">
                <div class="dialog-header">
                    <h3 class="dialog-title">Batch Create Tasks</h3>
                </div>
                <div class="dialog-body">
                    ${this.renderBatchCreateForm()}
                </div>
                <div class="dialog-footer">
                    <button class="btn-secondary" id="batch-create-cancel">Cancel</button>
                    <button class="btn-primary" id="batch-create-submit">Create Tasks</button>
                </div>
            </div>
        `;

        // Append to body
        backdrop.appendChild(dialog);
        document.body.appendChild(backdrop);

        // Trigger animation
        requestAnimationFrame(() => {
            backdrop.classList.add('dialog-backdrop--visible');
            dialog.classList.add('dialog-container--visible');
        });

        // Setup event handlers
        const closeDialog = () => {
            backdrop.classList.remove('dialog-backdrop--visible');
            dialog.classList.remove('dialog-container--visible');
            setTimeout(() => backdrop.remove(), 300);
        };

        // Cancel button
        dialog.querySelector('#batch-create-cancel').addEventListener('click', closeDialog);

        // Submit button
        dialog.querySelector('#batch-create-submit').addEventListener('click', () => {
            this.handleBatchCreate(dialog, closeDialog);
        });

        // Tab switching
        dialog.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const tabName = btn.getAttribute('data-tab');
                dialog.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                dialog.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                btn.classList.add('active');
                dialog.querySelector(`#${tabName}-tab`).classList.add('active');
            });
        });

        // CSV file change handler
        const csvFile = dialog.querySelector('#csv-file');
        if (csvFile) {
            csvFile.addEventListener('change', (e) => {
                this.handleCSVFileSelect(e.target.files[0], dialog);
            });
        }

        // Backdrop click to close
        backdrop.addEventListener('click', (e) => {
            if (e.target === backdrop) {
                closeDialog();
            }
        });

        // Escape key to close
        const handleKeyDown = (e) => {
            if (e.key === 'Escape') {
                closeDialog();
                document.removeEventListener('keydown', handleKeyDown);
            }
        };
        document.addEventListener('keydown', handleKeyDown);
    }

    renderBatchCreateForm() {
        return `
            <div class="batch-create-form">
                <div class="form-tabs">
                    <button class="tab-btn active" data-tab="text">Text Input</button>
                    <button class="tab-btn" data-tab="csv">CSV Upload</button>
                </div>

                <div class="tab-content active" id="text-tab">
                    <div class="form-group">
                        <label>Task Titles (one per line)</label>
                        <textarea
                            id="batch-titles"
                            rows="10"
                            class="form-control"
                            placeholder="Task 1&#10;Task 2&#10;Task 3"
                        ></textarea>
                        <small class="form-hint">Enter one task title per line (max 100)</small>
                    </div>

                    <div class="form-group">
                        <label>Default Created By (Optional)</label>
                        <input type="text" id="batch-created-by" class="form-control" placeholder="Your name or identifier" />
                    </div>

                    <div class="form-group">
                        <label>Default Metadata (JSON, Optional)</label>
                        <textarea
                            id="batch-metadata"
                            rows="4"
                            class="form-control"
                            placeholder='{"priority": "medium", "category": "development"}'
                        ></textarea>
                        <small class="form-hint">Optional JSON metadata to apply to all tasks</small>
                        <span class="form-error" id="batch-metadata-error"></span>
                    </div>
                </div>

                <div class="tab-content" id="csv-tab">
                    <div class="form-group">
                        <label>Upload CSV File</label>
                        <input type="file" id="csv-file" accept=".csv" class="form-control" />
                        <small class="form-hint">
                            CSV format: title,created_by,metadata<br>
                            Example: "Task 1","user@example.com","{\\"priority\\":\\"high\\"}"
                        </small>
                    </div>

                    <div id="csv-preview"></div>
                </div>
            </div>
        `;
    }

    async handleBatchCreate(dialog, closeDialog) {
        const activeTab = dialog.querySelector('.tab-content.active').id;

        // Clear previous errors
        dialog.querySelectorAll('.form-error').forEach(el => el.textContent = '');
        dialog.querySelectorAll('.form-control').forEach(el => el.classList.remove('error'));

        let tasks = [];

        if (activeTab === 'text-tab') {
            // Text input mode
            const titlesEl = dialog.querySelector('#batch-titles');
            const titles = titlesEl.value
                .split('\n')
                .map(line => line.trim())
                .filter(line => line.length > 0);

            if (titles.length === 0) {
                showToast('Please enter at least one task title', 'error');
                titlesEl.classList.add('error');
                return;
            }

            if (titles.length > 100) {
                showToast('Maximum 100 tasks allowed', 'error');
                titlesEl.classList.add('error');
                return;
            }

            const createdBy = dialog.querySelector('#batch-created-by').value.trim() || null;
            const metadataStr = dialog.querySelector('#batch-metadata').value.trim();

            let metadata = null;
            if (metadataStr) {
                try {
                    metadata = JSON.parse(metadataStr);
                } catch (e) {
                    const errorEl = dialog.querySelector('#batch-metadata-error');
                    const metadataEl = dialog.querySelector('#batch-metadata');
                    metadataEl.classList.add('error');
                    errorEl.textContent = 'Invalid JSON format';
                    showToast('Invalid JSON in metadata field', 'error');
                    return;
                }
            }

            tasks = titles.map(title => ({
                title,
                created_by: createdBy,
                metadata: metadata
            }));
        } else {
            // CSV mode
            const csvData = dialog.querySelector('#csv-file').csvData;
            if (!csvData || csvData.length === 0) {
                showToast('Please upload and preview a CSV file first', 'error');
                return;
            }
            tasks = csvData;
        }

        // Show loading state
        const submitBtn = dialog.querySelector('#batch-create-submit');
        const originalBtnText = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner"></span> Creating...';

        try {
            // Call batch creation API
            const result = await apiClient.post('/api/tasks/batch', { tasks }, {
                requestId: `batch-create-${Date.now()}`,
                timeout: 60000  // 60s timeout for batch operations
            });

            if (result.ok) {
                const data = result.data;
                const message = `Created ${data.successful} tasks successfully` +
                    (data.failed > 0 ? `, ${data.failed} failed` : '');

                showToast(message, data.failed > 0 ? 'warning' : 'success');

                // Show detailed results if there are failures
                if (data.failed > 0) {
                    this.showBatchCreateResults(data);
                }

                closeDialog();
                this.loadTasks(true);  // Refresh task list
            } else {
                showToast(`Batch creation failed: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Failed to create batch:', error);
            showToast('Failed to create tasks batch', 'error');
        } finally {
            // Restore button state
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtnText;
        }
    }

    async handleCSVFileSelect(file, dialog) {
        const previewDiv = dialog.querySelector('#csv-preview');

        if (!file) {
            previewDiv.innerHTML = '';
            return;
        }

        previewDiv.innerHTML = '<div class="loading-spinner">Parsing CSV...</div>';

        try {
            const csvData = await this.parseCSVFile(file);

            if (!csvData || csvData.length === 0) {
                previewDiv.innerHTML = '<div class="error-message">No valid data found in CSV</div>';
                return;
            }

            // Store parsed data for later use
            dialog.querySelector('#csv-file').csvData = csvData;

            // Show preview
            previewDiv.innerHTML = `
                <div class="csv-preview-container">
                    <h4>Preview (${csvData.length} tasks)</h4>
                    <div class="preview-table">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Title</th>
                                    <th>Created By</th>
                                    <th>Metadata</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${csvData.slice(0, 5).map((task, idx) => `
                                    <tr>
                                        <td>${idx + 1}</td>
                                        <td>${this._escapeHtml(task.title)}</td>
                                        <td>${task.created_by || 'N/A'}</td>
                                        <td>${task.metadata ? '<code>JSON</code>' : 'N/A'}</td>
                                    </tr>
                                `).join('')}
                                ${csvData.length > 5 ? `
                                    <tr>
                                        <td colspan="4" class="text-muted">... and ${csvData.length - 5} more tasks</td>
                                    </tr>
                                ` : ''}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        } catch (error) {
            previewDiv.innerHTML = `<div class="error-message">Failed to parse CSV: ${error.message}</div>`;
        }
    }

    async parseCSVFile(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                try {
                    const csv = e.target.result;
                    const lines = csv.split('\n').map(line => line.trim()).filter(line => line);

                    if (lines.length === 0) {
                        reject(new Error('CSV file is empty'));
                        return;
                    }

                    // Check if first line is a header
                    const firstLine = lines[0].toLowerCase();
                    const hasHeader = firstLine.includes('title');
                    const dataLines = hasHeader ? lines.slice(1) : lines;

                    if (dataLines.length === 0) {
                        reject(new Error('No data rows found in CSV'));
                        return;
                    }

                    if (dataLines.length > 100) {
                        reject(new Error('Maximum 100 tasks allowed'));
                        return;
                    }

                    const tasks = [];
                    for (let i = 0; i < dataLines.length; i++) {
                        const line = dataLines[i];

                        // Simple CSV parser (handles quoted fields)
                        const parts = this._parseCSVLine(line);

                        if (parts.length === 0 || !parts[0]) {
                            continue;  // Skip empty lines
                        }

                        const task = {
                            title: parts[0],
                            created_by: parts[1] || null,
                            metadata: null
                        };

                        // Parse metadata if present
                        if (parts[2]) {
                            try {
                                task.metadata = JSON.parse(parts[2]);
                            } catch (e) {
                                console.warn(`Failed to parse metadata for row ${i + 1}: ${e.message}`);
                            }
                        }

                        tasks.push(task);
                    }

                    resolve(tasks);
                } catch (error) {
                    reject(error);
                }
            };
            reader.onerror = () => reject(new Error('Failed to read file'));
            reader.readAsText(file);
        });
    }

    _parseCSVLine(line) {
        const parts = [];
        let current = '';
        let inQuotes = false;

        for (let i = 0; i < line.length; i++) {
            const char = line[i];

            if (char === '"') {
                inQuotes = !inQuotes;
            } else if (char === ',' && !inQuotes) {
                parts.push(current.trim());
                current = '';
            } else {
                current += char;
            }
        }

        parts.push(current.trim());
        return parts;
    }

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    escapeHtml(text) {
        return this._escapeHtml(text);
    }

    showBatchCreateResults(data) {
        // Create backdrop
        const backdrop = document.createElement('div');
        backdrop.className = 'dialog-backdrop';

        // Create dialog container
        const dialog = document.createElement('div');
        dialog.className = 'dialog-container dialog-container--large';

        // Build results HTML
        dialog.innerHTML = `
            <div class="dialog-content">
                <div class="dialog-header">
                    <h3 class="dialog-title">Batch Create Results</h3>
                </div>
                <div class="dialog-body">
                    <div class="batch-results">
                        <div class="result-summary">
                            <div class="summary-item">
                                <span class="summary-label">Total:</span>
                                <span class="summary-value">${data.total}</span>
                            </div>
                            <div class="summary-item success">
                                <span class="summary-label">Successful:</span>
                                <span class="summary-value">${data.successful}</span>
                            </div>
                            <div class="summary-item error">
                                <span class="summary-label">Failed:</span>
                                <span class="summary-value">${data.failed}</span>
                            </div>
                        </div>

                        ${data.failed > 0 ? `
                            <div class="failed-tasks">
                                <h4>Failed Tasks:</h4>
                                <table class="table">
                                    <thead>
                                        <tr>
                                            <th>Index</th>
                                            <th>Title</th>
                                            <th>Error</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${data.errors.map(err => `
                                            <tr>
                                                <td>${err.index + 1}</td>
                                                <td>${this._escapeHtml(err.title)}</td>
                                                <td>${this._escapeHtml(err.error)}</td>
                                            </tr>
                                        `).join('')}
                                    </tbody>
                                </table>

                                <button class="btn-secondary" id="download-failed-csv">
                                    <span class="material-icons md-18">arrow_downward</span>
                                    Download Failed Tasks (CSV)
                                </button>
                            </div>
                        ` : ''}
                    </div>
                </div>
                <div class="dialog-footer">
                    <button class="btn-primary" id="results-close">Close</button>
                </div>
            </div>
        `;

        // Append to body
        backdrop.appendChild(dialog);
        document.body.appendChild(backdrop);

        // Trigger animation
        requestAnimationFrame(() => {
            backdrop.classList.add('dialog-backdrop--visible');
            dialog.classList.add('dialog-container--visible');
        });

        // Close handler
        const closeDialog = () => {
            backdrop.classList.remove('dialog-backdrop--visible');
            dialog.classList.remove('dialog-container--visible');
            setTimeout(() => backdrop.remove(), 300);
        };

        dialog.querySelector('#results-close').addEventListener('click', closeDialog);

        // Download CSV handler
        const downloadBtn = dialog.querySelector('#download-failed-csv');
        if (downloadBtn) {
            downloadBtn.addEventListener('click', () => {
                this.downloadFailedTasksCSV(data.errors);
            });
        }

        // Backdrop click to close
        backdrop.addEventListener('click', (e) => {
            if (e.target === backdrop) {
                closeDialog();
            }
        });
    }

    downloadFailedTasksCSV(errors) {
        // Build CSV content
        const csvLines = ['Title,Error'];
        errors.forEach(err => {
            const title = err.title.replace(/"/g, '""');  // Escape quotes
            const error = err.error.replace(/"/g, '""');
            csvLines.push(`"${title}","${error}"`);
        });

        const csvContent = csvLines.join('\n');

        // Create download link
        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `failed-tasks-${Date.now()}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        showToast('Failed tasks downloaded', 'success');
    }

    // ==================== v0.4 Spec Management Methods ====================

    async freezeTaskSpec(taskId) {
        try {
            showToast('Freezing specification...', 'info', 2000);

            const result = await apiClient.post(`/api/tasks/${taskId}/spec/freeze`, null, {
                requestId: `freeze-spec-${taskId}`
            });

            if (!result.ok) {
                showToast(`Failed to freeze spec: ${result.message}`, 'error');
                return;
            }

            showToast('Specification frozen successfully', 'success');

            // Reload task details
            await this.showTaskDetail(taskId);
            this.loadTasks(true);

        } catch (err) {
            console.error('Failed to freeze spec:', err);
            showToast('Failed to freeze spec: ' + err.message, 'error');
        }
    }

    async markTaskReady(taskId) {
        try {
            showToast('Marking task as ready...', 'info', 2000);

            const result = await apiClient.patch(`/api/tasks/${taskId}`, { status: 'ready' }, {
                requestId: `mark-ready-${taskId}`
            });

            if (!result.ok) {
                showToast(`Failed to mark task as ready: ${result.message}`, 'error');
                return;
            }

            showToast('Task marked as ready', 'success');

            // Reload task details
            await this.showTaskDetail(taskId);
            this.loadTasks(true);

        } catch (err) {
            console.error('Failed to mark task as ready:', err);
            showToast('Failed to mark task as ready: ' + err.message, 'error');
        }
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    destroy() {
        // Cleanup
        this.container.innerHTML = '';
    }
}

// Export
window.TasksView = TasksView;
