/**
 * Skeleton Loader Components
 *
 * Provides consistent loading states across the application
 */

import { cn } from '@/lib/utils';

export interface SkeletonProps {
  className?: string;
}

/**
 * Base skeleton component
 */
export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-md bg-muted',
        className
      )}
    />
  );
}

/**
 * Card skeleton - for loading card components
 */
export function CardSkeleton({ className }: SkeletonProps) {
  return (
    <div className={cn('rounded-lg border bg-card p-6', className)}>
      <div className="space-y-3">
        <Skeleton className="h-4 w-[250px]" />
        <Skeleton className="h-4 w-[200px]" />
      </div>
    </div>
  );
}

/**
 * Stats card skeleton - for metric cards
 */
export function StatsCardSkeleton({ className }: SkeletonProps) {
  return (
    <div className={cn('rounded-lg border bg-card p-6', className)}>
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-[120px]" />
          <Skeleton className="h-4 w-4 rounded-full" />
        </div>
        <Skeleton className="h-8 w-[100px]" />
        <Skeleton className="h-3 w-[150px]" />
      </div>
    </div>
  );
}

/**
 * Table row skeleton
 */
export function TableRowSkeleton({ columns = 4 }: { columns?: number }) {
  return (
    <div className="flex items-center space-x-4 py-3">
      {Array.from({ length: columns }).map((_, i) => (
        <Skeleton key={i} className="h-4 flex-1" />
      ))}
    </div>
  );
}

/**
 * Health check component skeleton
 */
export function HealthCheckSkeleton({ className }: SkeletonProps) {
  return (
    <div className={cn('flex items-center gap-3 rounded-lg border p-3', className)}>
      <Skeleton className="h-8 w-8 rounded-full" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-3 w-[80px]" />
        <Skeleton className="h-4 w-[100px]" />
        <Skeleton className="h-2 w-[120px]" />
      </div>
    </div>
  );
}

/**
 * Dashboard skeleton - complete dashboard loading state
 */
export function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Skeleton className="h-10 w-10 rounded-lg" />
          <div className="space-y-2">
            <Skeleton className="h-6 w-[200px]" />
            <Skeleton className="h-4 w-[300px]" />
          </div>
        </div>
        <Skeleton className="h-6 w-[100px]" />
      </div>

      {/* Health Status Card */}
      <div className="rounded-lg border bg-card p-6">
        <div className="mb-4 flex items-center justify-between">
          <Skeleton className="h-6 w-[150px]" />
          <Skeleton className="h-6 w-[80px] rounded-full" />
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <HealthCheckSkeleton key={i} />
          ))}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <StatsCardSkeleton key={i} />
        ))}
      </div>

      {/* Bottom Cards */}
      <div className="grid gap-6 lg:grid-cols-2">
        {Array.from({ length: 2 }).map((_, i) => (
          <CardSkeleton key={i} className="h-[300px]" />
        ))}
      </div>
    </div>
  );
}

/**
 * Cache metrics skeleton
 */
export function CacheMetricsSkeleton() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Skeleton className="h-10 w-10 rounded-lg" />
          <div className="space-y-2">
            <Skeleton className="h-6 w-[200px]" />
            <Skeleton className="h-4 w-[300px]" />
          </div>
        </div>
        <Skeleton className="h-9 w-[100px]" />
      </div>

      {/* Metrics Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <StatsCardSkeleton key={i} />
        ))}
      </div>

      {/* Charts */}
      <div className="grid gap-6 lg:grid-cols-2">
        {Array.from({ length: 2 }).map((_, i) => (
          <div key={i} className="rounded-lg border bg-card p-6">
            <div className="mb-4 space-y-2">
              <Skeleton className="h-5 w-[150px]" />
              <Skeleton className="h-4 w-[200px]" />
            </div>
            <div className="space-y-4">
              {Array.from({ length: 3 }).map((_, j) => (
                <div key={j} className="space-y-2">
                  <div className="flex justify-between">
                    <Skeleton className="h-4 w-[100px]" />
                    <Skeleton className="h-4 w-[60px]" />
                  </div>
                  <Skeleton className="h-2 w-full" />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
