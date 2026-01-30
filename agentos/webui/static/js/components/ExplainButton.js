/**
 * ExplainButton Component
 *
 * A reusable button component that triggers BrainOS Explain drawer
 * for any entity (task, extension, file).
 *
 * Usage:
 *   const btn = new ExplainButton('task', task.id, task.name);
 *   containerEl.innerHTML = btn.render();
 *   ExplainButton.attachHandlers();
 *
 * Part of: PR-WebUI-BrainOS-1B (Explain Button Embedding)
 */

class ExplainButton {
    /**
     * Create an ExplainButton
     *
     * @param {string} entityType - Type of entity ('task', 'extension', 'file')
     * @param {string} entityKey - Key/ID used for querying
     * @param {string} entityName - Display name for the entity
     */
    constructor(entityType, entityKey, entityName) {
        this.entityType = entityType;
        this.entityKey = entityKey;
        this.entityName = entityName;
    }

    /**
     * Render the button HTML
     *
     * @returns {string} HTML string for the button
     */
    render() {
        return `
            <button class="explain-btn"
                    data-entity-type="${this.entityType}"
                    data-entity-key="${this.escapeHtml(this.entityKey)}"
                    data-entity-name="${this.escapeHtml(this.entityName)}"
                    title="Explain with BrainOS"
                    aria-label="Explain ${this.escapeHtml(this.entityName)} with BrainOS">
                psychology
            </button>
        `;
    }

    /**
     * Escape HTML to prevent XSS
     *
     * @param {string} str - String to escape
     * @returns {string} Escaped string
     */
    escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    /**
     * Attach event handlers to all explain buttons on the page
     * Call this after rendering buttons into the DOM
     */
    static attachHandlers() {
        document.querySelectorAll('.explain-btn:not([data-handler-attached])').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                e.preventDefault();

                const entityType = btn.dataset.entityType;
                const entityKey = btn.dataset.entityKey;
                const entityName = btn.dataset.entityName;

                // Ensure ExplainDrawer is available
                if (typeof ExplainDrawer !== 'undefined') {
                    ExplainDrawer.show(entityType, entityKey, entityName);
                } else {
                    console.error('ExplainDrawer is not loaded');
                }
            });

            // Mark handler as attached to prevent duplicate listeners
            btn.setAttribute('data-handler-attached', 'true');
        });
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.ExplainButton = ExplainButton;
}
