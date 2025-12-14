import { useMutation } from '@tanstack/react-query';
import { ApiClientError } from '@/lib/api/client';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const REQUEST_TIMEOUT = 60000;

interface QualityRequest {
  image: File | Blob;
}

// Matches actual backend response
interface BackendQualityResponse {
  overall_score: number;
  passed: boolean;
  issues: Array<{
    code: string;
    severity: string;
    message: string;
    value: number;
    threshold: number;
    suggestion: string;
  }>;
  metrics: {
    blur_score: number;
    brightness: number;
    face_size: number;
    face_angle: number;
    occlusion: number;
  };
}

// UI-friendly response
interface QualityResponse {
  overall_score: number;
  is_acceptable: boolean;
  metrics: {
    sharpness: number;
    brightness: number;
    contrast: number;
    face_size: number;
    pose_frontal: number;
    eyes_open: number;
    mouth_closed: number;
    no_occlusion: number;
  };
  recommendations: string[];
  issues: Array<{
    code: string;
    severity: string;
    message: string;
    suggestion: string;
  }>;
}

async function analyzeQuality(request: QualityRequest): Promise<QualityResponse> {
  const formData = new FormData();
  formData.append('file', request.image);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

  try {
    const response = await fetch(`${API_URL}/api/v1/quality/analyze`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Quality analysis failed' }));
      throw new ApiClientError(response.status, error.message || error.detail, {
        code: error.error_code,
        details: error,
      });
    }

    const data: BackendQualityResponse = await response.json();

    // Transform to UI-friendly format
    return {
      overall_score: data.overall_score,
      is_acceptable: data.passed,
      metrics: {
        sharpness: Math.min(100, data.metrics.blur_score / 10), // Normalize blur to 0-100
        brightness: data.metrics.brightness * 100, // Normalize to 0-100
        contrast: 75, // Not provided by backend, use default
        face_size: Math.min(100, (data.metrics.face_size / 200) * 100), // Normalize
        pose_frontal: Math.max(0, 100 - data.metrics.face_angle * 3), // Convert angle to score
        eyes_open: 100, // Not provided by backend
        mouth_closed: 100, // Not provided by backend
        no_occlusion: Math.max(0, 100 - data.metrics.occlusion * 100),
      },
      recommendations: data.issues.map((issue) => issue.suggestion),
      issues: data.issues.map((issue) => ({
        code: issue.code,
        severity: issue.severity,
        message: issue.message,
        suggestion: issue.suggestion,
      })),
    };
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiClientError(408, 'Request timeout - quality analysis took too long');
    }
    throw new ApiClientError(0, error instanceof Error ? error.message : 'Unknown error');
  } finally {
    clearTimeout(timeoutId);
  }
}

export function useQualityAnalysis() {
  return useMutation({
    mutationFn: analyzeQuality,
    mutationKey: ['quality-analysis'],
  });
}

export type { QualityRequest, QualityResponse };
