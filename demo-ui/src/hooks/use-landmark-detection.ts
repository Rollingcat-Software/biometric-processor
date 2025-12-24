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
  id: number;
  x: number;  // Pixel coordinate
  y: number;  // Pixel coordinate
  z?: number;
}

// Matches actual backend response
interface BackendLandmarkResponse {
  landmarks: LandmarkPoint[];
  landmark_count: number;
  model: string;
  regions?: Record<string, number[]>;  // Maps region name to landmark indices
  head_pose?: {
    pitch: number;
    yaw: number;
    roll: number;
  };
}

// UI-friendly response with resolved region points
interface LandmarkResponse {
  landmarks: LandmarkPoint[];
  landmark_count: number;
  model: string;
  regionIndices: Record<string, number[]>;  // Original indices for reference
  regions: Record<string, LandmarkPoint[]>; // Resolved points for drawing
  head_pose?: {
    pitch: number;
    yaw: number;
    roll: number;
  };
}

async function detectLandmarks(request: LandmarkRequest): Promise<LandmarkResponse> {
  const formData = new FormData();
  const filename = request.image instanceof File ? request.image.name : 'capture.jpg';
  formData.append('file', request.image, filename);
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

    // Create a lookup map for landmarks by id
    const landmarkById = new Map<number, LandmarkPoint>();
    data.landmarks.forEach((lm) => {
      landmarkById.set(lm.id, lm);
    });

    // Transform region indices to actual points
    const resolvedRegions: Record<string, LandmarkPoint[]> = {};
    const regionIndices = data.regions || {};

    Object.entries(regionIndices).forEach(([regionName, indices]) => {
      resolvedRegions[regionName] = indices
        .map((idx) => landmarkById.get(idx))
        .filter((point): point is LandmarkPoint => point !== undefined);
    });

    // Transform to UI-friendly format
    return {
      landmarks: data.landmarks,
      landmark_count: data.landmark_count,
      model: data.model,
      regionIndices: regionIndices,
      regions: resolvedRegions,
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
