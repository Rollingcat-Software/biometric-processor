import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

interface ComparisonRequest {
  image1: File | Blob;
  image2: File | Blob;
  threshold?: number;
}

interface ComparisonResponse {
  similarity: number;
  match: boolean;
  threshold: number;
  face1_quality: number;
  face2_quality: number;
  processing_time_ms: number;
}

async function compareFaces(request: ComparisonRequest): Promise<ComparisonResponse> {
  const formData = new FormData();
  formData.append('file1', request.image1);
  formData.append('file2', request.image2);
  if (request.threshold !== undefined) {
    formData.append('threshold', request.threshold.toString());
  }

  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'}/api/v1/compare`,
    {
      method: 'POST',
      body: formData,
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Face comparison failed' }));
    throw new Error(error.message || error.detail);
  }

  return response.json();
}

export function useFaceComparison() {
  return useMutation({
    mutationFn: compareFaces,
    mutationKey: ['face-comparison'],
  });
}
