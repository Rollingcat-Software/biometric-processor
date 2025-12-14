import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

interface Webhook {
  id: string;
  url: string;
  events: string[];
  secret?: string;
  is_active: boolean;
  created_at: string;
  last_triggered_at?: string;
  failure_count: number;
}

interface CreateWebhookRequest {
  url: string;
  events: string[];
  secret?: string;
}

interface UpdateWebhookRequest {
  id: string;
  url?: string;
  events?: string[];
  secret?: string;
  is_active?: boolean;
}

interface WebhookListResponse {
  webhooks: Webhook[];
  total: number;
}

async function fetchWebhooks(): Promise<WebhookListResponse> {
  const response = await apiClient.get<WebhookListResponse>('/webhooks');
  return response;
}

async function createWebhook(request: CreateWebhookRequest): Promise<Webhook> {
  const response = await apiClient.post<Webhook>('/webhooks/register', request);
  return response;
}

async function updateWebhook(request: UpdateWebhookRequest): Promise<Webhook> {
  const { id, ...data } = request;
  const response = await apiClient.put<Webhook>(`/webhooks/${id}`, data);
  return response;
}

async function deleteWebhook(id: string): Promise<void> {
  await apiClient.delete(`/webhooks/${id}`);
}

async function testWebhook(id: string): Promise<{ success: boolean; response_time_ms: number }> {
  const response = await apiClient.post<{ success: boolean; response_time_ms: number }>(
    `/webhooks/${id}/test`
  );
  return response;
}

export function useWebhookList() {
  return useQuery({
    queryKey: ['webhooks'],
    queryFn: fetchWebhooks,
  });
}

// Alias for useWebhookList
export const useWebhooks = useWebhookList;

export function useCreateWebhook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createWebhook,
    mutationKey: ['create-webhook'],
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
    },
  });
}

export function useUpdateWebhook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateWebhook,
    mutationKey: ['update-webhook'],
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
    },
  });
}

export function useDeleteWebhook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteWebhook,
    mutationKey: ['delete-webhook'],
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
    },
  });
}

export function useTestWebhook() {
  return useMutation({
    mutationFn: testWebhook,
    mutationKey: ['test-webhook'],
  });
}
