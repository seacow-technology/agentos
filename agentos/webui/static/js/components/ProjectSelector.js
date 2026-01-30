/**
 * ProjectSelector Component - Navbar project context selector
 *
 * Task #18: UI displays current Project context
 *
 * Features:
 * - Dropdown selector for switching projects
 * - Displays current project or "All Projects"
 * - Syncs with ProjectContext service
 * - Auto-refreshes views on change
 */

class ProjectSelector {
    constructor(container) {
        this.container = container;
        this.isOpen = false;

        this.render();
        this.setupEventListeners();
        this.subscribeToContext();
    }

    /**
     * Render the project selector UI
     */
    render() {
        const currentProject = window.projectContext.getCurrentProject();
        const currentProjectName = currentProject ? currentProject.name : 'All Projects';

        this.container.innerHTML = `
            <div class="project-selector">
                <span class="project-label">Project:</span>
                <div class="project-dropdown" id="project-dropdown">
                    <button class="project-dropdown-toggle" id="project-dropdown-toggle">
                        <span class="project-name" id="current-project-name">${this.escapeHtml(currentProjectName)}</span>
                        <span class="material-icons md-16">arrow_drop_down</span>
                    </button>
                    <div class="project-dropdown-menu hidden" id="project-dropdown-menu">
                        <div class="dropdown-menu-content">
                            <!-- Projects will be loaded here -->
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.loadProjects();
    }

    /**
     * Load and render projects list
     */
    async loadProjects() {
        const menu = this.container.querySelector('.dropdown-menu-content');
        const projects = window.projectContext.getProjects();
        const currentProjectId = window.projectContext.getCurrentProjectId();

        if (!menu) return;

        // Show loading state
        menu.innerHTML = '<div class="dropdown-loading">Loading...</div>';

        // Reload projects if empty
        if (projects.length === 0) {
            await window.projectContext.loadProjects();
        }

        const updatedProjects = window.projectContext.getProjects();

        // Render projects list
        menu.innerHTML = `
            <div class="dropdown-item ${!currentProjectId ? 'active' : ''}" data-project-id="">
                <span class="material-icons md-16">apps</span>
                <span>All Projects</span>
                ${!currentProjectId ? '<span class="material-icons md-16">check</span>' : ''}
            </div>
            ${updatedProjects.length > 0 ? '<div class="dropdown-divider"></div>' : ''}
            ${updatedProjects.map(project => `
                <div class="dropdown-item ${project.project_id === currentProjectId ? 'active' : ''}"
                     data-project-id="${project.project_id}">
                    <span class="material-icons md-16">folder</span>
                    <span>${this.escapeHtml(project.name)}</span>
                    ${project.project_id === currentProjectId ? '<span class="material-icons md-16">check</span>' : ''}
                </div>
            `).join('')}
            ${updatedProjects.length === 0 ? `
                <div class="dropdown-empty">
                    <span class="material-icons md-24">folder_open</span>
                    <p>No projects yet</p>
                    <a href="#/projects" class="dropdown-link">Create a project →</a>
                </div>
            ` : ''}
        `;

        // Setup item click handlers
        menu.querySelectorAll('.dropdown-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.stopPropagation();
                const projectId = item.getAttribute('data-project-id');
                this.selectProject(projectId || null);
            });
        });
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        const toggle = this.container.querySelector('#project-dropdown-toggle');
        const menu = this.container.querySelector('#project-dropdown-menu');

        if (!toggle || !menu) return;

        // Toggle dropdown
        toggle.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleDropdown();
        });

        // Close on outside click
        document.addEventListener('click', (e) => {
            if (!this.container.contains(e.target)) {
                this.closeDropdown();
            }
        });

        // Close on escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen) {
                this.closeDropdown();
            }
        });
    }

    /**
     * Subscribe to context changes
     */
    subscribeToContext() {
        window.projectContext.addListener((context) => {
            this.updateCurrentProject(context);
        });
    }

    /**
     * Update displayed current project
     */
    updateCurrentProject(context) {
        const nameElement = this.container.querySelector('#current-project-name');
        if (!nameElement) return;

        const displayName = context.project ? context.project.name : 'All Projects';
        nameElement.textContent = displayName;

        // Update active state in menu
        this.loadProjects();
    }

    /**
     * Toggle dropdown open/closed
     */
    toggleDropdown() {
        if (this.isOpen) {
            this.closeDropdown();
        } else {
            this.openDropdown();
        }
    }

    /**
     * Open dropdown
     */
    openDropdown() {
        const menu = this.container.querySelector('#project-dropdown-menu');
        const toggle = this.container.querySelector('#project-dropdown-toggle');

        if (!menu || !toggle) return;

        menu.classList.remove('hidden');
        toggle.classList.add('active');
        this.isOpen = true;

        // Reload projects when opening
        this.loadProjects();
    }

    /**
     * Close dropdown
     */
    closeDropdown() {
        const menu = this.container.querySelector('#project-dropdown-menu');
        const toggle = this.container.querySelector('#project-dropdown-toggle');

        if (!menu || !toggle) return;

        menu.classList.add('hidden');
        toggle.classList.remove('active');
        this.isOpen = false;
    }

    /**
     * Select a project
     */
    async selectProject(projectId) {
        this.closeDropdown();

        // Update context
        await window.projectContext.setCurrentProject(projectId);

        // Refresh current view
        if (typeof loadView === 'function' && window.state?.currentView) {
            loadView(window.state.currentView);
        }

        // Show toast
        const projectName = projectId
            ? window.projectContext.getProjectName(projectId)
            : 'All Projects';

        if (typeof showToast === 'function') {
            showToast(`Switched to: ${projectName}`, 'success', 2000);
        }
    }

    /**
     * Escape HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Destroy component
     */
    destroy() {
        this.container.innerHTML = '';
    }
}

// Export
window.ProjectSelector = ProjectSelector;
