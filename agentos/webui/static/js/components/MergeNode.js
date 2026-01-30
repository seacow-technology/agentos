/**
 * MergeNode Component - Work items convergence visualization
 *
 * PR-V4: Pipeline Visualization
 * Shows the convergence point after all work_items complete
 */

class MergeNode {
    /**
     * Create merge node
     *
     * @param {HTMLElement} container - Container element
     * @param {Object} [options] - Options
     * @param {number} [options.totalItems] - Total number of work items
     */
    constructor(container, options = {}) {
        this.container = container;
        this.totalItems = options.totalItems || 0;
        this.completedItems = 0;
        this.element = null;

        this.render();
    }

    /**
     * Render merge node
     */
    render() {
        const div = document.createElement('div');
        div.className = 'merge-node';
        div.style.display = 'none'; // Hidden by default

        div.innerHTML = `
            <div class="merge-icon">bolt</div>
            <div class="merge-label">Work Items Merged</div>
            <div class="merge-stats">${this.completedItems}/${this.totalItems}</div>
        `;

        this.element = div;
        this.container.appendChild(div);
    }

    /**
     * Update progress
     *
     * @param {number} completed - Number of completed items
     * @param {number} [total] - Total items (optional, uses initial value if not provided)
     */
    updateProgress(completed, total) {
        this.completedItems = completed;
        if (total !== undefined) {
            this.totalItems = total;
        }

        console.log(`[MergeNode] Progress: ${this.completedItems}/${this.totalItems}`);

        if (this.element) {
            const stats = this.element.querySelector('.merge-stats');
            if (stats) {
                stats.textContent = `${this.completedItems}/${this.totalItems}`;
            }

            // Show merge node when all items are complete
            if (this.completedItems === this.totalItems && this.totalItems > 0) {
                this.show();
            }
        }
    }

    /**
     * Show merge node
     */
    show() {
        console.log('[MergeNode] Showing merge node');

        if (this.element) {
            this.element.style.display = 'block';

            // Add entrance animation
            this.element.style.animation = 'stamp 0.6s ease-out';
        }
    }

    /**
     * Hide merge node
     */
    hide() {
        console.log('[MergeNode] Hiding merge node');

        if (this.element) {
            this.element.style.display = 'none';
        }
    }

    /**
     * Reset merge node
     */
    reset() {
        console.log('[MergeNode] Resetting merge node');

        this.completedItems = 0;
        this.hide();
    }

    /**
     * Destroy merge node
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
    module.exports = MergeNode;
}
