/**
 * API Client for Biometric Processor Frontend
 *
 * Provides a centralized, type-safe HTTP client with:
 * - Automatic correlation ID injection
 * - Request/response interceptors
 * - Retry logic for transient failures
 * - Timeout configuration
 * - Error handling and transformation
 */

import {
  ApiClientError,
  NetworkError,
  TimeoutError,
  createErrorFromResponse,
  isRetryableError,
} from './errors';

/**
 * API client configuration
 */
export interface ApiClientConfig {
  baseURL?: string;
  timeout?: number;
  retryAttempts?: number;
  retryDelay?: number;
  headers?: Record<string, string>;
  onRequest?: (url: string, options: RequestInit) => void | Promise<void>;
  onResponse?: (response: Response) => void | Promise<void>;
  onError?: (error: ApiClientError) => void | Promise<void>;
}

/**
 * Request options
 */
export interface RequestOptions extends Omit<RequestInit, 'body'> {
  timeout?: number;
  retry?: boolean;
  retryAttempts?: number;
  correlationId?: string;
  params?: Record<string, string | number | boolean | undefined>;
}

/**
 * Default configuration
 */
const DEFAULT_CONFIG: Required<Omit<ApiClientConfig, 'onRequest' | 'onResponse' | 'onError'>> = {
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001',
  timeout: 30000, // 30 seconds
  retryAttempts: 3,
  retryDelay: 1000, // 1 second base delay
  headers: {
    'Content-Type': 'application/json',
  },
};

/**
 * API Client class
 */
class ApiClient {
  private config: Required<Omit<ApiClientConfig, 'onRequest' | 'onResponse' | 'onError'>>;
  private onRequest?: (url: string, options: RequestInit) => void | Promise<void>;
  private onResponse?: (response: Response) => void | Promise<void>;
  private onError?: (error: ApiClientError) => void | Promise<void>;

  constructor(config: ApiClientConfig = {}) {
    this.config = {
      ...DEFAULT_CONFIG,
      ...config,
      headers: {
        ...DEFAULT_CONFIG.headers,
        ...config.headers,
      },
    };

    this.onRequest = config.onRequest;
    this.onResponse = config.onResponse;
    this.onError = config.onError;
  }

  /**
   * Generate correlation ID
   */
  private generateCorrelationId(): string {
    // Use crypto.randomUUID if available (modern browsers)
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID();
    }

    // Fallback: Generate UUID v4
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  /**
   * Build URL with query parameters
   */
  private buildUrl(path: string, params?: Record<string, string | number | boolean | undefined>): string {
    const url = new URL(path, this.config.baseURL);

    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value));
        }
      });
    }

    return url.toString();
  }

  /**
   * Execute request with timeout
   */
  private async fetchWithTimeout(
    url: string,
    options: RequestInit,
    timeout: number
  ): Promise<Response> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      return response;
    } catch (error) {
      clearTimeout(timeoutId);

      if (error instanceof Error && error.name === 'AbortError') {
        throw new TimeoutError(timeout);
      }

      throw error;
    }
  }

  /**
   * Execute request with retry logic
   */
  private async executeWithRetry<T>(
    url: string,
    options: RequestInit,
    requestOptions: RequestOptions
  ): Promise<T> {
    const maxAttempts = requestOptions.retry !== false
      ? (requestOptions.retryAttempts ?? this.config.retryAttempts)
      : 1;

    let lastError: Error | undefined;

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      try {
        // Call onRequest hook
        if (this.onRequest) {
          await this.onRequest(url, options);
        }

        // Execute request with timeout
        const timeout = requestOptions.timeout ?? this.config.timeout;
        const response = await this.fetchWithTimeout(url, options, timeout);

        // Call onResponse hook
        if (this.onResponse) {
          await this.onResponse(response);
        }

        // Handle error responses
        if (!response.ok) {
          const error = await createErrorFromResponse(response);

          // Call onError hook
          if (this.onError) {
            await this.onError(error);
          }

          // Don't retry if error is not retryable
          if (!isRetryableError(error) || attempt === maxAttempts - 1) {
            throw error;
          }

          lastError = error;
        } else {
          // Success - parse and return response
          const contentType = response.headers.get('content-type');

          if (contentType?.includes('application/json')) {
            return await response.json();
          }

          // Return response object for non-JSON responses
          return response as unknown as T;
        }
      } catch (error) {
        lastError = error as Error;

        // Network errors
        if (error instanceof TypeError || (error instanceof Error && error.message.includes('fetch'))) {
          const networkError = new NetworkError(
            'Network request failed. Please check your internet connection.',
            error as Error
          );

          if (this.onError) {
            await this.onError(networkError);
          }

          // Don't retry on last attempt
          if (attempt === maxAttempts - 1) {
            throw networkError;
          }
        } else if (error instanceof ApiClientError) {
          // API errors - already handled above
          if (!isRetryableError(error) || attempt === maxAttempts - 1) {
            throw error;
          }
        } else {
          // Unknown errors - don't retry
          throw error;
        }
      }

      // Exponential backoff before retry
      if (attempt < maxAttempts - 1) {
        const delay = this.config.retryDelay * Math.pow(2, attempt);
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }

    // This should never happen, but TypeScript needs it
    throw lastError || new Error('Request failed');
  }

  /**
   * Execute HTTP request
   */
  public async request<T>(
    method: string,
    path: string,
    data?: unknown,
    options: RequestOptions = {}
  ): Promise<T> {
    // Build URL with query parameters
    const url = this.buildUrl(path, options.params);

    // Generate or use provided correlation ID
    const correlationId = options.correlationId || this.generateCorrelationId();

    // Merge headers
    const headers: Record<string, string> = {
      ...this.config.headers,
      'X-Request-ID': correlationId,
      ...(options.headers as Record<string, string>),
    };

    // Build request options
    const requestInit: RequestInit = {
      method,
      headers,
      credentials: 'include', // Include cookies for CORS
      ...options,
    };

    // Add body for non-GET requests
    if (data && method !== 'GET' && method !== 'HEAD') {
      if (data instanceof FormData) {
        // Let browser set Content-Type for FormData
        delete headers['Content-Type'];
        requestInit.body = data;
      } else {
        requestInit.body = JSON.stringify(data);
      }
    }

    return this.executeWithRetry<T>(url, requestInit, options);
  }

  /**
   * HTTP GET request
   */
  public async get<T>(path: string, options: RequestOptions = {}): Promise<T> {
    return this.request<T>('GET', path, undefined, options);
  }

  /**
   * HTTP POST request
   */
  public async post<T>(path: string, data?: unknown, options: RequestOptions = {}): Promise<T> {
    return this.request<T>('POST', path, data, options);
  }

  /**
   * HTTP PUT request
   */
  public async put<T>(path: string, data?: unknown, options: RequestOptions = {}): Promise<T> {
    return this.request<T>('PUT', path, data, options);
  }

  /**
   * HTTP PATCH request
   */
  public async patch<T>(path: string, data?: unknown, options: RequestOptions = {}): Promise<T> {
    return this.request<T>('PATCH', path, data, options);
  }

  /**
   * HTTP DELETE request
   */
  public async delete<T>(path: string, options: RequestOptions = {}): Promise<T> {
    return this.request<T>('DELETE', path, undefined, options);
  }

  /**
   * Upload file(s) with FormData
   */
  public async upload<T>(
    path: string,
    formData: FormData,
    options: RequestOptions = {}
  ): Promise<T> {
    return this.request<T>('POST', path, formData, options);
  }
}

/**
 * Default API client instance
 */
export const apiClient = new ApiClient({
  onRequest: (url, options) => {
    // Log requests in development
    if (process.env.NODE_ENV === 'development') {
      console.log(`[API] ${options.method} ${url}`);
    }
  },
  onResponse: (response) => {
    // Log responses in development
    if (process.env.NODE_ENV === 'development') {
      const correlationId = response.headers.get('X-Request-ID');
      console.log(`[API] ${response.status} ${response.url}`, { correlationId });
    }
  },
  onError: (error) => {
    // Log errors in development
    if (process.env.NODE_ENV === 'development') {
      console.error('[API Error]', {
        message: error.message,
        status: error.status,
        errorCode: error.errorCode,
        requestId: error.requestId,
      });
    }
  },
});

/**
 * Create custom API client instance
 */
export function createApiClient(config: ApiClientConfig): ApiClient {
  return new ApiClient(config);
}

/**
 * Export error classes for convenience
 */
export {
  ApiClientError,
  NetworkError,
  TimeoutError,
  ValidationError,
  AuthenticationError,
  AuthorizationError,
  NotFoundError,
  ServerError,
  isRetryableError,
} from './errors';
