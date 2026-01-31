/**
 * ApiClient - Unified API request wrapper
 *
 * Features:
 * - Automatic timeout
 * - Error normalization
 * - Request ID tracking
 * - Retry logic
 * - Session expiry handling (401)
 *
 * v0.3.2 - WebUI 100% Coverage Sprint
 * v0.3.2 - M-16: Session Expiry Handler
 */

class ApiClient {
    constructor(baseUrl = '', defaultTimeout = 30000) {
        this.baseUrl = baseUrl;
        this.defaultTimeout = defaultTimeout;
        this.requestIdCounter = 0;
        this.sessionExpiredCallback = null;
        this.sessionExpiredShown = false; // Prevent multiple dialogs
    }

    /**
     * Generate unique request ID
     */
    generateRequestId() {
        this.requestIdCounter++;
        const timestamp = Date.now();
        return `req_${timestamp}_${this.requestIdCounter}`;
    }

    /**
     * Normalize error response
     */
    normalizeError(error, requestId) {
        // Network errors
        if (error.name === 'AbortError') {
            return {
                ok: false,
                error: 'timeout',
                message: 'Request timeout',
                request_id: requestId,
                timestamp: new Date().toISOString(),
            };
        }

        if (error.message === 'Failed to fetch' || error.message.includes('NetworkError')) {
            return {
                ok: false,
                error: 'network_error',
                message: 'Network connection failed',
                request_id: requestId,
                timestamp: new Date().toISOString(),
            };
        }

        // HTTP errors
        if (error.status) {
            const errorMap = {
                400: 'bad_request',
                401: 'unauthorized',
                403: 'forbidden',
                404: 'not_found',
                429: 'rate_limited',
                500: 'internal_error',
                502: 'bad_gateway',
                503: 'service_unavailable',
            };

            return {
                ok: false,
                error: errorMap[error.status] || 'http_error',
                message: error.message || `HTTP ${error.status}`,
                status: error.status,
                request_id: requestId,
                timestamp: new Date().toISOString(),
                detail: error.detail,
            };
        }

        // Generic error
        return {
            ok: false,
            error: 'unknown_error',
            message: error.message || 'An unknown error occurred',
            request_id: requestId,
            timestamp: new Date().toISOString(),
        };
    }

    /**
     * Make HTTP request with timeout and error handling
     */
    async request(url, options = {}) {
        const requestId = options.requestId || this.generateRequestId();
        const timeout = options.timeout || this.defaultTimeout;

        // Create abort controller for timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);

        try {
            // Add CSRF token for state-changing methods
            const method = (options.method || 'GET').toUpperCase();
            const protectedMethods = ['POST', 'PUT', 'PATCH', 'DELETE'];
            const needsCSRF = protectedMethods.includes(method);

            const headers = {
                'Content-Type': 'application/json',
                'X-Request-ID': requestId,
                ...options.headers,
            };

            if (needsCSRF) {
                const token = window.getCSRFToken && window.getCSRFToken();
                if (token) {
                    headers['X-CSRF-Token'] = token;
                }
            }

            // Merge options
            const fetchOptions = {
                ...options,
                signal: controller.signal,
                headers: headers,
            };

            // Make request
            const response = await fetch(this.baseUrl + url, fetchOptions);

            clearTimeout(timeoutId);

            // Parse response
            let data;
            const contentType = response.headers.get('content-type');

            if (contentType && contentType.includes('application/json')) {
                data = await response.json();
            } else {
                data = await response.text();
            }

            // Check HTTP status
            if (!response.ok) {
                const error = new Error(data.detail || data.message || `HTTP ${response.status}`);
                error.status = response.status;
                error.detail = data.detail;

                // Handle session expiry (401)
                if (response.status === 401 && !options.skipSessionExpiry) {
                    this.handleSessionExpired();
                }

                throw error;
            }

            // Task #14: Validate timestamps in development environment
            const isDev = (typeof process !== 'undefined' && process.env && process.env.NODE_ENV === 'development') ||
                          window.location.hostname === 'localhost' ||
                          window.location.hostname === '127.0.0.1';

            if (isDev && typeof data === 'object' && data !== null) {
                this._validateTimestamps(data, '', this.baseUrl + url);
            }

            // Success response
            return {
                ok: true,
                data: data,
                request_id: requestId,
                timestamp: new Date().toISOString(),
                status: response.status,
            };

        } catch (error) {
            clearTimeout(timeoutId);
            return this.normalizeError(error, requestId);
        }
    }

    /**
     * Convenience methods
     */
    async get(url, options = {}) {
        return this.request(url, { ...options, method: 'GET' });
    }

    async post(url, data, options = {}) {
        return this.request(url, {
            ...options,
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    async put(url, data, options = {}) {
        return this.request(url, {
            ...options,
            method: 'PUT',
            body: JSON.stringify(data),
        });
    }

    async patch(url, data, options = {}) {
        return this.request(url, {
            ...options,
            method: 'PATCH',
            body: JSON.stringify(data),
        });
    }

    async delete(url, options = {}) {
        return this.request(url, { ...options, method: 'DELETE' });
    }

    /**
     * Retry wrapper
     */
    async withRetry(fn, retries = 3, delay = 1000) {
        let lastError;

        for (let i = 0; i < retries; i++) {
            try {
                const result = await fn();
                if (result.ok) {
                    return result;
                }
                lastError = result;

                // Don't retry on client errors (4xx)
                if (result.status && result.status >= 400 && result.status < 500) {
                    return result;
                }
            } catch (error) {
                lastError = this.normalizeError(error, this.generateRequestId());
            }

            // Wait before retry (exponential backoff)
            if (i < retries - 1) {
                await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, i)));
            }
        }

        return lastError;
    }

    /**
     * Handle session expired (401)
     * M-16: Session Expiry Handler
     */
    handleSessionExpired() {
        // Only show once
        if (this.sessionExpiredShown) {
            return;
        }
        this.sessionExpiredShown = true;

        console.warn('[ApiClient] Session expired (401)');

        // Trigger custom callback if set
        if (this.sessionExpiredCallback) {
            this.sessionExpiredCallback();
            return;
        }

        // Default behavior: show dialog
        this.showSessionExpiredDialog();
    }

    /**
     * Show session expired dialog
     */
    showSessionExpiredDialog() {
        // Use Dialog component if available
        if (typeof Dialog !== 'undefined') {
            Dialog.show({
                title: 'Session Expired',
                message: 'Your session has expired. Please refresh the page to continue.',
                icon: 'lock_clock',
                type: 'warning',
                buttons: [
                    {
                        label: 'Refresh Page',
                        primary: true,
                        onClick: () => {
                            window.location.reload();
                        }
                    },
                    {
                        label: 'Stay',
                        onClick: () => {
                            this.sessionExpiredShown = false; // Allow showing again
                        }
                    }
                ]
            });
        } else {
            // Fallback to native confirm
            if (confirm('Your session has expired. Refresh the page to continue?')) {
                window.location.reload();
            } else {
                this.sessionExpiredShown = false; // Allow showing again
            }
        }
    }

    /**
     * Set custom session expired callback
     *
     * @param {Function} callback - Callback function
     */
    onSessionExpired(callback) {
        this.sessionExpiredCallback = callback;
    }

    /**
     * Reset session expired flag
     */
    resetSessionExpired() {
        this.sessionExpiredShown = false;
    }

    /**
     * Validate timestamp fields in API response (Task #14)
     * Checks if timestamp fields have proper timezone markers (Z or offset)
     *
     * @param {Object} obj - Object to validate
     * @param {string} path - Current object path for error reporting
     * @param {string} apiUrl - API URL for error reporting
     */
    _validateTimestamps(obj, path = '', apiUrl = '') {
        if (!obj || typeof obj !== 'object') return;

        // Timestamp field names
        const timeFieldNames = new Set([
            'created_at', 'updated_at', 'timestamp', 'reviewed_at',
            'executed_at', 'completed_at', 'started_at', 'ended_at',
            'last_updated', 'last_seen', 'expires_at', 'deleted_at',
            'scheduled_at', 'published_at', 'modified_at'
        ]);

        for (const [key, value] of Object.entries(obj)) {
            const fieldPath = path ? `${path}.${key}` : key;

            // Check if this is a timestamp field
            if (timeFieldNames.has(key) && typeof value === 'string') {
                // Check format
                if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(value)) {
                    const hasTimezone = value.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(value);

                    if (!hasTimezone) {
                        console.error(
                            `[ApiClient] API returned timestamp without timezone marker!\n` +
                            `   URL: ${apiUrl}\n` +
                            `   Field: ${fieldPath}\n` +
                            `   Value: ${value}\n` +
                            `   Expected: ${value}Z`
                        );
                    }
                }
            }

            // Recursively check nested objects and arrays
            if (typeof value === 'object' && value !== null) {
                if (Array.isArray(value)) {
                    value.forEach((item, index) => {
                        this._validateTimestamps(item, `${fieldPath}[${index}]`, apiUrl);
                    });
                } else {
                    this._validateTimestamps(value, fieldPath, apiUrl);
                }
            }
        }
    }
}

// Create global instance
window.apiClient = new ApiClient();
