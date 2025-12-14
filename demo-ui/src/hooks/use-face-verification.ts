import { useMutation } from '@tanstack/react-query';

interface VerificationRequest {
  image: File | Blob;
  user_id: string;
  threshold?: number;
}

interface VerificationResponse {
  match: boolean;
  similarity: number;
  threshold: number;
  user_id: string;
  confidence: number;
  processing_time_ms: number;
}

async function verifyFace(request: VerificationRequest): Promise<VerificationResponse> {
  const formData = new FormData();
  formData.append('file', request.image);
  formData.append('user_id', request.user_id);

  // Use fetch directly for FormData
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'}/api/v1/verify`,
    {
      method: 'POST',
      body: formData,
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Verification failed' }));
    throw new Error(error.message || error.detail);
  }

  return response.json();
}

export function useFaceVerification() {
  return useMutation({
    mutationFn: verifyFace,
    mutationKey: ['face-verification'],
  });
}
