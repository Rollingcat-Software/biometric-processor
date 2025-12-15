import { useMutation } from '@tanstack/react-query';
import { ApiClientError } from '@/lib/api/client';
import { API_CONFIG } from '@/config/api.config';

const API_URL = API_CONFIG.BASE_URL;
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

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

  try {
    const response = await fetch(`${API_URL}/api/v1/faces/detect-all`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Multi-face detection failed' }));
      throw new ApiClientError(response.status, error.message || error.detail, {
        code: error.error_code,
        details: error,
      });
    }

    const data: BackendMultiFaceResponse = await response.json();

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
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiClientError(408, 'Request timeout - multi-face detection took too long');
    }
    throw new ApiClientError(0, error instanceof Error ? error.message : 'Unknown error');
  } finally {
    clearTimeout(timeoutId);
  }
}

export function useMultiFaceDetection() {
  return useMutation({
    mutationFn: detectMultipleFaces,
    mutationKey: ['multi-face-detection'],
  });
}

export type { MultiFaceRequest, MultiFaceResponse, DetectedFace, BoundingBox };
