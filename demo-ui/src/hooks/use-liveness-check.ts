import { useMutation } from '@tanstack/react-query';
import { ApiClientError } from '@/lib/api/client';
import { API_CONFIG } from '@/config/api.config';

const API_URL = API_CONFIG.BASE_URL;
const REQUEST_TIMEOUT = API_CONFIG.TIMEOUT.DEFAULT;

interface LivenessRequest {
  image: File | Blob;
  strict_mode?: boolean;
}

// Matches actual backend response
interface LivenessResponse {
  is_live: boolean;
  liveness_score: number;
  challenge: string;
  challenge_completed: boolean;
  message: string;
}

// Extended response for UI display
interface LivenessResult {
  is_live: boolean;
  confidence: number;
  challenge: string;
  challenge_completed: boolean;
  message: string;
  checks: Array<{
    name: string;
    passed: boolean;
    score: number;
    details?: string;
  }>;
}

async function checkLiveness(request: LivenessRequest): Promise<LivenessResult> {
  const formData = new FormData();
  const filename = request.image instanceof File ? request.image.name : 'capture.jpg';
  formData.append('file', request.image, filename);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

  try {
    const response = await fetch(`${API_URL}/api/v1/liveness`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Liveness check failed' }));
      throw new ApiClientError(response.status, error.message || error.detail, {
        code: error.error_code,
        details: error,
      });
    }

    const data: LivenessResponse = await response.json();

    // Transform to UI-friendly format
    return {
      is_live: data.is_live,
      confidence: data.liveness_score / 100, // Normalize to 0-1
      challenge: data.challenge,
      challenge_completed: data.challenge_completed,
      message: data.message,
      checks: [
        {
          name: data.challenge === 'texture' ? 'Texture Analysis' : 'Combined Analysis',
          passed: data.is_live,
          score: data.liveness_score,
          details: data.message,
        },
      ],
    };
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiClientError(408, 'Request timeout - liveness check took too long');
    }
    throw new ApiClientError(0, error instanceof Error ? error.message : 'Unknown error');
  } finally {
    clearTimeout(timeoutId);
  }
}

export function useLivenessCheck() {
  return useMutation({
    mutationFn: checkLiveness,
    mutationKey: ['liveness-check'],
  });
}

export type { LivenessRequest, LivenessResult };
