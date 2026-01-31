/**
 * TimelineView - 叙事Time线视图
 *
 * PR-V5: Timeline View - 让User像读故事一样理解Task Execution过程
 *
 * 核心目标:
 * - 发生了什么（过去的事件，Time线叙事）
 * - 现在在做什么（当前活跃的Actions）
 * - 接下来会做什么（下一步预期）
 * - 为什么卡住/Retry（可解释的异常）
 *
 * Usage:
 * ```javascript
 * const view = new TimelineView(container, 'task_123');
 * // 自动Connection EventStreamService 并渲染Time线
 * ```
 */

import EventStreamService from '../services/EventStreamService.js';
import EventTranslator from '../services/EventTranslator.js';
import NextStepPredictor from '../services/NextStepPredictor.js';

class TimelineView {
    constructor(container, taskId) {
        this.container = container;
        this.taskId = taskId;
        this.events = []; // 已渲染的友好事件
        this.currentPhase = null;
        this.lastEvent = null;
        this.throttleMap = new Map(); // span_id -> last update timestamp
        this.aggregatedEvents = new Map(); // span_id -> DOM element
        this.eventStream = null;
        this.isDestroyed = false;

        this.init();
    }

    init() {
        this.render();
        this.setupEvidenceDrawer();
        this.setupEventStream();
        this.setupEventListeners();
    }

    /**
     * Setup evidence drawer (PR-V6)
     */
    setupEvidenceDrawer() {
        // Create drawer container if not exists
        if (!document.getElementById('timeline-evidence-drawer-container')) {
            const drawerContainer = document.createElement('div');
            drawerContainer.id = 'timeline-evidence-drawer-container';
            document.body.appendChild(drawerContainer);
        }
        this.evidenceDrawer = new EvidenceDrawer('timeline-evidence-drawer-container');
    }

    render() {
        this.container.innerHTML = `
            <div class="timeline-view">
                <div class="view-header">
                    <div>
                        <h1>任务Time线</h1>
                        <p class="text-sm text-gray-600 mt-1">Task execution timeline and tracking</p>
                    </div>
                    <div class="header-info">
                        <span class="task-id">Task ID: <code>${this.taskId}</code></span>
                        <div class="stream-status" id="timeline-stream-status">
                            <div class="status-dot disconnected"></div>
                            <span class="status-text">Connecting...</span>
                        </div>
                    </div>
                </div>

                <!-- 顶部Status卡 -->
                <div class="status-cards">
                    <div class="card current-activity">
                        <div class="card-header">
                            <span class="card-icon">track_changes</span>
                            <h3>当前正在做</h3>
                        </div>
                        <div class="card-body">
                            <p id="current-activity" class="activity-text">Waiting for task to start...</p>
                        </div>
                    </div>

                    <div class="card next-step">
                        <div class="card-header">
                            <span class="card-icon">arrow_forward</span>
                            <h3>下一步</h3>
                        </div>
                        <div class="card-body">
                            <p id="next-step" class="next-step-text">About to start planning...</p>
                        </div>
                    </div>

                    <div class="card issue-explanation" id="issue-card" style="display:none;">
                        <div class="card-header">
                            <span class="card-icon">warning</span>
                            <h3>问题Description</h3>
                            <button class="btn-dismiss" id="dismiss-issue">close</button>
                        </div>
                        <div class="card-body">
                            <p id="issue-explanation" class="issue-text"></p>
                        </div>
                    </div>
                </div>

                <!-- Time线 -->
                <div class="timeline-section">
                    <div class="timeline-header">
                        <h3>执行历史</h3>
                        <div class="timeline-controls">
                            <button class="btn-icon" id="timeline-scroll-top" title="Scroll to top">
                                <span class="material-icons md-18">arrow_upward</span>
                            </button>
                            <button class="btn-icon" id="timeline-scroll-bottom" title="Scroll to bottom">
                                <span class="material-icons md-18">arrow_downward</span>
                            </button>
                            <button class="btn-icon" id="timeline-clear" title="Clear history">
                                <span class="material-icons md-18">delete_sweep</span>
                            </button>
                        </div>
                    </div>

                    <div class="timeline-container">
                        <div class="timeline-track"></div>
                        <div id="timeline-events" class="timeline-events">
                            <div class="timeline-empty">
                                <span class="material-icons md-48">schedule</span>
                                <p>No events</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    setupEventStream() {
        this.eventStream = new EventStreamService(this.taskId, {
            since_seq: 0,
            batch_size: 20,
            flush_interval: 0.5,
            onEvent: (event) => this.handleEvent(event),
            onStateChange: (state) => this.updateStreamStatus(state),
            onError: (error) => {
                console.error('[TimelineView] Stream error:', error);
                this.showIssue('Connection Error', `Event stream connection failed: ${error.message}`);
            }
        });

        this.eventStream.start();
    }

    setupEventListeners() {
        // Dismiss issue card
        const dismissBtn = this.container.querySelector('#dismiss-issue');
        if (dismissBtn) {
            dismissBtn.addEventListener('click', () => this.hideIssue());
        }

        // Scroll controls
        const scrollTop = this.container.querySelector('#timeline-scroll-top');
        if (scrollTop) {
            scrollTop.addEventListener('click', () => {
                const container = this.container.querySelector('.timeline-container');
                container.scrollTo({ top: 0, behavior: 'smooth' });
            });
        }

        const scrollBottom = this.container.querySelector('#timeline-scroll-bottom');
        if (scrollBottom) {
            scrollBottom.addEventListener('click', () => {
                const container = this.container.querySelector('.timeline-container');
                container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
            });
        }

        const clearBtn = this.container.querySelector('#timeline-clear');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearTimeline());
        }
    }

    handleEvent(rawEvent) {
        if (this.isDestroyed) return;

        // 翻译为友好事件
        const friendlyEvent = EventTranslator.translate(rawEvent);

        // 检查是否需要节流
        if (this.shouldThrottle(friendlyEvent)) {
            this.updateAggregatedEvent(friendlyEvent);
            return;
        }

        // 添加到Time线
        this.addEvent(friendlyEvent);

        // 更新当前Phase
        if (rawEvent.phase) {
            this.currentPhase = rawEvent.phase;
        }

        // 更新最后事件
        this.lastEvent = friendlyEvent;

        // 更新Status卡
        this.updateCurrentActivity();
        this.updateNextStep();

        // 检查是否有问题需要Description
        if (friendlyEvent.level === 'error' || friendlyEvent.level === 'warning') {
            this.checkAndShowIssue(friendlyEvent);
        }

        // 自动滚动到最新事件（如果User没有手动滚动）
        this.autoScrollToBottom();
    }

    shouldThrottle(friendlyEvent) {
        const eventType = friendlyEvent.rawEvent?.event_type;
        const spanId = friendlyEvent.span_id;

        // 不节流的Event Type
        if (!EventTranslator.shouldThrottle(eventType)) {
            return false;
        }

        // 检查上次更新Time
        const lastUpdate = this.throttleMap.get(spanId);
        const now = Date.now();

        if (lastUpdate && (now - lastUpdate) < 1000) {
            // 1seconds内已更新过，节流
            return true;
        }

        // 更新Time戳
        this.throttleMap.set(spanId, now);
        return false;
    }

    updateAggregatedEvent(friendlyEvent) {
        const spanId = friendlyEvent.span_id;
        const existingElement = this.aggregatedEvents.get(spanId);

        if (existingElement) {
            // 更新已有元素的文本和Time戳
            const textElement = existingElement.querySelector('.event-text');
            const timestampElement = existingElement.querySelector('.event-timestamp');

            if (textElement) {
                textElement.textContent = friendlyEvent.text;
            }

            if (timestampElement) {
                timestampElement.textContent = this.formatTimestamp(friendlyEvent.timestamp);
            }

            // 添加更新动画
            existingElement.classList.add('event-updated');
            setTimeout(() => {
                existingElement.classList.remove('event-updated');
            }, 500);
        } else {
            // 首次添加
            this.addEvent(friendlyEvent);
            const element = this.container.querySelector(`[data-seq="${friendlyEvent.seq}"]`);
            if (element) {
                this.aggregatedEvents.set(spanId, element);
            }
        }
    }

    addEvent(friendlyEvent) {
        // 移除 "No events" Tip
        const emptyState = this.container.querySelector('.timeline-empty');
        if (emptyState) {
            emptyState.remove();
        }

        // 添加到事件列表
        this.events.push(friendlyEvent);

        // 创建事件 DOM 元素
        const eventElement = this.createEventElement(friendlyEvent);

        // 添加到Time线（追加到底部）
        const timeline = this.container.querySelector('#timeline-events');
        timeline.appendChild(eventElement);

        // 添加入场动画
        setTimeout(() => {
            eventElement.classList.add('event-visible');
        }, 10);
    }

    createEventElement(friendlyEvent) {
        const div = document.createElement('div');
        div.className = `timeline-event event-level-${friendlyEvent.level}`;
        div.setAttribute('data-seq', friendlyEvent.seq);
        div.setAttribute('data-event-type', friendlyEvent.rawEvent?.event_type || '');

        // PR-V6: Add checkpoint evidence button for checkpoint events
        const isCheckpointEvent = ['checkpoint_commit', 'checkpoint_verified', 'checkpoint_invalid'].includes(
            friendlyEvent.rawEvent?.event_type
        );
        const checkpointId = friendlyEvent.rawEvent?.payload?.checkpoint_id;

        let explanationHtml = '';
        if (friendlyEvent.explanation) {
            explanationHtml = `
                <div class="event-explanation">
                    <span class="material-icons md-14">info</span>
                    <span>${this.escapeHtml(friendlyEvent.explanation)}</span>
                </div>
            `;
        }

        div.innerHTML = `
            <div class="event-dot"></div>
            <div class="event-content">
                <div class="event-header">
                    <span class="event-icon">${friendlyEvent.icon}</span>
                    <span class="event-text">${this.escapeHtml(friendlyEvent.text)}</span>
                    ${isCheckpointEvent && checkpointId ? `
                        <button class="btn-view-evidence-inline" data-checkpoint-id="${checkpointId}" title="View Evidence">
                            <span class="material-icons md-16">check_circle</span>
                        </button>
                    ` : ''}
                </div>
                <div class="event-footer">
                    <span class="event-timestamp">${this.formatTimestamp(friendlyEvent.timestamp)}</span>
                    ${friendlyEvent.seq ? `<span class="event-seq">#${friendlyEvent.seq}</span>` : ''}
                </div>
                ${explanationHtml}
            </div>
        `;

        // PR-V6: Add click handler for evidence button
        if (isCheckpointEvent && checkpointId) {
            const evidenceBtn = div.querySelector('.btn-view-evidence-inline');
            if (evidenceBtn) {
                evidenceBtn.addEventListener('click', (e) => {
                    e.stopPropagation(); // Don't trigger event detail modal
                    this.openEvidenceDrawer(checkpointId);
                });
            }
        }

        // 点击ViewDetails
        div.addEventListener('click', () => {
            this.showEventDetail(friendlyEvent);
        });

        return div;
    }

    updateCurrentActivity() {
        const activityText = NextStepPredictor.describeCurrentActivity(this.lastEvent);
        const activityElement = this.container.querySelector('#current-activity');

        if (activityElement) {
            activityElement.textContent = activityText;

            // 添加更新动画
            activityElement.classList.add('text-updated');
            setTimeout(() => {
                activityElement.classList.remove('text-updated');
            }, 300);
        }
    }

    updateNextStep() {
        const nextStepText = NextStepPredictor.predict(this.currentPhase, this.lastEvent);
        const nextStepElement = this.container.querySelector('#next-step');

        if (nextStepElement) {
            nextStepElement.textContent = nextStepText;

            // 添加更新动画
            nextStepElement.classList.add('text-updated');
            setTimeout(() => {
                nextStepElement.classList.remove('text-updated');
            }, 300);
        }
    }

    checkAndShowIssue(friendlyEvent) {
        const eventType = friendlyEvent.rawEvent?.event_type;

        // Gate failed
        if (eventType === 'gate_result' && !friendlyEvent.rawEvent.payload?.passed) {
            const gateType = friendlyEvent.rawEvent.payload?.gate_type || 'gate';
            const reasonCode = friendlyEvent.rawEvent.payload?.reason_code || 'Unknown reason';
            const hint = friendlyEvent.rawEvent.payload?.hint || '';

            this.showIssue(
                `Checkpoint failed: ${gateType}`,
                hint || `Checkpoint validation failed（${reasonCode}）。System will replan and retry。`
            );
        }

        // Work item failed
        else if (eventType === 'work_item_failed' || eventType === 'WORK_ITEM_FAILED') {
            const itemId = friendlyEvent.rawEvent.payload?.work_item_id || 'unknown';
            const error = friendlyEvent.rawEvent.payload?.error || friendlyEvent.rawEvent.payload?.reason || 'Unknown error';

            this.showIssue(
                `Subtask #${itemId} failed`,
                `Execution failed: ${error}. System will try to retry or skip this task.`
            );
        }

        // Runner 异常退出
        else if (eventType === 'runner_exit') {
            const exitCode = friendlyEvent.rawEvent.payload?.exit_code;
            if (exitCode !== 0) {
                const reason = friendlyEvent.rawEvent.payload?.reason || 'Unknown reason';
                this.showIssue(
                    'Executor exited abnormally',
                    `Exit code ${exitCode}: ${reason}。Please check logs for details。`
                );
            }
        }

        // Checkpoint 无效
        else if (eventType === 'checkpoint_invalid') {
            const checkpointId = friendlyEvent.rawEvent.payload?.checkpoint_id || 'unknown';
            const reason = friendlyEvent.rawEvent.payload?.reason || 'Data inconsistency';

            this.showIssue(
                `Progress point ${checkpointId} validation failed`,
                `Reason: ${reason}. System will try to recover from last valid progress point.`
            );
        }
    }

    showIssue(title, message) {
        const issueCard = this.container.querySelector('#issue-card');
        const issueText = this.container.querySelector('#issue-explanation');

        if (issueCard && issueText) {
            issueText.innerHTML = `<strong>${this.escapeHtml(title)}</strong><br>${this.escapeHtml(message)}`;
            issueCard.style.display = 'block';

            // 添加入场动画
            issueCard.classList.add('card-show');
        }
    }

    hideIssue() {
        const issueCard = this.container.querySelector('#issue-card');
        if (issueCard) {
            issueCard.classList.remove('card-show');
            setTimeout(() => {
                issueCard.style.display = 'none';
            }, 300);
        }
    }

    updateStreamStatus(state) {
        const statusElement = this.container.querySelector('#timeline-stream-status');
        if (!statusElement) return;

        const dot = statusElement.querySelector('.status-dot');
        const text = statusElement.querySelector('.status-text');

        // 移除所有Status类
        dot.classList.remove('disconnected', 'connecting', 'connected', 'error');

        const stateLabels = {
            'disconnected': 'Disconnected',
            'connecting': 'Connecting...',
            'connected': 'Live Connection',
            'reconnecting': 'Reconnecting...',
            'error': 'Connection Error'
        };

        const stateClass = state === 'reconnecting' ? 'connecting' : state;
        dot.classList.add(stateClass);
        text.textContent = stateLabels[state] || state;
    }

    showEventDetail(friendlyEvent) {
        // 创建模态框Show完整Event Details
        const modal = document.createElement('div');
        modal.className = 'event-detail-modal';
        modal.innerHTML = `
            <div class="modal-overlay"></div>
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Event Details</h3>
                    <button class="btn-close">
                                <span class="material-icons">close</span>
                            </button>
                </div>
                <div class="modal-body">
                    <div class="detail-row">
                        <label>Event Type</label>
                        <span>${this.escapeHtml(friendlyEvent.rawEvent?.event_type || 'unknown')}</span>
                    </div>
                    <div class="detail-row">
                        <label>Description</label>
                        <span>${friendlyEvent.icon} ${this.escapeHtml(friendlyEvent.text)}</span>
                    </div>
                    <div class="detail-row">
                        <label>Time</label>
                        <span>${this.formatTimestamp(friendlyEvent.timestamp)}</span>
                    </div>
                    <div class="detail-row">
                        <label>Level</label>
                        <span class="badge badge-${friendlyEvent.level}">${friendlyEvent.level}</span>
                    </div>
                    ${friendlyEvent.seq ? `
                        <div class="detail-row">
                            <label>Sequence</label>
                            <span>#${friendlyEvent.seq}</span>
                        </div>
                    ` : ''}
                    ${friendlyEvent.phase ? `
                        <div class="detail-row">
                            <label>Phase</label>
                            <span>${this.escapeHtml(friendlyEvent.phase)}</span>
                        </div>
                    ` : ''}
                    ${friendlyEvent.explanation ? `
                        <div class="detail-row">
                            <label>Description</label>
                            <span>${this.escapeHtml(friendlyEvent.explanation)}</span>
                        </div>
                    ` : ''}
                    <div class="detail-row">
                        <label>Raw Data</label>
                        <pre class="json-preview">${JSON.stringify(friendlyEvent.rawEvent, null, 2)}</pre>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Close模态框
        const closeModal = () => {
            modal.remove();
        };

        modal.querySelector('.btn-close').addEventListener('click', closeModal);
        modal.querySelector('.modal-overlay').addEventListener('click', closeModal);

        // ESC 键Close
        const handleEsc = (e) => {
            if (e.key === 'Escape') {
                closeModal();
                document.removeEventListener('keydown', handleEsc);
            }
        };
        document.addEventListener('keydown', handleEsc);
    }

    autoScrollToBottom() {
        const container = this.container.querySelector('.timeline-container');
        if (!container) return;

        // 检查User是否手动滚动（距离底部 > 100px 认为是手动滚动）
        const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;

        if (isNearBottom) {
            setTimeout(() => {
                container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
            }, 50);
        }
    }

    /**
     * Open evidence drawer for checkpoint (PR-V6)
     */
    openEvidenceDrawer(checkpointId) {
        console.log('[TimelineView] Opening evidence drawer for:', checkpointId);
        if (this.evidenceDrawer) {
            this.evidenceDrawer.open(checkpointId);
        }
    }

    async clearTimeline() {
        const confirmed = await Dialog.confirm('Clear timeline history?', {
            title: 'Confirm Clear',
            confirmText: 'Clear'
        });

        if (!confirmed) {
            return;
        }

        this.events = [];
        this.aggregatedEvents.clear();
        this.throttleMap.clear();

        const timeline = this.container.querySelector('#timeline-events');
        timeline.innerHTML = `
            <div class="timeline-empty">
                <span class="material-icons md-48">schedule</span>
                <p>No events</p>
            </div>
        `;
    }

    formatTimestamp(timestamp) {
        if (!timestamp) return 'N/A';

        try {
            const date = new Date(timestamp);
            return date.toLocaleString('zh-CN', {
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

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    destroy() {
        this.isDestroyed = true;

        if (this.eventStream) {
            this.eventStream.stop();
            this.eventStream = null;
        }

        this.events = [];
        this.aggregatedEvents.clear();
        this.throttleMap.clear();

        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}

// Export
window.TimelineView = TimelineView;
export default TimelineView;
