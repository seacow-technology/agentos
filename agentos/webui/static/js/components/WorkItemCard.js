/**
 * WorkItemCard Component - Individual work item visualization
 *
 * PR-V4: Pipeline Visualization
 * Represents a single work_item in the parallel execution area
 */

class WorkItemCard {
    /**
     * Status definitions
     */
    static STATUS = {
        DISPATCHED: 'dispatched',
        RUNNING: 'running',
        DONE: 'done',
        FAILED: 'failed'
    };

    /**
     * Create work item card
     *
     * @param {string} spanId - Span ID
     * @param {Object} data - Work item data
     * @param {string} data.work_item_id - Work item ID
     * @param {string} [data.status] - Initial status
     * @param {Object} [data.payload] - Additional payload
     */
    constructor(spanId, data) {
        this.spanId = spanId;
        this.workItemId = data.work_item_id || spanId;
        this.status = data.status || WorkItemCard.STATUS.DISPATCHED;
        this.payload = data.payload || {};
        this.progress = 0;
        this.element = null;

        this.render();
    }

    /**
     * Render work item card
     *
     * @returns {HTMLElement}
     */
    render() {
        const div = document.createElement('div');
        div.className = `work-item-card ${this.status}`;
        div.dataset.spanId = this.spanId;

        div.innerHTML = `
            <div class="work-item-header">
                <div class="work-item-id">${this.workItemId}</div>
                <div class="work-item-status-badge ${this.status}">
                    ${this.getStatusLabel()}
                </div>
            </div>
            <div class="work-item-body">
                ${this.getBodyContent()}
            </div>
            ${this.status === WorkItemCard.STATUS.RUNNING ? `
                <div class="work-item-progress">
                    <div class="work-item-progress-bar" style="width: ${this.progress}%"></div>
                </div>
            ` : ''}
        `;

        this.element = div;
        return div;
    }

    /**
     * Get status label
     *
     * @returns {string}
     */
    getStatusLabel() {
        switch (this.status) {
            case WorkItemCard.STATUS.DISPATCHED:
                return 'circle Dispatched';
            case WorkItemCard.STATUS.RUNNING:
                return 'circle Running';
            case WorkItemCard.STATUS.DONE:
                return 'circle Done';
            case WorkItemCard.STATUS.FAILED:
                return 'circle Failed';
            default:
                return 'Unknown';
        }
    }

    /**
     * Get body content
     *
     * @returns {string}
     */
    getBodyContent() {
        if (this.payload.description) {
            return this.payload.description;
        }

        switch (this.status) {
            case WorkItemCard.STATUS.DISPATCHED:
                return 'Waiting to be picked up...';
            case WorkItemCard.STATUS.RUNNING:
                return 'Processing work item...';
            case WorkItemCard.STATUS.DONE:
                return 'Work item completed successfully!';
            case WorkItemCard.STATUS.FAILED:
                return this.payload.error || 'Work item failed';
            default:
                return 'Work item';
        }
    }

    /**
     * Update status
     *
     * @param {string} newStatus - New status
     * @param {Object} [payload] - Additional payload
     */
    updateStatus(newStatus, payload = {}) {
        console.log(`[WorkItemCard] ${this.workItemId}: ${this.status} -> ${newStatus}`);

        this.status = newStatus;
        this.payload = { ...this.payload, ...payload };

        // Update element classes
        if (this.element) {
            this.element.className = `work-item-card ${this.status}`;

            // Update status badge
            const badge = this.element.querySelector('.work-item-status-badge');
            if (badge) {
                badge.className = `work-item-status-badge ${this.status}`;
                badge.textContent = this.getStatusLabel();
            }

            // Update body content
            const body = this.element.querySelector('.work-item-body');
            if (body) {
                body.innerHTML = this.getBodyContent();
            }

            // Add/remove progress bar
            const existingProgress = this.element.querySelector('.work-item-progress');
            if (this.status === WorkItemCard.STATUS.RUNNING && !existingProgress) {
                const progressHtml = `
                    <div class="work-item-progress">
                        <div class="work-item-progress-bar" style="width: ${this.progress}%"></div>
                    </div>
                `;
                this.element.insertAdjacentHTML('beforeend', progressHtml);
            } else if (this.status !== WorkItemCard.STATUS.RUNNING && existingProgress) {
                existingProgress.remove();
            }
        }
    }

    /**
     * Update progress (only for running status)
     *
     * @param {number} percent - Progress percentage (0-100)
     */
    updateProgress(percent) {
        this.progress = Math.max(0, Math.min(100, percent));

        if (this.element && this.status === WorkItemCard.STATUS.RUNNING) {
            const progressBar = this.element.querySelector('.work-item-progress-bar');
            if (progressBar) {
                progressBar.style.width = `${this.progress}%`;
            }
        }
    }

    /**
     * Mark as dispatched
     */
    markDispatched() {
        this.updateStatus(WorkItemCard.STATUS.DISPATCHED);
    }

    /**
     * Mark as running
     */
    markRunning() {
        this.updateStatus(WorkItemCard.STATUS.RUNNING);
        this.updateProgress(10); // Start with 10%
    }

    /**
     * Mark as done
     *
     * @param {Object} [payload] - Completion payload
     */
    markDone(payload = {}) {
        this.updateStatus(WorkItemCard.STATUS.DONE, payload);
        this.updateProgress(100);
    }

    /**
     * Mark as failed
     *
     * @param {string} [error] - Error message
     */
    markFailed(error) {
        this.updateStatus(WorkItemCard.STATUS.FAILED, { error });
    }

    /**
     * Get element
     *
     * @returns {HTMLElement|null}
     */
    getElement() {
        return this.element;
    }

    /**
     * Destroy card
     */
    destroy() {
        if (this.element && this.element.parentNode) {
            this.element.remove();
        }
        this.element = null;
    }
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WorkItemCard;
}
