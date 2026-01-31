/**
 * PipelineView - Factory assembly line visualization
 *
 * PR-V4: Frontend Visualization
 * Main controller for the pipeline visualization UI
 */

class PipelineView {
    /**
     * Phase to stage mapping
     */
    static PHASE_TO_STAGE = {
        'planning': 'planning',
        'executing': 'executing',
        'verifying': 'verifying',
        'done': 'done',
        'completed': 'done',
        'failed': 'failed'
    };

    /**
     * Create pipeline view
     *
     * @param {HTMLElement} container - Container element
     * @param {string} taskId - Task ID to visualize
     */
    constructor(container, taskId) {
        this.container = container;
        this.taskId = taskId;

        // Components
        this.stageBar = null;
        this.mergeNode = null;
        this.eventStream = null;
        this.connectionStatus = null;

        // State
        this.workItems = new Map(); // span_id -> WorkItemCard
        this.branchArrows = [];
        this.currentPhase = null;
        this.eventFeed = [];

        // DOM elements
        this.stageBarContainer = null;
        this.workItemsContainer = null;
        this.mergeNodeContainer = null;
        this.svgContainer = null;
        this.eventFeedContainer = null;

        this.init();
    }

    /**
     * Initialize view
     */
    async init() {
        console.log(`[PipelineView] Initializing for task ${this.taskId}`);

        this.render();
        this.setupComponents();
        await this.loadInitialState();
        this.startEventStream();
    }

    /**
     * Render view structure
     */
    render() {
        this.container.innerHTML = `
            <div class="pipeline-view">
                <div class="view-header">
                    <div>
                        <h1>Pipeline Visualization</h1>
                        <p class="text-sm text-gray-600 mt-1">Real-time task execution pipeline visualization</p>
                    </div>
                    <div class="header-actions">
                        <div class="connection-status" id="pipeline-connection-status">
                            <div class="connection-status-dot"></div>
                            <span>Connecting...</span>
                        </div>
                        <button class="btn-refresh" id="pipeline-refresh" title="Refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                    </div>
                </div>

                <div class="filter-section">
                    <div class="filter-info">
                        <span class="filter-label">Task ID:</span>
                        <span class="filter-value">${this.taskId}</span>
                    </div>
                </div>

                <div class="table-section pipeline-canvas">
                    <!-- Stage Bar -->
                    <div id="pipeline-stage-bar"></div>

                    <!-- Main Runner Track -->
                    <div class="main-track">
                        <div class="runner-indicator">
                            <span>Runner Process</span>
                            <span class="runner-status" id="pipeline-runner-status">Initializing...</span>
                        </div>
                    </div>

                    <!-- Work Items Area -->
                    <div class="work-items-area">
                        <div class="work-items-label">Parallel Work Items</div>
                        <div class="work-items-grid" id="pipeline-work-items"></div>
                    </div>

                    <!-- Merge Node -->
                    <div id="pipeline-merge-node"></div>

                    <!-- Branch Arrows (SVG) -->
                    <svg class="branch-arrows" id="pipeline-branch-arrows"></svg>

                    <!-- Event Feed -->
                    <div class="event-feed" id="pipeline-event-feed">
                        <div class="event-feed-header">Recent Events</div>
                        <div class="event-feed-list" id="pipeline-event-feed-list"></div>
                    </div>
                </div>
            </div>
        `;

        // Store references
        this.stageBarContainer = this.container.querySelector('#pipeline-stage-bar');
        this.workItemsContainer = this.container.querySelector('#pipeline-work-items');
        this.mergeNodeContainer = this.container.querySelector('#pipeline-merge-node');
        this.svgContainer = this.container.querySelector('#pipeline-branch-arrows');
        this.eventFeedContainer = this.container.querySelector('#pipeline-event-feed-list');
        this.connectionStatusEl = this.container.querySelector('#pipeline-connection-status');
        this.runnerStatusEl = this.container.querySelector('#pipeline-runner-status');

        // Setup event listeners
        this.setupEventListeners();
    }

    /**
     * Setup components
     */
    setupComponents() {
        // Stage bar
        this.stageBar = new StageBar(this.stageBarContainer);

        // Merge node
        this.mergeNode = new MergeNode(this.mergeNodeContainer);

        // Evidence drawer (PR-V6)
        // Create drawer container if not exists
        if (!document.getElementById('pipeline-evidence-drawer-container')) {
            const drawerContainer = document.createElement('div');
            drawerContainer.id = 'pipeline-evidence-drawer-container';
            document.body.appendChild(drawerContainer);
        }
        this.evidenceDrawer = new EvidenceDrawer('pipeline-evidence-drawer-container');
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Refresh button
        const refreshBtn = this.container.querySelector('#pipeline-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.refresh();
            });
        }
    }

    /**
     * Load initial state from snapshot endpoint
     */
    async loadInitialState() {
        try {
            console.log('[PipelineView] Loading initial snapshot...');

            const response = await fetch(`/api/tasks/${this.taskId}/events/snapshot`);
            if (!response.ok) {
                throw new Error(`Failed to load snapshot: ${response.status}`);
            }

            const data = await response.json();
            console.log('[PipelineView] Snapshot loaded:', data);

            // Process initial events
            if (data.events && data.events.length > 0) {
                data.events.forEach(event => this.handleEvent(event));
            }

            // Set current phase
            if (data.current_phase) {
                this.updatePhase(data.current_phase);
            }

        } catch (error) {
            console.error('[PipelineView] Failed to load initial state:', error);
            this.updateRunnerStatus('Error loading state');
        }
    }

    /**
     * Start event stream
     */
    startEventStream() {
        console.log('[PipelineView] Starting event stream...');

        // Import EventStreamService (assuming it's loaded globally)
        if (typeof EventStreamService === 'undefined') {
            console.error('[PipelineView] EventStreamService not loaded');
            return;
        }

        this.eventStream = new EventStreamService(this.taskId, {
            since_seq: 0,
            onEvent: (event) => this.handleEvent(event),
            onStateChange: (state) => this.handleConnectionStateChange(state),
            onError: (error) => this.handleStreamError(error),
            onReconnect: () => this.handleReconnect()
        });

        this.eventStream.start();
    }

    /**
     * Handle incoming event
     *
     * @param {Object} event - Task event
     */
    handleEvent(event) {
        console.log('[PipelineView] Event:', event.event_type, event);

        // Add to feed
        this.addToEventFeed(event);

        // Route to appropriate handler
        switch (event.event_type) {
            case 'phase_enter':
                this.handlePhaseEnter(event);
                break;

            case 'phase_exit':
                this.handlePhaseExit(event);
                break;

            case 'work_item_dispatched':
                this.handleWorkItemDispatched(event);
                break;

            case 'work_item_picked':
                this.handleWorkItemPicked(event);
                break;

            case 'work_item_done':
                this.handleWorkItemDone(event);
                break;

            case 'work_item_failed':
                this.handleWorkItemFailed(event);
                break;

            case 'gate_result':
                this.handleGateResult(event);
                break;

            case 'checkpoint_commit':
                this.handleCheckpointCommit(event);
                break;

            case 'checkpoint_verified':
                this.handleCheckpointVerified(event);
                break;

            case 'checkpoint_invalid':
                this.handleCheckpointInvalid(event);
                break;

            case 'task_completed':
                this.handleTaskCompleted(event);
                break;

            case 'task_failed':
                this.handleTaskFailed(event);
                break;

            default:
                console.log('[PipelineView] Unhandled event type:', event.event_type);
        }
    }

    /**
     * Handle phase_enter event
     */
    handlePhaseEnter(event) {
        const phase = event.phase || event.payload?.phase;
        if (phase) {
            this.updatePhase(phase);
            const stage = PipelineView.PHASE_TO_STAGE[phase] || phase;
            this.stageBar.activateStage(stage);
            this.updateRunnerStatus(`Entering ${phase} phase`);
        }
    }

    /**
     * Handle phase_exit event
     */
    handlePhaseExit(event) {
        const phase = event.phase || event.payload?.phase;
        if (phase) {
            const stage = PipelineView.PHASE_TO_STAGE[phase] || phase;
            this.stageBar.completeStage(stage);
            this.updateRunnerStatus(`Completed ${phase} phase`);
        }
    }

    /**
     * Handle work_item_dispatched event
     */
    handleWorkItemDispatched(event) {
        const spanId = event.span_id;
        const workItemId = event.payload?.work_item_id || spanId;

        console.log('[PipelineView] Work item dispatched:', workItemId);

        // Create work item card
        const card = new WorkItemCard(spanId, {
            work_item_id: workItemId,
            status: 'dispatched',
            payload: event.payload
        });

        this.workItems.set(spanId, card);
        this.workItemsContainer.appendChild(card.getElement());

        // Update merge node total
        this.mergeNode.updateProgress(
            this.getCompletedWorkItemsCount(),
            this.workItems.size
        );

        this.updateRunnerStatus(`Dispatched work item: ${workItemId}`);
    }

    /**
     * Handle work_item_picked event
     */
    handleWorkItemPicked(event) {
        const spanId = event.span_id;
        const card = this.workItems.get(spanId);

        if (card) {
            card.markRunning();
            this.updateRunnerStatus(`Running work item: ${card.workItemId}`);
        }
    }

    /**
     * Handle work_item_done event
     */
    handleWorkItemDone(event) {
        const spanId = event.span_id;
        const card = this.workItems.get(spanId);

        if (card) {
            card.markDone(event.payload);
            this.updateRunnerStatus(`Completed work item: ${card.workItemId}`);

            // Update merge node
            this.mergeNode.updateProgress(
                this.getCompletedWorkItemsCount(),
                this.workItems.size
            );
        }
    }

    /**
     * Handle work_item_failed event
     */
    handleWorkItemFailed(event) {
        const spanId = event.span_id;
        const card = this.workItems.get(spanId);

        if (card) {
            const error = event.payload?.error || 'Work item failed';
            card.markFailed(error);
            this.updateRunnerStatus(`Failed work item: ${card.workItemId}`);
        }
    }

    /**
     * Handle gate_result event
     */
    handleGateResult(event) {
        const passed = event.payload?.passed;

        if (passed === false) {
            console.log('[PipelineView] Gate failed, showing branch arrow');

            // Show branch arrow from verifying back to planning
            const reason = event.payload?.reason || 'Gate verification failed';
            this.showBranchArrow('verifying', 'planning', reason);

            // Reset planning stage to show it will re-run
            this.stageBar.resetStage('planning');
            this.updateRunnerStatus(`Gate failed: ${reason}`);
        } else {
            console.log('[PipelineView] Gate passed');
            this.updateRunnerStatus('Gate verification passed');
        }
    }

    /**
     * Handle checkpoint_commit event (PR-V6)
     */
    handleCheckpointCommit(event) {
        const checkpointId = event.payload?.checkpoint_id;
        console.log('[PipelineView] Checkpoint committed:', checkpointId);

        if (checkpointId) {
            // Add checkpoint indicator to event feed with click handler
            this.addCheckpointToEventFeed(event, checkpointId);
        }
    }

    /**
     * Handle checkpoint_verified event (PR-V6)
     */
    handleCheckpointVerified(event) {
        const checkpointId = event.payload?.checkpoint_id;
        console.log('[PipelineView] Checkpoint verified:', checkpointId);
        this.updateRunnerStatus(`Checkpoint verified: ${checkpointId}`);
    }

    /**
     * Handle checkpoint_invalid event (PR-V6)
     */
    handleCheckpointInvalid(event) {
        const checkpointId = event.payload?.checkpoint_id;
        console.log('[PipelineView] Checkpoint invalid:', checkpointId);
        this.updateRunnerStatus(`warning Checkpoint invalid: ${checkpointId}`);
    }

    /**
     * Add checkpoint to event feed with evidence viewer link (PR-V6)
     */
    addCheckpointToEventFeed(event, checkpointId) {
        const eventItem = document.createElement('div');
        eventItem.className = 'event-feed-item checkpoint-event';
        eventItem.innerHTML = `
            <span class="event-time">${this.formatTime(event.created_at)}</span>
            <span class="event-text">${event.payload?.explanation || 'Checkpoint committed'}</span>
            <button class="btn-view-evidence" data-checkpoint-id="${checkpointId}" title="View Evidence">
                <span class="material-icons md-16">check_circle</span>
                View Evidence
            </button>
        `;

        // Add click handler for evidence button
        const evidenceBtn = eventItem.querySelector('.btn-view-evidence');
        evidenceBtn.addEventListener('click', () => {
            this.openEvidenceDrawer(checkpointId);
        });

        if (this.eventFeedContainer) {
            this.eventFeedContainer.insertBefore(eventItem, this.eventFeedContainer.firstChild);

            // Limit feed items to 20
            while (this.eventFeedContainer.children.length > 20) {
                this.eventFeedContainer.removeChild(this.eventFeedContainer.lastChild);
            }
        }
    }

    /**
     * Open evidence drawer for checkpoint (PR-V6)
     */
    openEvidenceDrawer(checkpointId) {
        console.log('[PipelineView] Opening evidence drawer for:', checkpointId);
        if (this.evidenceDrawer) {
            this.evidenceDrawer.open(checkpointId);
        }
    }

    /**
     * Handle task_completed event
     */
    handleTaskCompleted(event) {
        console.log('[PipelineView] Task completed');

        this.stageBar.activateStage('done');
        this.stageBar.completeStage('done');
        this.updateRunnerStatus('Task completed successfully! celebration');
    }

    /**
     * Handle task_failed event
     */
    handleTaskFailed(event) {
        console.log('[PipelineView] Task failed');

        const reason = event.payload?.reason || 'Task failed';
        this.stageBar.failStage(this.currentPhase || 'executing');
        this.updateRunnerStatus(`Task failed: ${reason}`);
    }

    /**
     * Show branch arrow
     */
    showBranchArrow(from, to, reason) {
        // Clear existing arrows
        this.clearBranchArrows();

        // Create new arrow
        const arrow = new BranchArrow(this.svgContainer, { from, to, reason });
        this.branchArrows.push(arrow);
    }

    /**
     * Clear branch arrows
     */
    clearBranchArrows() {
        this.branchArrows.forEach(arrow => arrow.destroy());
        this.branchArrows = [];
    }

    /**
     * Update current phase
     */
    updatePhase(phase) {
        this.currentPhase = phase;
        console.log('[PipelineView] Phase updated:', phase);
    }

    /**
     * Update runner status text
     */
    updateRunnerStatus(status) {
        if (this.runnerStatusEl) {
            this.runnerStatusEl.textContent = status;
        }
    }

    /**
     * Add event to feed
     */
    addToEventFeed(event) {
        this.eventFeed.unshift(event);

        // Keep only last 10 events
        if (this.eventFeed.length > 10) {
            this.eventFeed.pop();
        }

        // Render feed
        this.renderEventFeed();
    }

    /**
     * Render event feed
     */
    renderEventFeed() {
        if (!this.eventFeedContainer) return;

        const html = this.eventFeed.map(event => `
            <div class="event-feed-item">
                <div class="event-feed-item-type">${event.event_type}</div>
                <div class="event-feed-item-time">${this.formatTime(event.created_at)}</div>
            </div>
        `).join('');

        this.eventFeedContainer.innerHTML = html || '<div class="event-feed-item">No events yet</div>';
    }

    /**
     * Format time for display
     */
    formatTime(timestamp) {
        if (!timestamp) return 'N/A';

        const date = new Date(timestamp);
        return date.toLocaleTimeString();
    }

    /**
     * Get count of completed work items
     */
    getCompletedWorkItemsCount() {
        let count = 0;
        this.workItems.forEach(card => {
            if (card.status === 'done') {
                count++;
            }
        });
        return count;
    }

    /**
     * Handle connection state change
     */
    handleConnectionStateChange(state) {
        console.log('[PipelineView] Connection state:', state);

        if (this.connectionStatusEl) {
            this.connectionStatusEl.className = `connection-status ${state}`;

            const statusText = this.connectionStatusEl.querySelector('span');
            if (statusText) {
                switch (state) {
                    case 'connected':
                        statusText.textContent = 'Live';
                        break;
                    case 'connecting':
                        statusText.textContent = 'Connecting...';
                        break;
                    case 'reconnecting':
                        statusText.textContent = 'Reconnecting...';
                        break;
                    case 'error':
                        statusText.textContent = 'Connection Error';
                        break;
                    default:
                        statusText.textContent = 'Disconnected';
                }
            }
        }
    }

    /**
     * Handle stream error
     */
    handleStreamError(error) {
        console.error('[PipelineView] Stream error:', error);
        this.updateRunnerStatus('Stream error: ' + error.message);
    }

    /**
     * Handle reconnect
     */
    handleReconnect() {
        console.log('[PipelineView] Reconnected, refreshing state...');
        this.refresh();
    }

    /**
     * Refresh view
     */
    async refresh() {
        console.log('[PipelineView] Refreshing...');

        // Reset state
        this.reset();

        // Reload initial state
        await this.loadInitialState();
    }

    /**
     * Reset view
     */
    reset() {
        console.log('[PipelineView] Resetting view');

        // Clear work items
        this.workItems.forEach(card => card.destroy());
        this.workItems.clear();

        // Reset components
        if (this.stageBar) {
            this.stageBar.reset();
        }

        if (this.mergeNode) {
            this.mergeNode.reset();
        }

        // Clear branch arrows
        this.clearBranchArrows();

        // Clear event feed
        this.eventFeed = [];
        this.renderEventFeed();
    }

    /**
     * Destroy view
     */
    destroy() {
        console.log('[PipelineView] Destroying...');

        // Stop event stream
        if (this.eventStream) {
            this.eventStream.stop();
            this.eventStream = null;
        }

        // Destroy components
        this.workItems.forEach(card => card.destroy());
        this.workItems.clear();

        if (this.mergeNode) {
            this.mergeNode.destroy();
        }

        this.clearBranchArrows();

        // Clear container
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PipelineView;
}
