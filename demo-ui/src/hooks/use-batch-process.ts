import { useMutation } from '@tanstack/react-query';
import { ApiClientError } from '@/lib/api/client';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const REQUEST_TIMEOUT = 120000; // 2 minutes for batch operations

interface BatchEnrollRequest {
  files: File[];
  user_ids: string[];
}

interface BatchVerifyRequest {
  files: File[];
  user_ids: string[];
  threshold?: number;
}

// Backend response types
interface BackendBatchEnrollResult {
  user_id: string;
  success: boolean;
  embedding_id?: string;
  error?: string;
}

interface BackendBatchEnrollResponse {
  results: BackendBatchEnrollResult[];
  total_processed: number;
  successful: number;
  failed: number;
  processing_time_ms: number;
}

interface BackendBatchVerifyResult {
  user_id: string;
  success: boolean;
  match?: boolean;
  similarity?: number;
  error?: string;
}

interface BackendBatchVerifyResponse {
  results: BackendBatchVerifyResult[];
  total_processed: number;
  matched: number;
  unmatched: number;
  failed: number;
  processing_time_ms: number;
}

// UI-friendly types
interface BatchResult {
  index: number;
  success: boolean;
  user_id?: string;
  error?: string;
  similarity?: number;
  match?: boolean;
  embedding_id?: string;
}

interface BatchEnrollResponse {
  results: BatchResult[];
  total: number;
  successful: number;
  failed: number;
  processing_time_ms: number;
}

interface BatchVerifyResponse {
  results: BatchResult[];
  total: number;
  matched: number;
  unmatched: number;
  failed: number;
  processing_time_ms: number;
}

async function batchEnroll(request: BatchEnrollRequest): Promise<BatchEnrollResponse> {
  const formData = new FormData();

  // Backend expects 'files' field name and 'items' as JSON string
  request.files.forEach((file) => {
    formData.append('files', file);
  });

  // Backend expects items as JSON array
  const items = request.user_ids.map((user_id) => ({ user_id }));
  formData.append('items', JSON.stringify(items));

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

  try {
    const response = await fetch(`${API_URL}/api/v1/batch/enroll`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Batch enrollment failed' }));
      throw new ApiClientError(response.status, error.message || error.detail, {
        code: error.error_code,
        details: error,
      });
    }

    const data: BackendBatchEnrollResponse = await response.json();

    // Transform to UI-friendly format
    return {
      results: data.results.map((result, index) => ({
        index,
        success: result.success,
        user_id: result.user_id,
        error: result.error,
        embedding_id: result.embedding_id,
      })),
      total: data.total_processed,
      successful: data.successful,
      failed: data.failed,
      processing_time_ms: data.processing_time_ms,
    };
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiClientError(408, 'Request timeout - batch enrollment took too long');
    }
    throw new ApiClientError(0, error instanceof Error ? error.message : 'Unknown error');
  } finally {
    clearTimeout(timeoutId);
  }
}

async function batchVerify(request: BatchVerifyRequest): Promise<BatchVerifyResponse> {
  const formData = new FormData();

  // Backend expects 'files' field name
  request.files.forEach((file) => {
    formData.append('files', file);
  });

  // Backend expects items as JSON array
  const items = request.user_ids.map((user_id) => ({ user_id }));
  formData.append('items', JSON.stringify(items));

  if (request.threshold !== undefined) {
    formData.append('threshold', request.threshold.toString());
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

  try {
    const response = await fetch(`${API_URL}/api/v1/batch/verify`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Batch verification failed' }));
      throw new ApiClientError(response.status, error.message || error.detail, {
        code: error.error_code,
        details: error,
      });
    }

    const data: BackendBatchVerifyResponse = await response.json();

    // Transform to UI-friendly format
    return {
      results: data.results.map((result, index) => ({
        index,
        success: result.success,
        user_id: result.user_id,
        error: result.error,
        match: result.match,
        similarity: result.similarity,
      })),
      total: data.total_processed,
      matched: data.matched,
      unmatched: data.unmatched,
      failed: data.failed,
      processing_time_ms: data.processing_time_ms,
    };
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiClientError(408, 'Request timeout - batch verification took too long');
    }
    throw new ApiClientError(0, error instanceof Error ? error.message : 'Unknown error');
  } finally {
    clearTimeout(timeoutId);
  }
}

export function useBatchEnroll() {
  return useMutation({
    mutationFn: batchEnroll,
    mutationKey: ['batch-enroll'],
  });
}

export function useBatchVerify() {
  return useMutation({
    mutationFn: batchVerify,
    mutationKey: ['batch-verify'],
  });
}

// Generic batch process hook
interface BatchProcessRequest {
  files: File[];
  operation: 'enroll' | 'verify' | 'quality' | 'demographics';
  user_ids?: string[];
  threshold?: number;
}

interface BatchProcessResponse {
  results: BatchResult[];
  total: number;
  successful: number;
  failed: number;
  processing_time_ms: number;
}

async function batchProcess(request: BatchProcessRequest): Promise<BatchProcessResponse> {
  const formData = new FormData();

  // Backend expects 'files' field name
  request.files.forEach((file) => {
    formData.append('files', file);
  });

  // Backend expects items as JSON array for enroll/verify
  if (request.user_ids && (request.operation === 'enroll' || request.operation === 'verify')) {
    const items = request.user_ids.map((user_id) => ({ user_id }));
    formData.append('items', JSON.stringify(items));
  }

  if (request.threshold !== undefined) {
    formData.append('threshold', request.threshold.toString());
  }

  const endpoints: Record<string, string> = {
    enroll: '/api/v1/batch/enroll',
    verify: '/api/v1/batch/verify',
    quality: '/api/v1/batch/quality',
    demographics: '/api/v1/batch/demographics',
  };

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

  try {
    const response = await fetch(`${API_URL}${endpoints[request.operation]}`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Batch processing failed' }));
      throw new ApiClientError(response.status, error.message || error.detail, {
        code: error.error_code,
        details: error,
      });
    }

    const data = await response.json();

    // Transform to UI-friendly format
    return {
      results: (data.results || []).map((result: Record<string, unknown>, index: number) => ({
        index,
        success: result.success as boolean,
        user_id: result.user_id as string | undefined,
        error: result.error as string | undefined,
        match: result.match as boolean | undefined,
        similarity: result.similarity as number | undefined,
      })),
      total: data.total_processed || data.total || 0,
      successful: data.successful || 0,
      failed: data.failed || 0,
      processing_time_ms: data.processing_time_ms || 0,
    };
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiClientError(408, 'Request timeout - batch processing took too long');
    }
    throw new ApiClientError(0, error instanceof Error ? error.message : 'Unknown error');
  } finally {
    clearTimeout(timeoutId);
  }
}

export function useBatchProcess() {
  return useMutation({
    mutationFn: batchProcess,
    mutationKey: ['batch-process'],
  });
}

export type {
  BatchEnrollRequest,
  BatchVerifyRequest,
  BatchProcessRequest,
  BatchEnrollResponse,
  BatchVerifyResponse,
  BatchProcessResponse,
  BatchResult,
};
