import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { API_CONFIG } from '@/config/api.config';

interface SimilarityMatrixRequest {
  files: File[];
  labels?: string[];
  threshold?: number;
}

interface SimilarityPair {
  a: string;
  b: string;
  similarity: number;
  match: boolean;
}

interface Cluster {
  cluster_id: number;
  members: string[];
}

interface SimilarityMatrixResponse {
  size: number;
  matrix: number[][];
  labels: string[];
  clusters: Cluster[];
  pairs: SimilarityPair[];
  threshold: number;
  computation_time_ms: number;
}

// For per-image validation
interface ImageValidationResult {
  index: number;
  label: string;
  valid: boolean;
  error?: string;
}

export interface SimilarityResult extends SimilarityMatrixResponse {
  validationResults?: ImageValidationResult[];
}

// Validate a single image for face detection
async function validateImage(file: File, label: string, index: number): Promise<ImageValidationResult> {
  const formData = new FormData();
  formData.append('file', file, file.name);

  try {
    const data = await apiClient.upload('/api/v1/quality/analyze', formData);
    return {
      index,
      label,
      valid: true,
      error: (data as any).passed ? undefined : 'Low quality face',
    };
  } catch (error) {
    return {
      index,
      label,
      valid: false,
      error: error instanceof Error ? error.message : 'Failed to analyze image',
    };
  }
}

// Validate all images before matrix computation
export async function validateImages(
  files: File[],
  labels: string[]
): Promise<ImageValidationResult[]> {
  const results = await Promise.all(
    files.map((file, index) => validateImage(file, labels[index] || `Image ${index + 1}`, index))
  );
  return results;
}

async function computeSimilarityMatrix(request: SimilarityMatrixRequest): Promise<SimilarityMatrixResponse> {
  const formData = new FormData();
  request.files.forEach((file) => {
    formData.append('files', file);
  });
  if (request.labels && request.labels.length > 0) {
    formData.append('labels', request.labels.join(','));
  }

  const params: Record<string, string | number | boolean | undefined> = {};
  if (request.threshold !== undefined) {
    params.threshold = request.threshold;
  }

  // Use centralized API client with built-in retry, timeout, and error handling
  return apiClient.upload<SimilarityMatrixResponse>('/api/v1/similarity/matrix', formData, {
    params,
  });
}

export function useSimilarityMatrix() {
  return useMutation({
    mutationFn: computeSimilarityMatrix,
    mutationKey: ['similarity-matrix'],
  });
}

export type { ImageValidationResult, Cluster, SimilarityPair };
