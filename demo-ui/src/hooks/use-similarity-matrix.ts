import { useMutation } from '@tanstack/react-query';

interface SimilarityMatrixRequest {
  files: File[];
  labels?: string[];
  threshold?: number;
}

interface SimilarityMatrixResponse {
  matrix: number[][];
  labels: string[];
  clusters?: string[][];
  processing_time_ms: number;
}

async function computeSimilarityMatrix(request: SimilarityMatrixRequest): Promise<SimilarityMatrixResponse> {
  const formData = new FormData();
  request.files.forEach((file) => {
    formData.append('files', file);
  });
  if (request.labels && request.labels.length > 0) {
    formData.append('labels', request.labels.join(','));
  }

  const url = new URL(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'}/api/v1/similarity/matrix`);
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
