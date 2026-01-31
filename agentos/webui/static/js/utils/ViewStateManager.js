/**
 * ViewStateManager - Manage view state persistence across navigation
 *
 * Features:
 * - Save/restore view state using sessionStorage
 * - URL query parameter integration
 * - Automatic cleanup of old states
 * - Deep merge support for nested state
 * - View-specific state isolation
 *
 * Usage:
 * ```javascript
 * const stateManager = new ViewStateManager('historyView');
 *
 * // Save state
 * stateManager.saveState({ filters: { status: 'success' }, scrollTop: 100 });
 *
 * // Restore state
 * const state = stateManager.restoreState();
 * ```
 *
 * v0.3.2 - M-11: View State Management
 */

class ViewStateManager {
    constructor(viewName, options = {}) {
        this.viewName = viewName;
        this.options = {
            // Storage key prefix
            prefix: options.prefix || 'agentos_view_state',
            // Max age in milliseconds (default 1 hour)
            maxAge: options.maxAge || 3600000,
            // Use URL parameters
            useUrlParams: options.useUrlParams !== false,
            // Deep merge nested objects
            deepMerge: options.deepMerge !== false,
            // Auto-save on changes
            autoSave: options.autoSave || false,
            ...options
        };

        this.storageKey = `${this.options.prefix}_${this.viewName}`;
        this.currentState = null;

        // Auto-cleanup old states on initialization
        this.cleanupOldStates();
    }

    /**
     * Get storage key for view
     */
    getStorageKey() {
        return this.storageKey;
    }

    /**
     * Save view state
     *
     * @param {Object} state - State object to save
     * @param {boolean} [merge=true] - Merge with existing state
     */
    saveState(state, merge = true) {
        try {
            let finalState = state;

            if (merge && this.options.deepMerge) {
                const existing = this.restoreState();
                finalState = this.deepMerge(existing || {}, state);
            }

            const stateData = {
                state: finalState,
                timestamp: Date.now(),
                version: '1.0'
            };

            sessionStorage.setItem(this.storageKey, JSON.stringify(stateData));
            this.currentState = finalState;

            // Also save to URL if enabled
            if (this.options.useUrlParams) {
                this.saveToUrl(finalState);
            }

            return true;
        } catch (error) {
            console.error(`[ViewStateManager] Failed to save state for ${this.viewName}:`, error);
            return false;
        }
    }

    /**
     * Restore view state
     *
     * @param {Object} [defaultState={}] - Default state if none saved
     * @returns {Object} Restored state or default
     */
    restoreState(defaultState = {}) {
        try {
            // First try to restore from sessionStorage
            const stored = sessionStorage.getItem(this.storageKey);

            if (stored) {
                const stateData = JSON.parse(stored);

                // Check if state is expired
                if (this.options.maxAge && Date.now() - stateData.timestamp > this.options.maxAge) {
                    console.log(`[ViewStateManager] State expired for ${this.viewName}, using default`);
                    this.clearState();
                    return defaultState;
                }

                this.currentState = stateData.state;
                return stateData.state;
            }

            // Try to restore from URL parameters
            if (this.options.useUrlParams) {
                const urlState = this.restoreFromUrl();
                if (Object.keys(urlState).length > 0) {
                    this.currentState = urlState;
                    return urlState;
                }
            }

            return defaultState;
        } catch (error) {
            console.error(`[ViewStateManager] Failed to restore state for ${this.viewName}:`, error);
            return defaultState;
        }
    }

    /**
     * Update partial state
     *
     * @param {Object} partialState - Partial state to merge
     */
    updateState(partialState) {
        const current = this.restoreState();
        const updated = this.deepMerge(current, partialState);
        this.saveState(updated, false);
    }

    /**
     * Clear view state
     */
    clearState() {
        try {
            sessionStorage.removeItem(this.storageKey);
            this.currentState = null;

            // Clear URL params if enabled
            if (this.options.useUrlParams) {
                this.clearUrl();
            }

            return true;
        } catch (error) {
            console.error(`[ViewStateManager] Failed to clear state for ${this.viewName}:`, error);
            return false;
        }
    }

    /**
     * Get current state (cached)
     *
     * @returns {Object} Current state
     */
    getCurrentState() {
        if (!this.currentState) {
            this.currentState = this.restoreState();
        }
        return this.currentState;
    }

    /**
     * Deep merge objects
     *
     * @param {Object} target - Target object
     * @param {Object} source - Source object
     * @returns {Object} Merged object
     */
    deepMerge(target, source) {
        const result = { ...target };

        for (const key in source) {
            if (source.hasOwnProperty(key)) {
                if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
                    result[key] = this.deepMerge(result[key] || {}, source[key]);
                } else {
                    result[key] = source[key];
                }
            }
        }

        return result;
    }

    /**
     * Save state to URL parameters
     *
     * @param {Object} state - State to save
     */
    saveToUrl(state) {
        try {
            const url = new URL(window.location.href);

            // Serialize state to URL params (only top-level primitive values)
            for (const key in state) {
                if (state.hasOwnProperty(key)) {
                    const value = state[key];
                    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
                        url.searchParams.set(`${this.viewName}_${key}`, String(value));
                    }
                }
            }

            // Update URL without reload
            window.history.replaceState({}, '', url.toString());
        } catch (error) {
            console.error(`[ViewStateManager] Failed to save state to URL:`, error);
        }
    }

    /**
     * Restore state from URL parameters
     *
     * @returns {Object} State from URL
     */
    restoreFromUrl() {
        try {
            const url = new URL(window.location.href);
            const state = {};
            const prefix = `${this.viewName}_`;

            for (const [key, value] of url.searchParams.entries()) {
                if (key.startsWith(prefix)) {
                    const stateKey = key.substring(prefix.length);
                    // Try to parse as number or boolean
                    if (value === 'true') {
                        state[stateKey] = true;
                    } else if (value === 'false') {
                        state[stateKey] = false;
                    } else if (!isNaN(value) && value !== '') {
                        state[stateKey] = Number(value);
                    } else {
                        state[stateKey] = value;
                    }
                }
            }

            return state;
        } catch (error) {
            console.error(`[ViewStateManager] Failed to restore state from URL:`, error);
            return {};
        }
    }

    /**
     * Clear URL parameters for this view
     */
    clearUrl() {
        try {
            const url = new URL(window.location.href);
            const prefix = `${this.viewName}_`;
            const keysToDelete = [];

            for (const key of url.searchParams.keys()) {
                if (key.startsWith(prefix)) {
                    keysToDelete.push(key);
                }
            }

            keysToDelete.forEach(key => url.searchParams.delete(key));
            window.history.replaceState({}, '', url.toString());
        } catch (error) {
            console.error(`[ViewStateManager] Failed to clear URL:`, error);
        }
    }

    /**
     * Cleanup old states from sessionStorage
     */
    cleanupOldStates() {
        try {
            const now = Date.now();
            const prefix = this.options.prefix;

            for (let i = 0; i < sessionStorage.length; i++) {
                const key = sessionStorage.key(i);
                if (key && key.startsWith(prefix)) {
                    try {
                        const data = JSON.parse(sessionStorage.getItem(key));
                        if (data.timestamp && now - data.timestamp > this.options.maxAge) {
                            sessionStorage.removeItem(key);
                        }
                    } catch (e) {
                        // Invalid data, remove it
                        sessionStorage.removeItem(key);
                    }
                }
            }
        } catch (error) {
            console.error('[ViewStateManager] Failed to cleanup old states:', error);
        }
    }

    /**
     * Export state as JSON
     *
     * @returns {string} JSON string
     */
    exportState() {
        const state = this.getCurrentState();
        return JSON.stringify(state, null, 2);
    }

    /**
     * Import state from JSON
     *
     * @param {string} json - JSON string
     */
    importState(json) {
        try {
            const state = JSON.parse(json);
            this.saveState(state, false);
            return true;
        } catch (error) {
            console.error('[ViewStateManager] Failed to import state:', error);
            return false;
        }
    }

    /**
     * Get all saved views
     *
     * @returns {Array} List of view names with saved states
     */
    static getAllSavedViews() {
        const views = [];
        const prefix = 'agentos_view_state_';

        try {
            for (let i = 0; i < sessionStorage.length; i++) {
                const key = sessionStorage.key(i);
                if (key && key.startsWith(prefix)) {
                    const viewName = key.substring(prefix.length);
                    const data = JSON.parse(sessionStorage.getItem(key));
                    views.push({
                        name: viewName,
                        timestamp: data.timestamp,
                        age: Date.now() - data.timestamp
                    });
                }
            }
        } catch (error) {
            console.error('[ViewStateManager] Failed to get saved views:', error);
        }

        return views;
    }

    /**
     * Clear all view states
     */
    static clearAllStates() {
        const prefix = 'agentos_view_state_';
        const keysToDelete = [];

        try {
            for (let i = 0; i < sessionStorage.length; i++) {
                const key = sessionStorage.key(i);
                if (key && key.startsWith(prefix)) {
                    keysToDelete.push(key);
                }
            }

            keysToDelete.forEach(key => sessionStorage.removeItem(key));
            return true;
        } catch (error) {
            console.error('[ViewStateManager] Failed to clear all states:', error);
            return false;
        }
    }
}

// Export for use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ViewStateManager;
}

// Also expose globally
if (typeof window !== 'undefined') {
    window.ViewStateManager = ViewStateManager;
}
