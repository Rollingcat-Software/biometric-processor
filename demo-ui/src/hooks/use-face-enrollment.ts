import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ApiClientError } from '@/lib/api/client';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const REQUEST_TIMEOUT = 60000; // 60 seconds for enrollment

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
}

async function enrollFace(params: EnrollmentParams): Promise<EnrollmentResponse> {
  const formData = new FormData();
  formData.append('user_id', params.person_id);
  formData.append('file', params.image);

  if (params.metadata?.tenant_id) {
    formData.append('tenant_id', params.metadata.tenant_id as string);
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

  try {
    const response = await fetch(`${API_URL}/api/v1/enroll`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Enrollment failed' }));

      // Handle specific error codes
      if (error.error_code === 'USER_ALREADY_EXISTS') {
        throw new ApiClientError(response.status, error.message, {
          code: error.error_code,
          details: error,
          userMessage: 'This user ID is already enrolled. Use a different ID or delete the existing enrollment first.',
        });
      }

      if (error.error_code === 'FACE_NOT_DETECTED') {
        throw new ApiClientError(response.status, error.message, {
          code: error.error_code,
          details: error,
          userMessage: 'No face detected in the image. Please use a clear photo with a visible face.',
        });
      }

      throw new ApiClientError(response.status, error.message || error.detail, {
        code: error.error_code,
        details: error,
      });
    }

    const data: BackendEnrollmentResponse = await response.json();

    // Return as-is since backend and UI formats are similar
    return {
      user_id: data.user_id,
      embedding_id: data.embedding_id,
      success: data.success,
      message: data.message,
      quality_score: data.quality_score,
      created_at: data.created_at,
    };
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiClientError(408, 'Request timeout - enrollment took too long');
    }
    throw new ApiClientError(0, error instanceof Error ? error.message : 'Unknown error');
  } finally {
    clearTimeout(timeoutId);
  }
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
