/**
 * Centralized API Configuration
 *
 * This file provides a single source of truth for all API-related configuration.
 * All components and hooks should import from here instead of using environment
 * variables directly, ensuring consistency across the application.
 */

// Default configuration values
const DEFAULTS = {
  API_PORT: 8000,
  API_HOST: 'localhost',
  API_PROTOCOL: 'http',
  WS_PROTOCOL: 'ws',
  API_VERSION: 'v1',
  REQUEST_TIMEOUT: 60000, // 60 seconds for ML operations
  LONG_REQUEST_TIMEOUT: 120000, // 120 seconds for batch/heavy operations
} as const;

/**
 * Build the API base URL from environment or defaults
 */
function buildApiUrl(): string {
  // Priority: environment variable > default construction
  if (process.env.NEXT_PUBLIC_API_URL) {
    // If explicitly set (even if empty), use it
    if (process.env.NEXT_PUBLIC_API_URL === '') {
      // Empty means same origin (static export served by FastAPI)
      return typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8001';
    }
    return process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, '');
  }

  const protocol = process.env.NEXT_PUBLIC_API_PROTOCOL || DEFAULTS.API_PROTOCOL;
  const host = process.env.NEXT_PUBLIC_API_HOST || DEFAULTS.API_HOST;
  const port = process.env.NEXT_PUBLIC_API_PORT || DEFAULTS.API_PORT;

  return `${protocol}://${host}:${port}`;
}

/**
 * Build the WebSocket URL from environment or defaults
 */
function buildWsUrl(): string {
  if (process.env.NEXT_PUBLIC_WS_URL) {
    return process.env.NEXT_PUBLIC_WS_URL.replace(/\/$/, '');
  }

  // If API URL is empty (same origin), derive WebSocket URL from current location
  if (process.env.NEXT_PUBLIC_API_URL === '' && typeof window !== 'undefined') {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return `${protocol}://${window.location.host}`;
  }

  const protocol = process.env.NEXT_PUBLIC_WS_PROTOCOL || DEFAULTS.WS_PROTOCOL;
  const host = process.env.NEXT_PUBLIC_API_HOST || DEFAULTS.API_HOST;
  const port = process.env.NEXT_PUBLIC_API_PORT || DEFAULTS.API_PORT;

  return `${protocol}://${host}:${port}`;
}

/**
 * API Configuration object - use this throughout the application
 */
export const API_CONFIG = {
  // Base URLs
  BASE_URL: buildApiUrl(),
  WS_URL: buildWsUrl(),

  // API Version
  VERSION: DEFAULTS.API_VERSION,

  // Full API path prefix
  get API_PREFIX() {
    return `/api/${this.VERSION}`;
  },

  // Timeouts
  TIMEOUT: {
    DEFAULT: DEFAULTS.REQUEST_TIMEOUT,
    LONG: DEFAULTS.LONG_REQUEST_TIMEOUT,
    SHORT: 30000, // 30 seconds for quick operations
  },

  // Endpoints
  ENDPOINTS: {
    // Health & Status
    HEALTH: '/health',

    // Face Operations
    ENROLL: '/enroll',
    VERIFY: '/verify',
    SEARCH: '/search',
    COMPARE: '/compare',

    // Analysis
    QUALITY: '/quality',
    LIVENESS: '/liveness',
    DEMOGRAPHICS: '/demographics',
    LANDMARKS: '/landmarks',

    // Multi-face
    DETECT_FACES: '/detect-faces',
    SIMILARITY_MATRIX: '/similarity-matrix',

    // Batch
    BATCH_PROCESS: '/batch/process',

    // Card Detection
    CARD_DETECTION: '/card-detection',

    // Management
    EMBEDDINGS: '/embeddings',
    DELETE_USER: '/delete',
  },

  /**
   * Build full endpoint URL
   */
  buildUrl(endpoint: string): string {
    return `${this.BASE_URL}${this.API_PREFIX}${endpoint}`;
  },

  /**
   * Build WebSocket endpoint URL
   */
  buildWsUrl(endpoint: string): string {
    return `${this.WS_URL}${this.API_PREFIX}${endpoint}`;
  },
} as const;

// Export individual values for convenience
export const API_BASE_URL = API_CONFIG.BASE_URL;
export const API_WS_URL = API_CONFIG.WS_URL;
export const API_TIMEOUT = API_CONFIG.TIMEOUT.DEFAULT;
export const API_LONG_TIMEOUT = API_CONFIG.TIMEOUT.LONG;

// Type exports
export type ApiEndpoint = keyof typeof API_CONFIG.ENDPOINTS;
