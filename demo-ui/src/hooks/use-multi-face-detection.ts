import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

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

interface DetectedFace {
  bounding_box: BoundingBox;
  confidence: number;
  quality_score?: number;
  landmarks?: Array<{ x: number; y: number }>;
}

interface MultiFaceResponse {
  faces: DetectedFace[];
  face_count: number;
  image_width: number;
  image_height: number;
  processing_time_ms: number;
}

async function detectMultipleFaces(request: MultiFaceRequest): Promise<MultiFaceResponse> {
  const formData = new FormData();
  formData.append('file', request.image);
  if (request.max_faces !== undefined) {
    formData.append('max_faces', request.max_faces.toString());
  }

  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'}/api/v1/faces/detect-all`,
    {
      method: 'POST',
      body: formData,
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Multi-face detection failed' }));
    throw new Error(error.message || error.detail);
  }

  return response.json();
}

export function useMultiFaceDetection() {
  return useMutation({
    mutationFn: detectMultipleFaces,
    mutationKey: ['multi-face-detection'],
  });
}
