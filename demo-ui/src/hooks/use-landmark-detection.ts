import { useMutation } from '@tanstack/react-query';
import { ApiClientError } from '@/lib/api/client';
import { API_CONFIG } from '@/config/api.config';

const API_URL = API_CONFIG.BASE_URL;
const REQUEST_TIMEOUT = API_CONFIG.TIMEOUT.DEFAULT;

interface LandmarkRequest {
  image: File | Blob;
  include_3d?: boolean;
}

interface LandmarkPoint {
  x: number;
  y: number;
  z?: number;
}

// Matches actual backend response
interface BackendLandmarkResponse {
  landmarks: LandmarkPoint[];
  landmark_count: number;
  model: string;
  regions?: {
    left_eye?: LandmarkPoint[];
    right_eye?: LandmarkPoint[];
    nose?: LandmarkPoint[];
    mouth?: LandmarkPoint[];
    face_contour?: LandmarkPoint[];
    left_eyebrow?: LandmarkPoint[];
    right_eyebrow?: LandmarkPoint[];
  };
  head_pose?: {
    pitch: number;
    yaw: number;
    roll: number;
  };
}

// UI-friendly response
interface LandmarkResponse {
  landmarks: LandmarkPoint[];
  landmark_count: number;
  model: string;
  regions: {
    left_eye: LandmarkPoint[];
    right_eye: LandmarkPoint[];
    nose: LandmarkPoint[];
    mouth: LandmarkPoint[];
    face_contour: LandmarkPoint[];
    left_eyebrow: LandmarkPoint[];
    right_eyebrow: LandmarkPoint[];
  };
  head_pose?: {
    pitch: number;
    yaw: number;
    roll: number;
  };
}

async function detectLandmarks(request: LandmarkRequest): Promise<LandmarkResponse> {
  const formData = new FormData();
  formData.append('file', request.image);
  if (request.include_3d !== undefined) {
    formData.append('include_3d', request.include_3d.toString());
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

  try {
    const response = await fetch(`${API_URL}/api/v1/landmarks/detect`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Landmark detection failed' }));

      // Handle specific error for dlib not installed
      if (error.error_code === 'LANDMARK_ERROR') {
        throw new ApiClientError(response.status, error.message, {
          code: error.error_code,
          details: error,
          userMessage: 'Landmark detection is not available. The dlib library is not installed on the server.',
        });
      }

      throw new ApiClientError(response.status, error.message || error.detail, {
        code: error.error_code,
        details: error,
      });
    }

    const data: BackendLandmarkResponse = await response.json();

    // Transform to UI-friendly format with default empty arrays
    return {
      landmarks: data.landmarks,
      landmark_count: data.landmark_count,
      model: data.model,
      regions: {
        left_eye: data.regions?.left_eye ?? [],
        right_eye: data.regions?.right_eye ?? [],
        nose: data.regions?.nose ?? [],
        mouth: data.regions?.mouth ?? [],
        face_contour: data.regions?.face_contour ?? [],
        left_eyebrow: data.regions?.left_eyebrow ?? [],
        right_eyebrow: data.regions?.right_eyebrow ?? [],
      },
      head_pose: data.head_pose,
    };
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiClientError(408, 'Request timeout - landmark detection took too long');
    }
    throw new ApiClientError(0, error instanceof Error ? error.message : 'Unknown error');
  } finally {
    clearTimeout(timeoutId);
  }
}

export function useLandmarkDetection() {
  return useMutation({
    mutationFn: detectLandmarks,
    mutationKey: ['landmark-detection'],
  });
}

export type { LandmarkRequest, LandmarkResponse, LandmarkPoint };
