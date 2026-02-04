/**
 * Platform HTTP Layer - Error Definitions
 *
 * Unified error model for all API interactions.
 * All errors extend from ApiError base class.
 */

export class ApiError extends Error {
  public readonly code: string;
  public readonly status?: number;
  public readonly details?: unknown;

  constructor(message: string, code: string, status?: number, details?: unknown) {
    super(message);
    this.name = this.constructor.name;
    this.code = code;
    this.status = status;
    this.details = details;

    // Maintains proper stack trace for where our error was thrown (only available on V8)
    if (typeof (Error as any).captureStackTrace === 'function') {
      (Error as any).captureStackTrace(this, this.constructor);
    }
  }

  public toJSON() {
    return {
      name: this.name,
      message: this.message,
      code: this.code,
      status: this.status,
      details: this.details,
    };
  }
}

/**
 * Network connectivity errors (DNS, connection refused, timeout, etc.)
 */
export class NetworkError extends ApiError {
  constructor(message: string = 'Network connection failed', details?: unknown) {
    super(message, 'NETWORK_ERROR', undefined, details);
  }
}

/**
 * Authentication errors (401/403)
 */
export class AuthError extends ApiError {
  constructor(message: string = 'Authentication failed', status: number, details?: unknown) {
    super(message, 'AUTH_ERROR', status, details);
  }
}

/**
 * Server errors (5xx)
 */
export class ServerError extends ApiError {
  constructor(message: string = 'Server error occurred', status: number, details?: unknown) {
    super(message, 'SERVER_ERROR', status, details);
  }
}

/**
 * Validation errors (400, 422)
 */
export class ValidationError extends ApiError {
  constructor(message: string = 'Validation failed', status: number, details?: unknown) {
    super(message, 'VALIDATION_ERROR', status, details);
  }
}

/**
 * Client errors (4xx, excluding auth and validation)
 */
export class ClientError extends ApiError {
  constructor(message: string = 'Client error occurred', status: number, details?: unknown) {
    super(message, 'CLIENT_ERROR', status, details);
  }
}

/**
 * Timeout errors
 */
export class TimeoutError extends ApiError {
  constructor(message: string = 'Request timeout', details?: unknown) {
    super(message, 'TIMEOUT_ERROR', 408, details);
  }
}
