import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

interface QualityRequest {
  image: File | Blob;
}

interface QualityMetrics {
  sharpness: number;
  brightness: number;
  contrast: number;
  face_size: number;
  pose_frontal: number;
  eyes_open: number;
  mouth_closed: number;
  no_occlusion: number;
}

interface QualityResponse {
  overall_score: number;
  is_acceptable: boolean;
  metrics: QualityMetrics;
  recommendations: string[];
  processing_time_ms: number;
}

async function analyzeQuality(request: QualityRequest): Promise<QualityResponse> {
  const formData = new FormData();
  formData.append('file', request.image);

  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'}/api/v1/quality/analyze`,
    {
      method: 'POST',
      body: formData,
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Quality analysis failed' }));
    throw new Error(error.message || error.detail);
  }

  return response.json();
}

export function useQualityAnalysis() {
  return useMutation({
    mutationFn: analyzeQuality,
    mutationKey: ['quality-analysis'],
  });
}
