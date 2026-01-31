/**
 * EventsView - Event Stream UI
 *
 * PR-2: Observability Module - Events View
 * Coverage: GET /api/events
 */

class EventsView {
    constructor(container) {
        this.container = container;
        this.filterBar = null;
        this.dataTable = null;
        this.currentFilters = {};
        this.events = [];
        this.streamMode = false;
        this.streamInterval = null;
        this.lastEventTimestamp = null;

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="events-view">
                <div class="view-header">
                    <div>
                        <h1>Event Stream</h1>
                        <p class="text-sm text-gray-600 mt-1">Live event stream and activity feed</p>
                    </div>
                    <div class="header-actions">
                        <div class="stream-toggle">
                            <label class="switch">
                                <input type="checkbox" id="events-stream-toggle">
                                <span class="slider"></span>
                            </label>
                            <span class="toggle-label">Live Stream</span>
                        </div>
                        <button class="btn-refresh" id="events-refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                        <button class="btn-secondary" id="events-clear">
                            <span class="icon"><span class="material-icons md-18">delete</span></span> Clear
                        </button>
                    </div>
                </div>

                <div id="events-filter-bar" class="filter-section"></div>

                <div class="stream-status" id="events-stream-status" style="display: none;">
                    <div class="status-indicator pulsing"></div>
                    <span>Live streaming events...</span>
                </div>

                <div id="events-table" class="table-section"></div>

                <div id="events-detail-drawer" class="drawer hidden">
                    <div class="drawer-overlay" id="events-drawer-overlay"></div>
                    <div class="drawer-content">
                        <div class="drawer-header">
                            <h3>Event Details</h3>
                            <button class="btn-close" id="events-drawer-close">
                                <span class="material-icons">close</span>
                            </button>
                        </div>
                        <div class="drawer-body" id="events-drawer-body">
                            <!-- Event details will be rendered here -->
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.setupFilterBar();
        this.setupDataTable();
        this.setupEventListeners();
        this.loadEvents();
    }

    setupFilterBar() {
        const filterContainer = this.container.querySelector('#events-filter-bar');

        this.filterBar = new FilterBar(filterContainer, {
            filters: [
                {
                    type: 'text',
                    key: 'event_id',
                    label: 'Event ID',
                    placeholder: 'Filter by event ID...'
                },
                {
                    type: 'select',
                    key: 'type',
                    label: 'Event Type',
                    options: [
                        { value: '', label: 'All Types' },
                        { value: 'task.created', label: 'Task Created' },
                        { value: 'task.started', label: 'Task Started' },
                        { value: 'task.completed', label: 'Task Completed' },
                        { value: 'task.failed', label: 'Task Failed' },
                        { value: 'session.created', label: 'Session Created' },
                        { value: 'session.ended', label: 'Session Ended' },
                        { value: 'message.sent', label: 'Message Sent' },
                        { value: 'message.received', label: 'Message Received' },
                        { value: 'error', label: 'Error' },
                        { value: 'system', label: 'System' }
                    ]
                },
                {
                    type: 'text',
                    key: 'task_id',
                    label: 'Task ID',
                    placeholder: 'Filter by task...'
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
        const tableContainer = this.container.querySelector('#events-table');

        this.dataTable = new DataTable(tableContainer, {
            columns: [
                {
                    key: 'timestamp',
                    label: 'Timestamp',
                    width: '180px',
                    render: (value) => this.formatTimestamp(value)
                },
                {
                    key: 'type',
                    label: 'Type',
                    width: '200px',
                    render: (value) => this.renderEventType(value)
                },
                {
                    key: 'task_id',
                    label: 'Task',
                    width: '150px',
                    render: (value) => value ? `<code class="code-inline">${value.substring(0, 8)}...</code>` : 'N/A'
                },
                {
                    key: 'session_id',
                    label: 'Session',
                    width: '150px',
                    render: (value) => value ? `<code class="code-inline">${value.substring(0, 8)}...</code>` : 'N/A'
                },
                {
                    key: 'message',
                    label: 'Message',
                    width: '400px',
                    render: (value, row) => {
                        const msg = value || row.description || 'No message';
                        return msg.length > 60 ? msg.substring(0, 60) + '...' : msg;
                    }
                }
            ],
            data: [],
            emptyText: 'No events found',
            loadingText: 'Loading events...',
            onRowClick: (event) => this.showEventDetail(event),
            pagination: true,
            pageSize: 10
        });
    }

    setupEventListeners() {
        // Stream toggle
        this.container.querySelector('#events-stream-toggle').addEventListener('change', (e) => {
            this.toggleStreamMode(e.target.checked);
        });

        // Refresh button
        this.container.querySelector('#events-refresh').addEventListener('click', () => {
            this.loadEvents(true);
        });

        // Clear button
        this.container.querySelector('#events-clear').addEventListener('click', async () => {
            const confirmed = await Dialog.confirm('Clear all displayed events?', {
                title: 'Clear Events',
                confirmText: 'Clear',
                danger: true
            });
            if (confirmed) {
                this.events = [];
                this.dataTable.setData([]);
            }
        });

        // Drawer close
        this.container.querySelector('#events-drawer-close').addEventListener('click', () => {
            this.hideEventDetail();
        });

        this.container.querySelector('#events-drawer-overlay').addEventListener('click', () => {
            this.hideEventDetail();
        });

        // Keyboard shortcut
        const handleKeydown = (e) => {
            if (e.key === 'Escape' && !this.container.querySelector('#events-detail-drawer').classList.contains('hidden')) {
                this.hideEventDetail();
            }
        };
        document.addEventListener('keydown', handleKeydown);
    }

    handleFilterChange(filters) {
        this.currentFilters = filters;
        this.loadEvents();
    }

    async loadEvents(forceRefresh = false) {
        this.dataTable.setLoading(true);

        try {
            // Build query parameters (use only supported backend filters)
            const params = new URLSearchParams();

            if (this.currentFilters.type) {
                params.append('type', this.currentFilters.type);
            }
            if (this.currentFilters.task_id) {
                params.append('task_id', this.currentFilters.task_id);
            }
            if (this.currentFilters.session_id) {
                params.append('session_id', this.currentFilters.session_id);
            }

            // Always set a reasonable limit
            params.append('limit', '200');

            const url = `/api/events?${params.toString()}`;
            const result = await apiClient.get(url, {
                requestId: `events-list-${Date.now()}`
            });

            if (result.ok) {
                // Backend returns array directly
                const eventsData = Array.isArray(result.data) ? result.data : (result.data.events || []);

                this.events = eventsData;

                // Apply client-side filters for unsupported backend filters
                if (this.currentFilters.event_id) {
                    this.events = this.events.filter(e =>
                        e.id && e.id.includes(this.currentFilters.event_id)
                    );
                }

                // Backend already sorts by timestamp (newest first), but ensure it
                this.events.sort((a, b) => {
                    const timeA = new Date(a.timestamp || a.created_at || 0);
                    const timeB = new Date(b.timestamp || b.created_at || 0);
                    return timeB - timeA;
                });

                // Update last event timestamp for streaming
                if (this.events.length > 0) {
                    this.lastEventTimestamp = this.events[0].timestamp || this.events[0].created_at;
                }

                this.dataTable.setData(this.events);

                if (forceRefresh) {
                    showToast(`Loaded ${this.events.length} event(s)`, 'success', 2000);
                }
            } else {
                const errorMsg = result.error || result.message || 'Unknown error';
                showToast(`Failed to load events: ${errorMsg}`, 'error');
                this.dataTable.setData([]);
            }
        } catch (error) {
            console.error('Failed to load events:', error);
            const errorMsg = error.message || String(error);
            showToast(`Failed to load events: ${errorMsg}`, 'error');
            this.dataTable.setData([]);
        } finally {
            this.dataTable.setLoading(false);
        }
    }

    toggleStreamMode(enabled) {
        this.streamMode = enabled;
        const statusBar = this.container.querySelector('#events-stream-status');

        if (enabled) {
            statusBar.style.display = 'flex';
            this.startStreaming();
        } else {
            statusBar.style.display = 'none';
            this.stopStreaming();
        }
    }

    startStreaming() {
        // Poll for new events every 3 seconds
        this.streamInterval = setInterval(() => {
            this.fetchNewEvents();
        }, 3000);

        // Initial fetch
        this.fetchNewEvents();
    }

    stopStreaming() {
        if (this.streamInterval) {
            clearInterval(this.streamInterval);
            this.streamInterval = null;
        }
    }

    async fetchNewEvents() {
        try {
            const params = new URLSearchParams();

            // Only fetch events after the last known timestamp
            if (this.lastEventTimestamp) {
                params.append('since', this.lastEventTimestamp);
            }

            // Apply current filters (backend now supports all filters)
            if (this.currentFilters.type) {
                params.append('type', this.currentFilters.type);
            }
            if (this.currentFilters.task_id) {
                params.append('task_id', this.currentFilters.task_id);
            }
            if (this.currentFilters.session_id) {
                params.append('session_id', this.currentFilters.session_id);
            }

            // Set reasonable limit for streaming
            params.append('limit', '50');

            const url = `/api/events?${params.toString()}`;
            const result = await apiClient.get(url, {
                requestId: `events-stream-${Date.now()}`,
                timeout: 5000
            });

            if (result.ok) {
                const newEvents = Array.isArray(result.data) ? result.data : (result.data.events || []);

                if (newEvents.length > 0) {
                    // Prepend new events (avoid duplicates)
                    const existingIds = new Set(this.events.map(e => e.id));
                    const uniqueNew = newEvents.filter(e => !existingIds.has(e.id));

                    if (uniqueNew.length > 0) {
                        this.events = [...uniqueNew, ...this.events];

                        // Update last timestamp
                        this.lastEventTimestamp = uniqueNew[0].timestamp || uniqueNew[0].created_at;

                        // Update table
                        this.dataTable.setData(this.events);

                        // Show notification
                        showToast(`${uniqueNew.length} new event(s)`, 'info', 1500);
                    }
                }
            }
        } catch (error) {
            console.error('Failed to fetch new events:', error);
            // Don't show error toast during streaming - just log it
        }
    }

    showEventDetail(event) {
        const drawer = this.container.querySelector('#events-detail-drawer');
        const drawerBody = this.container.querySelector('#events-drawer-body');

        drawer.classList.remove('hidden');

        drawerBody.innerHTML = `
            <div class="event-detail">
                <div class="detail-section">
                    <h4>Event Information</h4>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <label>Event ID</label>
                            <div class="detail-value">
                                <code>${event.event_id || event.id || 'N/A'}</code>
                                ${event.event_id ? `
                                    <button class="btn-copy" data-copy="${event.event_id}" title="Copy Event ID">
                                        <span class="material-icons md-18">content_copy</span>
                                    </button>
                                ` : ''}
                            </div>
                        </div>
                        <div class="detail-item">
                            <label>Type</label>
                            <div class="detail-value">${this.renderEventType(event.type)}</div>
                        </div>
                        <div class="detail-item">
                            <label>Timestamp</label>
                            <div class="detail-value">${this.formatTimestamp(event.timestamp || event.created_at)}</div>
                        </div>
                        ${event.task_id ? `
                            <div class="detail-item">
                                <label>Task ID</label>
                                <div class="detail-value">
                                    <code>${event.task_id}</code>
                                    <button class="btn-link" data-task="${event.task_id}">View Task</button>
                                </div>
                            </div>
                        ` : ''}
                        ${event.session_id ? `
                            <div class="detail-item">
                                <label>Session ID</label>
                                <div class="detail-value">
                                    <code>${event.session_id}</code>
                                    <button class="btn-link" data-session="${event.session_id}">View Session</button>
                                </div>
                            </div>
                        ` : ''}
                    </div>
                </div>

                ${event.message || event.description ? `
                    <div class="detail-section">
                        <h4>Message</h4>
                        <div class="detail-description">${event.message || event.description}</div>
                    </div>
                ` : ''}

                <div class="detail-section">
                    <h4>Full Event Data</h4>
                    <div id="event-json-viewer"></div>
                </div>
            </div>
        `;

        // Render JSON viewer
        const jsonContainer = drawerBody.querySelector('#event-json-viewer');
        new JsonViewer(jsonContainer, event, {
            collapsed: false,
            maxDepth: 3,
            showToolbar: true,
            fileName: `event-${event.event_id || event.id || 'unknown'}.json`
        });

        // Setup action buttons
        this.setupEventDetailActions(event);
    }

    setupEventDetailActions(event) {
        const drawerBody = this.container.querySelector('#events-drawer-body');

        // Store event reference for potential future actions
        drawerBody.dataset.eventId = event.event_id || event.id || '';

        // Copy buttons
        drawerBody.querySelectorAll('.btn-copy').forEach(btn => {
            btn.addEventListener('click', () => {
                const text = btn.getAttribute('data-copy');
                navigator.clipboard.writeText(text);
                showToast('Copied to clipboard', 'success', 1500);
            });
        });

        // View task button
        const taskBtn = drawerBody.querySelector('.btn-link[data-task]');
        if (taskBtn) {
            taskBtn.addEventListener('click', () => {
                const taskId = taskBtn.getAttribute('data-task');
                window.navigateToView('tasks', { task_id: taskId });
                this.hideEventDetail();
            });
        }

        // View session button
        const sessionBtn = drawerBody.querySelector('.btn-link[data-session]');
        if (sessionBtn) {
            sessionBtn.addEventListener('click', () => {
                const sessionId = sessionBtn.getAttribute('data-session');
                window.navigateToView('chat', { session_id: sessionId });
                this.hideEventDetail();
            });
        }
    }

    hideEventDetail() {
        const drawer = this.container.querySelector('#events-detail-drawer');
        drawer.classList.add('hidden');
    }

    renderEventType(type) {
        const typeMap = {
            'task.created': { label: 'Task Created', class: 'event-type-info', icon: '<span class="material-icons md-18">add</span>' },
            'task.started': { label: 'Task Started', class: 'event-type-info', icon: '<span class="material-icons md-18">play_arrow</span>' },
            'task.completed': { label: 'Task Completed', class: 'event-type-success', icon: '<span class="material-icons md-18">done</span>' },
            'task.failed': { label: 'Task Failed', class: 'event-type-error', icon: '<span class="material-icons md-18">cancel</span>' },
            'session.created': { label: 'Session Created', class: 'event-type-info', icon: '<span class="material-icons md-18">fiber_new</span>' },
            'session.ended': { label: 'Session Ended', class: 'event-type-warning', icon: '<span class="material-icons md-18">block</span>' },
            'message.sent': { label: 'Message Sent', class: 'event-type-default', icon: '<span class="material-icons md-18">send</span>' },
            'message.received': { label: 'Message Received', class: 'event-type-default', icon: '<span class="material-icons md-18">inbox</span>' },
            'error': { label: 'Error', class: 'event-type-error', icon: '<span class="material-icons md-18">warning</span>' },
            'system': { label: 'System', class: 'event-type-system', icon: '<span class="material-icons md-18">settings</span>' }
        };

        const config = typeMap[type] || { label: type, class: 'event-type-default', icon: '<span class="material-icons md-18">edit_note</span>' };
        return `<span class="event-type ${config.class}">${config.icon} ${config.label}</span>`;
    }

    formatTimestamp(timestamp) {
        if (!timestamp) return 'N/A';

        try {
            const date = new Date(timestamp);
            return date.toLocaleString('en-US', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false
            });
        } catch (e) {
            return timestamp;
        }
    }

    destroy() {
        this.stopStreaming();
        this.container.innerHTML = '';
    }
}

// Export
window.EventsView = EventsView;
