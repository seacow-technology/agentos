/**
 * StageBar Component - Horizontal stage progress visualization
 *
 * PR-V4: Pipeline Visualization
 * Displays: Planning → Executing → Verifying → Done
 */

class StageBar {
    /**
     * Stage definitions matching v0.4 task phases
     */
    static STAGES = [
        { id: 'planning', label: 'Planning', icon: 'assignment' },
        { id: 'executing', label: 'Executing', icon: 'settings' },
        { id: 'verifying', label: 'Verifying', icon: 'check' },
        { id: 'done', label: 'Done', icon: 'check' }
    ];

    /**
     * Create stage bar
     *
     * @param {HTMLElement} container - Container element
     */
    constructor(container) {
        this.container = container;
        this.currentStage = null;
        this.completedStages = new Set();
        this.failedStages = new Set();

        this.render();
    }

    /**
     * Render stage bar
     */
    render() {
        const html = `
            <div class="stage-bar">
                ${StageBar.STAGES.map((stage, index) => `
                    <div class="stage" data-stage="${stage.id}">
                        <div class="stage-indicator">
                            <span class="stage-icon">${stage.icon}</span>
                        </div>
                        <div class="stage-label">${stage.label}</div>
                        ${index < StageBar.STAGES.length - 1 ? '<div class="stage-connector"></div>' : ''}
                    </div>
                `).join('')}
            </div>
        `;

        this.container.innerHTML = html;
    }

    /**
     * Activate stage (set as current)
     *
     * @param {string} stageId - Stage ID (planning, executing, verifying, done)
     */
    activateStage(stageId) {
        console.log(`[StageBar] Activating stage: ${stageId}`);

        // Remove active from all stages
        this.container.querySelectorAll('.stage').forEach(el => {
            el.classList.remove('active');
        });

        // Add active to current stage
        const stageEl = this.container.querySelector(`[data-stage="${stageId}"]`);
        if (stageEl) {
            stageEl.classList.add('active');
            this.currentStage = stageId;
        }
    }

    /**
     * Complete stage (mark as done)
     *
     * @param {string} stageId - Stage ID
     */
    completeStage(stageId) {
        console.log(`[StageBar] Completing stage: ${stageId}`);

        const stageEl = this.container.querySelector(`[data-stage="${stageId}"]`);
        if (stageEl) {
            stageEl.classList.remove('active');
            stageEl.classList.add('completed');
            this.completedStages.add(stageId);
        }
    }

    /**
     * Fail stage (mark as failed)
     *
     * @param {string} stageId - Stage ID
     */
    failStage(stageId) {
        console.log(`[StageBar] Failing stage: ${stageId}`);

        const stageEl = this.container.querySelector(`[data-stage="${stageId}"]`);
        if (stageEl) {
            stageEl.classList.remove('active');
            stageEl.classList.add('failed');
            this.failedStages.add(stageId);
        }
    }

    /**
     * Reset stage (back to pending)
     *
     * @param {string} stageId - Stage ID
     */
    resetStage(stageId) {
        console.log(`[StageBar] Resetting stage: ${stageId}`);

        const stageEl = this.container.querySelector(`[data-stage="${stageId}"]`);
        if (stageEl) {
            stageEl.classList.remove('active', 'completed', 'failed');
            this.completedStages.delete(stageId);
            this.failedStages.delete(stageId);
        }
    }

    /**
     * Get current stage
     *
     * @returns {string|null}
     */
    getCurrentStage() {
        return this.currentStage;
    }

    /**
     * Check if stage is completed
     *
     * @param {string} stageId - Stage ID
     * @returns {boolean}
     */
    isCompleted(stageId) {
        return this.completedStages.has(stageId);
    }

    /**
     * Check if stage is failed
     *
     * @param {string} stageId - Stage ID
     * @returns {boolean}
     */
    isFailed(stageId) {
        return this.failedStages.has(stageId);
    }

    /**
     * Reset all stages
     */
    reset() {
        console.log('[StageBar] Resetting all stages');

        this.currentStage = null;
        this.completedStages.clear();
        this.failedStages.clear();

        this.container.querySelectorAll('.stage').forEach(el => {
            el.classList.remove('active', 'completed', 'failed');
        });
    }
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = StageBar;
}
