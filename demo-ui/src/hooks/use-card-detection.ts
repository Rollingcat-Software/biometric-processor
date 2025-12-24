import { useMutation } from '@tanstack/react-query';
import { API_CONFIG } from '@/config/api.config';

const API_URL = API_CONFIG.BASE_URL;

interface CardDetectionRequest {
  image: File | Blob;
}

// Backend response format
interface BackendCardDetectionResponse {
  detected: boolean;
  class_id?: number;
  class_name?: string;
  confidence?: number;
}

// Frontend expected format
interface CardDetectionResponse {
  card_type: 'tc_kimlik' | 'ehliyet' | 'pasaport' | 'ogrenci_karti' | 'unknown';
  confidence: number;
  detected: boolean;
}

async function detectCard(request: CardDetectionRequest): Promise<CardDetectionResponse> {
  const formData = new FormData();
  const filename = request.image instanceof File ? request.image.name : 'capture.jpg';
  formData.append('file', request.image, filename);

  const response = await fetch(
    `${API_URL}/api/v1/card-type/detect-live`,
    {
      method: 'POST',
      body: formData,
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Card detection failed' }));
    throw new Error(error.message || error.detail);
  }

  const data: BackendCardDetectionResponse = await response.json();

  // Map backend response to frontend format
  return {
    card_type: (data.class_name as CardDetectionResponse['card_type']) || 'unknown',
    confidence: data.confidence || 0,
    detected: data.detected,
  };
}

export function useCardDetection() {
  return useMutation({
    mutationFn: detectCard,
    mutationKey: ['card-detection'],
  });
}
