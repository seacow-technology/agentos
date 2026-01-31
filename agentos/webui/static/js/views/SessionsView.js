/**
 * SessionsView - Session Management UI
 *
 * PR-3: Sessions First-class Citizen
 * Coverage: GET /api/sessions, GET /api/sessions/{id}, POST/PATCH/DELETE
 */

class SessionsView {
    constructor(container) {
        this.container = container;
        this.filterBar = null;
        this.dataTable = null;
        this.detailDrawer = null;
        this.currentFilters = {};
        this.sessions = [];
        this.selectedSession = null;

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="sessions-view">
                <div class="view-header">
                    <div>
                        <h1>Session Management</h1>
                        <p class="text-sm text-gray-600 mt-1">Manage chat sessions and conversations</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="sessions-refresh">
                            <span class="material-icons md-18">refresh</span> Refresh
                        </button>
                        <button class="btn-primary" id="sessions-create">
                            <span class="material-icons md-18">add</span> New Session
                        </button>
                    </div>
                </div>

                <div id="sessions-filter-bar" class="filter-section"></div>

                <div id="sessions-table" class="table-section"></div>

                <div id="sessions-detail-drawer" class="drawer hidden">
                    <div class="drawer-overlay" id="sessions-drawer-overlay"></div>
                    <div class="drawer-content">
                        <div class="drawer-header">
                            <h3>Session Details</h3>
                            <button class="btn-close" id="sessions-drawer-close">
                                <span class="material-icons">close</span>
                            </button>
                        </div>
                        <div class="drawer-body" id="sessions-drawer-body">
                            <!-- Session details will be rendered here -->
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.setupFilterBar();
        this.setupDataTable();
        this.setupEventListeners();
        this.loadSessions();
    }

    setupFilterBar() {
        const filterContainer = this.container.querySelector('#sessions-filter-bar');

        this.filterBar = new FilterBar(filterContainer, {
            filters: [
                {
                    type: 'text',
                    key: 'session_id',
                    label: 'Session ID',
                    placeholder: 'Filter by session ID...'
                },
                {
                    type: 'text',
                    key: 'title',
                    label: 'Title',
                    placeholder: 'Filter by title...'
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
        const tableContainer = this.container.querySelector('#sessions-table');

        this.dataTable = new DataTable(tableContainer, {
            columns: [
                {
                    key: 'session_id',
                    label: 'Session ID',
                    width: '250px',
                    render: (value) => {
                        // PR-3 护栏Rule：missing session_id Show badge
                        if (!value) {
                            return '<span class="status-badge status-unknown">(missing)</span>';
                        }
                        return `<code class="code-inline">${value}</code>`;
                    }
                },
                {
                    key: 'title',
                    label: 'Title',
                    width: '200px',
                    render: (value) => value || 'Untitled'
                },
                {
                    key: 'created_at',
                    label: 'Created',
                    width: '180px',
                    render: (value) => this.formatTimestamp(value)
                },
                {
                    key: 'updated_at',
                    label: 'Last Active',
                    width: '180px',
                    render: (value) => this.formatTimestamp(value)
                },
                {
                    key: 'message_count',
                    label: 'Messages',
                    width: '100px',
                    render: (value) => value !== undefined ? value : 'N/A'
                },
                {
                    key: 'task_count',
                    label: 'Tasks',
                    width: '100px',
                    render: (value) => value !== undefined ? value : 'N/A'
                }
            ],
            data: [],
            emptyText: 'No sessions found',
            loadingText: 'Loading sessions...',
            onRowClick: (session, event) => {
                // Stop event propagation to prevent it from reaching overlay
                if (event) {
                    event.stopPropagation();
                    event.preventDefault();
                }
                console.log('[SessionsView] Row clicked, showing detail for:', session.session_id);
                this.showSessionDetail(session);
            },
            pagination: true,
            pageSize: 10
        });
    }

    setupEventListeners() {
        // Refresh button
        this.container.querySelector('#sessions-refresh').addEventListener('click', () => {
            this.loadSessions(true);
        });

        // Create button
        this.container.querySelector('#sessions-create').addEventListener('click', () => {
            this.createSession();
        });

        // Drawer close button
        this.container.querySelector('#sessions-drawer-close').addEventListener('click', () => {
            console.log('[SessionsView] Close button clicked');
            this.hideSessionDetail();
        });

        // Drawer overlay click - check if click target is exactly the overlay
        const overlay = this.container.querySelector('#sessions-drawer-overlay');
        overlay.addEventListener('click', (e) => {
            console.log('[SessionsView] Overlay click event:', {
                target: e.target,
                currentTarget: e.currentTarget,
                isOverlay: e.target === overlay,
                targetClass: e.target.className,
                targetId: e.target.id
            });

            // Only close if user clicked directly on the overlay (not on drawer-content)
            if (e.target === overlay) {
                console.log('[SessionsView] Overlay clicked (valid close)');
                this.hideSessionDetail();
            } else {
                console.log('[SessionsView] Overlay child clicked (ignored)');
            }
        });

        // Keyboard shortcut: Escape to close drawer
        const handleKeydown = (e) => {
            if (e.key === 'Escape' && !this.container.querySelector('#sessions-detail-drawer').classList.contains('hidden')) {
                console.log('[SessionsView] Escape pressed, closing drawer');
                this.hideSessionDetail();
            }
        };
        document.addEventListener('keydown', handleKeydown);
    }

    handleFilterChange(filters) {
        this.currentFilters = filters;
        this.loadSessions();
    }

    async loadSessions(forceRefresh = false) {
        this.dataTable.setLoading(true);

        try {
            // Build query parameters
            const params = new URLSearchParams();

            if (this.currentFilters.session_id) {
                params.append('session_id', this.currentFilters.session_id);
            }
            if (this.currentFilters.title) {
                params.append('title', this.currentFilters.title);
            }
            if (this.currentFilters.time_range) {
                const { start, end } = this.currentFilters.time_range;
                if (start) params.append('start_time', start);
                if (end) params.append('end_time', end);
            }

            const url = `/api/sessions${params.toString() ? '?' + params.toString() : ''}`;
            const result = await apiClient.get(url, {
                requestId: `sessions-list-${Date.now()}`
            });

            if (result.ok) {
                // PR-3 护栏Rule：检查 session_id
                const sessions = result.data.sessions || result.data || [];

                // Validate: 所有 session 必须有 session_id
                const invalidSessions = sessions.filter(s => !s.session_id && !s.id);
                if (invalidSessions.length > 0) {
                    showToast('Warning: Some sessions are missing session_id (backend contract bug)', 'warning');
                    console.error('Invalid sessions:', invalidSessions);
                }

                // 标准化 session_id 字段（支持 id 或 session_id）
                this.sessions = sessions.map(s => ({
                    ...s,
                    session_id: s.session_id || s.id
                }));

                this.dataTable.setData(this.sessions);

                if (forceRefresh) {
                    showToast('Sessions refreshed', 'success', 2000);
                }
            } else {
                showToast(`Failed to load sessions: ${result.message}`, 'error');
                this.dataTable.setData([]);
            }
        } catch (error) {
            console.error('Failed to load sessions:', error);
            showToast('Failed to load sessions', 'error');
            this.dataTable.setData([]);
        } finally {
            this.dataTable.setLoading(false);
        }
    }

    async showSessionDetail(session) {
        console.log('[SessionsView] showSessionDetail called for:', session.session_id);

        // PR-3 护栏Rule：没有 session_id 则不允许Open
        if (!session.session_id) {
            showToast('Cannot open session: missing session_id', 'error');
            return;
        }

        this.selectedSession = session;
        const drawer = this.container.querySelector('#sessions-detail-drawer');
        const drawerBody = this.container.querySelector('#sessions-drawer-body');

        // Prevent closing during loading
        this._drawerIsLoading = true;

        // Show drawer with loading state
        drawer.classList.remove('hidden');
        drawer.classList.add('visible');  // 添加 visible 类以显示内容
        console.log('[SessionsView] Drawer shown with visible class, loading details...');
        drawerBody.innerHTML = '<div class="loading-spinner">Loading session details...</div>';

        // Small delay to prevent immediate close from event bubbling
        await new Promise(resolve => setTimeout(resolve, 50));

        try {
            // Fetch full session details
            const result = await apiClient.get(`/api/sessions/${session.session_id}`, {
                requestId: `session-detail-${session.session_id}`
            });

            if (result.ok) {
                const sessionDetail = result.data;
                console.log('[SessionsView] Session details loaded successfully');
                this.renderSessionDetail(sessionDetail);
            } else {
                // 404 或其他Error
                console.error('[SessionsView] Failed to load session details:', result.message);
                drawerBody.innerHTML = `
                    <div class="error-message">
                        <div class="error-icon"><span class="material-icons md-18">warning</span></div>
                        <div class="error-text">Failed to load session details: ${result.message}</div>
                    </div>
                `;
            }
        } catch (error) {
            console.error('[SessionsView] Exception loading session detail:', error);
            drawerBody.innerHTML = `
                <div class="error-message">
                    <div class="error-icon"><span class="material-icons md-18">warning</span></div>
                    <div class="error-text">Failed to load session details</div>
                </div>
            `;
        } finally {
            // Allow closing after loading completes
            this._drawerIsLoading = false;
            console.log('[SessionsView] Drawer loading complete');

            // Debug: Check drawer state
            const drawer = this.container.querySelector('#sessions-detail-drawer');
            const drawerContent = this.container.querySelector('.drawer-content');
            const overlay = this.container.querySelector('#sessions-drawer-overlay');

            console.log('[SessionsView] Drawer state check:');
            console.log('  - drawer.classList:', drawer ? Array.from(drawer.classList) : 'NULL');
            console.log('  - drawer display:', drawer ? window.getComputedStyle(drawer).display : 'NULL');
            console.log('  - drawerContent exists:', !!drawerContent);
            console.log('  - overlay exists:', !!overlay);

            if (drawerContent) {
                const contentStyle = window.getComputedStyle(drawerContent);
                console.log('  - drawer-content display:', contentStyle.display);
                console.log('  - drawer-content transform:', contentStyle.transform);
                console.log('  - drawer-content opacity:', contentStyle.opacity);
                console.log('  - drawer-content visibility:', contentStyle.visibility);
                console.log('  - drawer-content width:', contentStyle.width);
                console.log('  - drawer-content right:', contentStyle.right);
            }

            if (drawer && drawer.classList.contains('hidden')) {
                console.error('[SessionsView] ⚠️ PROBLEM: Drawer has hidden class after loading!');
            }

            // Check again after a delay to see if something changes
            setTimeout(() => {
                console.log('[SessionsView] Drawer state check (after 1s):');
                const drawer2 = this.container.querySelector('#sessions-detail-drawer');
                const drawerContent2 = this.container.querySelector('.drawer-content');
                console.log('  - drawer still exists:', !!drawer2);
                console.log('  - drawer-content still exists:', !!drawerContent2);
                if (drawerContent2) {
                    const style2 = window.getComputedStyle(drawerContent2);
                    console.log('  - drawer-content display:', style2.display);
                    console.log('  - drawer-content transform:', style2.transform);
                }
            }, 1000);
        }
    }

    renderSessionDetail(session) {
        const drawerBody = this.container.querySelector('#sessions-drawer-body');

        drawerBody.innerHTML = `
            <div class="session-detail">
                <!-- Header Section: Session ID + Copy + Open Chat -->
                <div class="detail-section" style="background: #f8f9fa; border: 2px solid #dee2e6;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <label style="font-size: 12px; color: #6c757d; font-weight: 600; text-transform: uppercase;">Session ID</label>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <code style="font-size: 16px; font-weight: 600;">${session.session_id || session.id}</code>
                                <button class="btn-copy" data-copy="${session.session_id || session.id}" title="Copy Session ID">
                                    <span class="material-icons md-18">content_copy</span>
                                </button>
                            </div>
                        </div>
                        <button class="btn-primary" id="session-open-chat">
                            <span class="material-icons md-18">add_comment</span> Open Chat
                        </button>
                    </div>
                </div>

                <!-- Basic Information -->
                <div class="detail-section">
                    <h4>Basic Information</h4>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <label>Title</label>
                            <div class="detail-value" id="session-title-display">
                                ${session.title || 'Untitled'}
                                <button class="btn-link" id="session-rename-btn">Rename</button>
                            </div>
                        </div>
                        <div class="detail-item">
                            <label>Created</label>
                            <div class="detail-value">${this.formatTimestamp(session.created_at)}</div>
                        </div>
                        <div class="detail-item">
                            <label>Last Active</label>
                            <div class="detail-value">${this.formatTimestamp(session.updated_at || session.last_active)}</div>
                        </div>
                        <div class="detail-item">
                            <label>Message Count</label>
                            <div class="detail-value">${session.message_count !== undefined ? session.message_count : 'N/A'}</div>
                        </div>
                        <div class="detail-item">
                            <label>Task Count</label>
                            <div class="detail-value">${session.task_count !== undefined ? session.task_count : 'N/A'}</div>
                        </div>
                    </div>
                </div>

                <!-- Metadata (JsonViewer) -->
                <div class="detail-section">
                    <h4>Metadata</h4>
                    <div id="session-json-viewer"></div>
                </div>

                <!-- Quick Links (Cross-navigation) -->
                <div class="detail-section">
                    <h4>Related Data</h4>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                        <button class="btn-secondary" id="session-view-tasks">
                            <span class="material-icons md-18">task</span> View Tasks
                        </button>
                        <button class="btn-secondary" id="session-view-events">
                            <span class="material-icons md-18">sensors</span> View Events
                        </button>
                        <button class="btn-secondary" id="session-view-logs">
                            <span class="material-icons md-18">edit_note</span> View Logs
                        </button>
                    </div>
                </div>

                <!-- Lifecycle (Rename / Delete) -->
                <div class="detail-section" style="border-top: 2px solid #dee2e6; padding-top: 16px;">
                    <h4>Lifecycle Management</h4>
                    <div style="display: flex; gap: 12px; align-items: center;">
                        <button class="btn-danger" id="session-delete">
                            <span class="material-icons md-18">delete</span> Delete Session
                        </button>
                    </div>
                </div>
            </div>
        `;

        // Render JSON viewer
        const jsonContainer = drawerBody.querySelector('#session-json-viewer');
        new JsonViewer(jsonContainer, session, {
            collapsed: true,
            maxDepth: 2,
            showToolbar: true,
            fileName: `session-${session.session_id || session.id}.json`
        });

        // Setup action buttons
        this.setupSessionDetailActions(session);
    }

    setupSessionDetailActions(session) {
        const drawerBody = this.container.querySelector('#sessions-drawer-body');

        // Store session reference
        drawerBody.dataset.sessionId = session.session_id || session.id;

        // Copy button
        drawerBody.querySelectorAll('.btn-copy').forEach(btn => {
            btn.addEventListener('click', () => {
                const text = btn.getAttribute('data-copy');
                navigator.clipboard.writeText(text);
                showToast('Copied to clipboard', 'success', 1500);
            });
        });

        // Open Chat button
        const openChatBtn = drawerBody.querySelector('#session-open-chat');
        if (openChatBtn) {
            openChatBtn.addEventListener('click', () => {
                // PR-3 核心路径：从 SessionsView 进入 Chat
                window.navigateToView('chat', { session_id: session.session_id || session.id });
                this.hideSessionDetail();
            });
        }

        // Rename button
        const renameBtn = drawerBody.querySelector('#session-rename-btn');
        if (renameBtn) {
            renameBtn.addEventListener('click', () => {
                this.showRenameDialog(session);
            });
        }

        // View Tasks button
        const tasksBtn = drawerBody.querySelector('#session-view-tasks');
        if (tasksBtn) {
            tasksBtn.addEventListener('click', () => {
                window.navigateToView('tasks', { session_id: session.session_id || session.id });
                this.hideSessionDetail();
            });
        }

        // View Events button
        const eventsBtn = drawerBody.querySelector('#session-view-events');
        if (eventsBtn) {
            eventsBtn.addEventListener('click', () => {
                window.navigateToView('events', { session_id: session.session_id || session.id });
                this.hideSessionDetail();
            });
        }

        // View Logs button
        const logsBtn = drawerBody.querySelector('#session-view-logs');
        if (logsBtn) {
            logsBtn.addEventListener('click', () => {
                window.navigateToView('logs', { session_id: session.session_id || session.id });
                this.hideSessionDetail();
            });
        }

        // Delete button
        const deleteBtn = drawerBody.querySelector('#session-delete');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', async () => {
                await this.deleteSession(session);
            });
        }
    }

    hideSessionDetail() {
        // Get stack trace to see who called this
        const stack = new Error().stack;
        console.log('[SessionsView] hideSessionDetail called, loading:', this._drawerIsLoading);
        console.log('[SessionsView] Call stack:', stack);

        // Don't close if still loading (prevent premature close)
        if (this._drawerIsLoading) {
            console.log('[SessionsView] Drawer is loading, ignoring close request');
            return;
        }

        const drawer = this.container.querySelector('#sessions-detail-drawer');
        if (drawer) {
            const wasHidden = drawer.classList.contains('hidden');
            drawer.classList.remove('visible');  // 移除 visible 类
            drawer.classList.add('hidden');
            console.log('[SessionsView] Drawer hidden (was already hidden:', wasHidden, ')');
        } else {
            console.error('[SessionsView] Drawer element not found!');
        }
        this.selectedSession = null;
    }

    /**
     * Create new session (Step 4: CRUD)
     * PR-3 最小Success：创建并跳转进入
     */
    async createSession() {
        // Check if Dialog is available
        if (typeof Dialog === 'undefined') {
            console.error('Dialog component not loaded');
            showToast('Dialog component not available', 'error');
            return;
        }

        // Prompt for session title
        let title;
        try {
            title = await Dialog.prompt('Enter session title (optional):', {
                title: 'Create New Session',
                defaultValue: 'New Session',
                placeholder: 'My Session'
            });
        } catch (error) {
            console.error('Dialog.prompt error:', error);
            showToast('Failed to show dialog', 'error');
            return;
        }

        // User cancelled
        if (title === null) {
            return;
        }

        try {
            const result = await apiClient.post('/api/sessions', {
                title: title || 'Untitled Session',
                // 可以传其他默认参数
            }, {
                requestId: `session-create-${Date.now()}`
            });

            if (result.ok) {
                const newSession = result.data;

                // PR-3 护栏Rule：验证返回的 session_id
                const sessionId = newSession.session_id || newSession.id;
                if (!sessionId) {
                    showToast('Error: Backend did not return session_id (contract bug)', 'error');
                    console.error('Invalid session response:', newSession);
                    return;
                }

                showToast('Session created successfully', 'success');

                // Refresh列表
                await this.loadSessions(true);

                // PR-3 核心路径：创建后跳转到 Chat
                window.navigateToView('chat', { session_id: sessionId });
            } else {
                showToast(`Failed to create session: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Failed to create session:', error);
            showToast('Failed to create session', 'error');
        }
    }

    /**
     * Rename session (Step 4: CRUD)
     * PR-3: PATCH/PUT 任一方式
     */
    async showRenameDialog(session) {
        // Check if Dialog is available
        if (typeof Dialog === 'undefined') {
            console.error('Dialog component not loaded');
            showToast('Dialog component not available', 'error');
            return;
        }

        const currentTitle = session.title || 'Untitled';
        let newTitle;
        try {
            newTitle = await Dialog.prompt('Enter new title:', {
                title: 'Rename Session',
                defaultValue: currentTitle,
                placeholder: 'Session Title'
            });
        } catch (error) {
            console.error('Dialog.prompt error:', error);
            showToast('Failed to show dialog', 'error');
            return;
        }

        // User cancelled
        if (newTitle === null || newTitle === currentTitle) {
            return;
        }

        this.renameSession(session, newTitle);
    }

    async renameSession(session, newTitle) {
        try {
            // Try PATCH first (更语义化), fallback to PUT if needed
            const result = await apiClient.request(`/api/sessions/${session.session_id || session.id}`, {
                method: 'PATCH',
                body: JSON.stringify({ title: newTitle }),
                headers: { 'Content-Type': 'application/json' },
                requestId: `session-rename-${session.session_id || session.id}`
            });

            if (result.ok) {
                showToast('Session renamed successfully', 'success');

                // 更新本地数据
                session.title = newTitle;

                // Refresh列表
                await this.loadSessions(true);

                // 如果 drawer 还开着，更新 drawer 内容
                if (this.selectedSession && (this.selectedSession.session_id === session.session_id || this.selectedSession.id === session.id)) {
                    this.showSessionDetail(session);
                }
            } else {
                showToast(`Failed to rename session: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Failed to rename session:', error);
            showToast('Failed to rename session', 'error');
        }
    }

    /**
     * Delete session (Step 4: CRUD)
     * PR-3 护栏Rule：不要求级联清理，只ShowDelete结果
     */
    async deleteSession(session) {
        const sessionId = session.session_id || session.id;

        // 确认弹窗
        const confirmed = await Dialog.confirm(
            `Are you sure you want to delete this session?\n\n` +
            `Session ID: ${sessionId}\n` +
            `Title: ${session.title || 'Untitled'}\n\n` +
            `This action cannot be undone.`,
            {
                title: 'Delete Session',
                confirmText: 'Delete',
                danger: true
            }
        );

        if (!confirmed) {
            return;
        }

        try {
            const result = await apiClient.request(`/api/sessions/${sessionId}`, {
                method: 'DELETE',
                requestId: `session-delete-${sessionId}`
            });

            if (result.ok) {
                showToast('Session deleted successfully', 'success');

                // Close drawer
                this.hideSessionDetail();

                // Refresh列表
                await this.loadSessions(true);
            } else {
                showToast(`Failed to delete session: ${result.message}`, 'error');
                // drawer 保持Open（按蓝图要求）
            }
        } catch (error) {
            console.error('Failed to delete session:', error);
            showToast('Failed to delete session', 'error');
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

    destroy() {
        // Cleanup
        this.container.innerHTML = '';
    }
}

// Export
window.SessionsView = SessionsView;
