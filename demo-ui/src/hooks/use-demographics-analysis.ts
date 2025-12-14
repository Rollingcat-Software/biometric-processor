import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

interface DemographicsRequest {
  image: File | Blob;
}

interface EmotionScores {
  happy: number;
  sad: number;
  angry: number;
  surprised: number;
  fearful: number;
  disgusted: number;
  neutral: number;
}

interface DemographicsResponse {
  age: number;
  age_range: { min: number; max: number };
  gender: 'male' | 'female';
  gender_confidence: number;
  dominant_emotion: string;
  emotion_scores: EmotionScores;
  processing_time_ms: number;
}

async function analyzeDemographics(request: DemographicsRequest): Promise<DemographicsResponse> {
  const formData = new FormData();
  formData.append('file', request.image);

  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'}/api/v1/demographics/analyze`,
    {
      method: 'POST',
      body: formData,
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Demographics analysis failed' }));
    throw new Error(error.message || error.detail);
  }

  return response.json();
}

export function useDemographicsAnalysis() {
  return useMutation({
    mutationFn: analyzeDemographics,
    mutationKey: ['demographics-analysis'],
  });
}
