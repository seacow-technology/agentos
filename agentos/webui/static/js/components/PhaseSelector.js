/**
 * PhaseSelector Component
 *
 * Execution phase selector for chat sessions.
 * Provides 2 phases: planning, execution
 *
 * Usage:
 *   const selector = new PhaseSelector({
 *     container: document.getElementById('phase-selector-container'),
 *     currentPhase: 'planning',
 *     sessionId: 'session-123',
 *     conversationMode: 'chat',
 *     onChange: (phase) => { console.log('Phase changed:', phase); }
 *   });
 */

class PhaseSelector {
    /**
     * @param {Object} options
     * @param {HTMLElement} options.container - Container element
     * @param {string} options.currentPhase - Current phase (default: 'planning')
     * @param {string} options.sessionId - Current session ID
     * @param {string} options.conversationMode - Current conversation mode
     * @param {Function} options.onChange - Callback when phase changes (phase) => void
     */
    constructor(options) {
        this.container = options.container;
        this.currentPhase = options.currentPhase || 'planning';
        this.sessionId = options.sessionId;
        this.conversationMode = options.conversationMode || 'chat';
        this.onChange = options.onChange || (() => {});

        this.phases = [
            {
                value: 'planning',
                label: 'Planning',
                description: 'Internal operations only'
            },
            {
                value: 'execution',
                label: 'Execution',
                description: 'External communication enabled'
            }
        ];

        this.render();
    }

    render() {
        const isDisabled = this.isDisabled();

        this.container.innerHTML = `
            <div class="phase-selector ${isDisabled ? 'disabled' : ''}">
                <label class="phase-selector-label">Execution Phase</label>
                <div class="phase-selector-options">
                    ${this.phases.map(phase => `
                        <button
                            class="phase-selector-option ${phase.value === this.currentPhase ? 'active' : ''} ${isDisabled ? 'disabled' : ''}"
                            data-phase="${phase.value}"
                            title="${isDisabled ? 'Phase selector is locked in Plan mode' : phase.description}"
                            ${isDisabled ? 'disabled' : ''}
                        >
                            <span class="phase-label">${phase.label}</span>
                        </button>
                    `).join('')}
                </div>
                ${isDisabled ? '<div class="phase-selector-hint">Fixed to Planning in Plan mode</div>' : ''}
            </div>
        `;

        if (!isDisabled) {
            this.attachEventListeners();
        }
    }

    attachEventListeners() {
        const buttons = this.container.querySelectorAll('.phase-selector-option');
        buttons.forEach(button => {
            button.addEventListener('click', () => {
                const phase = button.getAttribute('data-phase');
                this.selectPhase(phase);
            });
        });
    }

    isDisabled() {
        // Phase selector is disabled when conversation mode is 'plan'
        return this.conversationMode === 'plan';
    }

    async selectPhase(phase) {
        if (phase === this.currentPhase) {
            return; // Already selected
        }

        if (!this.sessionId || this.sessionId === 'main') {
            console.warn('[PhaseSelector] Invalid session ID, cannot update phase');
            this.showToast('Cannot update phase: Please start or select a valid session first', 'error');
            return;
        }

        console.log(`[PhaseSelector] Attempting to switch phase: ${this.currentPhase} -> ${phase}, session: ${this.sessionId}`);

        // Show confirmation dialog when switching to execution
        if (phase === 'execution') {
            const confirmed = await this.showConfirmDialog();
            if (!confirmed) {
                console.log('[PhaseSelector] User cancelled phase switch');
                return; // User cancelled
            }
        }

        try {
            const requestData = {
                phase,
                actor: 'user',
                reason: `User switched to ${phase} phase via WebUI`,
                confirmed: true  // Task #4: Safety check confirmation
            };

            console.log('[PhaseSelector] Sending API request:', requestData);

            // CSRF Fix: Use fetchWithCSRF for consistency and simplified code
            const response = await window.fetchWithCSRF(`/api/sessions/${this.sessionId}/phase`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });

            console.log('[PhaseSelector] API response status:', response.status, response.statusText);

            if (!response.ok) {
                // Special handling for 404 - session not found
                if (response.status === 404) {
                    console.error('[PhaseSelector] Session not found:', this.sessionId);
                    throw new Error('Session not found. Please refresh the page or start a new conversation.');
                }

                let error;
                try {
                    error = await response.json();
                } catch (parseError) {
                    console.error('[PhaseSelector] Failed to parse error response:', parseError);
                    throw new Error(`Failed to update phase (HTTP ${response.status})`);
                }

                // Handle both string and object detail formats
                let errorMessage = 'Failed to update phase';
                if (typeof error.detail === 'string') {
                    errorMessage = error.detail;
                } else if (error.detail && error.detail.message) {
                    errorMessage = error.detail.message;
                } else if (error.detail && error.detail.error) {
                    errorMessage = error.detail.error;
                } else if (error.message) {
                    errorMessage = error.message;
                }

                console.error('[PhaseSelector] Phase update failed:', error);
                throw new Error(errorMessage);
            }

            const data = await response.json();
            console.log('[PhaseSelector] Phase updated successfully:', data);

            // Update current phase
            this.currentPhase = phase;

            // Update UI
            this.updateActiveButton(phase);

            // Trigger callback
            this.onChange(phase, data);

            // Show success toast
            this.showToast(`Phase changed to: ${phase}`, 'success');

        } catch (error) {
            console.error('[PhaseSelector] Failed to update execution phase:', error);
            // Show detailed error message to user
            this.showToast(`Failed to update phase: ${error.message}`, 'error');
        }
    }

    async showConfirmDialog() {
        // Always use Dialog component (no fallback to native confirm)
        if (!window.Dialog || typeof window.Dialog.confirm !== 'function') {
            console.error('Dialog component not loaded! Cannot show confirmation.');
            // Show error toast and return false
            this.showToast('Cannot show confirmation dialog: Dialog component not loaded', 'error');
            return false;
        }

        return await window.Dialog.confirm(
            'Switch to execution phase? This allows external communication including web search and URL fetching.',
            {
                title: 'Confirm Phase Change',
                confirmText: 'Switch to Execution',
                cancelText: 'Cancel'
            }
        );
    }

    updateActiveButton(phase) {
        const buttons = this.container.querySelectorAll('.phase-selector-option');
        buttons.forEach(button => {
            if (button.getAttribute('data-phase') === phase) {
                button.classList.add('active');
            } else {
                button.classList.remove('active');
            }
        });
    }

    setSessionId(sessionId) {
        this.sessionId = sessionId;
    }

    setPhase(phase) {
        this.currentPhase = phase;
        this.updateActiveButton(phase);
    }

    setConversationMode(mode) {
        this.conversationMode = mode;

        // Force to planning phase if mode is 'plan'
        if (mode === 'plan' && this.currentPhase !== 'planning') {
            this.currentPhase = 'planning';
        }

        // Re-render to update disabled state
        this.render();
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
    module.exports = PhaseSelector;
}
