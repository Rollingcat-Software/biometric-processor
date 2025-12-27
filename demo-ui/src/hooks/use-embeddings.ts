import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

interface Embedding {
  id: string;
  user_id: string;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, any>;
}

interface EmbeddingListParams {
  page?: number;
  page_size?: number;
  search?: string;
}

interface EmbeddingListResponse {
  embeddings: Embedding[];
  total: number;
  unique_users: number;
  added_today: number;
  page: number;
  page_size: number;
}

async function fetchEmbeddings(params: EmbeddingListParams): Promise<EmbeddingListResponse> {
  try {
    // Use centralized API client
    const data = await apiClient.get<{ embeddings: any[] }>('/api/v1/embeddings/export', {
      params: { tenant_id: 'default' }
    });

    const embeddings = data.embeddings || [];

    // Transform to expected format with pagination
    const page = params.page || 1;
    const pageSize = params.page_size || 20;
    const start = (page - 1) * pageSize;
    const paginatedEmbeddings = embeddings.slice(start, start + pageSize);

    return {
      embeddings: paginatedEmbeddings.map((e: any, i: number) => ({
        id: e.user_id || `embedding-${i}`,
        user_id: e.user_id,
        created_at: e.created_at || new Date().toISOString(),
        updated_at: e.updated_at || new Date().toISOString(),
        metadata: e.metadata,
      })),
      total: embeddings.length,
      unique_users: embeddings.length,
      added_today: 0,
      page,
      page_size: pageSize,
    };
  } catch {
    // Return empty data on error
    return {
      embeddings: [],
      total: 0,
      unique_users: 0,
      added_today: 0,
      page: params.page || 1,
      page_size: params.page_size || 20,
    };
  }
}

async function deleteEmbedding(id: string): Promise<void> {
  await apiClient.delete(`/embeddings/${id}`);
}

async function deleteUserEmbeddings(userId: string): Promise<{ deleted_count: number }> {
  const response = await apiClient.delete<{ deleted_count: number }>(`/embeddings/user/${userId}`);
  return response;
}

export function useEmbeddingList(params: EmbeddingListParams) {
  return useQuery({
    queryKey: ['embeddings', params],
    queryFn: () => fetchEmbeddings(params),
  });
}

export function useDeleteEmbedding() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteEmbedding,
    mutationKey: ['delete-embedding'],
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['embeddings'] });
    },
  });
}

export function useDeleteUserEmbeddings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteUserEmbeddings,
    mutationKey: ['delete-user-embeddings'],
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['embeddings'] });
    },
  });
}
