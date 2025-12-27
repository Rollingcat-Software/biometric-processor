import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { API_CONFIG } from '@/config/api.config';

const REQUEST_TIMEOUT = API_CONFIG.TIMEOUT.LONG; // 2 minutes for first-time model loading

interface DemographicsRequest {
  image: File | Blob;
}

// Matches actual backend response
interface BackendDemographicsResponse {
  age: {
    value: number;
    range: [number, number];
    confidence: number;
  };
  gender: {
    value: 'male' | 'female';
    confidence: number;
  };
  race: {
    dominant: string;
    confidence: number;
    all: Record<string, number>;
  } | null;
  emotion: {
    dominant: string;
    confidence: number;
    all: Record<string, number>;
  } | null;
}

// UI-friendly response
interface EmotionScores {
  happy: number;
  sad: number;
  angry: number;
  surprise: number;
  fear: number;
  disgust: number;
  neutral: number;
}

interface DemographicsResponse {
  age: number;
  age_range: { min: number; max: number };
  age_confidence: number;
  gender: 'male' | 'female';
  gender_confidence: number;
  dominant_emotion: string;
  emotion_confidence: number;
  emotion_scores: EmotionScores;
  race?: string;
  race_confidence?: number;
}

async function analyzeDemographics(request: DemographicsRequest): Promise<DemographicsResponse> {
  const formData = new FormData();
  const filename = request.image instanceof File ? request.image.name : 'capture.jpg';
  formData.append('file', request.image, filename);

  // Use centralized API client with built-in retry, timeout, and error handling
  const data = await apiClient.upload<BackendDemographicsResponse>('/api/v1/demographics/analyze', formData, {
    timeout: REQUEST_TIMEOUT,
  });

  // Transform emotion scores to expected format
  const emotionScores: EmotionScores = {
    happy: data.emotion?.all?.happy ?? 0,
    sad: data.emotion?.all?.sad ?? 0,
    angry: data.emotion?.all?.angry ?? 0,
    surprise: data.emotion?.all?.surprise ?? 0,
    fear: data.emotion?.all?.fear ?? 0,
    disgust: data.emotion?.all?.disgust ?? 0,
    neutral: data.emotion?.all?.neutral ?? 0,
  };

  // Transform to UI-friendly format
  return {
    age: data.age.value,
    age_range: { min: data.age.range[0], max: data.age.range[1] },
    age_confidence: data.age.confidence,
    gender: data.gender.value,
    gender_confidence: data.gender.confidence,
    dominant_emotion: data.emotion?.dominant ?? 'unknown',
    emotion_confidence: data.emotion?.confidence ?? 0,
    emotion_scores: emotionScores,
    race: data.race?.dominant,
    race_confidence: data.race?.confidence,
  };
}

export function useDemographicsAnalysis() {
  return useMutation({
    mutationFn: analyzeDemographics,
    mutationKey: ['demographics-analysis'],
  });
}

export type { DemographicsRequest, DemographicsResponse, EmotionScores };
