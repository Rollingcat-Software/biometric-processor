import { useMutation } from '@tanstack/react-query';
import { API_CONFIG } from '@/config/api.config';

const API_URL = API_CONFIG.BASE_URL;

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
    const response = await fetch(`${API_URL}/api/v1/quality/analyze`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'No face detected' }));
      return {
        index,
        label,
        valid: false,
        error: error.message || error.detail || 'No face detected',
      };
    }

    const data = await response.json();
    return {
      index,
      label,
      valid: true,
      error: data.passed ? undefined : 'Low quality face',
    };
  } catch {
    return {
      index,
      label,
      valid: false,
      error: 'Failed to analyze image',
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

  const url = new URL(`${API_URL}/api/v1/similarity/matrix`);
  if (request.threshold !== undefined) {
    url.searchParams.set('threshold', request.threshold.toString());
  }

  const response = await fetch(url.toString(), {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Similarity matrix computation failed' }));
    throw new Error(error.message || error.detail);
  }

  return response.json();
}

export function useSimilarityMatrix() {
  return useMutation({
    mutationFn: computeSimilarityMatrix,
    mutationKey: ['similarity-matrix'],
  });
}

export type { ImageValidationResult, Cluster, SimilarityPair };
