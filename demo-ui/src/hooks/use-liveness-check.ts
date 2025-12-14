import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

interface LivenessRequest {
  image: File | Blob;
  strict_mode?: boolean;
}

interface LivenessCheck {
  name: string;
  passed: boolean;
  score: number;
  details?: string;
}

interface LivenessResponse {
  is_live: boolean;
  confidence: number;
  checks: LivenessCheck[];
  spoof_type?: string;
  processing_time_ms: number;
}

async function checkLiveness(request: LivenessRequest): Promise<LivenessResponse> {
  const formData = new FormData();
  formData.append('file', request.image);

  // Use fetch directly for FormData
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'}/api/v1/liveness`,
    {
      method: 'POST',
      body: formData,
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Liveness check failed' }));
    throw new Error(error.message || error.detail);
  }

  return response.json();
}

export function useLivenessCheck() {
  return useMutation({
    mutationFn: checkLiveness,
    mutationKey: ['liveness-check'],
  });
}
