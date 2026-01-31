/**
 * CSRF Protection Utility
 *
 * Provides automatic CSRF token injection for fetch requests.
 *
 * Security Issue: Task #36 - P0-5: Implement CSRF protection for Extensions interface
 *
 * Features:
 * - Reads CSRF token from cookie
 * - Automatically adds X-CSRF-Token header to state-changing requests
 * - Transparent integration with existing fetch calls
 * - Token refresh handling
 *
 * Usage:
 *   import { fetchWithCSRF } from './utils/csrf.js';
 *
 *   // Use fetchWithCSRF instead of fetch for protected endpoints
 *   const response = await fetchWithCSRF('/api/extensions/install', {
 *     method: 'POST',
 *     body: formData
 *   });
 */

/**
 * Get CSRF token from cookie
 *
 * @returns {string|null} CSRF token or null if not found
 */
export function getCSRFToken() {
    const name = 'csrf_token=';
    const decodedCookie = decodeURIComponent(document.cookie);
    const cookies = decodedCookie.split(';');

    for (let i = 0; i < cookies.length; i++) {
        let cookie = cookies[i].trim();
        if (cookie.indexOf(name) === 0) {
            return cookie.substring(name.length, cookie.length);
        }
    }

    return null;
}

/**
 * Check if method requires CSRF protection
 *
 * @param {string} method - HTTP method
 * @returns {boolean} True if method requires CSRF token
 */
function requiresCSRFProtection(method) {
    const protectedMethods = ['POST', 'PUT', 'PATCH', 'DELETE'];
    return protectedMethods.includes(method.toUpperCase());
}

/**
 * Fetch wrapper with automatic CSRF token injection
 *
 * This function wraps the native fetch API and automatically adds
 * the CSRF token to state-changing requests (POST, PUT, PATCH, DELETE).
 *
 * @param {string|Request} input - URL or Request object
 * @param {RequestInit} [init] - Fetch options
 * @returns {Promise<Response>} Fetch response
 */
export async function fetchWithCSRF(input, init = {}) {
    // Determine method
    const method = init.method || 'GET';

    // Only add CSRF token for state-changing methods
    if (requiresCSRFProtection(method)) {
        const token = getCSRFToken();

        if (!token) {
            console.warn('[CSRF] No CSRF token found in cookie. Request may fail.');
        }

        // Add CSRF token to headers
        const headers = new Headers(init.headers || {});
        if (token) {
            headers.set('X-CSRF-Token', token);
        }

        init.headers = headers;
    }

    try {
        const response = await fetch(input, init);

        // Check if CSRF token was rejected
        if (response.status === 403) {
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                const error = await response.clone().json();
                if (error.reason_code === 'CSRF_TOKEN_INVALID') {
                    console.error('[CSRF] Token validation failed. This may indicate a CSRF attack or expired session.');
                    // Show user-friendly error
                    showCSRFError();
                }
            }
        }

        return response;
    } catch (error) {
        console.error('[CSRF] Fetch error:', error);
        throw error;
    }
}

/**
 * Show CSRF error notification to user
 */
function showCSRFError() {
    // Create error notification
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        background: #ef4444;
        color: white;
        border-radius: 0.5rem;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        z-index: 10000;
        font-size: 0.875rem;
        font-weight: 500;
        max-width: 400px;
        animation: slideIn 0.3s ease;
    `;
    notification.innerHTML = `
        <div style="display: flex; align-items: start; gap: 0.75rem;">
            <span style="font-size: 1.25rem;">⚠️</span>
            <div>
                <div style="font-weight: 600; margin-bottom: 0.25rem;">Security Error</div>
                <div style="font-size: 0.8125rem; opacity: 0.95;">
                    Your session may have expired. Please refresh the page and try again.
                </div>
            </div>
        </div>
    `;

    document.body.appendChild(notification);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

/**
 * Inject CSRF token into form
 *
 * This is a utility for traditional HTML forms (if needed).
 * For AJAX requests, use fetchWithCSRF instead.
 *
 * @param {HTMLFormElement} form - Form element
 */
export function injectCSRFTokenIntoForm(form) {
    const token = getCSRFToken();

    if (!token) {
        console.warn('[CSRF] No CSRF token found. Form submission may fail.');
        return;
    }

    // Check if token input already exists
    let tokenInput = form.querySelector('input[name="csrf_token"]');

    if (!tokenInput) {
        // Create hidden input for token
        tokenInput = document.createElement('input');
        tokenInput.type = 'hidden';
        tokenInput.name = 'csrf_token';
        form.appendChild(tokenInput);
    }

    // Set token value
    tokenInput.value = token;
}

/**
 * Initialize CSRF protection globally
 *
 * This function can be called on page load to set up global CSRF protection.
 * It will automatically inject tokens into forms and provide a global fetch wrapper.
 */
export function initCSRFProtection() {
    console.log('[CSRF] Protection initialized');

    // Check if token exists
    const token = getCSRFToken();
    if (!token) {
        console.warn('[CSRF] No CSRF token found in cookie. Token will be generated on next GET request.');
    } else {
        console.log('[CSRF] Token found:', token.substring(0, 8) + '...');
    }

    // Optionally: Automatically inject into all forms on submit
    document.addEventListener('submit', (e) => {
        if (e.target.tagName === 'FORM') {
            const form = e.target;
            const method = (form.method || 'GET').toUpperCase();

            if (requiresCSRFProtection(method)) {
                injectCSRFTokenIntoForm(form);
            }
        }
    }, true);
}

// Add CSS for notifications
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Export for global use (non-module)
if (typeof window !== 'undefined') {
    window.getCSRFToken = getCSRFToken;
    window.fetchWithCSRF = fetchWithCSRF;
    window.initCSRFProtection = initCSRFProtection;
}
