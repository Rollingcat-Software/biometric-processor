import { useMutation } from '@tanstack/react-query';
import { ApiClientError } from '@/lib/api/client';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const REQUEST_TIMEOUT = 60000;

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
  formData.append('file1', request.image1);
  formData.append('file2', request.image2);
  if (request.threshold !== undefined) {
    formData.append('threshold', request.threshold.toString());
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

  try {
    const response = await fetch(`${API_URL}/api/v1/compare`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Face comparison failed' }));
      throw new ApiClientError(response.status, error.message || error.detail, {
        code: error.error_code,
        details: error,
      });
    }

    const data: BackendComparisonResponse = await response.json();

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
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiClientError(408, 'Request timeout - face comparison took too long');
    }
    throw new ApiClientError(0, error instanceof Error ? error.message : 'Unknown error');
  } finally {
    clearTimeout(timeoutId);
  }
}

export function useFaceComparison() {
  return useMutation({
    mutationFn: compareFaces,
    mutationKey: ['face-comparison'],
  });
}

export type { ComparisonRequest, ComparisonResponse };
