'use client';

import { motion } from 'framer-motion';
import {
  LayoutDashboard,
  Users,
  Activity,
  Shield,
  Clock,
  TrendingUp,
  Server,
  Database,
  Cpu,
  HardDrive,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  Zap,
  Globe,
  Settings,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { useAdminStats } from '@/hooks/use-admin-stats';
import { useDetailedHealth } from '@/hooks/use-api-health';
import { formatDuration } from '@/lib/utils';

export default function AdminDashboardPage() {
  const {
    data: healthData,
    isHealthy,
    isDegraded,
    isUnhealthy,
    isLoading: healthLoading,
    isError: healthError,
  } = useDetailedHealth();
  const { data: stats, isLoading: statsLoading } = useAdminStats();

  const isLoading = healthLoading || statsLoading;

  // Helper to get status color
  const getStatusColor = (status?: string) => {
    switch (status) {
      case 'healthy':
        return 'text-green-500';
      case 'degraded':
        return 'text-orange-500';
      case 'unhealthy':
        return 'text-red-500';
      default:
        return 'text-gray-500';
    }
  };

  // Helper to get status icon
  const getStatusIcon = (status?: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle2 className="h-5 w-5" />;
      case 'degraded':
        return <AlertTriangle className="h-5 w-5" />;
      case 'unhealthy':
        return <AlertCircle className="h-5 w-5" />;
      default:
        return <AlertCircle className="h-5 w-5" />;
    }
  };

  // Helper to format uptime
  const formatUptime = (seconds?: number) => {
    if (!seconds) return '0h';
    const hours = Math.floor(seconds / 3600);
    const days = Math.floor(hours / 24);
    if (days > 0) return `${days}d ${hours % 24}h`;
    return `${hours}h`;
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-500/10">
              <LayoutDashboard className="h-5 w-5 text-slate-500" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Admin Dashboard</h1>
              <p className="text-muted-foreground">System overview and statistics</p>
            </div>
          </div>

          {/* Environment Badge */}
          {healthData?.environment && (
            <div className="flex items-center gap-2">
              <Globe className="h-4 w-4 text-muted-foreground" />
              <Badge variant={healthData.environment === 'production' ? 'destructive' : 'secondary'}>
                {healthData.environment.toUpperCase()}
              </Badge>
            </div>
          )}
        </div>
      </motion.div>

      {/* Overall System Health */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.1 }}
      >
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CardTitle>System Health</CardTitle>
                {healthData?.uptime_seconds && (
                  <span className="text-sm text-muted-foreground">
                    Uptime: {formatUptime(healthData.uptime_seconds)}
                  </span>
                )}
              </div>
              <Badge
                variant={isHealthy ? 'default' : isDegraded ? 'secondary' : 'destructive'}
                className="flex items-center gap-1"
              >
                {isHealthy && <CheckCircle2 className="h-3 w-3" />}
                {isDegraded && <AlertTriangle className="h-3 w-3" />}
                {isUnhealthy && <AlertCircle className="h-3 w-3" />}
                {isHealthy ? 'Healthy' : isDegraded ? 'Degraded' : 'Unhealthy'}
              </Badge>
            </div>
            {healthData?.version && (
              <CardDescription>
                Version: {healthData.version} • Last checked: {new Date(healthData.timestamp).toLocaleTimeString()}
              </CardDescription>
            )}
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              {/* Application Status */}
              <div className="flex items-center gap-3 rounded-lg border p-3">
                <div className={getStatusColor(healthData?.checks?.application?.status)}>
                  <Server className="h-8 w-8" />
                </div>
                <div className="flex-1">
                  <p className="text-sm text-muted-foreground">Application</p>
                  <p className="font-semibold capitalize">
                    {healthData?.checks?.application?.status || 'Unknown'}
                  </p>
                  {healthData?.checks?.application?.version && (
                    <p className="text-xs text-muted-foreground">
                      v{healthData.checks.application.version}
                    </p>
                  )}
                </div>
              </div>

              {/* Database Status */}
              <div className="flex items-center gap-3 rounded-lg border p-3">
                <div className={getStatusColor(healthData?.checks?.database?.status)}>
                  <Database className="h-8 w-8" />
                </div>
                <div className="flex-1">
                  <p className="text-sm text-muted-foreground">Database</p>
                  <p className="font-semibold capitalize">
                    {healthData?.checks?.database?.status || 'Unknown'}
                  </p>
                  {healthData?.checks?.database?.embeddings_count !== undefined && (
                    <p className="text-xs text-muted-foreground">
                      {healthData.checks.database.embeddings_count.toLocaleString()} embeddings
                    </p>
                  )}
                  {healthData?.checks?.database?.error && (
                    <p className="text-xs text-red-600 truncate" title={healthData.checks.database.error}>
                      {healthData.checks.database.error}
                    </p>
                  )}
                </div>
              </div>

              {/* Cache Status */}
              <div className="flex items-center gap-3 rounded-lg border p-3">
                <div className={getStatusColor(healthData?.checks?.cache?.status)}>
                  <Zap className="h-8 w-8" />
                </div>
                <div className="flex-1">
                  <p className="text-sm text-muted-foreground">Cache</p>
                  <p className="font-semibold capitalize">
                    {healthData?.checks?.cache?.enabled ? (
                      healthData.checks.cache.status || 'Enabled'
                    ) : (
                      'Disabled'
                    )}
                  </p>
                  {healthData?.checks?.cache?.stats && (
                    <p className="text-xs text-muted-foreground">
                      Hit rate: {healthData.checks.cache.stats.hit_rate_percent.toFixed(1)}%
                    </p>
                  )}
                  {healthData?.checks?.cache?.error && (
                    <p className="text-xs text-red-600 truncate" title={healthData.checks.cache.error}>
                      {healthData.checks.cache.error}
                    </p>
                  )}
                </div>
              </div>

              {/* Configuration Status */}
              <div className="flex items-center gap-3 rounded-lg border p-3">
                <div className={getStatusColor(healthData?.checks?.configuration?.status)}>
                  <Settings className="h-8 w-8" />
                </div>
                <div className="flex-1">
                  <p className="text-sm text-muted-foreground">Configuration</p>
                  <p className="font-semibold capitalize">
                    {healthData?.checks?.configuration?.status || 'Unknown'}
                  </p>
                  {healthData?.checks?.configuration?.face_recognition_model && (
                    <p className="text-xs text-muted-foreground truncate"
                       title={healthData.checks.configuration.face_recognition_model}>
                      {healthData.checks.configuration.face_recognition_model}
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Configuration Details */}
            {healthData?.checks?.configuration && (
              <div className="mt-4 rounded-lg bg-muted p-4">
                <h4 className="mb-3 text-sm font-medium">System Configuration</h4>
                <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
                  <div>
                    <p className="text-xs text-muted-foreground">Multi-Image Enrollment</p>
                    <p className="text-sm font-medium">
                      {healthData.checks.configuration.multi_image_enrollment ? (
                        <span className="text-green-600">Enabled</span>
                      ) : (
                        <span className="text-gray-600">Disabled</span>
                      )}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Embedding Dimension</p>
                    <p className="text-sm font-medium font-mono">
                      {healthData.checks.configuration.embedding_dimension}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Face Detection</p>
                    <p className="text-sm font-medium">
                      {healthData.checks.configuration.face_detection_backend}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Recognition Model</p>
                    <p className="text-sm font-medium truncate"
                       title={healthData.checks.configuration.face_recognition_model}>
                      {healthData.checks.configuration.face_recognition_model}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>

      {/* Stats Grid */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.2 }}
        className="grid gap-4 md:grid-cols-2 lg:grid-cols-4"
      >
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Enrollments</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats?.total_enrollments?.toLocaleString() || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              <TrendingUp className="inline h-3 w-3 mr-1" />
              Total enrolled users
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Verifications</CardTitle>
            <Shield className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats?.total_verifications?.toLocaleString() || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Total verification attempts
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Sessions</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats?.active_sessions?.toLocaleString() || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Currently active
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Response Time</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats?.average_response_time_ms || 0}ms
            </div>
            <p className="text-xs text-muted-foreground">
              System performance
            </p>
          </CardContent>
        </Card>
      </motion.div>

      {/* Recent Activity & System Info */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Recent Activity */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.3 }}
        >
          <Card>
            <CardHeader>
              <CardTitle>Recent Activity</CardTitle>
              <CardDescription>Last 10 operations</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground text-center py-4">
                  No recent activity
                </p>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* System Resources */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.4 }}
        >
          <Card>
            <CardHeader>
              <CardTitle>System Information</CardTitle>
              <CardDescription>Runtime metrics and resource usage</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Cache Performance */}
              {healthData?.checks?.cache?.stats && (
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>Cache Hit Rate</span>
                    <span className="font-mono">
                      {healthData.checks.cache.stats.hit_rate_percent.toFixed(1)}%
                    </span>
                  </div>
                  <Progress value={healthData.checks.cache.stats.hit_rate_percent} />
                  <p className="text-xs text-muted-foreground">
                    {healthData.checks.cache.stats.cache_hits.toLocaleString()} hits / {' '}
                    {healthData.checks.cache.stats.total_requests.toLocaleString()} requests
                  </p>
                </div>
              )}

              {/* Cache Size */}
              {healthData?.checks?.cache?.stats && (
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>Cache Utilization</span>
                    <span className="font-mono">
                      {healthData.checks.cache.stats.current_size} / {healthData.checks.cache.stats.max_size}
                    </span>
                  </div>
                  <Progress
                    value={(healthData.checks.cache.stats.current_size / healthData.checks.cache.stats.max_size) * 100}
                  />
                </div>
              )}

              {/* Storage */}
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Storage Used</span>
                  <span className="font-mono">{stats?.storage_used_gb || 0} GB</span>
                </div>
                <Progress value={Math.min(((stats?.storage_used_gb || 0) / 100) * 100, 100)} />
              </div>

              {/* Uptime */}
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>System Uptime</span>
                  <span className="font-mono">
                    {healthData?.uptime_seconds ? formatUptime(healthData.uptime_seconds) : `${stats?.uptime_hours || 0}h`}
                  </span>
                </div>
              </div>

              {/* API Calls */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-muted-foreground">API Calls Today</p>
                  <p className="text-lg font-semibold">{stats?.api_calls_today?.toLocaleString() || 0}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">API Calls This Week</p>
                  <p className="text-lg font-semibold">{stats?.api_calls_this_week?.toLocaleString() || 0}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
