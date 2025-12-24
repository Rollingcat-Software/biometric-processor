import { Loader2, Video } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';

/**
 * Loading component for proctoring session page.
 * Shows while the page is loading.
 */
export default function Loading() {
  return (
    <div className="space-y-6">
      {/* Header Skeleton */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-500/10">
          <Video className="h-5 w-5 text-red-500" />
        </div>
        <div className="space-y-2">
          <div className="h-6 w-48 animate-pulse rounded bg-muted" />
          <div className="h-4 w-64 animate-pulse rounded bg-muted" />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Video Card Skeleton */}
        <Card className="lg:col-span-2">
          <CardContent className="p-6">
            <div className="relative aspect-video rounded-lg bg-black overflow-hidden flex items-center justify-center">
              <div className="text-center text-white">
                <Loader2 className="h-12 w-12 mx-auto mb-4 animate-spin opacity-70" />
                <p className="text-sm opacity-70">Loading proctoring session...</p>
              </div>
            </div>
            <div className="mt-4 space-y-3">
              <div className="h-10 w-full animate-pulse rounded bg-muted" />
            </div>
          </CardContent>
        </Card>

        {/* Stats Skeleton */}
        <div className="space-y-6">
          <Card>
            <CardContent className="p-6 space-y-4">
              <div className="h-5 w-32 animate-pulse rounded bg-muted" />
              <div className="grid grid-cols-2 gap-4">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="rounded-lg border p-3 space-y-2">
                    <div className="h-3 w-16 animate-pulse rounded bg-muted" />
                    <div className="h-6 w-12 animate-pulse rounded bg-muted" />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6 space-y-4">
              <div className="h-5 w-40 animate-pulse rounded bg-muted" />
              <div className="h-32 w-full animate-pulse rounded bg-muted" />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
