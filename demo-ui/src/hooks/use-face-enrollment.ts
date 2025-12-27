import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { API_CONFIG } from '@/config/api.config';

const REQUEST_TIMEOUT = API_CONFIG.TIMEOUT.DEFAULT;

interface EnrollmentParams {
  person_id: string;
  image: File | Blob;
  metadata?: Record<string, unknown>;
}

// Backend response type
interface BackendEnrollmentResponse {
  user_id: string;
  embedding_id: string;
  success: boolean;
  message: string;
  quality_score?: number;
  created_at?: string;
}

// UI-friendly response
interface EnrollmentResponse {
  user_id: string;
  embedding_id: string;
  success: boolean;
  message: string;
  quality_score?: number;
  created_at?: string;
  // Add missing properties that UI expects
  face_id: string;
  person_id: string;
}

async function enrollFace(params: EnrollmentParams): Promise<EnrollmentResponse> {
  const formData = new FormData();
  formData.append('user_id', params.person_id);

  // Ensure Blob has a proper filename with extension for backend validation
  const filename = params.image instanceof File ? params.image.name : 'capture.jpg';
  formData.append('file', params.image, filename);

  if (params.metadata?.tenant_id) {
    formData.append('tenant_id', params.metadata.tenant_id as string);
  }

  // Use centralized API client with built-in retry, timeout, and error handling
  const data = await apiClient.upload<BackendEnrollmentResponse>('/api/v1/enroll', formData, {
    timeout: REQUEST_TIMEOUT,
  });

  // Transform backend response to UI-friendly format
  return {
    user_id: data.user_id,
    embedding_id: data.embedding_id,
    success: data.success,
    message: data.message,
    quality_score: data.quality_score,
    created_at: data.created_at,
    // Map to UI expected properties
    face_id: data.embedding_id,
    person_id: data.user_id,
  };
}

export function useFaceEnrollment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: enrollFace,
    mutationKey: ['face-enrollment'],
    onSuccess: () => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['enrolled-faces'] });
      queryClient.invalidateQueries({ queryKey: ['face-count'] });
    },
  });
}

export type { EnrollmentParams, EnrollmentResponse };
