import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { API_CONFIG } from '@/config/api.config';

const API_URL = API_CONFIG.BASE_URL;

interface SystemStats {
  total_enrollments: number;
  total_verifications: number;
  total_searches: number;
  active_sessions: number;
  api_calls_today: number;
  api_calls_this_week: number;
  average_response_time_ms: number;
  storage_used_gb: number;
  uptime_hours: number;
}

interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  database: {
    status: 'connected' | 'disconnected';
    latency_ms: number;
  };
  redis: {
    status: 'connected' | 'disconnected';
    latency_ms: number;
  };
  model: {
    status: 'loaded' | 'loading' | 'error';
    name: string;
    version: string;
  };
  timestamp: string;
}

interface RecentActivity {
  activities: Array<{
    id: string;
    type: string;
    user_id?: string;
    timestamp: string;
    details?: Record<string, any>;
  }>;
}

async function fetchSystemStats(): Promise<SystemStats> {
  const response = await fetch(
    `${API_URL}/api/v1/admin/stats`,
    { method: 'GET' }
  );

  if (!response.ok) {
    throw new Error('Failed to fetch system stats');
  }

  return response.json();
}

async function fetchHealthStatus(): Promise<HealthStatus> {
  const response = await apiClient.get<HealthStatus>('/health');
  return response;
}

async function fetchRecentActivity(): Promise<RecentActivity> {
  const response = await fetch(
    `${API_URL}/api/v1/admin/activity`,
    { method: 'GET' }
  );

  if (!response.ok) {
    throw new Error('Failed to fetch recent activity');
  }

  return response.json();
}

export function useSystemStats() {
  return useQuery({
    queryKey: ['system-stats'],
    queryFn: fetchSystemStats,
    refetchInterval: 30000, // Refresh every 30 seconds
  });
}

// Alias for useSystemStats
export const useAdminStats = useSystemStats;

export function useHealthStatus() {
  return useQuery({
    queryKey: ['health-status'],
    queryFn: fetchHealthStatus,
    refetchInterval: 10000, // Refresh every 10 seconds
  });
}

export function useRecentActivity() {
  return useQuery({
    queryKey: ['recent-activity'],
    queryFn: fetchRecentActivity,
    refetchInterval: 15000, // Refresh every 15 seconds
  });
}
