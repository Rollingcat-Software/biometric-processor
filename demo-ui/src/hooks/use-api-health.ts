/**
 * Hooks for API health monitoring
 *
 * Provides comprehensive health checks including:
 * - Basic health status
 * - Detailed health diagnostics
 * - Liveness probe (Kubernetes)
 * - Readiness probe (Kubernetes)
 */

import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import type {
  HealthCheckResponse,
  DetailedHealthResponse,
  LivenessResponse,
  ReadinessResponse,
} from '@/types/api';

/**
 * Basic health check (legacy endpoint for compatibility)
 */
async function checkHealth(): Promise<HealthCheckResponse> {
  const startTime = performance.now();

  const response = await apiClient.get<HealthCheckResponse>('/api/v1/health', {
    retry: false, // Don't retry health checks
  });
  const endTime = performance.now();

  return {
    ...response,
    timestamp: new Date().toISOString(),
    latency: Math.round(endTime - startTime),
  };
}

/**
 * Detailed health check with comprehensive diagnostics
 */
async function checkDetailedHealth(): Promise<DetailedHealthResponse> {
  return apiClient.get<DetailedHealthResponse>('/api/v1/health/detailed', {
    retry: false,
    timeout: 10000, // 10 second timeout for health checks
  });
}

/**
 * Liveness probe - indicates if application is running
 */
async function checkLiveness(): Promise<LivenessResponse> {
  return apiClient.get<LivenessResponse>('/api/v1/health/live', {
    retry: false,
    timeout: 5000, // 5 second timeout
  });
}

/**
 * Readiness probe - indicates if application is ready to serve traffic
 */
async function checkReadiness(): Promise<ReadinessResponse> {
  return apiClient.get<ReadinessResponse>('/api/v1/health/ready', {
    retry: false,
    timeout: 10000, // 10 second timeout
  });
}

/**
 * Hook for basic health check
 */
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

/**
 * Hook for detailed health check with comprehensive diagnostics
 */
export function useDetailedHealth() {
  const query = useQuery({
    queryKey: ['health-detailed'],
    queryFn: checkDetailedHealth,
    refetchInterval: 15000, // Refetch every 15 seconds
    retry: 1,
    staleTime: 5000,
  });

  const getOverallStatus = () => {
    if (!query.data) return 'unknown';
    return query.data.status;
  };

  const isHealthy = query.isSuccess && query.data?.status === 'healthy';
  const isDegraded = query.isSuccess && query.data?.status === 'degraded';
  const isUnhealthy = query.isSuccess && query.data?.status === 'unhealthy';

  return {
    ...query,
    isHealthy,
    isDegraded,
    isUnhealthy,
    overallStatus: getOverallStatus(),
  };
}

/**
 * Hook for liveness check
 */
export function useLivenessCheck() {
  return useQuery({
    queryKey: ['health-live'],
    queryFn: checkLiveness,
    refetchInterval: 10000, // Refetch every 10 seconds
    retry: 1,
    staleTime: 5000,
  });
}

/**
 * Hook for readiness check
 */
export function useReadinessCheck() {
  return useQuery({
    queryKey: ['health-ready'],
    queryFn: checkReadiness,
    refetchInterval: 15000, // Refetch every 15 seconds
    retry: 1,
    staleTime: 5000,
  });
}

/**
 * Hook for comprehensive health monitoring (combines all checks)
 */
export function useComprehensiveHealth() {
  const detailed = useDetailedHealth();
  const liveness = useLivenessCheck();
  const readiness = useReadinessCheck();

  return {
    detailed,
    liveness,
    readiness,
    isLoading: detailed.isLoading || liveness.isLoading || readiness.isLoading,
    isError: detailed.isError || liveness.isError || readiness.isError,
    isHealthy: detailed.isHealthy && liveness.isSuccess && readiness.data?.ready,
  };
}
