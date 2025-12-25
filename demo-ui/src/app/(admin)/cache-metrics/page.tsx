'use client';

import { motion } from 'framer-motion';
import {
  Zap,
  TrendingUp,
  TrendingDown,
  Database,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Info,
  RefreshCw,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { useCacheMetrics } from '@/hooks/use-cache-metrics';

export default function CacheMetricsPage() {
  const {
    data: cacheData,
    isLoading,
    isError,
    error,
    refetch,
    cacheEnabled,
    efficiency,
    utilization,
  } = useCacheMetrics();

  const getEfficiencyColor = () => {
    switch (efficiency) {
      case 'excellent':
        return 'text-green-600';
      case 'good':
        return 'text-blue-600';
      case 'fair':
        return 'text-orange-600';
      case 'poor':
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  const getEfficiencyBadge = () => {
    switch (efficiency) {
      case 'excellent':
        return <Badge className="bg-green-600">Excellent</Badge>;
      case 'good':
        return <Badge className="bg-blue-600">Good</Badge>;
      case 'fair':
        return <Badge className="bg-orange-600">Fair</Badge>;
      case 'poor':
        return <Badge variant="destructive">Poor</Badge>;
      default:
        return <Badge variant="secondary">Unknown</Badge>;
    }
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
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-500/10">
              <Zap className="h-5 w-5 text-purple-500" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Cache Metrics</h1>
              <p className="text-muted-foreground">Real-time cache performance monitoring</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {cacheData?.timestamp && (
              <span className="text-sm text-muted-foreground">
                Last updated: {new Date(cacheData.timestamp).toLocaleTimeString()}
              </span>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              disabled={isLoading}
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>
      </motion.div>

      {/* Cache Status Banner */}
      {!cacheEnabled && !isLoading && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
        >
          <Card className="border-orange-200 bg-orange-50 dark:border-orange-800 dark:bg-orange-950">
            <CardContent className="flex items-center gap-3 pt-6">
              <AlertTriangle className="h-5 w-5 text-orange-600" />
              <div>
                <p className="font-medium text-orange-900 dark:text-orange-100">
                  Cache is Disabled
                </p>
                <p className="text-sm text-orange-800 dark:text-orange-200">
                  Enable caching in the backend configuration to improve performance.
                </p>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Error State */}
      {isError && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
        >
          <Card className="border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950">
            <CardContent className="flex items-center gap-3 pt-6">
              <AlertTriangle className="h-5 w-5 text-red-600" />
              <div>
                <p className="font-medium text-red-900 dark:text-red-100">
                  Failed to load cache metrics
                </p>
                <p className="text-sm text-red-800 dark:text-red-200">
                  {error?.message || 'An error occurred while fetching cache metrics'}
                </p>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Key Metrics Cards */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.2 }}
        className="grid gap-4 md:grid-cols-2 lg:grid-cols-4"
      >
        {/* Hit Rate */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cache Hit Rate</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${getEfficiencyColor()}`}>
              {cacheData?.metrics?.hit_rate_percent.toFixed(1) || 0}%
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {getEfficiencyBadge()}
            </p>
          </CardContent>
        </Card>

        {/* Total Requests */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Requests</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {cacheData?.metrics?.total_requests.toLocaleString() || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              {cacheData?.metrics?.cache_hits.toLocaleString() || 0} hits / {' '}
              {cacheData?.metrics?.cache_misses.toLocaleString() || 0} misses
            </p>
          </CardContent>
        </Card>

        {/* Cache Size */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cache Utilization</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {utilization.toFixed(0)}%
            </div>
            <p className="text-xs text-muted-foreground">
              {cacheData?.metrics?.current_size || 0} / {cacheData?.metrics?.max_size || 0} items
            </p>
          </CardContent>
        </Card>

        {/* TTL */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cache TTL</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {cacheData?.metrics?.ttl_seconds || 0}s
            </div>
            <p className="text-xs text-muted-foreground">
              Time to live
            </p>
          </CardContent>
        </Card>
      </motion.div>

      {/* Detailed Metrics */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Performance Chart */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.3 }}
        >
          <Card>
            <CardHeader>
              <CardTitle>Cache Performance</CardTitle>
              <CardDescription>Hit vs Miss distribution</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Hit Rate Visualization */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                    Cache Hits
                  </span>
                  <span className="font-mono font-medium">
                    {cacheData?.metrics?.cache_hits.toLocaleString() || 0}
                  </span>
                </div>
                <Progress
                  value={cacheData?.metrics?.hit_rate_percent || 0}
                  className="h-2"
                />
              </div>

              {/* Miss Rate Visualization */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-2">
                    <TrendingDown className="h-4 w-4 text-orange-600" />
                    Cache Misses
                  </span>
                  <span className="font-mono font-medium">
                    {cacheData?.metrics?.cache_misses.toLocaleString() || 0}
                  </span>
                </div>
                <Progress
                  value={
                    100 - (cacheData?.metrics?.hit_rate_percent || 0)
                  }
                  className="h-2"
                />
              </div>

              {/* Cache Size */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-2">
                    <Database className="h-4 w-4 text-blue-600" />
                    Cache Utilization
                  </span>
                  <span className="font-mono font-medium">
                    {cacheData?.metrics?.current_size || 0} / {cacheData?.metrics?.max_size || 0}
                  </span>
                </div>
                <Progress value={utilization} className="h-2" />
              </div>

              {/* Statistics Summary */}
              <div className="rounded-lg bg-muted p-4">
                <h4 className="mb-3 text-sm font-medium">Quick Stats</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-muted-foreground">Avg Hit Rate</p>
                    <p className="text-lg font-semibold">
                      {cacheData?.metrics?.hit_rate_percent.toFixed(1) || 0}%
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Cache Efficiency</p>
                    <p className="text-lg font-semibold capitalize">
                      {efficiency}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Items Cached</p>
                    <p className="text-lg font-semibold">
                      {cacheData?.metrics?.current_size.toLocaleString() || 0}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Max Capacity</p>
                    <p className="text-lg font-semibold">
                      {cacheData?.metrics?.max_size.toLocaleString() || 0}
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Recommendations */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.4 }}
        >
          <Card>
            <CardHeader>
              <CardTitle>Recommendations</CardTitle>
              <CardDescription>Performance optimization suggestions</CardDescription>
            </CardHeader>
            <CardContent>
              {cacheData?.recommendations && cacheData.recommendations.length > 0 ? (
                <div className="space-y-3">
                  {cacheData.recommendations.map((recommendation, index) => (
                    <div
                      key={index}
                      className="flex items-start gap-3 rounded-lg border p-3"
                    >
                      <Info className="mt-0.5 h-5 w-5 flex-shrink-0 text-blue-500" />
                      <p className="text-sm text-muted-foreground">
                        {recommendation}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <CheckCircle2 className="mb-3 h-12 w-12 text-green-500" />
                  <p className="text-sm font-medium">No recommendations</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Your cache is performing optimally!
                  </p>
                </div>
              )}

              {/* Cache Configuration */}
              <div className="mt-6 rounded-lg bg-muted p-4">
                <h4 className="mb-3 text-sm font-medium">Cache Configuration</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Status</span>
                    <span className="font-medium">
                      {cacheEnabled ? (
                        <span className="text-green-600">Enabled</span>
                      ) : (
                        <span className="text-red-600">Disabled</span>
                      )}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Max Size</span>
                    <span className="font-mono">
                      {cacheData?.metrics?.max_size.toLocaleString() || 'N/A'} items
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">TTL</span>
                    <span className="font-mono">
                      {cacheData?.metrics?.ttl_seconds || 0} seconds
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Last Updated</span>
                    <span className="font-mono text-xs">
                      {cacheData?.timestamp
                        ? new Date(cacheData.timestamp).toLocaleString()
                        : 'N/A'}
                    </span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Performance Tips */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.5 }}
      >
        <Card>
          <CardHeader>
            <CardTitle>Cache Performance Guide</CardTitle>
            <CardDescription>Understanding cache metrics</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-lg border p-4">
                <h4 className="mb-2 font-medium text-green-600">Excellent (90%+)</h4>
                <p className="text-sm text-muted-foreground">
                  Your cache is highly effective. Most requests are served from cache,
                  providing optimal performance.
                </p>
              </div>
              <div className="rounded-lg border p-4">
                <h4 className="mb-2 font-medium text-blue-600">Good (75-90%)</h4>
                <p className="text-sm text-muted-foreground">
                  Cache is performing well. Minor optimizations may improve hit rate further.
                </p>
              </div>
              <div className="rounded-lg border p-4">
                <h4 className="mb-2 font-medium text-orange-600">Fair (50-75%)</h4>
                <p className="text-sm text-muted-foreground">
                  Cache is working but could be optimized. Consider increasing cache size or TTL.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
