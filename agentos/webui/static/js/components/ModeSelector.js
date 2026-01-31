/**
 * ModeSelector Component
 *
 * Conversation mode selector for chat sessions.
 * Provides 5 modes: chat, discussion, plan, development, task
 *
 * Usage:
 *   const selector = new ModeSelector({
 *     container: document.getElementById('mode-selector-container'),
 *     currentMode: 'chat',
 *     sessionId: 'session-123',
 *     onChange: (mode) => { console.log('Mode changed:', mode); }
 *   });
 */

class ModeSelector {
    /**
     * @param {Object} options
     * @param {HTMLElement} options.container - Container element
     * @param {string} options.currentMode - Current mode (default: 'chat')
     * @param {string} options.sessionId - Current session ID
     * @param {Function} options.onChange - Callback when mode changes (mode) => void
     */
    constructor(options) {
        this.container = options.container;
        this.currentMode = options.currentMode || 'chat';
        this.sessionId = options.sessionId;
        this.onChange = options.onChange || (() => {});

        this.modes = [
            {
                value: 'chat',
                label: 'Chat - Free Chat',
                description: 'Free-form conversation'
            },
            {
                value: 'discussion',
                label: 'Discussion - Structured',
                description: 'Structured brainstorming'
            },
            {
                value: 'plan',
                label: 'Plan - Planning',
                description: 'Planning and design'
            },
            {
                value: 'development',
                label: 'Development - Coding',
                description: 'Active development work'
            },
            {
                value: 'task',
                label: 'Task - Focused',
                description: 'Task-focused conversation'
            }
        ];

        this.render();
    }

    render() {
        this.container.innerHTML = `
            <select class="mode-selector-select" id="mode-selector-select" title="Conversation Mode">
                ${this.modes.map(mode => `
                    <option value="${mode.value}" ${mode.value === this.currentMode ? 'selected' : ''}>
                        ${mode.label}
                    </option>
                `).join('')}
            </select>
        `;

        this.attachEventListeners();
    }

    attachEventListeners() {
        const select = this.container.querySelector('.mode-selector-select');
        if (select) {
            select.addEventListener('change', (e) => {
                const mode = e.target.value;
                this.selectMode(mode);
            });
        }
    }

    async selectMode(mode) {
        if (mode === this.currentMode) {
            return; // Already selected
        }

        if (!this.sessionId || this.sessionId === 'main') {
            console.warn('Invalid session ID, cannot update mode');
            this.showToast('Cannot update mode: Please start or select a valid session first', 'error');
            return;
        }

        try {
            // CSRF Fix: Use fetchWithCSRF for consistency and simplified code
            const response = await window.fetchWithCSRF(`/api/sessions/${this.sessionId}/mode`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ mode })
            });

            if (!response.ok) {
                // Special handling for 404 - session not found
                if (response.status === 404) {
                    throw new Error('Session not found. Please refresh the page or start a new conversation.');
                }

                const error = await response.json();
                throw new Error(error.detail || 'Failed to update mode');
            }

            const data = await response.json();

            // Update current mode
            this.currentMode = mode;

            // Update UI
            this.updateActiveButton(mode);

            // Trigger callback
            this.onChange(mode, data);

            // Show success toast
            this.showToast(`Mode changed to: ${mode}`, 'success');

        } catch (error) {
            console.error('Failed to update conversation mode:', error);
            this.showToast(`Failed to update mode: ${error.message}`, 'error');
        }
    }

    updateActiveButton(mode) {
        const select = this.container.querySelector('.mode-selector-select');
        if (select) {
            select.value = mode;
        }
    }

    setSessionId(sessionId) {
        this.sessionId = sessionId;
    }

    setMode(mode) {
        this.currentMode = mode;
        this.updateActiveButton(mode);
    }

    showToast(message, type = 'info') {
        // Use Toast component if available, otherwise console
        if (window.Toast && typeof window.Toast.show === 'function') {
            window.Toast.show(message, type);
        } else {
            console.log(`[${type.toUpperCase()}] ${message}`);
        }
    }

    destroy() {
        this.container.innerHTML = '';
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ModeSelector;
}
