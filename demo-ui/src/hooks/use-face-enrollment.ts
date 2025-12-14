import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient, ApiClientError } from '@/lib/api/client';
import type { EnrollmentResponse } from '@/types/api';

interface EnrollmentParams {
  person_id: string;
  image: File | Blob;
  metadata?: Record<string, unknown>;
}

async function enrollFace(params: EnrollmentParams): Promise<EnrollmentResponse> {
  const formData = new FormData();
  formData.append('user_id', params.person_id);
  formData.append('file', params.image);

  if (params.metadata) {
    formData.append('tenant_id', params.metadata.tenant_id as string || '');
  }

  // Use fetch directly for FormData
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'}/api/v1/enroll`,
    {
      method: 'POST',
      body: formData,
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Enrollment failed' }));
    throw new ApiClientError(response.status, error.message || error.detail);
  }

  return response.json();
}

export function useFaceEnrollment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: enrollFace,
    onSuccess: () => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['enrolled-faces'] });
      queryClient.invalidateQueries({ queryKey: ['face-count'] });
    },
  });
}
