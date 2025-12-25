/**
 * Hook for multi-image enrollment
 *
 * Allows enrolling a user with 2-5 face images for improved accuracy.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import type { MultiImageEnrollmentResponse } from '@/types/api';

export interface MultiImageEnrollmentParams {
  user_id: string;
  files: File[];
  tenant_id?: string;
}

/**
 * Enroll user with multiple images
 */
async function enrollMultiImage(
  params: MultiImageEnrollmentParams
): Promise<MultiImageEnrollmentResponse> {
  // Validate file count
  if (params.files.length < 2) {
    throw new Error('At least 2 images are required for multi-image enrollment');
  }

  if (params.files.length > 5) {
    throw new Error('Maximum 5 images allowed for multi-image enrollment');
  }

  // Create FormData
  const formData = new FormData();
  formData.append('user_id', params.user_id);

  // Append all files
  params.files.forEach((file) => {
    formData.append('files', file);
  });

  // Optional tenant ID
  if (params.tenant_id) {
    formData.append('tenant_id', params.tenant_id);
  }

  // Upload with extended timeout (multi-image processing takes longer)
  return apiClient.upload<MultiImageEnrollmentResponse>(
    '/api/v1/enroll/multi',
    formData,
    {
      timeout: 60000, // 60 seconds for multi-image processing
    }
  );
}

/**
 * Hook for multi-image enrollment
 */
export function useMultiImageEnrollment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: enrollMultiImage,
    onSuccess: () => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['enrolled-faces'] });
      queryClient.invalidateQueries({ queryKey: ['face-count'] });
      queryClient.invalidateQueries({ queryKey: ['embeddings'] });
    },
  });
}
