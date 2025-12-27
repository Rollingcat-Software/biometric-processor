import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { API_CONFIG } from '@/config/api.config';

const REQUEST_TIMEOUT = API_CONFIG.TIMEOUT.DEFAULT;

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
    // Optional metrics that backend may provide
    contrast?: number;
    eyes_open?: number;
    mouth_closed?: number;
  };
}

// UI-friendly response
interface QualityResponse {
  overall_score: number;
  is_acceptable: boolean;
  metrics: {
    sharpness: number;
    brightness: number;
    contrast: number | null; // Nullable instead of hardcoded default
    face_size: number;
    pose_frontal: number;
    eyes_open: number | null; // Nullable instead of hardcoded default
    mouth_closed: number | null; // Nullable instead of hardcoded default
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
  const filename = request.image instanceof File ? request.image.name : 'capture.jpg';
  formData.append('file', request.image, filename);

  // Use centralized API client with built-in retry, timeout, and error handling
  const data = await apiClient.upload<BackendQualityResponse>('/api/v1/quality/analyze', formData, {
    timeout: REQUEST_TIMEOUT,
  });

  // Transform backend response to UI-friendly format
  // All metrics normalized to 0-100, use null for unavailable metrics instead of hardcoded defaults
  return {
    overall_score: data.overall_score,
    is_acceptable: data.passed,
    metrics: {
      sharpness: data.metrics.blur_score, // Already normalized 0-100
      brightness: data.metrics.brightness, // Already normalized 0-100
      contrast: data.metrics.contrast ?? null, // Use null if not provided
      face_size: data.metrics.face_size, // Already normalized 0-100
      pose_frontal: data.metrics.face_angle, // Already normalized 0-100 (100 = frontal)
      eyes_open: data.metrics.eyes_open ?? null, // Use null if not provided
      mouth_closed: data.metrics.mouth_closed ?? null, // Use null if not provided
      no_occlusion: 100 - data.metrics.occlusion, // Invert (0 occlusion = 100% good)
    },
    recommendations: data.issues.map((issue) => issue.suggestion),
    issues: data.issues.map((issue) => ({
      code: issue.code,
      severity: issue.severity,
      message: issue.message,
      suggestion: issue.suggestion,
    })),
  };
}

export function useQualityAnalysis() {
  return useMutation({
    mutationFn: analyzeQuality,
    mutationKey: ['quality-analysis'],
  });
}

export type { QualityRequest, QualityResponse };
