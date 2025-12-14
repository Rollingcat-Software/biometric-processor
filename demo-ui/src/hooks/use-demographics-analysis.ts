import { useMutation } from '@tanstack/react-query';
import { ApiClientError } from '@/lib/api/client';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const REQUEST_TIMEOUT = 120000; // 2 minutes for first-time model loading

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
  formData.append('file', request.image);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

  try {
    const response = await fetch(`${API_URL}/api/v1/demographics/analyze`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Demographics analysis failed' }));
      throw new ApiClientError(response.status, error.message || error.detail, {
        code: error.error_code,
        details: error,
      });
    }

    const data: BackendDemographicsResponse = await response.json();

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
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiClientError(408, 'Request timeout - demographics analysis took too long (model may be loading)');
    }
    throw new ApiClientError(0, error instanceof Error ? error.message : 'Unknown error');
  } finally {
    clearTimeout(timeoutId);
  }
}

export function useDemographicsAnalysis() {
  return useMutation({
    mutationFn: analyzeDemographics,
    mutationKey: ['demographics-analysis'],
  });
}

export type { DemographicsRequest, DemographicsResponse, EmotionScores };
