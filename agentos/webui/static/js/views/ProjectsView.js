/**
 * ProjectsView - Multi-repository project management UI
 *
 * Phase 6.2: WebUI Multi-repository view enhancement
 */

class ProjectsView {
    constructor(container) {
        this.container = container;
        this.projects = [];
        this.selectedProject = null;
        this.selectedRepo = null;
        this.filterBar = null;
        this.searchQuery = '';

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="projects-view">
                <div class="view-header">
                    <div>
                        <h1>Projects</h1>
                        <p class="text-sm text-gray-600 mt-1">Manage multi-repository project configurations</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="projects-refresh" title="Refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                        <button class="btn-primary" id="projects-create" title="Create New Project">
                            <span class="icon"><span class="material-icons md-18">add</span></span> New Project
                        </button>
                    </div>
                </div>

                <div id="projects-filter-bar" class="filter-section"></div>

                <div class="table-section">
                    <!-- Projects List -->
                    <div id="projects-list" class="projects-section">
                        <div class="loading-spinner">Loading projects...</div>
                    </div>
                </div>

                    <!-- Project Detail Drawer -->
                    <div id="project-detail-drawer" class="drawer hidden">
                        <div class="drawer-overlay" id="project-drawer-overlay"></div>
                        <div class="drawer-content">
                            <div class="drawer-header">
                                <h3>Project Details</h3>
                                <button class="btn-close" id="project-drawer-close">
                                <span class="material-icons">close</span>
                            </button>
                            </div>
                            <div class="drawer-body" id="project-drawer-body">
                                <!-- Project details will be rendered here -->
                            </div>
                        </div>
                    </div>

                    <!-- Repo Detail Drawer -->
                    <div id="repo-detail-drawer" class="drawer hidden">
                        <div class="drawer-overlay" id="repo-drawer-overlay"></div>
                        <div class="drawer-content">
                            <div class="drawer-header">
                                <h3>Repository Details</h3>
                                <button class="btn-close" id="repo-drawer-close">
                                <span class="material-icons">close</span>
                            </button>
                            </div>
                            <div class="drawer-body" id="repo-drawer-body">
                                <!-- Repo details will be rendered here -->
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Repository Modal -->
                <div id="repo-modal" class="modal" style="display: none;">
                    <div class="modal-overlay"></div>
                    <div class="modal-content">
                        <div class="modal-header">
                            <h2 id="repo-modal-title">Add Repository</h2>
                            <button class="modal-close" id="repo-modal-close">&times;</button>
                        </div>
                        <div class="modal-body">
                            <form id="repo-form">
                                <input type="hidden" id="repo-project-id">
                                <input type="hidden" id="repo-id">

                                <div class="form-group">
                                    <label for="repo-name">Name *</label>
                                    <input type="text" id="repo-name" required placeholder="my-repo">
                                </div>

                                <div class="form-group">
                                    <label for="repo-remote-url">Remote URL (optional)</label>
                                    <input type="text" id="repo-remote-url" placeholder="https://github.com/user/repo.git">
                                </div>

                                <div class="form-group">
                                    <label for="repo-workspace-path">Workspace Path * (relative)</label>
                                    <input type="text" id="repo-workspace-path" required placeholder="." pattern="^[^/].*" title="Cannot start with /">
                                    <small class="form-hint">Relative path from workspace root. Use "." for root.</small>
                                    <small id="path-error" class="form-error"></small>
                                </div>

                                <div class="form-group">
                                    <label for="repo-role">Role *</label>
                                    <select id="repo-role" required>
                                        <option value="code">Code</option>
                                        <option value="docs">Docs</option>
                                        <option value="infra">Infrastructure</option>
                                        <option value="mono-subdir">Monorepo Subdirectory</option>
                                    </select>
                                </div>

                                <div class="form-group">
                                    <label for="repo-default-branch">Default Branch</label>
                                    <input type="text" id="repo-default-branch" value="main">
                                </div>

                                <div class="form-group">
                                    <label>
                                        <input type="checkbox" id="repo-writable" checked>
                                        Allow write operations
                                    </label>
                                </div>

                                <div class="modal-actions" style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px;">
                                    <button type="button" class="btn-secondary" id="repo-cancel-btn">Cancel</button>
                                    <button type="submit" class="btn-primary">Save</button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>

                <!-- Confirm Modal -->
                <div id="confirm-modal" class="modal" style="display: none;">
                </div>

                <!-- Project Modal -->
                <div id="project-modal" class="modal" style="display: none;">
                    <div class="modal-overlay"></div>
                    <div class="modal-content">
                        <div class="modal-header">
                            <h2 id="project-modal-title">Create Project</h2>
                            <button class="modal-close" id="project-modal-close">&times;</button>
                        </div>

                        <!-- Tabs Navigation -->
                        <div class="tabs">
                            <button type="button" class="tab-btn active" data-tab="basic">Basic Info</button>
                            <button type="button" class="tab-btn" data-tab="settings">Settings</button>
                        </div>

                        <div class="modal-body">
                            <form id="project-form">
                                <input type="hidden" id="project-id">

                                <!-- Basic Info Tab -->
                                <div id="tab-basic" class="tab-content active">
                                    <div class="form-group">
                                        <label for="project-name">Name *</label>
                                        <input type="text" id="project-name" required placeholder="Enter project name">
                                    </div>

                                    <div class="form-group">
                                        <label for="project-description">Description</label>
                                        <textarea id="project-description" rows="3" placeholder="Optional project description"></textarea>
                                    </div>

                                    <div class="form-group">
                                        <label for="project-tags">Tags</label>
                                        <input type="text" id="project-tags" placeholder="python, web, api (comma-separated)">
                                    </div>

                                    <div class="form-group">
                                        <label for="project-workdir">Default Working Directory</label>
                                        <input type="text" id="project-workdir" placeholder="/path/to/workspace">
                                    </div>
                                </div>

                                <!-- Settings Tab -->
                                <div id="tab-settings" class="tab-content">
                                    <h3 class="settings-section-title">Execution Settings</h3>

                                    <div class="form-group">
                                        <label for="settings-default-runner">Default Runner</label>
                                        <select id="settings-default-runner">
                                            <option value="">-- System Default --</option>
                                            <option value="llama.cpp">Llama.cpp (Local)</option>
                                            <option value="openai">OpenAI</option>
                                            <option value="anthropic">Anthropic</option>
                                        </select>
                                        <small class="form-hint">Default AI provider for tasks in this project</small>
                                    </div>

                                    <div class="form-group">
                                        <label for="settings-provider-policy">Provider Policy</label>
                                        <select id="settings-provider-policy">
                                            <option value="">-- None --</option>
                                            <option value="prefer-local">Prefer Local</option>
                                            <option value="cloud-only">Cloud Only</option>
                                            <option value="local-only">Local Only</option>
                                        </select>
                                        <small class="form-hint">Control which providers are allowed</small>
                                    </div>

                                    <h3 class="settings-section-title">Environment Variables</h3>
                                    <div class="form-group">
                                        <label>Environment Overrides</label>
                                        <div id="env-overrides-list" class="env-overrides-container">
                                            <!-- Dynamic key-value pairs will be added here -->
                                        </div>
                                        <button type="button" class="btn-secondary btn-sm" id="add-env-override-btn">
                                            <span class="material-icons md-16">add</span> Add Variable
                                        </button>
                                        <small class="form-hint">Environment variables to inject (whitelist only)</small>
                                    </div>

                                    <h3 class="settings-section-title">Risk Profile</h3>
                                    <div class="form-group">
                                        <label class="checkbox-label">
                                            <input type="checkbox" id="settings-allow-shell-write">
                                            Allow shell write operations
                                        </label>
                                        <small class="form-hint">Permit tasks to write files via shell commands</small>
                                    </div>

                                    <div class="form-group">
                                        <label class="checkbox-label">
                                            <input type="checkbox" id="settings-require-admin-token">
                                            Require admin token for high-risk operations
                                        </label>
                                        <small class="form-hint">Enforce token validation for dangerous actions</small>
                                    </div>

                                    <div class="form-group">
                                        <label for="settings-writable-paths">Writable Paths (one per line)</label>
                                        <textarea id="settings-writable-paths" rows="4"
                                                  placeholder="/path/to/allowed/dir&#10;./relative/path"></textarea>
                                        <small class="form-hint">Paths where write operations are allowed</small>
                                    </div>
                                </div>

                                <div class="modal-actions" style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px;">
                                    <button type="button" class="btn-secondary" id="project-cancel-btn">Cancel</button>
                                    <button type="submit" class="btn-primary">Save</button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.setupFilterBar();
        this.setupEventListeners();
        this.loadProjects();
    }

    setupFilterBar() {
        const filterContainer = this.container.querySelector('#projects-filter-bar');

        this.filterBar = new FilterBar(filterContainer, {
            filters: [
                {
                    type: 'text',
                    key: 'search',
                    label: 'Search',
                    placeholder: 'Search projects by name...'
                }
            ],
            onChange: (filters) => this.handleFilterChange(filters),
            debounceMs: 300
        });
    }

    handleFilterChange(filters) {
        this.searchQuery = filters.search || '';
        this.filterProjects();
    }

    filterProjects() {
        const query = this.searchQuery.toLowerCase();
        const projectCards = this.container.querySelectorAll('.project-card');

        projectCards.forEach(card => {
            const projectName = card.dataset.projectName?.toLowerCase() || '';
            const projectDesc = card.dataset.projectDesc?.toLowerCase() || '';

            if (projectName.includes(query) || projectDesc.includes(query)) {
                card.style.display = '';
            } else {
                card.style.display = 'none';
            }
        });
    }

    setupEventListeners() {
        // Refresh button
        this.container.querySelector('#projects-refresh').addEventListener('click', () => {
            this.loadProjects(true);
        });

        // Project drawer close
        this.container.querySelector('#project-drawer-close').addEventListener('click', () => {
            this.hideProjectDetail();
        });

        this.container.querySelector('#project-drawer-overlay').addEventListener('click', () => {
            this.hideProjectDetail();
        });

        // Repo drawer close
        this.container.querySelector('#repo-drawer-close').addEventListener('click', () => {
            this.hideRepoDetail();
        });

        this.container.querySelector('#repo-drawer-overlay').addEventListener('click', () => {
            this.hideRepoDetail();
        });

        // Repo modal close handlers
        this.container.querySelector('#repo-modal-close').addEventListener('click', () => {
            this.closeRepoModal();
        });

        this.container.querySelector('#repo-cancel-btn').addEventListener('click', () => {
            this.closeRepoModal();
        });

        // Repo form submit
        this.container.querySelector('#repo-form').addEventListener('submit', (e) => {
            this.submitRepoForm(e);
        });

        // Path validation
        this.container.querySelector('#repo-workspace-path').addEventListener('input', (e) => {
            this.validateRepoPath(e.target);
        });

        // Tab switching for project modal
        this.container.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.switchProjectTab(e.target.getAttribute('data-tab'));
            });
        });

        // Add environment variable button
        this.container.querySelector('#add-env-override-btn')?.addEventListener('click', () => {
            this.addEnvOverride();
        });

        // Project create button
        this.container.querySelector('#projects-create').addEventListener('click', () => {
            this.showCreateProjectModal();
        });

        // Project modal close handlers
        this.container.querySelector('#project-modal-close').addEventListener('click', () => {
            this.closeProjectModal();
        });

        this.container.querySelector('#project-cancel-btn').addEventListener('click', () => {
            this.closeProjectModal();
        });

        // Project form submit
        this.container.querySelector('#project-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.submitProjectForm();
        });
    }

    async loadProjects(forceRefresh = false) {
        const projectsList = this.container.querySelector('#projects-list');
        projectsList.innerHTML = '<div class="loading-spinner">Loading projects...</div>';

        try {
            const result = await apiClient.get('/api/projects', {
                requestId: `projects-list-${Date.now()}`
            });

            if (result.ok) {
                // API returns {projects: [...], total: N, limit: M, offset: O}
                this.projects = result.data?.projects || [];
                this.renderProjects();

                if (forceRefresh) {
                    showToast('Projects refreshed', 'success', 2000);
                }
            } else {
                projectsList.innerHTML = `
                    <div class="error-message">
                        <div class="error-icon"><span class="material-icons md-18">warning</span></div>
                        <div class="error-text">Failed to load projects: ${result.message}</div>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Failed to load projects:', error);
            projectsList.innerHTML = `
                <div class="error-message">
                    <div class="error-icon"><span class="material-icons md-18">warning</span></div>
                    <div class="error-text">Failed to load projects</div>
                </div>
            `;
        }
    }

    renderProjects() {
        const projectsList = this.container.querySelector('#projects-list');

        if (this.projects.length === 0) {
            projectsList.innerHTML = this.renderEmptyState();
            return;
        }

        projectsList.innerHTML = `
            <div class="projects-grid">
                ${this.projects.map(project => this.renderProjectCard(project)).join('')}
            </div>
        `;

        // Setup click handlers for project cards (body only, not footer links)
        projectsList.querySelectorAll('.project-card').forEach(card => {
            // Click on card header/body to show details
            const cardHeader = card.querySelector('.card-header');
            const cardBody = card.querySelector('.card-body');

            [cardHeader, cardBody].forEach(element => {
                element?.addEventListener('click', (e) => {
                    // Don't trigger if clicking on action buttons
                    if (e.target.closest('.btn-icon') || e.target.closest('.btn-icon-menu')) {
                        return;
                    }
                    const projectId = card.getAttribute('data-project-id');
                    this.showProjectDetail(projectId);
                });
            });
        });

        // Setup quick action handlers
        projectsList.querySelectorAll('.action-open-repos').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const projectId = btn.getAttribute('data-project-id');
                this.showProjectDetail(projectId);
            });
        });
        // Setup edit buttons
        projectsList.querySelectorAll('.btn-edit-project').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const projectId = btn.getAttribute('data-project-id');
                this.editProject(projectId);
            });
        });

        // Setup menu buttons
        projectsList.querySelectorAll('.btn-project-menu').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const projectId = btn.getAttribute('data-project-id');
                this.showProjectMenu(projectId, btn);
            });
        });

        // Load stats for each project
        this.projects.forEach(project => {
            this.loadProjectStats(project.project_id);
        });
    }

    renderEmptyState() {
        return `
            <div class="empty-state">
                <div class="empty-icon">
                    <span class="material-icons md-18">folder_open</span>
                </div>
                <h2>Create your first project</h2>
                <p class="empty-description">
                    Projects help you organize repositories, tasks, and execution context.
                    Get started by creating a new project.
                </p>
            </div>
        `;
    }

    renderProjectCard(project) {
        const description = project.description || '';
        const tags = project.tags || [];
        const createdAt = project.created_at || project.updated_at;

        return `
            <div class="project-card"
                 data-project-id="${project.project_id}"
                 data-project-name="${this.escapeHtml(project.name || '')}"
                 data-project-desc="${this.escapeHtml(project.description || '')}">
                <div class="card-header">
                    <h3>${this.escapeHtml(project.name)}</h3>
                    <div class="card-actions">
                        <button class="btn-icon btn-edit-project" data-project-id="${project.project_id}" title="Edit">
                            <span class="material-icons md-18">edit</span>
                        </button>
                        <button class="btn-icon btn-project-menu" data-project-id="${project.project_id}" title="More">
                            <span class="material-icons md-18">more_vert</span>
                        </button>
                    </div>
                </div>

                <div class="card-body">
                    ${description ? `<p class="project-description">${this.escapeHtml(description)}</p>` : ''}

                    ${tags.length > 0 ? `
                        <div class="project-tags">
                            ${tags.map(tag => `<span class="tag">${this.escapeHtml(tag)}</span>`).join('')}
                        </div>
                    ` : ''}

                    <div class="project-stats" id="project-stats-${project.project_id}">
                        <div class="stat">
                            <span class="material-icons md-16">folder</span>
                            <span>${project.repo_count || 0} Repos</span>
                        </div>
                        <div class="stat">
                            <span class="material-icons md-16">task</span>
                            <span id="tasks-count-${project.project_id}">... Tasks (7d)</span>
                        </div>
                        <div class="stat">
                            <span class="material-icons md-16">schedule</span>
                            <span>Updated ${this.formatRelativeTime(createdAt)}</span>
                        </div>
                    </div>

                    <div id="health-indicator-${project.project_id}"></div>
                </div>

                <div class="card-footer">
                    <a href="#" class="card-link action-open-repos" data-project-id="${project.project_id}" title="Open Repos">
                        <span class="material-icons md-16">folder</span>
                    </a>
                    <a href="#/tasks?project=${project.project_id}" class="card-link" title="View Tasks">
                        <span class="material-icons md-16">list</span>
                    </a>
                    <a href="#/events?project=${project.project_id}" class="card-link" title="View Events">
                        <span class="material-icons md-16">analytics</span>
                    </a>
                </div>
            </div>
        `;
    }

    async showProjectDetail(projectId) {
        this.selectedProject = projectId;
        const drawer = this.container.querySelector('#project-detail-drawer');
        const drawerBody = this.container.querySelector('#project-drawer-body');

        // Show drawer with loading state
        drawer.classList.remove('hidden');
        drawerBody.innerHTML = '<div class="loading-spinner">Loading project details...</div>';

        try {
            const result = await apiClient.get(`/api/projects/${projectId}`, {
                requestId: `project-detail-${projectId}`
            });

            if (result.ok) {
                const project = result.data;
                this.renderProjectDetail(project);
            } else {
                drawerBody.innerHTML = `
                    <div class="error-message">
                        <div class="error-icon"><span class="material-icons md-18">warning</span></div>
                        <div class="error-text">Failed to load project details: ${result.message}</div>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Failed to load project detail:', error);
            drawerBody.innerHTML = `
                <div class="error-message">
                    <div class="error-icon"><span class="material-icons md-18">warning</span></div>
                    <div class="error-text">Failed to load project details</div>
                </div>
            `;
        }
    }

    async renderProjectDetail(project) {
        const drawerBody = this.container.querySelector('#project-drawer-body');

        // Fetch recent tasks for this project
        let recentTasks = [];
        try {
            const tasksResult = await apiClient.get(`/api/tasks?project_id=${project.project_id}&limit=10&sort=updated_at:desc`);
            if (tasksResult.ok && tasksResult.data.tasks) {
                recentTasks = tasksResult.data.tasks;
            }
        } catch (error) {
            console.error('Failed to fetch recent tasks:', error);
        }

        drawerBody.innerHTML = `
            <div class="project-detail">
                <!-- Project Info -->
                <div class="detail-section">
                    <h4>Project Information</h4>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <label>Project ID</label>
                            <div class="detail-value"><code>${project.project_id}</code></div>
                        </div>
                        <div class="detail-item">
                            <label>Name</label>
                            <div class="detail-value">${project.name}</div>
                        </div>
                        <div class="detail-item">
                            <label>Repositories</label>
                            <div class="detail-value">${project.repos_count || project.repo_count || 0}</div>
                        </div>
                        <div class="detail-item">
                            <label>Workspace Root</label>
                            <div class="detail-value"><code>${project.workspace_root || project.default_workdir || 'N/A'}</code></div>
                        </div>
                    </div>
                </div>

                <!-- Tabs Navigation -->
                <div class="tabs-container">
                    <div class="tabs">
                        <button type="button" class="tab-btn active" data-tab="overview">Overview</button>
                        <button type="button" class="tab-btn" data-tab="task-graph">Task Graph</button>
                        <button type="button" class="tab-btn" data-tab="repos">Repositories</button>
                    </div>
                </div>

                <!-- Overview Tab -->
                <div id="tab-overview" class="tab-content active">
                    <!-- Recent Tasks -->
                    <div class="detail-section">
                        <div class="section-header">
                            <h4>Recent Tasks (Last 10)</h4>
                            <a href="#/tasks?project=${project.project_id}" class="btn-link">View All →</a>
                        </div>
                        ${recentTasks.length > 0 ? `
                            <div class="tasks-list">
                                ${recentTasks.map(task => `
                                    <div class="task-item">
                                        <div class="task-header">
                                            <code class="code-inline">${task.task_id.substring(0, 12)}...</code>
                                            <span class="task-status status-${task.status}">${task.status}</span>
                                        </div>
                                        <div class="task-title">${task.title}</div>
                                        <div class="task-meta">
                                            <span class="material-icons md-14">schedule</span>
                                            <span>${this.formatTimestamp(task.updated_at || task.created_at)}</span>
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        ` : '<p class="text-muted">No tasks found for this project</p>'}
                    </div>
                </div>

                <!-- Task Graph Tab -->
                <div id="tab-task-graph" class="tab-content">
                    <div class="detail-section">
                        <div id="task-graph-container" style="width: 100%; height: 600px; border: 1px solid #ddd; border-radius: 4px; background-color: #fafafa;"></div>
                        <div id="graph-legend" class="graph-legend"></div>
                    </div>
                </div>

                <!-- Repositories Tab -->
                <div id="tab-repos" class="tab-content">
                    <div class="detail-section">
                    <div class="section-header">
                        <h4>Repositories (${project.repos.length})</h4>
                        <button class="btn-primary btn-sm" id="add-repo-btn" data-project-id="${project.project_id}" style="display: flex; align-items: center; gap: 4px;">
                            <span class="material-icons md-16">add</span> Add Repository
                        </button>
                    </div>
                    ${project.repos.length > 0 ? `
                        <div class="repos-table">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Name</th>
                                        <th>Path</th>
                                        <th>Role</th>
                                        <th>Writable</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${project.repos.map(repo => `
                                        <tr>
                                            <td><strong>${repo.name}</strong></td>
                                            <td><code class="code-inline">${repo.workspace_relpath}</code></td>
                                            <td><span class="role-badge role-${repo.role}">${repo.role}</span></td>
                                            <td>${repo.is_writable ? '<span class="badge-success"><span class="material-icons md-18">check</span></span>' : '<span class="badge-muted">Read-only</span>'}</td>
                                            <td style="display: flex; gap: 8px; align-items: center;">
                                                <button class="btn-link btn-view-repo" data-repo-id="${repo.repo_id}" data-project-id="${project.project_id}" title="View">
                                                    <span class="material-icons md-16">preview</span>
                                                </button>
                                                <button class="btn-icon btn-edit-repo" data-repo-id="${repo.repo_id}" data-project-id="${project.project_id}" title="Edit">
                                                    <span class="material-icons md-16">edit</span>
                                                </button>
                                                <button class="btn-icon danger btn-delete-repo" data-repo-id="${repo.repo_id}" data-project-id="${project.project_id}" title="Remove">
                                                    <span class="material-icons md-16">delete</span>
                                                </button>
                                            </td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    ` : '<p class="text-muted">No repositories in this project</p>'}
                    </div>
                </div>
            </div>
        `;

        // Setup tab switching
        drawerBody.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const tabName = btn.getAttribute('data-tab');
                this.switchTab(drawerBody, tabName);

                // Load task graph when tab is opened
                if (tabName === 'task-graph') {
                    this.renderTaskGraph(project.project_id);
                }
            });
        });

        // Setup add repo button
        const addRepoBtn = drawerBody.querySelector('#add-repo-btn');
        if (addRepoBtn) {
            addRepoBtn.addEventListener('click', () => {
                const projectId = addRepoBtn.getAttribute('data-project-id');
                this.showAddRepoModal(projectId);
            });
        }

        // Setup repo view buttons
        drawerBody.querySelectorAll('.btn-view-repo').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const repoId = btn.getAttribute('data-repo-id');
                const projectId = btn.getAttribute('data-project-id');
                this.showRepoDetail(projectId, repoId);
            });
        });

        // Setup repo edit buttons
        drawerBody.querySelectorAll('.btn-edit-repo').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const repoId = btn.getAttribute('data-repo-id');
                const projectId = btn.getAttribute('data-project-id');
                this.editRepo(projectId, repoId);
            });
        });

        // Setup repo delete buttons
        drawerBody.querySelectorAll('.btn-delete-repo').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const repoId = btn.getAttribute('data-repo-id');
                const projectId = btn.getAttribute('data-project-id');
                this.removeRepo(projectId, repoId);
            });
        });
    }

    async showRepoDetail(projectId, repoId) {
        this.selectedRepo = repoId;
        const drawer = this.container.querySelector('#repo-detail-drawer');
        const drawerBody = this.container.querySelector('#repo-drawer-body');

        // Show drawer with loading state
        drawer.classList.remove('hidden');
        drawerBody.innerHTML = '<div class="loading-spinner">Loading repository details...</div>';

        try {
            // Fetch repo details and tasks in parallel
            const [repoResult, tasksResult] = await Promise.all([
                apiClient.get(`/api/projects/${projectId}/repos/${repoId}`, {
                    requestId: `repo-detail-${repoId}`
                }),
                apiClient.get(`/api/projects/${projectId}/repos/${repoId}/tasks`, {
                    requestId: `repo-tasks-${repoId}`
                })
            ]);

            if (repoResult.ok) {
                const repo = repoResult.data;
                const tasks = tasksResult.ok ? tasksResult.data : [];
                this.renderRepoDetail(repo, tasks);
            } else {
                drawerBody.innerHTML = `
                    <div class="error-message">
                        <div class="error-icon"><span class="material-icons md-18">warning</span></div>
                        <div class="error-text">Failed to load repository details: ${repoResult.message}</div>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Failed to load repo detail:', error);
            drawerBody.innerHTML = `
                <div class="error-message">
                    <div class="error-icon"><span class="material-icons md-18">warning</span></div>
                    <div class="error-text">Failed to load repository details</div>
                </div>
            `;
        }
    }

    renderRepoDetail(repo, tasks) {
        const drawerBody = this.container.querySelector('#repo-drawer-body');

        // Calculate total stats from tasks
        const totalFiles = tasks.reduce((sum, task) => sum + task.files_changed, 0);
        const totalLinesAdded = tasks.reduce((sum, task) => sum + task.lines_added, 0);
        const totalLinesDeleted = tasks.reduce((sum, task) => sum + task.lines_deleted, 0);

        drawerBody.innerHTML = `
            <div class="repo-detail">
                <!-- Repo Info -->
                <div class="detail-section">
                    <h4>Repository Information</h4>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <label>Name</label>
                            <div class="detail-value">${repo.name}</div>
                        </div>
                        <div class="detail-item">
                            <label>Repository ID</label>
                            <div class="detail-value"><code>${repo.repo_id}</code></div>
                        </div>
                        <div class="detail-item">
                            <label>Remote URL</label>
                            <div class="detail-value"><code class="code-inline">${repo.remote_url || 'Local'}</code></div>
                        </div>
                        <div class="detail-item">
                            <label>Role</label>
                            <div class="detail-value"><span class="role-badge role-${repo.role}">${repo.role}</span></div>
                        </div>
                        <div class="detail-item">
                            <label>Access</label>
                            <div class="detail-value">${repo.is_writable ? '<span class="badge-success">Writable</span>' : '<span class="badge-muted">Read-only</span>'}</div>
                        </div>
                        <div class="detail-item">
                            <label>Default Branch</label>
                            <div class="detail-value"><code>${repo.default_branch}</code></div>
                        </div>
                        <div class="detail-item">
                            <label>Workspace Path</label>
                            <div class="detail-value"><code>${repo.workspace_relpath}</code></div>
                        </div>
                        <div class="detail-item">
                            <label>Tasks</label>
                            <div class="detail-value">${repo.task_count || tasks.length}</div>
                        </div>
                    </div>
                </div>

                <!-- Statistics -->
                ${tasks.length > 0 ? `
                    <div class="detail-section">
                        <h4>Statistics</h4>
                        <div class="stats-grid">
                            <div class="stat-card">
                                <div class="stat-value">${totalFiles}</div>
                                <div class="stat-label">Files Changed</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-value text-success">+${totalLinesAdded}</div>
                                <div class="stat-label">Lines Added</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-value text-danger">-${totalLinesDeleted}</div>
                                <div class="stat-label">Lines Deleted</div>
                            </div>
                        </div>
                    </div>
                ` : ''}

                <!-- Tasks Timeline -->
                <div class="detail-section">
                    <h4>Tasks (${tasks.length})</h4>
                    ${tasks.length > 0 ? `
                        <div class="tasks-timeline">
                            ${tasks.map(task => `
                                <div class="timeline-item">
                                    <div class="timeline-marker"></div>
                                    <div class="timeline-content">
                                        <div class="timeline-header">
                                            <code class="code-inline">${task.task_id}</code>
                                            <span class="timeline-time">${this.formatTimestamp(task.created_at)}</span>
                                        </div>
                                        <div class="timeline-stats">
                                            <span>${task.files_changed} files</span>
                                            <span class="text-success">+${task.lines_added}</span>
                                            <span class="text-danger">-${task.lines_deleted}</span>
                                            ${task.commit_hash ? `<code class="code-inline">${task.commit_hash.substring(0, 7)}</code>` : ''}
                                        </div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    ` : '<p class="text-muted">No tasks have modified this repository</p>'}
                </div>
            </div>
        `;
    }

    hideProjectDetail() {
        const drawer = this.container.querySelector('#project-detail-drawer');
        drawer.classList.add('hidden');
        this.selectedProject = null;
    }

    hideRepoDetail() {
        const drawer = this.container.querySelector('#repo-detail-drawer');
        drawer.classList.add('hidden');
        this.selectedRepo = null;
    }

    async loadProjectStats(projectId) {
        try {
            // Get 7 days ago timestamp
            const sevenDaysAgo = new Date();
            sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
            const createdAfter = sevenDaysAgo.toISOString();

            // Fetch recent tasks for this project
            const result = await apiClient.get(`/api/tasks?project_id=${projectId}&created_after=${createdAfter}`);

            if (result.ok && result.data) {
                const tasks = result.data.tasks || [];
                const recentTasksCount = tasks.length;
                const failedTasksCount = tasks.filter(t =>
                    t.status === 'failed' || t.status === 'error'
                ).length;

                // Update tasks count
                const tasksCountEl = this.container.querySelector(`#tasks-count-${projectId}`);
                if (tasksCountEl) {
                    tasksCountEl.textContent = `${recentTasksCount} Tasks (7d)`;
                }

                // Show health indicator if there are failed tasks
                if (failedTasksCount > 0) {
                    const healthIndicatorEl = this.container.querySelector(`#health-indicator-${projectId}`);
                    if (healthIndicatorEl) {
                        healthIndicatorEl.innerHTML = `
                            <div class="health-indicator warning">
                                <span class="material-icons md-16">warning</span>
                                <span>${failedTasksCount} failed task${failedTasksCount > 1 ? 's' : ''}</span>
                            </div>
                        `;
                    }
                }
            }
        } catch (error) {
            console.error(`Failed to load stats for project ${projectId}:`, error);
        }
    }

    filterProjects(query) {
        const lowerQuery = query.toLowerCase().trim();
        const cards = this.container.querySelectorAll('.project-card');

        cards.forEach(card => {
            const projectId = card.getAttribute('data-project-id');
            const project = this.projects.find(p => p.project_id === projectId);

            if (!project) return;

            const matchesName = project.name.toLowerCase().includes(lowerQuery);
            const matchesDesc = (project.description || '').toLowerCase().includes(lowerQuery);
            const matchesTags = (project.tags || []).some(tag =>
                tag.toLowerCase().includes(lowerQuery)
            );

            if (matchesName || matchesDesc || matchesTags || lowerQuery === '') {
                card.style.display = 'block';
            } else {
                card.style.display = 'none';
            }
        });
    }

    formatRelativeTime(timestamp) {
        if (!timestamp) return 'N/A';

        try {
            const now = new Date();
            const date = new Date(timestamp);
            const diff = now - date;

            const seconds = Math.floor(diff / 1000);
            const minutes = Math.floor(seconds / 60);
            const hours = Math.floor(minutes / 60);
            const days = Math.floor(hours / 24);

            if (days > 0) return `${days}d ago`;
            if (hours > 0) return `${hours}h ago`;
            if (minutes > 0) return `${minutes}m ago`;
            return 'Just now';
        } catch (e) {
            return timestamp;
        }
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

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ==================== Repository Management Methods ====================

    showAddRepoModal(projectId) {
        const modal = this.container.querySelector('#repo-modal');
        const form = this.container.querySelector('#repo-form');

        form.reset();
        this.container.querySelector('#repo-project-id').value = projectId;
        this.container.querySelector('#repo-id').value = '';
        this.container.querySelector('#repo-modal-title').textContent = 'Add Repository';
        this.container.querySelector('#repo-default-branch').value = 'main';
        this.container.querySelector('#repo-writable').checked = true;

        modal.style.display = 'flex';
    }

    async editRepo(projectId, repoId) {
        try {
            const result = await apiClient.get(`/api/projects/${projectId}/repos/${repoId}`, {
                requestId: `edit-repo-${repoId}`
            });

            if (!result.ok) {
                showToast('Failed to load repository details', 'error');
                return;
            }

            const repo = result.data;

            // Fill form
            this.container.querySelector('#repo-project-id').value = projectId;
            this.container.querySelector('#repo-id').value = repo.repo_id;
            this.container.querySelector('#repo-name').value = repo.name;
            this.container.querySelector('#repo-remote-url').value = repo.remote_url || '';
            this.container.querySelector('#repo-workspace-path').value = repo.workspace_relpath;
            this.container.querySelector('#repo-role').value = repo.role;
            this.container.querySelector('#repo-writable').checked = repo.is_writable;
            this.container.querySelector('#repo-default-branch').value = repo.default_branch || 'main';

            // Show modal
            this.container.querySelector('#repo-modal-title').textContent = 'Edit Repository';
            this.container.querySelector('#repo-modal').style.display = 'flex';
        } catch (err) {
            console.error('Failed to load repository:', err);
            showToast('Failed to load repository: ' + err.message, 'error');
        }
    }

    async removeRepo(projectId, repoId) {
        const confirmed = await this.showConfirmDialog(
            'Remove Repository',
            'Remove this repository from the project? Tasks and artifacts will be preserved.',
            'danger'
        );

        if (!confirmed) return;

        try {
            const result = await apiClient.delete(`/api/projects/${projectId}/repos/${repoId}`, {
                requestId: `delete-repo-${repoId}`
            });

            if (!result.ok) {
                showToast(result.message || 'Failed to remove repository', 'error');
                return;
            }

            showToast('Repository removed successfully', 'success');

            // Reload project detail
            await this.showProjectDetail(projectId);
        } catch (err) {
            console.error('Failed to remove repository:', err);
            showToast('Failed to remove repository: ' + err.message, 'error');
        }
    }

    async submitRepoForm(event) {
        event.preventDefault();

        const projectId = this.container.querySelector('#repo-project-id').value;
        const repoId = this.container.querySelector('#repo-id').value;
        const isEdit = !!repoId;

        const formData = {
            name: this.container.querySelector('#repo-name').value,
            remote_url: this.container.querySelector('#repo-remote-url').value || null,
            workspace_relpath: this.container.querySelector('#repo-workspace-path').value,
            role: this.container.querySelector('#repo-role').value,
            is_writable: this.container.querySelector('#repo-writable').checked,
            default_branch: this.container.querySelector('#repo-default-branch').value || 'main'
        };

        // Path validation
        if (formData.workspace_relpath.includes('..') ||
            formData.workspace_relpath.startsWith('/')) {
            showToast('Invalid path: cannot contain ".." or start with "/"', 'error');
            return;
        }

        // Check for duplicate name (only for new repos)
        if (!isEdit) {
            try {
                const projectResult = await apiClient.get(`/api/projects/${projectId}`, {
                    requestId: `check-duplicate-${Date.now()}`
                });

                if (projectResult.ok && projectResult.data.repos) {
                    const duplicate = projectResult.data.repos.find(r => r.name === formData.name);
                    if (duplicate) {
                        showToast(`Repository name "${formData.name}" already exists in this project`, 'error');
                        return;
                    }
                }
            } catch (err) {
                console.error('Failed to check for duplicate:', err);
            }
        }

        try {
            const url = isEdit
                ? `/api/projects/${projectId}/repos/${repoId}`
                : `/api/projects/${projectId}/repos`;
            const method = isEdit ? 'PUT' : 'POST';

            const result = method === 'PUT'
                ? await apiClient.put(url, formData, { requestId: `save-repo-${Date.now()}` })
                : await apiClient.post(url, formData, { requestId: `save-repo-${Date.now()}` });

            if (!result.ok) {
                showToast(result.message || 'Failed to save repository', 'error');
                return;
            }

            this.closeRepoModal();
            showToast(isEdit ? 'Repository updated' : 'Repository added', 'success');

            // Reload project detail
            await this.showProjectDetail(projectId);
        } catch (err) {
            console.error('Failed to save repository:', err);
            showToast('Failed to save repository: ' + err.message, 'error');
        }
    }

    closeRepoModal() {
        const modal = this.container.querySelector('#repo-modal');
        modal.style.display = 'none';
        this.container.querySelector('#repo-form').reset();
        this.container.querySelector('#path-error').textContent = '';
    }

    validateRepoPath(input) {
        const path = input.value;
        const errorElement = this.container.querySelector('#path-error');

        if (path.includes('..')) {
            input.setCustomValidity('Path cannot contain ".."');
            if (errorElement) errorElement.textContent = 'Path cannot contain ".."';
        } else if (path.startsWith('/')) {
            input.setCustomValidity('Path cannot be absolute (start with "/")');
            if (errorElement) errorElement.textContent = 'Must be a relative path';
        } else {
            input.setCustomValidity('');
            if (errorElement) errorElement.textContent = '';
        }
    }

    async showConfirmDialog(title, message, type = 'danger') {
        return new Promise((resolve) => {
            const modal = this.container.querySelector('#confirm-modal');
            if (!modal) {
                resolve(false);
                return;
            }

            const iconMap = {
                'danger': 'warning',
                'warning': 'warning',
                'info': 'info'
            };

            const colorMap = {
                'danger': 'text-red-600',
                'warning': 'text-orange-600',
                'info': 'text-blue-600'
            };

            modal.innerHTML = `
                <div class="modal-overlay"></div>
                <div class="modal-content" style="max-width: 500px;">
                    <div class="modal-header">
                        <h2>${title}</h2>
                    </div>

                    <div class="modal-body">
                        <div style="display: flex; align-items: start; gap: 12px;">
                            <span class="material-icons md-24 ${colorMap[type]}">${iconMap[type]}</span>
                            <p style="margin: 0; color: #374151;">${message}</p>
                        </div>
                    </div>

                    <div class="modal-actions" style="display: flex; gap: 10px; justify-content: flex-end; padding: 0 24px 24px;">
                        <button class="btn-secondary modal-cancel-btn">Cancel</button>
                        <button class="btn-${type === 'info' ? 'primary' : 'danger'} modal-confirm-btn">Confirm</button>
                    </div>
                </div>
            `;

            modal.style.display = 'flex';

            modal.querySelector('.modal-cancel-btn')?.addEventListener('click', () => {
                modal.style.display = 'none';
                resolve(false);
            });

            modal.querySelector('.modal-confirm-btn')?.addEventListener('click', () => {
                modal.style.display = 'none';
                resolve(true);
            });

            modal.querySelector('.modal-overlay')?.addEventListener('click', () => {
                modal.style.display = 'none';
                resolve(false);
            });
        });
    }


    // ==================== Tab Management ====================

    switchProjectTab(tabName) {
        // Update button states
        this.container.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.getAttribute('data-tab') === tabName) {
                btn.classList.add('active');
            }
        });

        // Update content visibility
        this.container.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        this.container.querySelector(`#tab-${tabName}`)?.classList.add('active');
    }

    // ==================== Environment Variables Management ====================

    addEnvOverride(key = '', value = '') {
        const container = this.container.querySelector('#env-overrides-list');
        const row = document.createElement('div');
        row.className = 'env-override-row';
        row.innerHTML = `
            <input type="text" placeholder="KEY" value="${this.escapeHtml(key)}" class="env-key">
            <input type="text" placeholder="value" value="${this.escapeHtml(value)}" class="env-value">
            <button type="button" class="btn-icon btn-remove-env" title="Remove">
                <span class="material-icons md-18">delete</span>
            </button>
        `;
        container.appendChild(row);

        // Add remove handler
        row.querySelector('.btn-remove-env').addEventListener('click', () => {
            row.remove();
        });
    }

    collectEnvOverrides() {
        const rows = this.container.querySelectorAll('.env-override-row');
        const overrides = {};
        rows.forEach(row => {
            const key = row.querySelector('.env-key').value.trim();
            const value = row.querySelector('.env-value').value.trim();
            if (key) {
                overrides[key] = value;
            }
        });
        return overrides;
    }

    clearEnvOverrides() {
        const container = this.container.querySelector('#env-overrides-list');
        container.innerHTML = '';
    }

    // ==================== Project CRUD Methods ====================

    showCreateProjectModal() {
        this.currentEditingProjectId = null;

        // Reset form
        this.container.querySelector('#project-form').reset();
        this.container.querySelector('#project-id').value = '';
        this.container.querySelector('#project-modal-title').textContent = 'Create New Project';

        // Clear environment variables
        this.clearEnvOverrides();

        // Reset to basic tab
        this.switchProjectTab('basic');

        // Show modal
        const modal = this.container.querySelector('#project-modal');
        modal.style.display = 'flex';
    }

    async editProject(projectId) {
        try {
            // Fetch project details
            const result = await apiClient.get(`/api/projects/${projectId}`);

            if (!result.ok) {
                showToast(`Failed to load project: ${result.message}`, 'error');
                return;
            }

            const project = result.data;
            this.currentEditingProjectId = projectId;

            // Fill basic info
            this.container.querySelector('#project-id').value = project.project_id;
            this.container.querySelector('#project-name').value = project.name;
            this.container.querySelector('#project-description').value = project.description || '';
            this.container.querySelector('#project-tags').value = (project.tags || []).join(', ');
            this.container.querySelector('#project-workdir').value = project.default_workdir || '';

            // Fill Settings tab
            const settings = project.settings || {};

            // Execution Settings
            this.container.querySelector('#settings-default-runner').value = settings.default_runner || '';
            this.container.querySelector('#settings-provider-policy').value = settings.provider_policy || '';

            // Environment Variables
            this.clearEnvOverrides();
            if (settings.env_overrides) {
                Object.entries(settings.env_overrides).forEach(([key, value]) => {
                    this.addEnvOverride(key, value);
                });
            }

            // Risk Profile
            const riskProfile = settings.risk_profile || {};
            this.container.querySelector('#settings-allow-shell-write').checked = riskProfile.allow_shell_write || false;
            this.container.querySelector('#settings-require-admin-token').checked = riskProfile.require_admin_token || false;
            this.container.querySelector('#settings-writable-paths').value =
                (riskProfile.writable_paths || []).join('\n');

            // Reset to basic tab
            this.switchProjectTab('basic');

            // Show modal
            this.container.querySelector('#project-modal-title').textContent = 'Edit Project';
            const modal = this.container.querySelector('#project-modal');
            modal.style.display = 'flex';

        } catch (error) {
            console.error('Failed to load project for editing:', error);
            showToast('Failed to load project details', 'error');
        }
    }

    async submitProjectForm() {
        const projectId = this.container.querySelector('#project-id').value;
        const isEdit = !!projectId;

        // Collect basic form data
        const formData = {
            name: this.container.querySelector('#project-name').value.trim(),
            description: this.container.querySelector('#project-description').value.trim(),
            tags: this.container.querySelector('#project-tags').value
                .split(',')
                .map(t => t.trim())
                .filter(t => t.length > 0),
            default_workdir: this.container.querySelector('#project-workdir').value.trim() || null
        };

        // Collect Settings data
        const defaultRunner = this.container.querySelector('#settings-default-runner').value;
        const providerPolicy = this.container.querySelector('#settings-provider-policy').value;
        const envOverrides = this.collectEnvOverrides();
        const writablePaths = this.container.querySelector('#settings-writable-paths').value
            .split('\n')
            .map(p => p.trim())
            .filter(p => p.length > 0);

        formData.settings = {
            default_runner: defaultRunner || null,
            provider_policy: providerPolicy || null,
            env_overrides: envOverrides,
            risk_profile: {
                allow_shell_write: this.container.querySelector('#settings-allow-shell-write').checked,
                require_admin_token: this.container.querySelector('#settings-require-admin-token').checked,
                writable_paths: writablePaths
            }
        };

        // Validate
        if (!formData.name) {
            showToast('Project name is required', 'error');
            return;
        }

        try {
            const url = isEdit ? `/api/projects/${projectId}` : '/api/projects';
            const method = isEdit ? 'PATCH' : 'POST';

            const result = await apiClient.request(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            if (!result.ok) {
                showToast(`Failed to ${isEdit ? 'update' : 'create'} project: ${result.message}`, 'error');
                return;
            }

            // Success
            this.closeProjectModal();
            showToast(`Project ${isEdit ? 'updated' : 'created'} successfully`, 'success');
            this.loadProjects();

        } catch (error) {
            console.error(`Failed to ${isEdit ? 'update' : 'create'} project:`, error);
            showToast(`Failed to ${isEdit ? 'update' : 'create'} project`, 'error');
        }
    }

    showProjectMenu(projectId, buttonElement) {
        // Remove any existing menus
        document.querySelectorAll('.dropdown-menu').forEach(menu => menu.remove());

        // Create dropdown menu
        const menu = document.createElement('div');
        menu.className = 'dropdown-menu';
        menu.innerHTML = `
            <a href="#" class="dropdown-item" data-action="export">
                <span class="material-icons md-16">arrow_downward</span> Export Snapshot
            </a>
            <a href="#" class="dropdown-item" data-action="history">
                <span class="material-icons md-16">history</span> Snapshot History
            </a>
            <div class="dropdown-divider"></div>
            <a href="#" class="dropdown-item" data-action="archive">
                <span class="material-icons md-16">archive</span> Archive
            </a>
            <a href="#" class="dropdown-item danger" data-action="delete">
                <span class="material-icons md-16">delete</span> Delete
            </a>
        `;

        // Position the menu
        const rect = buttonElement.getBoundingClientRect();
        menu.style.position = 'absolute';
        menu.style.top = `${rect.bottom + window.scrollY}px`;
        menu.style.left = `${rect.left + window.scrollX - 150}px`;

        document.body.appendChild(menu);

        // Handle menu clicks
        menu.querySelectorAll('.dropdown-item').forEach(item => {
            item.addEventListener('click', async (e) => {
                e.preventDefault();
                const action = item.getAttribute('data-action');

                if (action === 'export') {
                    await this.exportProjectSnapshot(projectId);
                } else if (action === 'history') {
                    await this.showSnapshotHistory(projectId);
                } else if (action === 'archive') {
                    await this.archiveProject(projectId);
                } else if (action === 'delete') {
                    await this.deleteProject(projectId);
                }

                menu.remove();
            });
        });

        // Close menu when clicking outside
        setTimeout(() => {
            const closeMenu = (e) => {
                if (!menu.contains(e.target) && e.target !== buttonElement) {
                    menu.remove();
                    document.removeEventListener('click', closeMenu);
                }
            };
            document.addEventListener('click', closeMenu);
        }, 0);
    }

    async archiveProject(projectId) {
        const confirmed = await Dialog.confirm(
            'Archive this project? Tasks will be preserved and you can restore it later.',
            {
                title: 'Archive Project',
                confirmText: 'Archive',
                confirmClass: 'btn-primary'
            }
        );
        
        if (!confirmed) return;
        
        try {
            const result = await apiClient.request(`/api/projects/${projectId}/archive`, {
                method: 'POST'
            });
            
            if (!result.ok) {
                showToast(`Failed to archive project: ${result.message}`, 'error');
                return;
            }
            
            showToast('Project archived successfully', 'success');
            this.loadProjects();
            
        } catch (error) {
            console.error('Failed to archive project:', error);
            showToast('Failed to archive project', 'error');
        }
    }

    async deleteProject(projectId) {
        const confirmed = await Dialog.confirm(
            'Delete this project? This cannot be undone. Only empty projects can be deleted.',
            {
                title: 'Delete Project',
                confirmText: 'Delete',
                danger: true
            }
        );
        
        if (!confirmed) return;
        
        try {
            const result = await apiClient.request(`/api/projects/${projectId}`, {
                method: 'DELETE'
            });
            
            if (!result.ok) {
                // Show friendly error for non-empty projects
                if (result.message?.includes('tasks') || result.message?.includes('repositories')) {
                    showToast('Cannot delete project with existing tasks or repositories. Please archive instead.', 'error', 5000);
                } else {
                    showToast(`Failed to delete project: ${result.message}`, 'error');
                }
                return;
            }
            
            showToast('Project deleted successfully', 'success');
            this.loadProjects();
            
        } catch (error) {
            console.error('Failed to delete project:', error);
            showToast('Failed to delete project', 'error');
        }
    }

    closeProjectModal() {
        const modal = this.container.querySelector('#project-modal');
        modal.style.display = 'none';
        this.currentEditingProjectId = null;
    }

    // ==================== Task Graph Methods ====================

    switchTab(container, tabName) {
        // Update button states
        container.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.getAttribute('data-tab') === tabName) {
                btn.classList.add('active');
            }
        });

        // Update content visibility
        container.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        container.querySelector(`#tab-${tabName}`)?.classList.add('active');
    }

    async renderTaskGraph(projectId) {
        const container = document.getElementById('task-graph-container');
        if (!container) return;

        try {
            // Show loading state
            container.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 100%;"><div class="loading-spinner">Loading task graph...</div></div>';

            // Fetch graph data
            const response = await apiClient.get(`/api/projects/${projectId}/task-graph`);

            if (!response.ok) {
                container.innerHTML = `<div class="error-message">Failed to load task graph: ${response.message}</div>`;
                return;
            }

            const data = response.data;

            // Check if there are any tasks
            if (!data.nodes || data.nodes.length === 0) {
                container.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 100%; color: #999;">No tasks found for this project</div>';
                document.getElementById('graph-legend').innerHTML = '';
                return;
            }

            // Prepare vis.js data
            const nodes = new vis.DataSet(
                data.nodes.map(node => ({
                    id: node.task_id,
                    label: this.truncateText(node.title, 30),
                    title: `${node.title}\nStatus: ${node.status}\nRepos: ${node.repos.length}\nCreated: ${this.formatTimestamp(node.created_at)}`,
                    color: this.getNodeColor(node),
                    shape: 'box',
                    font: { size: 14, color: '#333' },
                    borderWidth: 2,
                    margin: 10
                }))
            );

            const edges = new vis.DataSet(
                data.edges.map(edge => ({
                    from: edge.from,
                    to: edge.to,
                    label: edge.type,
                    title: edge.reason || edge.type,
                    arrows: 'to',
                    color: this.getEdgeColor(edge.type),
                    width: 2,
                    font: { size: 10, color: '#666', align: 'middle' }
                }))
            );

            // Create network
            const graphData = { nodes, edges };
            const options = {
                layout: {
                    hierarchical: {
                        direction: 'UD',
                        sortMethod: 'directed',
                        nodeSpacing: 150,
                        levelSeparation: 200
                    }
                },
                physics: {
                    enabled: true,
                    hierarchicalRepulsion: {
                        nodeDistance: 150
                    }
                },
                interaction: {
                    hover: true,
                    tooltipDelay: 100,
                    navigationButtons: true,
                    keyboard: true
                },
                nodes: {
                    borderWidth: 2,
                    font: { size: 14 }
                },
                edges: {
                    smooth: {
                        type: 'cubicBezier',
                        forceDirection: 'vertical'
                    }
                }
            };

            // Clear container and create network
            container.innerHTML = '';
            const network = new vis.Network(container, graphData, options);

            // Handle node clicks
            network.on('click', (params) => {
                if (params.nodes.length > 0) {
                    const taskId = params.nodes[0];
                    // Navigate to task detail
                    window.location.hash = `#/tasks?id=${taskId}`;
                }
            });

            // Render legend
            this.renderGraphLegend(data.repos);

        } catch (err) {
            console.error('Failed to render task graph:', err);
            container.innerHTML = '<div class="error-message">Failed to load task graph</div>';
        }
    }

    getNodeColor(node) {
        // Color based on task status
        const statusColors = {
            'completed': { background: '#d4edda', border: '#28a745' },
            'succeeded': { background: '#d4edda', border: '#28a745' },
            'running': { background: '#fff3cd', border: '#ffc107' },
            'pending': { background: '#e7f3ff', border: '#007bff' },
            'failed': { background: '#f8d7da', border: '#dc3545' },
            'error': { background: '#f8d7da', border: '#dc3545' },
            'created': { background: '#e7f3ff', border: '#007bff' }
        };
        return statusColors[node.status] || statusColors['created'];
    }

    getEdgeColor(type) {
        const edgeColors = {
            'blocks': '#dc3545',
            'requires': '#ffc107',
            'suggests': '#6c757d'
        };
        return edgeColors[type] || '#6c757d';
    }

    renderGraphLegend(repos) {
        const legendContainer = document.getElementById('graph-legend');
        if (!legendContainer) return;

        legendContainer.innerHTML = `
            <div class="legend-section">
                <h4>Repositories</h4>
                ${repos.length > 0 ? repos.map(repo => `
                    <div class="legend-item">
                        <span class="legend-color" style="background-color: ${repo.color}"></span>
                        <span>${this.escapeHtml(repo.name)} (${repo.role})</span>
                    </div>
                `).join('') : '<p class="text-muted">No repositories</p>'}
            </div>
            <div class="legend-section">
                <h4>Task Status</h4>
                <div class="legend-item">
                    <span class="legend-status completed"></span>
                    <span>Completed</span>
                </div>
                <div class="legend-item">
                    <span class="legend-status running"></span>
                    <span>Running</span>
                </div>
                <div class="legend-item">
                    <span class="legend-status failed"></span>
                    <span>Failed</span>
                </div>
                <div class="legend-item">
                    <span class="legend-status created"></span>
                    <span>Created/Pending</span>
                </div>
            </div>
            <div class="legend-section">
                <h4>Dependencies</h4>
                <div class="legend-item">
                    <span class="legend-arrow blocks"></span>
                    <span>Blocks (must complete first)</span>
                </div>
                <div class="legend-item">
                    <span class="legend-arrow requires"></span>
                    <span>Requires (soft dependency)</span>
                </div>
                <div class="legend-item">
                    <span class="legend-arrow suggests"></span>
                    <span>Suggests (weak dependency)</span>
                </div>
            </div>
        `;
    }

    truncateText(text, maxLength) {
        if (!text) return '';
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }

    // ==================== Snapshot Methods ====================

    async exportProjectSnapshot(projectId) {
        try {
            // Show loading toast
            showToast('Creating snapshot...', 'info', 3000);

            // Create snapshot
            const result = await apiClient.post(`/api/projects/${projectId}/snapshot`);

            if (!result.ok) {
                showToast(`Failed to create snapshot: ${result.message}`, 'error');
                return;
            }

            const snapshot = result.data;

            // Download JSON file
            const blob = new Blob([JSON.stringify(snapshot, null, 2)], {
                type: 'application/json'
            });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${snapshot.project.name}-snapshot-${snapshot.snapshot_id}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            showToast('Snapshot created and downloaded', 'success');

        } catch (err) {
            console.error('Export failed:', err);
            showToast('Failed to export snapshot: ' + err.message, 'error');
        }
    }

    async showSnapshotHistory(projectId) {
        try {
            const result = await apiClient.get(`/api/projects/${projectId}/snapshots`);

            if (!result.ok) {
                showToast('Failed to load snapshot history', 'error');
                return;
            }

            const data = result.data;

            // Create and show modal
            const modalHtml = `
                <div id="snapshot-history-modal" class="modal" style="display: flex;">
                    <div class="modal-overlay"></div>
                    <div class="modal-content" style="max-width: 700px;">
                        <div class="modal-header">
                            <h2>Snapshot History</h2>
                            <button class="modal-close" id="close-snapshot-modal">&times;</button>
                        </div>
                        <div class="modal-body">
                            ${data.snapshots.length > 0 ? `
                                <table class="table" style="width: 100%;">
                                    <thead>
                                        <tr>
                                            <th>Snapshot ID</th>
                                            <th>Created At</th>
                                            <th style="text-align: right;">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${data.snapshots.map(snap => `
                                            <tr>
                                                <td><code class="code-inline">${snap.snapshot_id}</code></td>
                                                <td>${this.formatTimestamp(snap.created_at)}</td>
                                                <td style="text-align: right;">
                                                    <button class="btn-primary btn-sm btn-download-snapshot"
                                                            data-project-id="${projectId}"
                                                            data-snapshot-id="${snap.snapshot_id}">
                                                        <span class="material-icons md-16">arrow_downward</span> Download
                                                    </button>
                                                </td>
                                            </tr>
                                        `).join('')}
                                    </tbody>
                                </table>
                            ` : `
                                <div class="empty-state" style="padding: 40px 20px;">
                                    <div class="empty-icon">
                                        <span class="material-icons md-48">history</span>
                                    </div>
                                    <p class="text-muted">No snapshots yet</p>
                                </div>
                            `}
                        </div>
                    </div>
                </div>
            `;

            // Remove any existing modal
            const existingModal = document.getElementById('snapshot-history-modal');
            if (existingModal) {
                existingModal.remove();
            }

            // Insert modal
            document.body.insertAdjacentHTML('beforeend', modalHtml);

            // Setup event listeners
            const modal = document.getElementById('snapshot-history-modal');
            const closeBtn = document.getElementById('close-snapshot-modal');

            closeBtn.addEventListener('click', () => {
                modal.remove();
            });

            modal.querySelector('.modal-overlay').addEventListener('click', () => {
                modal.remove();
            });

            // Setup download buttons
            modal.querySelectorAll('.btn-download-snapshot').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const snapshotId = btn.getAttribute('data-snapshot-id');
                    await this.downloadSnapshot(projectId, snapshotId);
                });
            });

        } catch (err) {
            console.error('Failed to load snapshot history:', err);
            showToast('Failed to load snapshot history', 'error');
        }
    }

    async downloadSnapshot(projectId, snapshotId) {
        try {
            const result = await apiClient.get(`/api/projects/${projectId}/snapshots/${snapshotId}`);

            if (!result.ok) {
                showToast('Failed to download snapshot', 'error');
                return;
            }

            const snapshot = result.data;

            // Download
            const blob = new Blob([JSON.stringify(snapshot, null, 2)], {
                type: 'application/json'
            });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `snapshot-${snapshotId}.json`;
            a.click();
            URL.revokeObjectURL(url);

            showToast('Snapshot downloaded', 'success');
        } catch (err) {
            console.error('Failed to download snapshot:', err);
            showToast('Failed to download snapshot', 'error');
        }
    }

    destroy() {
        // Cleanup
        this.container.innerHTML = '';
    }
}

// Export
window.ProjectsView = ProjectsView;
