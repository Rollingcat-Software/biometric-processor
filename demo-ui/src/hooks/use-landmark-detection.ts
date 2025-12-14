import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

interface LandmarkRequest {
  image: File | Blob;
  include_3d?: boolean;
}

interface LandmarkPoint {
  x: number;
  y: number;
  z?: number;
}

interface LandmarkResponse {
  landmarks: LandmarkPoint[];
  landmark_count: number;
  regions: {
    left_eye: LandmarkPoint[];
    right_eye: LandmarkPoint[];
    nose: LandmarkPoint[];
    mouth: LandmarkPoint[];
    face_contour: LandmarkPoint[];
    left_eyebrow: LandmarkPoint[];
    right_eyebrow: LandmarkPoint[];
  };
  processing_time_ms: number;
}

async function detectLandmarks(request: LandmarkRequest): Promise<LandmarkResponse> {
  const formData = new FormData();
  formData.append('file', request.image);
  if (request.include_3d !== undefined) {
    formData.append('include_3d', request.include_3d.toString());
  }

  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'}/api/v1/landmarks/detect`,
    {
      method: 'POST',
      body: formData,
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Landmark detection failed' }));
    throw new Error(error.message || error.detail);
  }

  return response.json();
}

export function useLandmarkDetection() {
  return useMutation({
    mutationFn: detectLandmarks,
    mutationKey: ['landmark-detection'],
  });
}
