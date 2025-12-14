import { Loader2 } from 'lucide-react';

/**
 * Global loading component for page transitions.
 * This file is automatically used by Next.js App Router during navigation.
 */
export default function Loading() {
  return (
    <div className="flex items-center justify-center min-h-[50vh]">
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    </div>
  );
}
