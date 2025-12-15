import { useMutation } from '@tanstack/react-query';
import { API_CONFIG } from '@/config/api.config';

const API_URL = API_CONFIG.BASE_URL;
const REQUEST_TIMEOUT = API_CONFIG.TIMEOUT.DEFAULT;

interface VerificationRequest {
  image: File | Blob;
  user_id: string;
  threshold?: number;
}

/**
 * Backend response format from /api/v1/verify
 */
interface BackendVerificationResponse {
  verified: boolean;
  confidence: number;
  distance: number;
  threshold: number;
  user_id: string;
  processing_time_ms?: number;
}

/**
 * Frontend response format expected by demo UI
 */
interface VerificationResponse {
  match: boolean;
  similarity: number;
  threshold: number;
  user_id: string;
  confidence: number;
  processing_time_ms: number;
  // Original backend fields preserved
  verified: boolean;
  distance: number;
}

async function verifyFace(request: VerificationRequest): Promise<VerificationResponse> {
  const formData = new FormData();
  const filename = request.image instanceof File ? request.image.name : 'capture.jpg';
  formData.append('file', request.image, filename);
  formData.append('user_id', request.user_id);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

  try {
    const response = await fetch(
      `${API_URL}/api/v1/verify`,
      {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Verification failed' }));
      throw new Error(error.message || error.detail);
    }

    const data: BackendVerificationResponse = await response.json();

    // Map backend response to frontend expected format
    return {
      // Frontend expected fields
      match: data.verified,
      similarity: data.confidence, // confidence is 0-1, maps to similarity
      // Common fields
      threshold: data.threshold,
      user_id: data.user_id,
      confidence: data.confidence,
      processing_time_ms: data.processing_time_ms || 0,
      // Preserve original backend fields
      verified: data.verified,
      distance: data.distance,
    };
  } finally {
    clearTimeout(timeoutId);
  }
}

export function useFaceVerification() {
  return useMutation({
    mutationFn: verifyFace,
    mutationKey: ['face-verification'],
  });
}
