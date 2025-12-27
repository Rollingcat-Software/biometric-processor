import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { API_CONFIG } from '@/config/api.config';

const REQUEST_TIMEOUT = API_CONFIG.TIMEOUT.DEFAULT;

interface MultiFaceRequest {
  image: File | Blob;
  max_faces?: number;
}

interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

// Matches actual backend response
interface BackendDetectedFace {
  face_id: number;
  bounding_box: BoundingBox;
  confidence: number;
  quality_score: number;
  landmarks: Array<{ x: number; y: number }> | null;
}

interface BackendMultiFaceResponse {
  face_count: number;
  faces: BackendDetectedFace[];
  image_dimensions: {
    width: number;
    height: number;
  };
}

// UI-friendly types
interface DetectedFace {
  face_id: number;
  bounding_box: BoundingBox;
  confidence: number;
  quality_score: number;
  landmarks?: Array<{ x: number; y: number }>;
}

interface MultiFaceResponse {
  faces: DetectedFace[];
  face_count: number;
  image_width: number;
  image_height: number;
}

async function detectMultipleFaces(request: MultiFaceRequest): Promise<MultiFaceResponse> {
  const formData = new FormData();
  const filename = request.image instanceof File ? request.image.name : 'capture.jpg';
  formData.append('file', request.image, filename);
  if (request.max_faces !== undefined) {
    formData.append('max_faces', request.max_faces.toString());
  }

  // Use centralized API client with built-in retry, timeout, and error handling
  const data = await apiClient.upload<BackendMultiFaceResponse>('/api/v1/faces/detect-all', formData, {
    timeout: REQUEST_TIMEOUT,
  });

  // Transform to UI-friendly format
  return {
    face_count: data.face_count,
    faces: data.faces.map((face) => ({
      face_id: face.face_id,
      bounding_box: face.bounding_box,
      confidence: face.confidence,
      quality_score: face.quality_score,
      landmarks: face.landmarks ?? undefined,
    })),
    image_width: data.image_dimensions.width,
    image_height: data.image_dimensions.height,
  };
}

export function useMultiFaceDetection() {
  return useMutation({
    mutationFn: detectMultipleFaces,
    mutationKey: ['multi-face-detection'],
  });
}

export type { MultiFaceRequest, MultiFaceResponse, DetectedFace, BoundingBox };
