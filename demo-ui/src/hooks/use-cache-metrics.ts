/**
 * Hook for cache metrics monitoring
 *
 * Provides real-time cache performance metrics and recommendations
 */

import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import type { CacheMetricsResponse } from '@/types/api';

/**
 * Fetch cache metrics from the backend
 */
async function fetchCacheMetrics(): Promise<CacheMetricsResponse> {
  return apiClient.get<CacheMetricsResponse>('/metrics/cache', {
    retry: false,
    timeout: 10000, // 10 second timeout
  });
}

/**
 * Hook for cache metrics monitoring
 */
export function useCacheMetrics() {
  const query = useQuery({
    queryKey: ['cache-metrics'],
    queryFn: fetchCacheMetrics,
    refetchInterval: 5000, // Refetch every 5 seconds for real-time monitoring
    retry: 1,
    staleTime: 2000,
  });

  const getCacheEfficiency = () => {
    if (!query.data?.metrics) return 'unknown';
    const hitRate = query.data.metrics.hit_rate_percent;
    if (hitRate >= 90) return 'excellent';
    if (hitRate >= 75) return 'good';
    if (hitRate >= 50) return 'fair';
    return 'poor';
  };

  const getCacheUtilization = () => {
    if (!query.data?.metrics) return 0;
    return (query.data.metrics.current_size / query.data.metrics.max_size) * 100;
  };

  return {
    ...query,
    cacheEnabled: query.data?.cache_enabled ?? false,
    efficiency: getCacheEfficiency(),
    utilization: getCacheUtilization(),
  };
}
