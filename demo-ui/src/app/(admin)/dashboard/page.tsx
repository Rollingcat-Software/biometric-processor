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
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { useAdminStats } from '@/hooks/use-admin-stats';
import { useApiHealth } from '@/hooks/use-api-health';

export default function AdminDashboardPage() {
  const { isHealthy } = useApiHealth();
  const { data: stats } = useAdminStats();

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
                  <p className="font-semibold">Connected</p>
                </div>
              </div>
              <div className="flex items-center gap-3 rounded-lg border p-3">
                <Cpu className="h-8 w-8 text-purple-500" />
                <div>
                  <p className="text-sm text-muted-foreground">ML Models</p>
                  <p className="font-semibold">Loaded</p>
                </div>
              </div>
              <div className="flex items-center gap-3 rounded-lg border p-3">
                <HardDrive className="h-8 w-8 text-orange-500" />
                <div>
                  <p className="text-sm text-muted-foreground">Redis</p>
                  <p className="font-semibold">Connected</p>
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
            <div className="text-2xl font-bold">{stats?.total_verifications || 0}</div>
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
            <div className="text-2xl font-bold">{stats?.active_sessions || 0}</div>
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
            <div className="text-2xl font-bold">{stats?.average_response_time_ms || 0}ms</div>
            <p className="text-xs text-muted-foreground">
              System performance
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
              <CardTitle>System Resources</CardTitle>
              <CardDescription>Current resource utilization</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Storage Used</span>
                  <span className="font-mono">{stats?.storage_used_gb || 0} GB</span>
                </div>
                <Progress value={Math.min(((stats?.storage_used_gb || 0) / 100) * 100, 100)} />
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Uptime</span>
                  <span className="font-mono">{stats?.uptime_hours || 0} hours</span>
                </div>
                <Progress value={100} />
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>API Calls Today</span>
                  <span className="font-mono">{stats?.api_calls_today || 0}</span>
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>API Calls This Week</span>
                  <span className="font-mono">{stats?.api_calls_this_week || 0}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
