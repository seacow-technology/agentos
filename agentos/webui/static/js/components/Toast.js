/**
 * Toast - Toast notification component
 *
 * Features:
 * - Success/Error/Warning/Info types
 * - Auto-dismiss
 * - Manual dismiss
 * - Stacking
 * - Position configuration
 * - Action buttons (M-13: Unified Error Handling)
 * - Error categorization
 *
 * v0.3.2 - WebUI 100% Coverage Sprint
 * v0.3.2 - M-13: Unified Error Notification
 */

class ToastManager {
    constructor(options = {}) {
        this.options = {
            position: options.position || 'top-right',
            duration: options.duration || 3000,
            maxToasts: options.maxToasts || 5,
            ...options,
        };

        this.toasts = [];
        this.container = null;
        this.init();
    }

    /**
     * Initialize toast container
     */
    init() {
        this.container = document.createElement('div');
        this.container.className = `toast-container ${this.options.position}`;
        document.body.appendChild(this.container);
    }

    /**
     * Show toast
     *
     * @param {string|Object} message - Message or options object
     * @param {string} type - Toast type (info, success, error, warning)
     * @param {number} duration - Duration in ms (0 = no auto-dismiss)
     * @param {Object} options - Additional options (action, details, etc.)
     */
    show(message, type = 'info', duration = null, options = {}) {
        // Handle object parameter
        if (typeof message === 'object') {
            options = message;
            message = options.message;
            type = options.type || type;
            duration = options.duration !== undefined ? options.duration : duration;
        }

        // Remove oldest toast if at max capacity
        if (this.toasts.length >= this.options.maxToasts) {
            this.remove(this.toasts[0]);
        }

        const toast = this.createToast(message, type, duration, options);
        this.toasts.push(toast);
        this.container.appendChild(toast.element);

        // Trigger animation
        setTimeout(() => {
            toast.element.classList.add('show');
        }, 10);

        // Auto-dismiss
        if (toast.duration > 0) {
            toast.timer = setTimeout(() => {
                this.remove(toast);
            }, toast.duration);
        }

        return toast;
    }

    /**
     * Create toast element
     * M-13: Enhanced with action buttons and details
     */
    createToast(message, type, duration, options = {}) {
        const toast = {
            id: Date.now() + Math.random(),
            type: type,
            message: message,
            duration: duration !== null ? duration : this.options.duration,
            element: null,
            timer: null,
            options: options
        };

        // Toast element
        const element = document.createElement('div');
        element.className = `toast toast-${type}`;
        element.dataset.toastId = toast.id;

        // Icon
        const icon = document.createElement('div');
        icon.className = 'toast-icon';
        icon.innerHTML = this.getIcon(type);
        element.appendChild(icon);

        // Content
        const content = document.createElement('div');
        content.className = 'toast-content';

        const messageEl = document.createElement('div');
        messageEl.className = 'toast-message';
        messageEl.textContent = message;
        content.appendChild(messageEl);

        // Details (optional)
        if (options.details) {
            const detailsEl = document.createElement('div');
            detailsEl.className = 'toast-details';
            detailsEl.textContent = options.details;
            content.appendChild(detailsEl);
        }

        // Action button (optional)
        if (options.action) {
            const actionBtn = document.createElement('button');
            actionBtn.className = 'toast-action';
            actionBtn.textContent = options.action.label || 'Action';
            actionBtn.onclick = () => {
                if (options.action.onClick) {
                    options.action.onClick(toast);
                }
                if (options.action.dismiss !== false) {
                    this.remove(toast);
                }
            };
            content.appendChild(actionBtn);
        }

        element.appendChild(content);

        // Close button
        const closeBtn = document.createElement('button');
        closeBtn.className = 'toast-close';
        closeBtn.innerHTML = '×';
        closeBtn.onclick = () => this.remove(toast);
        element.appendChild(closeBtn);

        toast.element = element;
        return toast;
    }

    /**
     * Get icon for toast type
     */
    getIcon(type) {
        const icons = {
            success: 'check_circle',
            error: 'cancel',
            warning: 'warning',
            info: 'info',
        };
        const iconName = icons[type] || icons.info;
        return `<span class="material-icons">${iconName}</span>`;
    }

    /**
     * Remove toast
     */
    remove(toast) {
        if (!toast || !toast.element) {
            return;
        }

        // Clear timer
        if (toast.timer) {
            clearTimeout(toast.timer);
        }

        // Fade out
        toast.element.classList.remove('show');

        // Remove from DOM after animation
        setTimeout(() => {
            if (toast.element && toast.element.parentNode) {
                toast.element.parentNode.removeChild(toast.element);
            }

            // Remove from array
            this.toasts = this.toasts.filter(t => t.id !== toast.id);
        }, 300);
    }

    /**
     * Remove all toasts
     */
    clear() {
        this.toasts.forEach(toast => this.remove(toast));
    }

    /**
     * Convenience methods
     */
    success(message, duration, options) {
        return this.show(message, 'success', duration, options);
    }

    error(message, duration, options) {
        return this.show(message, 'error', duration, options);
    }

    warning(message, duration, options) {
        return this.show(message, 'warning', duration, options);
    }

    info(message, duration, options) {
        return this.show(message, 'info', duration, options);
    }

    /**
     * M-13: Show error with retry action
     */
    showErrorWithRetry(message, retryCallback, details = null) {
        return this.error(message, 0, {
            details: details,
            action: {
                label: 'Retry',
                onClick: (toast) => {
                    if (retryCallback) {
                        retryCallback();
                    }
                },
                dismiss: true
            }
        });
    }

    /**
     * M-13: Show API error (normalized)
     */
    showApiError(apiResponse, retryCallback = null) {
        const errorType = apiResponse.error || 'unknown_error';
        const message = apiResponse.message || 'An error occurred';
        const details = apiResponse.detail || null;

        const options = {
            details: details
        };

        // Add retry action for retryable errors
        if (retryCallback && this.isRetryableError(errorType)) {
            options.action = {
                label: 'Retry',
                onClick: retryCallback,
                dismiss: true
            };
        }

        return this.error(message, 0, options);
    }

    /**
     * M-13: Check if error is retryable
     */
    isRetryableError(errorType) {
        const retryableErrors = [
            'timeout',
            'network_error',
            'service_unavailable',
            'bad_gateway',
            'rate_limited'
        ];
        return retryableErrors.includes(errorType);
    }
}

// Create global instance
window.toastManager = new ToastManager();

// Global function for convenience
window.showToast = (message, type, duration, options) => {
    return window.toastManager.show(message, type, duration, options);
};

// Export Toast object for convenience (alias to toastManager)
window.Toast = window.toastManager;
