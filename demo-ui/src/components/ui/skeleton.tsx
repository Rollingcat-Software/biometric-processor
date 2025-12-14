import { cn } from '@/lib/utils/cn';

/**
 * Skeleton loading placeholder component.
 * Use this to indicate content that is loading.
 */
function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('animate-pulse rounded-md bg-muted', className)}
      {...props}
    />
  );
}

export { Skeleton };
