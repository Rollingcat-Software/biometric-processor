import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { API_CONFIG } from '@/config/api.config';

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

  // Use centralized API client with built-in retry, timeout, and error handling
  const data = await apiClient.upload<BackendLandmarkResponse>('/api/v1/landmarks/detect', formData, {
    timeout: REQUEST_TIMEOUT,
  });

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
}

export function useLandmarkDetection() {
  return useMutation({
    mutationFn: detectLandmarks,
    mutationKey: ['landmark-detection'],
  });
}

export type { LandmarkRequest, LandmarkResponse, LandmarkPoint };
