/**
 * API Error Classes for Biometric Processor Frontend
 *
 * Provides structured error handling for all API interactions.
 */

export interface ApiErrorDetails {
  error_code?: string;
  details?: Record<string, unknown>;
  request_id?: string;
  timestamp?: string;
}

/**
 * Base API client error class
 */
export class ApiClientError extends Error {
  public readonly status: number;
  public readonly errorCode?: string;
  public readonly details?: Record<string, unknown>;
  public readonly requestId?: string;
  public readonly timestamp?: string;
  public readonly isRetryable: boolean;

  constructor(
    status: number,
    message: string,
    errorDetails?: ApiErrorDetails,
    isRetryable: boolean = false
  ) {
    super(message);
    this.name = 'ApiClientError';
    this.status = status;
    this.errorCode = errorDetails?.error_code;
    this.details = errorDetails?.details;
    this.requestId = errorDetails?.request_id;
    this.timestamp = errorDetails?.timestamp;
    this.isRetryable = isRetryable;

    // Maintain proper stack trace for where our error was thrown (V8 only)
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, ApiClientError);
    }
  }

  /**
   * Get user-friendly error message
   */
  public getUserMessage(): string {
    // Map error codes to user-friendly messages
    const errorCodeMessages: Record<string, string> = {
      'FACE_NOT_DETECTED': 'No face detected in the image. Please ensure your face is clearly visible.',
      'MULTIPLE_FACES_DETECTED': 'Multiple faces detected. Please ensure only one face is in the image.',
      'LOW_QUALITY_IMAGE': 'Image quality is too low. Please use a clearer, well-lit image.',
      'ML_MODEL_TIMEOUT': 'The processing took too long. Please try again.',
      'ENROLLMENT_SESSION_INVALID': 'Your enrollment session has expired. Please start over.',
      'INSUFFICIENT_IMAGES': 'Not enough images provided. Please upload at least 2 images.',
      'TOO_MANY_IMAGES': 'Too many images provided. Maximum is 5 images.',
      'USER_ALREADY_ENROLLED': 'This user is already enrolled in the system.',
      'USER_NOT_FOUND': 'User not found in the system.',
      'INVALID_TENANT': 'Invalid tenant identifier.',
      'RATE_LIMIT_EXCEEDED': 'Too many requests. Please wait a moment and try again.',
    };

    return errorCodeMessages[this.errorCode || ''] || this.message;
  }

  /**
   * Format error for support request
   */
  public formatForSupport(): string {
    const parts = [
      `Error: ${this.message}`,
      this.errorCode ? `Code: ${this.errorCode}` : null,
      this.requestId ? `Request ID: ${this.requestId}` : null,
      this.timestamp ? `Time: ${this.timestamp}` : null,
      this.status ? `Status: ${this.status}` : null,
    ].filter(Boolean);

    return parts.join('\n');
  }
}

/**
 * Network error (timeout, connection refused, etc.)
 */
export class NetworkError extends ApiClientError {
  constructor(message: string, originalError?: Error) {
    super(0, message, undefined, true); // Network errors are retryable
    this.name = 'NetworkError';

    if (originalError) {
      this.stack = originalError.stack;
    }
  }
}

/**
 * Request timeout error
 */
export class TimeoutError extends ApiClientError {
  public readonly timeoutMs: number;

  constructor(timeoutMs: number, message?: string) {
    super(
      408,
      message || `Request timed out after ${timeoutMs}ms`,
      { error_code: 'REQUEST_TIMEOUT' },
      true // Timeouts are retryable
    );
    this.name = 'TimeoutError';
    this.timeoutMs = timeoutMs;
  }
}

/**
 * Validation error (400 Bad Request)
 */
export class ValidationError extends ApiClientError {
  public readonly fieldErrors?: Record<string, string[]>;

  constructor(message: string, errorDetails?: ApiErrorDetails & { field_errors?: Record<string, string[]> }) {
    super(400, message, errorDetails, false);
    this.name = 'ValidationError';
    this.fieldErrors = errorDetails?.field_errors;
  }
}

/**
 * Authentication error (401 Unauthorized)
 */
export class AuthenticationError extends ApiClientError {
  constructor(message: string = 'Authentication required', errorDetails?: ApiErrorDetails) {
    super(401, message, errorDetails, false);
    this.name = 'AuthenticationError';
  }
}

/**
 * Authorization error (403 Forbidden)
 */
export class AuthorizationError extends ApiClientError {
  constructor(message: string = 'Access forbidden', errorDetails?: ApiErrorDetails) {
    super(403, message, errorDetails, false);
    this.name = 'AuthorizationError';
  }
}

/**
 * Not found error (404)
 */
export class NotFoundError extends ApiClientError {
  public readonly resource?: string;

  constructor(message: string = 'Resource not found', resource?: string, errorDetails?: ApiErrorDetails) {
    super(404, message, errorDetails, false);
    this.name = 'NotFoundError';
    this.resource = resource;
  }
}

/**
 * Server error (500+)
 */
export class ServerError extends ApiClientError {
  constructor(status: number, message: string, errorDetails?: ApiErrorDetails) {
    super(
      status,
      message,
      errorDetails,
      true // Server errors are retryable (with exponential backoff)
    );
    this.name = 'ServerError';
  }
}

/**
 * Determine if an error is retryable
 */
export function isRetryableError(error: unknown): boolean {
  if (error instanceof ApiClientError) {
    return error.isRetryable;
  }

  // Network errors, timeouts, and 5xx errors are retryable
  if (error instanceof TypeError || error instanceof Error) {
    const message = error.message.toLowerCase();
    return (
      message.includes('network') ||
      message.includes('fetch') ||
      message.includes('timeout') ||
      message.includes('aborted')
    );
  }

  return false;
}

/**
 * Create appropriate error from HTTP response
 */
export async function createErrorFromResponse(
  response: Response,
  fallbackMessage: string = 'Request failed'
): Promise<ApiClientError> {
  let errorBody: any;

  try {
    const contentType = response.headers.get('content-type');
    if (contentType?.includes('application/json')) {
      errorBody = await response.json();
    } else {
      errorBody = { message: await response.text() };
    }
  } catch {
    errorBody = { message: fallbackMessage };
  }

  const message = errorBody.message || errorBody.detail || fallbackMessage;
  const errorDetails: ApiErrorDetails = {
    error_code: errorBody.error_code,
    details: errorBody.details,
    request_id: response.headers.get('X-Request-ID') || errorBody.request_id,
    timestamp: new Date().toISOString(),
  };

  // Create specific error types based on status code
  switch (response.status) {
    case 400:
      return new ValidationError(message, {
        ...errorDetails,
        field_errors: errorBody.field_errors,
      });

    case 401:
      return new AuthenticationError(message, errorDetails);

    case 403:
      return new AuthorizationError(message, errorDetails);

    case 404:
      return new NotFoundError(message, undefined, errorDetails);

    case 408:
      return new TimeoutError(30000, message);

    case 429:
      return new ApiClientError(429, message, {
        ...errorDetails,
        error_code: 'RATE_LIMIT_EXCEEDED',
      }, true);

    default:
      if (response.status >= 500) {
        return new ServerError(response.status, message, errorDetails);
      }
      return new ApiClientError(response.status, message, errorDetails);
  }
}
