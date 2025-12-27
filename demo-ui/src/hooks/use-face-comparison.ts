import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { API_CONFIG } from '@/config/api.config';

const REQUEST_TIMEOUT = API_CONFIG.TIMEOUT.DEFAULT;

interface ComparisonRequest {
  image1: File | Blob;
  image2: File | Blob;
  threshold?: number;
}

// Matches actual backend response
interface BackendComparisonResponse {
  match: boolean;
  similarity: number;
  distance: number;
  threshold: number;
  confidence: string;
  face1: {
    detected: boolean;
    quality_score: number;
    bounding_box: {
      x: number;
      y: number;
      width: number;
      height: number;
    };
  };
  face2: {
    detected: boolean;
    quality_score: number;
    bounding_box: {
      x: number;
      y: number;
      width: number;
      height: number;
    };
  };
  message: string;
}

// UI-friendly response
interface ComparisonResponse {
  similarity: number;
  match: boolean;
  threshold: number;
  distance: number;
  confidence: string;
  face1_quality: number;
  face2_quality: number;
  face1_detected: boolean;
  face2_detected: boolean;
  message: string;
}

async function compareFaces(request: ComparisonRequest): Promise<ComparisonResponse> {
  const formData = new FormData();
  const filename1 = request.image1 instanceof File ? request.image1.name : 'capture1.jpg';
  const filename2 = request.image2 instanceof File ? request.image2.name : 'capture2.jpg';
  formData.append('file1', request.image1, filename1);
  formData.append('file2', request.image2, filename2);
  if (request.threshold !== undefined) {
    formData.append('threshold', request.threshold.toString());
  }

  // Use centralized API client with built-in retry, timeout, and error handling
  const data = await apiClient.upload<BackendComparisonResponse>('/api/v1/compare', formData, {
    timeout: REQUEST_TIMEOUT,
  });

  // Transform to UI-friendly format
  return {
    similarity: data.similarity,
    match: data.match,
    threshold: data.threshold,
    distance: data.distance,
    confidence: data.confidence,
    face1_quality: data.face1.quality_score,
    face2_quality: data.face2.quality_score,
    face1_detected: data.face1.detected,
    face2_detected: data.face2.detected,
    message: data.message,
  };
}

export function useFaceComparison() {
  return useMutation({
    mutationFn: compareFaces,
    mutationKey: ['face-comparison'],
  });
}

export type { ComparisonRequest, ComparisonResponse };
