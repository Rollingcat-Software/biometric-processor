import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

interface BatchEnrollRequest {
  files: File[];
  user_ids: string[];
}

interface BatchVerifyRequest {
  files: File[];
  user_ids: string[];
  threshold?: number;
}

interface BatchResult {
  index: number;
  success: boolean;
  user_id?: string;
  error?: string;
  similarity?: number;
  match?: boolean;
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
  request.files.forEach((file, i) => {
    formData.append('images', file);
    formData.append('user_ids', request.user_ids[i] || `user_${i}`);
  });

  const response = await apiClient.post<BatchEnrollResponse>('/batch/enroll', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response;
}

async function batchVerify(request: BatchVerifyRequest): Promise<BatchVerifyResponse> {
  const formData = new FormData();
  request.files.forEach((file, i) => {
    formData.append('images', file);
    formData.append('user_ids', request.user_ids[i] || '');
  });
  if (request.threshold !== undefined) {
    formData.append('threshold', request.threshold.toString());
  }

  const response = await apiClient.post<BatchVerifyResponse>('/batch/verify', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response;
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
  request.files.forEach((file, i) => {
    formData.append('images', file);
    if (request.user_ids?.[i]) {
      formData.append('user_ids', request.user_ids[i]);
    }
  });

  if (request.threshold !== undefined) {
    formData.append('threshold', request.threshold.toString());
  }

  const endpoints: Record<string, string> = {
    enroll: '/batch/enroll',
    verify: '/batch/verify',
    quality: '/batch/quality',
    demographics: '/batch/demographics',
  };

  const response = await apiClient.post<BatchProcessResponse>(
    endpoints[request.operation],
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
  return response;
}

export function useBatchProcess() {
  return useMutation({
    mutationFn: batchProcess,
    mutationKey: ['batch-process'],
  });
}
