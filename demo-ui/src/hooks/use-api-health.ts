import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

interface HealthCheckResponse {
  status: string;
  version: string;
  timestamp: string;
  latency?: number;
}

async function checkHealth(): Promise<HealthCheckResponse> {
  const startTime = performance.now();

  const response = await apiClient.get<HealthCheckResponse>('/health');
  const endTime = performance.now();

  return {
    ...response,
    latency: Math.round(endTime - startTime),
  };
}

export function useApiHealth() {
  const query = useQuery({
    queryKey: ['api-health'],
    queryFn: checkHealth,
    refetchInterval: 30000, // Refetch every 30 seconds
    retry: 1,
    staleTime: 10000,
  });

  return {
    ...query,
    isHealthy: query.isSuccess && query.data?.status === 'healthy',
  };
}
