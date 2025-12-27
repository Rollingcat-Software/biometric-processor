import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { API_CONFIG } from '@/config/api.config';

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

  if (request.strict_mode !== undefined) {
    formData.append('strict_mode', request.strict_mode.toString());
  }

  // Use centralized API client with built-in retry, timeout, and error handling
  const data = await apiClient.upload<LivenessResponse>('/api/v1/liveness', formData, {
    timeout: REQUEST_TIMEOUT,
  });

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
}

export function useLivenessCheck() {
  return useMutation({
    mutationFn: checkLiveness,
    mutationKey: ['liveness-check'],
  });
}

export type { LivenessRequest, LivenessResult };
