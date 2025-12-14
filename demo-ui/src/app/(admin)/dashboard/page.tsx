'use client';

import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import {
  LayoutDashboard,
  Users,
  Activity,
  Shield,
  Clock,
  CheckCircle2,
  XCircle,
  TrendingUp,
  Server,
  Database,
  Cpu,
  HardDrive,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { useAdminStats } from '@/hooks/use-admin-stats';
import { useApiHealth } from '@/hooks/use-api-health';

export default function AdminDashboardPage() {
  const { t } = useTranslation();
  const { data: healthData, isHealthy, isLoading: healthLoading } = useApiHealth();
  const { data: stats, isLoading: statsLoading } = useAdminStats();

  const isLoading = healthLoading || statsLoading;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-500/10">
            <LayoutDashboard className="h-5 w-5 text-slate-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Admin Dashboard</h1>
            <p className="text-muted-foreground">System overview and statistics</p>
          </div>
        </div>
      </motion.div>

      {/* Health Status */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.1 }}
      >
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>System Health</CardTitle>
              <Badge variant={isHealthy ? 'default' : 'destructive'}>
                {isHealthy ? 'Healthy' : 'Unhealthy'}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-4">
              <div className="flex items-center gap-3 rounded-lg border p-3">
                <Server className={`h-8 w-8 ${isHealthy ? 'text-green-500' : 'text-red-500'}`} />
                <div>
                  <p className="text-sm text-muted-foreground">API Server</p>
                  <p className="font-semibold">{isHealthy ? 'Online' : 'Offline'}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 rounded-lg border p-3">
                <Database className="h-8 w-8 text-blue-500" />
                <div>
                  <p className="text-sm text-muted-foreground">Database</p>
                  <p className="font-semibold">{healthData?.services?.database?.status || 'Unknown'}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 rounded-lg border p-3">
                <Cpu className="h-8 w-8 text-purple-500" />
                <div>
                  <p className="text-sm text-muted-foreground">ML Models</p>
                  <p className="font-semibold">{healthData?.services?.ml_models?.status || 'Unknown'}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 rounded-lg border p-3">
                <HardDrive className="h-8 w-8 text-orange-500" />
                <div>
                  <p className="text-sm text-muted-foreground">Redis</p>
                  <p className="font-semibold">{healthData?.services?.redis?.status || 'Unknown'}</p>
                </div>
              </div>
            </div>
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
            <div className="text-2xl font-bold">{stats?.total_enrollments || 0}</div>
            <p className="text-xs text-muted-foreground">
              <TrendingUp className="inline h-3 w-3 mr-1" />
              +{stats?.enrollments_today || 0} today
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Verifications</CardTitle>
            <Shield className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_verifications || 0}</div>
            <p className="text-xs text-muted-foreground">
              {stats?.verification_success_rate || 0}% success rate
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Liveness Checks</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_liveness_checks || 0}</div>
            <p className="text-xs text-muted-foreground">
              {stats?.spoof_detection_rate || 0}% spoof detected
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Response Time</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.avg_response_time || 0}ms</div>
            <p className="text-xs text-muted-foreground">
              p99: {stats?.p99_response_time || 0}ms
            </p>
          </CardContent>
        </Card>
      </motion.div>

      {/* Recent Activity & Performance */}
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
                {(stats?.recent_activity || []).slice(0, 10).map((activity: any, index: number) => (
                  <div key={index} className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      {activity.success ? (
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                      ) : (
                        <XCircle className="h-4 w-4 text-red-500" />
                      )}
                      <div>
                        <p className="text-sm font-medium">{activity.operation}</p>
                        <p className="text-xs text-muted-foreground">{activity.user_id}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-sm">{activity.duration}ms</p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(activity.timestamp).toLocaleTimeString()}
                      </p>
                    </div>
                  </div>
                ))}
                {(!stats?.recent_activity || stats.recent_activity.length === 0) && (
                  <p className="text-sm text-muted-foreground text-center py-4">
                    No recent activity
                  </p>
                )}
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
              <CardTitle>System Resources</CardTitle>
              <CardDescription>Current resource utilization</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>CPU Usage</span>
                  <span className="font-mono">{stats?.cpu_usage || 0}%</span>
                </div>
                <Progress value={stats?.cpu_usage || 0} />
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Memory Usage</span>
                  <span className="font-mono">{stats?.memory_usage || 0}%</span>
                </div>
                <Progress value={stats?.memory_usage || 0} />
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>GPU Memory</span>
                  <span className="font-mono">{stats?.gpu_memory || 0}%</span>
                </div>
                <Progress value={stats?.gpu_memory || 0} />
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Disk Usage</span>
                  <span className="font-mono">{stats?.disk_usage || 0}%</span>
                </div>
                <Progress value={stats?.disk_usage || 0} />
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
