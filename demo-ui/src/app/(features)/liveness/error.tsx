'use client';

import { useEffect } from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export default function LivenessError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    if (process.env.NODE_ENV === 'development') {
      console.error('Liveness detection page error:', error);
    }
  }, [error]);

  return (
    <div className="flex min-h-[60vh] items-center justify-center p-4">
      <Card className="w-full max-w-2xl border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/50">
        <div className="p-8 space-y-6">
          <div className="flex items-start gap-4">
            <div className="flex-shrink-0">
              <div className="rounded-full bg-red-100 p-3 dark:bg-red-900">
                <AlertTriangle className="h-8 w-8 text-red-600 dark:text-red-400" />
              </div>
            </div>
            <div className="flex-1">
              <h1 className="text-2xl font-bold text-red-900 dark:text-red-100">
                Liveness Detection Failed
              </h1>
              <p className="mt-2 text-red-800 dark:text-red-200">
                An error occurred during liveness detection. Please try again with a clear face image.
              </p>
            </div>
          </div>

          {process.env.NODE_ENV === 'development' && (
            <div className="rounded-lg bg-red-100 dark:bg-red-900/50 p-4 space-y-2">
              <h3 className="font-semibold text-red-900 dark:text-red-100">Error Details (Development Only)</h3>
              <pre className="mt-1 overflow-auto rounded bg-red-200 dark:bg-red-800 p-2 text-xs text-red-900 dark:text-red-100">
                {error.message}
              </pre>
            </div>
          )}

          <div className="flex flex-wrap gap-3">
            <Button onClick={reset} className="flex items-center gap-2">
              <RefreshCw className="h-4 w-4" />
              Try Again
            </Button>
            <Button variant="outline" onClick={() => (window.location.href = '/')} className="flex items-center gap-2">
              <Home className="h-4 w-4" />
              Go to Home
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
