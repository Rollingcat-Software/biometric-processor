import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { API_CONFIG } from '@/config/api.config';

const REQUEST_TIMEOUT = API_CONFIG.TIMEOUT.DEFAULT;

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

  // Use centralized API client with built-in retry, timeout, and error handling
  const data = await apiClient.upload<BackendCardDetectionResponse>('/api/v1/card-type/detect-live', formData, {
    timeout: REQUEST_TIMEOUT,
  });

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
