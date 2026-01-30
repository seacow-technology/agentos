/**
 * AdminTokenGate - Admin Token Protection Component
 *
 * PR-4: Skills/Memory/Config Write Protection
 * Provides UI-level token management for high-risk write operations
 */

class AdminTokenGate {
    constructor() {
        this.TOKEN_KEY = 'agentos_admin_token';
        this.token = this.loadToken();
    }

    /**
     * Load token from sessionStorage
     */
    loadToken() {
        try {
            return sessionStorage.getItem(this.TOKEN_KEY);
        } catch (e) {
            console.warn('Failed to load admin token:', e);
            return null;
        }
    }

    /**
     * Save token to sessionStorage
     */
    saveToken(token) {
        try {
            if (token) {
                sessionStorage.setItem(this.TOKEN_KEY, token);
                this.token = token;
            } else {
                this.clearToken();
            }
        } catch (e) {
            console.error('Failed to save admin token:', e);
        }
    }

    /**
     * Clear token from sessionStorage
     */
    clearToken() {
        try {
            sessionStorage.removeItem(this.TOKEN_KEY);
            this.token = null;
        } catch (e) {
            console.error('Failed to clear admin token:', e);
        }
    }

    /**
     * Check if token is available
     */
    hasToken() {
        return !!this.token;
    }

    /**
     * Get token (returns null if not available)
     */
    getToken() {
        return this.token;
    }

    /**
     * Prompt user for token (if not already available)
     * Returns: Promise<string|null>
     */
    async promptForToken(options = {}) {
        const {
            title = 'Admin Token Required',
            message = 'This operation requires admin privileges. Please enter your admin token:',
            allowSkip = false
        } = options;

        // If token already available, return it
        if (this.hasToken()) {
            return this.token;
        }

        // Show token input dialog
        return new Promise((resolve) => {
            const dialog = this.createTokenDialog(title, message, allowSkip, (token, remember) => {
                if (token) {
                    if (remember) {
                        this.saveToken(token);
                    }
                    resolve(token);
                } else {
                    resolve(null);
                }
            });

            document.body.appendChild(dialog);
        });
    }

    /**
     * Create token input dialog
     */
    createTokenDialog(title, message, allowSkip, onSubmit) {
        const dialog = document.createElement('div');
        dialog.className = 'admin-token-dialog';
        dialog.innerHTML = `
            <div class="admin-token-overlay"></div>
            <div class="admin-token-content">
                <div class="admin-token-header">
                    <h3>${title}</h3>
                    <button class="btn-close" id="token-dialog-close">close</button>
                </div>
                <div class="admin-token-body">
                    <p>${message}</p>
                    <div class="form-group">
                        <label for="admin-token-input">Admin Token</label>
                        <input
                            type="password"
                            id="admin-token-input"
                            class="form-control"
                            placeholder="Enter admin token..."
                            autocomplete="off"
                        />
                    </div>
                    <div class="form-group">
                        <label class="checkbox-label">
                            <input type="checkbox" id="token-remember" />
                            <span>Remember token for this session</span>
                        </label>
                    </div>
                    ${allowSkip ? '<p class="text-sm text-gray-500">Note: You can skip this step, but the operation may fail if authentication is required.</p>' : ''}
                </div>
                <div class="admin-token-footer">
                    ${allowSkip ? '<button class="btn-secondary" id="token-skip">Skip</button>' : ''}
                    <button class="btn-secondary" id="token-cancel">Cancel</button>
                    <button class="btn-primary" id="token-submit">Submit</button>
                </div>
            </div>
        `;

        // Setup event listeners
        const overlay = dialog.querySelector('.admin-token-overlay');
        const closeBtn = dialog.querySelector('#token-dialog-close');
        const cancelBtn = dialog.querySelector('#token-cancel');
        const submitBtn = dialog.querySelector('#token-submit');
        const skipBtn = dialog.querySelector('#token-skip');
        const input = dialog.querySelector('#admin-token-input');
        const rememberCheckbox = dialog.querySelector('#token-remember');

        const closeDialog = () => {
            dialog.remove();
        };

        const submit = () => {
            const token = input.value.trim();
            const remember = rememberCheckbox.checked;
            closeDialog();
            onSubmit(token, remember);
        };

        const cancel = () => {
            closeDialog();
            onSubmit(null, false);
        };

        overlay.addEventListener('click', cancel);
        closeBtn.addEventListener('click', cancel);
        cancelBtn.addEventListener('click', cancel);
        submitBtn.addEventListener('click', submit);

        if (skipBtn) {
            skipBtn.addEventListener('click', () => {
                closeDialog();
                onSubmit('', false); // Empty token = skip
            });
        }

        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                submit();
            }
        });

        // Auto-focus input
        setTimeout(() => input.focus(), 100);

        return dialog;
    }

    /**
     * Execute a protected operation (with token gate)
     * Returns: Promise<result>
     */
    async executeProtected(operation, options = {}) {
        const {
            requireToken = false,
            allowSkip = false,
            title,
            message
        } = options;

        // If token not required, execute directly
        if (!requireToken) {
            return await operation(null);
        }

        // Get token (prompt if necessary)
        const token = await this.promptForToken({ title, message, allowSkip });

        if (!token && !allowSkip) {
            throw new Error('Admin token required but not provided');
        }

        // Execute operation with token
        return await operation(token);
    }

    /**
     * Inject token into API request headers
     * (Call this in ApiClient before sending requests)
     */
    injectTokenHeader(headers = {}) {
        if (this.hasToken()) {
            headers['X-Admin-Token'] = this.token;
        }
        return headers;
    }

    /**
     * Show token status in UI
     */
    renderTokenStatus(container) {
        if (!container) return;

        container.innerHTML = `
            <div class="admin-token-status">
                ${this.hasToken() ? `
                    <span class="status-indicator status-success">
                        <span class="status-dot"></span>
                        <span>Admin Token Active</span>
                    </span>
                    <button class="btn-sm btn-secondary" id="clear-token-btn">Clear Token</button>
                ` : `
                    <span class="status-indicator status-inactive">
                        <span class="status-dot"></span>
                        <span>No Admin Token</span>
                    </span>
                    <button class="btn-sm btn-primary" id="set-token-btn">Set Token</button>
                `}
            </div>
        `;

        const clearBtn = container.querySelector('#clear-token-btn');
        const setBtn = container.querySelector('#set-token-btn');

        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                this.clearToken();
                if (window.showToast) {
                    window.showToast('Admin token cleared', 'info');
                }
                this.renderTokenStatus(container);
            });
        }

        if (setBtn) {
            setBtn.addEventListener('click', async () => {
                await this.promptForToken({
                    title: 'Set Admin Token',
                    message: 'Enter your admin token to enable protected operations:'
                });
                this.renderTokenStatus(container);
            });
        }
    }
}

// Export global instance
window.adminTokenGate = new AdminTokenGate();
