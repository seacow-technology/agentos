/**
 * FormValidator - Real-time form validation utility
 *
 * Features:
 * - Input-time validation with debouncing
 * - Visual feedback (success/error states)
 * - Field-level error messages
 * - Custom validation rules
 * - Async validation support
 * - Form-level validation
 *
 * Usage:
 * ```javascript
 * const validator = new FormValidator(formElement, {
 *     fields: {
 *         email: {
 *             rules: ['required', 'email'],
 *             message: 'Please enter a valid email'
 *         },
 *         password: {
 *             rules: ['required', 'minLength:8'],
 *             message: 'Password must be at least 8 characters'
 *         }
 *     }
 * });
 *
 * validator.onValidate((isValid, errors) => {
 *     submitButton.disabled = !isValid;
 * });
 * ```
 *
 * v0.3.2 - M-14: Real-time Form Validation
 */

class FormValidator {
    constructor(formElement, options = {}) {
        this.form = formElement;
        this.options = {
            // Validation rules for each field
            fields: options.fields || {},
            // Debounce delay for input validation (ms)
            debounceDelay: options.debounceDelay || 300,
            // Validate on blur
            validateOnBlur: options.validateOnBlur !== false,
            // Validate on input
            validateOnInput: options.validateOnInput !== false,
            // Show success state
            showSuccess: options.showSuccess !== false,
            // Callback on validation change
            onChange: options.onChange,
            // Custom validators
            customValidators: options.customValidators || {},
            ...options
        };

        this.fields = {};
        this.errors = {};
        this.isValid = false;
        this.debounceTimers = {};

        this.init();
    }

    /**
     * Initialize validator
     */
    init() {
        if (!this.form) {
            console.error('[FormValidator] Form element not found');
            return;
        }

        // Setup field validation
        for (const [fieldName, fieldConfig] of Object.entries(this.options.fields)) {
            this.setupField(fieldName, fieldConfig);
        }

        // Prevent native HTML5 validation
        this.form.setAttribute('novalidate', 'novalidate');
    }

    /**
     * Setup validation for a field
     */
    setupField(fieldName, fieldConfig) {
        const field = this.form.querySelector(`[name="${fieldName}"]`);

        if (!field) {
            console.warn(`[FormValidator] Field "${fieldName}" not found in form`);
            return;
        }

        this.fields[fieldName] = {
            element: field,
            config: fieldConfig,
            wrapper: this.findFieldWrapper(field)
        };

        // Setup event listeners
        if (this.options.validateOnInput) {
            field.addEventListener('input', () => {
                this.validateFieldDebounced(fieldName);
            });
        }

        if (this.options.validateOnBlur) {
            field.addEventListener('blur', () => {
                this.validateField(fieldName);
            });
        }

        // Initial validation state
        this.clearFieldError(fieldName);
    }

    /**
     * Find field wrapper element
     */
    findFieldWrapper(field) {
        // Try to find wrapper with specific classes
        let wrapper = field.closest('.form-group, .field-group, .input-group');

        // If not found, create a wrapper
        if (!wrapper) {
            wrapper = document.createElement('div');
            wrapper.className = 'form-field-wrapper';
            field.parentNode.insertBefore(wrapper, field);
            wrapper.appendChild(field);
        }

        return wrapper;
    }

    /**
     * Validate field (debounced)
     */
    validateFieldDebounced(fieldName) {
        // Clear existing timer
        if (this.debounceTimers[fieldName]) {
            clearTimeout(this.debounceTimers[fieldName]);
        }

        // Set new timer
        this.debounceTimers[fieldName] = setTimeout(() => {
            this.validateField(fieldName);
        }, this.options.debounceDelay);
    }

    /**
     * Validate single field
     */
    async validateField(fieldName) {
        const fieldData = this.fields[fieldName];
        if (!fieldData) return true;

        const { element, config } = fieldData;
        const value = element.value;
        const rules = config.rules || [];

        // Run validation rules
        for (const rule of rules) {
            const error = await this.runRule(rule, value, fieldName, element);
            if (error) {
                this.setFieldError(fieldName, error);
                return false;
            }
        }

        // Validation passed
        this.clearFieldError(fieldName);
        return true;
    }

    /**
     * Run validation rule
     */
    async runRule(rule, value, fieldName, element) {
        // Parse rule (e.g., "minLength:8" => {name: "minLength", param: "8"})
        let ruleName = rule;
        let ruleParam = null;

        if (typeof rule === 'string' && rule.includes(':')) {
            const [name, param] = rule.split(':');
            ruleName = name;
            ruleParam = param;
        }

        // Check custom validators first
        if (this.options.customValidators[ruleName]) {
            const validator = this.options.customValidators[ruleName];
            return await validator(value, ruleParam, element);
        }

        // Built-in validators
        switch (ruleName) {
            case 'required':
                if (!value || value.trim() === '') {
                    return `${this.getFieldLabel(fieldName)} is required`;
                }
                break;

            case 'email':
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (value && !emailRegex.test(value)) {
                    return 'Please enter a valid email address';
                }
                break;

            case 'url':
                try {
                    new URL(value);
                } catch (e) {
                    return 'Please enter a valid URL';
                }
                break;

            case 'minLength':
                const minLen = parseInt(ruleParam);
                if (value.length < minLen) {
                    return `Must be at least ${minLen} characters`;
                }
                break;

            case 'maxLength':
                const maxLen = parseInt(ruleParam);
                if (value.length > maxLen) {
                    return `Must be no more than ${maxLen} characters`;
                }
                break;

            case 'min':
                const minVal = parseFloat(ruleParam);
                if (parseFloat(value) < minVal) {
                    return `Must be at least ${minVal}`;
                }
                break;

            case 'max':
                const maxVal = parseFloat(ruleParam);
                if (parseFloat(value) > maxVal) {
                    return `Must be no more than ${maxVal}`;
                }
                break;

            case 'pattern':
                const regex = new RegExp(ruleParam);
                if (!regex.test(value)) {
                    return this.fields[fieldName].config.message || 'Invalid format';
                }
                break;

            case 'match':
                const matchField = this.form.querySelector(`[name="${ruleParam}"]`);
                if (matchField && value !== matchField.value) {
                    return `Must match ${this.getFieldLabel(ruleParam)}`;
                }
                break;

            case 'number':
                if (isNaN(value) || value === '') {
                    return 'Must be a valid number';
                }
                break;

            case 'integer':
                if (!Number.isInteger(Number(value))) {
                    return 'Must be a whole number';
                }
                break;

            case 'alphanum':
                if (!/^[a-zA-Z0-9]+$/.test(value)) {
                    return 'Must contain only letters and numbers';
                }
                break;

            case 'alpha':
                if (!/^[a-zA-Z]+$/.test(value)) {
                    return 'Must contain only letters';
                }
                break;

            default:
                console.warn(`[FormValidator] Unknown rule: ${ruleName}`);
        }

        return null; // No error
    }

    /**
     * Set field error
     */
    setFieldError(fieldName, error) {
        const fieldData = this.fields[fieldName];
        if (!fieldData) return;

        const { element, wrapper } = fieldData;
        this.errors[fieldName] = error;

        // Add error class
        wrapper.classList.add('has-error');
        wrapper.classList.remove('has-success');
        element.classList.add('is-invalid');
        element.classList.remove('is-valid');

        // Show error message
        let errorEl = wrapper.querySelector('.field-error');
        if (!errorEl) {
            errorEl = document.createElement('div');
            errorEl.className = 'field-error';
            wrapper.appendChild(errorEl);
        }
        errorEl.textContent = error;
        errorEl.style.display = 'block';

        // Update form validity
        this.updateFormValidity();
    }

    /**
     * Clear field error
     */
    clearFieldError(fieldName) {
        const fieldData = this.fields[fieldName];
        if (!fieldData) return;

        const { element, wrapper } = fieldData;
        delete this.errors[fieldName];

        // Remove error class
        wrapper.classList.remove('has-error');
        element.classList.remove('is-invalid');

        // Add success class if enabled
        if (this.options.showSuccess && element.value) {
            wrapper.classList.add('has-success');
            element.classList.add('is-valid');
        }

        // Hide error message
        const errorEl = wrapper.querySelector('.field-error');
        if (errorEl) {
            errorEl.style.display = 'none';
        }

        // Update form validity
        this.updateFormValidity();
    }

    /**
     * Get field label
     */
    getFieldLabel(fieldName) {
        const fieldData = this.fields[fieldName];
        if (!fieldData) return fieldName;

        const { wrapper } = fieldData;
        const label = wrapper.querySelector('label');

        if (label) {
            return label.textContent.trim().replace('*', '');
        }

        // Convert camelCase to Title Case
        return fieldName
            .replace(/([A-Z])/g, ' $1')
            .replace(/^./, str => str.toUpperCase())
            .trim();
    }

    /**
     * Validate all fields
     */
    async validateAll() {
        const validations = [];

        for (const fieldName of Object.keys(this.fields)) {
            validations.push(this.validateField(fieldName));
        }

        const results = await Promise.all(validations);
        return results.every(result => result === true);
    }

    /**
     * Update form validity
     */
    updateFormValidity() {
        const wasValid = this.isValid;
        this.isValid = Object.keys(this.errors).length === 0;

        // Trigger callback if validity changed
        if (wasValid !== this.isValid && this.options.onChange) {
            this.options.onChange(this.isValid, this.errors);
        }
    }

    /**
     * Get validation errors
     */
    getErrors() {
        return { ...this.errors };
    }

    /**
     * Check if form is valid
     */
    isFormValid() {
        return this.isValid && Object.keys(this.errors).length === 0;
    }

    /**
     * Reset validation
     */
    reset() {
        for (const fieldName of Object.keys(this.fields)) {
            this.clearFieldError(fieldName);
        }
        this.errors = {};
        this.isValid = false;
    }

    /**
     * Add field dynamically
     */
    addField(fieldName, fieldConfig) {
        this.options.fields[fieldName] = fieldConfig;
        this.setupField(fieldName, fieldConfig);
    }

    /**
     * Remove field
     */
    removeField(fieldName) {
        if (this.fields[fieldName]) {
            delete this.fields[fieldName];
            delete this.errors[fieldName];
            this.updateFormValidity();
        }
    }

    /**
     * Destroy validator
     */
    destroy() {
        // Clear timers
        for (const timer of Object.values(this.debounceTimers)) {
            clearTimeout(timer);
        }

        // Remove error elements
        for (const fieldData of Object.values(this.fields)) {
            const errorEl = fieldData.wrapper.querySelector('.field-error');
            if (errorEl) {
                errorEl.remove();
            }
        }

        this.fields = {};
        this.errors = {};
    }
}

// Export for use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = FormValidator;
}

// Also expose globally
if (typeof window !== 'undefined') {
    window.FormValidator = FormValidator;
}
