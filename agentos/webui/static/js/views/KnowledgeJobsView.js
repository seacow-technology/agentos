/**
 * KnowledgeJobsView - Index Jobs Tracking
 *
 * Phase 3: Index Jobs (Knowledge/RAG Workbench)
 * Coverage: GET /api/knowledge/jobs, POST /api/knowledge/jobs, GET /api/knowledge/jobs/{id}
 * WebSocket: Listen for task.progress events
 */

class KnowledgeJobsView {
    constructor(container) {
        this.container = container;
        this.dataTable = null;
        this.jobs = [];
        this.websocket = null;
        this.refreshInterval = null;
        this.currentJobId = null;

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="knowledge-jobs-view">
                <div class="view-header">
                    <div>
                        <h1>Index Jobs</h1>
                        <p class="text-sm text-gray-600 mt-1">Monitor knowledge indexing jobs and status</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-primary" id="jobs-trigger-incremental">
                            <span class="material-icons md-18">refresh</span> Incremental
                        </button>
                        <button class="btn-primary" id="jobs-trigger-rebuild">
                            <span class="material-icons md-18">refresh</span> Rebuild
                        </button>
                        <button class="btn-secondary" id="jobs-trigger-repair">
                            <span class="material-icons md-18">build</span> Repair
                        </button>
                        <button class="btn-secondary" id="jobs-trigger-vacuum">
                            <span class="material-icons md-18">delete_sweep</span> Vacuum
                        </button>
                        <button class="btn-refresh" id="jobs-refresh">
                            <span class="material-icons md-18">refresh</span> Refresh
                        </button>
                        <button class="btn-secondary" id="jobs-cleanup-stale">
                            <span class="material-icons md-18">delete_sweep</span> Clean Stale
                        </button>
                    </div>
                </div>

                <div id="jobs-table" class="table-section"></div>

                <div id="jobs-detail-drawer" class="drawer hidden">
                    <div class="drawer-overlay" id="jobs-drawer-overlay"></div>
                    <div class="drawer-content">
                        <div class="drawer-header">
                            <h3>Job Details</h3>
                            <button class="btn-close" id="jobs-drawer-close">close</button>
                        </div>
                        <div class="drawer-body" id="jobs-drawer-body">
                            <!-- Job details will be rendered here -->
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.setupDataTable();
        this.setupEventListeners();
        this.setupWebSocket();
        this.loadJobs();
        this.startAutoRefresh();
    }

    setupDataTable() {
        const tableContainer = this.container.querySelector('#jobs-table');

        this.dataTable = new DataTable(tableContainer, {
            columns: [
                {
                    key: 'job_id',
                    label: 'Job ID',
                    width: '120px',
                    render: (value) => `<span class="font-mono text-xs">${value.substring(0, 8)}</span>`
                },
                {
                    key: 'type',
                    label: 'Type',
                    width: '120px',
                    render: (value) => this.renderJobType(value)
                },
                {
                    key: 'status',
                    label: 'Status',
                    width: '120px',
                    render: (value) => this.renderStatus(value)
                },
                {
                    key: 'progress',
                    label: 'Progress',
                    width: '200px',
                    render: (value, row) => this.renderProgress(value, row.message)
                },
                {
                    key: 'files_processed',
                    label: 'Files',
                    width: '80px',
                    render: (value) => (value !== null && value !== undefined) ? value.toLocaleString() : '0'
                },
                {
                    key: 'chunks_processed',
                    label: 'Chunks',
                    width: '80px',
                    render: (value) => (value !== null && value !== undefined) ? value.toLocaleString() : '0'
                },
                {
                    key: 'errors',
                    label: 'Errors',
                    width: '80px',
                    render: (value) => value > 0 ? `<span class="text-red-600">${value}</span>` : value
                },
                {
                    key: 'duration_ms',
                    label: 'Duration',
                    width: '100px',
                    render: (value) => value ? this.formatDuration(value) : '-'
                },
                {
                    key: 'created_at',
                    label: 'Created',
                    width: '180px',
                    render: (value) => this.formatTimestamp(value)
                }
            ],
            onRowClick: (row) => this.showJobDetails(row.job_id),
            emptyMessage: 'No index jobs found. Trigger a job to get started.',
            pagination: true,
            pageSize: 10
        });
    }

    setupEventListeners() {
        // Trigger buttons
        this.container.querySelector('#jobs-trigger-incremental').addEventListener('click', () => {
            this.triggerJob('incremental');
        });

        this.container.querySelector('#jobs-trigger-rebuild').addEventListener('click', () => {
            this.triggerJob('rebuild');
        });

        this.container.querySelector('#jobs-trigger-repair').addEventListener('click', () => {
            this.triggerJob('repair');
        });

        this.container.querySelector('#jobs-trigger-vacuum').addEventListener('click', () => {
            this.triggerJob('vacuum');
        });

        // Refresh button
        this.container.querySelector('#jobs-refresh').addEventListener('click', () => {
            this.loadJobs();
        });

        // Cleanup stale jobs button
        this.container.querySelector('#jobs-cleanup-stale').addEventListener('click', async () => {
            await this.cleanupStaleJobs();
        });

        // Drawer close
        this.container.querySelector('#jobs-drawer-close').addEventListener('click', () => {
            this.closeDrawer();
        });

        this.container.querySelector('#jobs-drawer-overlay').addEventListener('click', () => {
            this.closeDrawer();
        });
    }

    setupWebSocket() {
        // Use global WebSocket if available, otherwise create new one
        if (window.state && window.state.websocket) {
            this.websocket = window.state.websocket;

            // Add event listener for WebSocket messages
            const originalOnMessage = this.websocket.onmessage;
            this.websocket.onmessage = (event) => {
                // Call original handler
                if (originalOnMessage) {
                    originalOnMessage(event);
                }

                // Handle our events
                this.handleWebSocketMessage(event);
            };
        } else {
            // Create new WebSocket connection
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/events`;

            this.websocket = new WebSocket(wsUrl);

            this.websocket.onopen = () => {
                console.log('KnowledgeJobsView: WebSocket connected');
            };

            this.websocket.onmessage = (event) => {
                this.handleWebSocketMessage(event);
            };

            this.websocket.onerror = (error) => {
                console.error('KnowledgeJobsView: WebSocket error:', error);
            };

            this.websocket.onclose = () => {
                console.log('KnowledgeJobsView: WebSocket closed');
                // Attempt to reconnect after 5 seconds
                setTimeout(() => {
                    this.setupWebSocket();
                }, 5000);
            };
        }
    }

    handleWebSocketMessage(event) {
        try {
            const data = JSON.parse(event.data);

            // Debug: Log all received WebSocket messages
            console.log('KnowledgeJobsView: WebSocket message received:', data);

            // Only handle task.progress events
            if (data.type === 'task.progress' || data.type === 'task.completed' || data.type === 'task.failed') {
                const taskId = data.entity ? data.entity.id : null;

                if (taskId) {
                    // Check if this is a KB index task by looking at our current jobs
                    const job = this.jobs.find(j => j.job_id === taskId);

                    if (job) {
                        // Update job in real-time
                        this.updateJobFromEvent(taskId, data);
                    }
                }
            }
        } catch (err) {
            console.error('KnowledgeJobsView: Failed to parse WebSocket message:', err);
        }
    }

    async updateJobFromEvent(jobId, event) {
        // Update the job in our local list
        const jobIndex = this.jobs.findIndex(j => j.job_id === jobId);

        if (jobIndex !== -1) {
            // Ensure payload exists
            const payload = event.payload || {};

            if (event.type === 'task.progress') {
                // Update progress and message
                if (payload.progress !== undefined) {
                    this.jobs[jobIndex].progress = payload.progress;
                }
                if (payload.message) {
                    this.jobs[jobIndex].message = payload.message;
                }
                // Update status if task is now in_progress (from created)
                if (this.jobs[jobIndex].status === 'created') {
                    this.jobs[jobIndex].status = 'in_progress';
                }
            } else if (event.type === 'task.completed') {
                this.jobs[jobIndex].status = 'completed';
                this.jobs[jobIndex].progress = 100;
                this.jobs[jobIndex].message = 'Completed';
                if (payload.duration_ms) {
                    this.jobs[jobIndex].duration_ms = payload.duration_ms;
                }
                if (payload.stats) {
                    Object.assign(this.jobs[jobIndex], payload.stats);
                }
            } else if (event.type === 'task.failed') {
                this.jobs[jobIndex].status = 'failed';
                this.jobs[jobIndex].message = payload.error || 'Failed';
            }

            // Refresh table
            this.dataTable.setData(this.jobs);

            // If drawer is open for this job, refresh it
            if (this.currentJobId === jobId) {
                this.showJobDetails(jobId);
            }
        } else {
            // Job not in list, refresh the list
            this.loadJobs();
        }
    }

    async loadJobs() {
        try {
            const response = await fetch('/api/knowledge/jobs?limit=100');
            const result = await response.json();

            if (result.ok) {
                this.jobs = result.data;
                this.dataTable.setData(this.jobs);
            } else {
                Toast.error('Failed to load jobs: ' + (result.error || 'Unknown error'));
            }
        } catch (err) {
            console.error('Failed to load jobs:', err);
            Toast.error('Failed to load jobs: ' + err.message);
        }
    }

    async triggerJob(type) {
        try {
            const response = await fetch('/api/knowledge/jobs', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ type })
            });

            const result = await response.json();

            if (result.ok) {
                Toast.success(`${type} job triggered successfully`);
                // Reload jobs after a short delay
                setTimeout(() => {
                    this.loadJobs();
                }, 500);
            } else {
                Toast.error('Failed to trigger job: ' + (result.error || 'Unknown error'));
            }
        } catch (err) {
            console.error('Failed to trigger job:', err);
            Toast.error('Failed to trigger job: ' + err.message);
        }
    }

    async cleanupStaleJobs() {
        try {
            // Confirm with user
            const confirmed = await Dialog.confirm(
                'This will mark all stale jobs (inactive for 1+ hours) as failed. Continue?',
                {
                    title: 'Clean Stale Jobs',
                    confirmText: 'Clean',
                    danger: true
                }
            );

            if (!confirmed) return;

            // Show loading toast
            Toast.info('Cleaning stale jobs...');

            // Call API
            const response = await fetch('/api/knowledge/jobs/cleanup', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    older_than_hours: 1
                })
            });

            const result = await response.json();

            if (result.ok) {
                if (result.cleaned_count > 0) {
                    Toast.success(`Cleaned ${result.cleaned_count} stale job(s)`);
                    // Reload the list
                    this.loadJobs();
                } else {
                    Toast.info('No stale jobs found');
                }
            } else {
                Toast.error('Failed to clean jobs: ' + (result.error || 'Unknown error'));
            }
        } catch (err) {
            console.error('Failed to cleanup stale jobs:', err);
            Toast.error('Failed to cleanup stale jobs: ' + err.message);
        }
    }

    async showJobDetails(jobId) {
        this.currentJobId = jobId;

        try {
            const response = await fetch(`/api/knowledge/jobs/${jobId}`);
            const result = await response.json();

            if (result.ok) {
                const job = result.data;
                this.renderJobDetails(job);
                this.openDrawer();
            } else {
                Toast.error('Failed to load job details: ' + (result.error || 'Unknown error'));
            }
        } catch (err) {
            console.error('Failed to load job details:', err);
            Toast.error('Failed to load job details: ' + err.message);
        }
    }

    renderJobDetails(job) {
        const drawerBody = this.container.querySelector('#jobs-drawer-body');

        drawerBody.innerHTML = `
            <div class="job-details">
                <div class="detail-section">
                    <h4>Overview</h4>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <span class="detail-label">Job ID:</span>
                            <span class="detail-value font-mono">${job.job_id}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Type:</span>
                            <span class="detail-value">${this.renderJobType(job.type)}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Status:</span>
                            <span class="detail-value">${this.renderStatus(job.status)}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Progress:</span>
                            <span class="detail-value">${this.renderProgress(job.progress, job.message)}</span>
                        </div>
                    </div>
                </div>

                <div class="detail-section">
                    <h4>Statistics</h4>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <span class="detail-label">Files Processed:</span>
                            <span class="detail-value">${job.files_processed.toLocaleString()}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Chunks Processed:</span>
                            <span class="detail-value">${job.chunks_processed.toLocaleString()}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Errors:</span>
                            <span class="detail-value ${job.errors > 0 ? 'text-red-600' : ''}">${job.errors}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Duration:</span>
                            <span class="detail-value">${job.duration_ms ? this.formatDuration(job.duration_ms) : 'In progress...'}</span>
                        </div>
                    </div>
                </div>

                <div class="detail-section">
                    <h4>Timeline</h4>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <span class="detail-label">Created:</span>
                            <span class="detail-value">${this.formatTimestamp(job.created_at)}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Updated:</span>
                            <span class="detail-value">${this.formatTimestamp(job.updated_at)}</span>
                        </div>
                    </div>
                </div>

                <div class="detail-section">
                    <h4>Related</h4>
                    <div class="related-links">
                        <a href="#" class="related-link" onclick="loadView('events'); return false;">
                            View Events (filter by task_id: ${job.job_id.substring(0, 8)})
                        </a>
                        <a href="#" class="related-link" onclick="loadView('logs'); return false;">
                            View Logs (filter by task_id: ${job.job_id.substring(0, 8)})
                        </a>
                    </div>
                </div>
            </div>
        `;
    }

    renderJobType(type) {
        const badges = {
            'incremental': '<span class="badge badge-blue">Incremental</span>',
            'rebuild': '<span class="badge badge-purple">Rebuild</span>',
            'repair': '<span class="badge badge-orange">Repair</span>',
            'vacuum': '<span class="badge badge-green">Vacuum</span>'
        };
        return badges[type] || `<span class="badge badge-gray">${type}</span>`;
    }

    renderStatus(status) {
        const badges = {
            'created': '<span class="status-badge status-info">Pending...</span>',
            'in_progress': '<span class="status-badge status-warning">In Progress</span>',
            'completed': '<span class="status-badge status-success">Completed</span>',
            'failed': '<span class="status-badge status-error">Failed</span>'
        };
        return badges[status] || `<span class="status-badge status-gray">${status}</span>`;
    }

    renderProgress(progress, message) {
        const percentage = Math.min(100, Math.max(0, progress || 0));
        const messageText = message || `${percentage}%`;

        return `
            <div class="progress-container">
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${percentage}%"></div>
                </div>
                <div class="progress-text">${messageText}</div>
            </div>
        `;
    }

    formatTimestamp(timestamp) {
        if (!timestamp) return '-';

        try {
            const date = new Date(timestamp);
            const now = new Date();
            const diff = now - date;

            // If less than 1 minute ago
            if (diff < 60000) {
                return 'Just now';
            }

            // If less than 1 hour ago
            if (diff < 3600000) {
                const minutes = Math.floor(diff / 60000);
                return `${minutes}m ago`;
            }

            // If less than 24 hours ago
            if (diff < 86400000) {
                const hours = Math.floor(diff / 3600000);
                return `${hours}h ago`;
            }

            // Otherwise show date
            return date.toLocaleString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (err) {
            return timestamp;
        }
    }

    formatDuration(ms) {
        if (!ms) return '-';

        const seconds = Math.floor(ms / 1000);

        if (seconds < 60) {
            return `${seconds}s`;
        }

        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;

        if (minutes < 60) {
            return `${minutes}m ${remainingSeconds}s`;
        }

        const hours = Math.floor(minutes / 60);
        const remainingMinutes = minutes % 60;

        return `${hours}h ${remainingMinutes}m`;
    }

    openDrawer() {
        const drawer = this.container.querySelector('#jobs-detail-drawer');
        drawer.classList.remove('hidden');
        setTimeout(() => {
            drawer.classList.add('open');
        }, 10);
    }

    closeDrawer() {
        const drawer = this.container.querySelector('#jobs-detail-drawer');
        drawer.classList.remove('open');
        setTimeout(() => {
            drawer.classList.add('hidden');
            this.currentJobId = null;
        }, 300);
    }

    startAutoRefresh() {
        // Refresh every 2 seconds if there are in-progress jobs
        // Faster polling for better real-time experience
        this.refreshInterval = setInterval(() => {
            const hasInProgress = this.jobs.some(j => j.status === 'in_progress' || j.status === 'created');
            if (hasInProgress) {
                this.loadJobs();
            }
        }, 2000);
    }

    cleanup() {
        // Clear refresh interval
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }

        // Note: We don't close the WebSocket here as it might be shared
        this.currentJobId = null;
    }

    destroy() {
        // Call cleanup
        this.cleanup();

        // Clean up components
        if (this.dataTable && typeof this.dataTable.destroy === 'function') {
            this.dataTable.destroy();
        }

        // Clear container
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}

// Render function for main.js integration
function renderKnowledgeJobsView(container) {
    // Cleanup previous instance if exists
    if (window.state && window.state.currentViewInstance && window.state.currentViewInstance.cleanup) {
        window.state.currentViewInstance.cleanup();
    }

    // Create new instance
    const view = new KnowledgeJobsView(container);

    // Store instance for cleanup
    if (window.state) {
        window.state.currentViewInstance = view;
    }
}
