import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

interface CardDetectionRequest {
  image: File | Blob;
}

interface CardDetectionResponse {
  card_type: 'tc_kimlik' | 'ehliyet' | 'pasaport' | 'ogrenci_karti' | 'unknown';
  confidence: number;
  bounding_box?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  extracted_fields?: Record<string, string>;
  processing_time_ms: number;
}

async function detectCard(request: CardDetectionRequest): Promise<CardDetectionResponse> {
  const formData = new FormData();
  formData.append('file', request.image);

  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'}/api/v1/card-type/detect-live`,
    {
      method: 'POST',
      body: formData,
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Card detection failed' }));
    throw new Error(error.message || error.detail);
  }

  return response.json();
}

export function useCardDetection() {
  return useMutation({
    mutationFn: detectCard,
    mutationKey: ['card-detection'],
  });
}
