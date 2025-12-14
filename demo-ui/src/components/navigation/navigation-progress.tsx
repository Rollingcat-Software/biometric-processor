'use client';

import { useEffect, useState, useRef } from 'react';
import { usePathname, useSearchParams } from 'next/navigation';

/**
 * Global navigation progress bar component.
 * Shows a progress bar at the top of the page during route transitions.
 */
export function NavigationProgress() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isNavigating, setIsNavigating] = useState(false);
  const [progress, setProgress] = useState(0);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // Reset progress when navigation completes
  useEffect(() => {
    // Clear any running interval
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    setIsNavigating(false);
    setProgress(100);

    // Hide the bar after animation
    const timeout = setTimeout(() => {
      setProgress(0);
    }, 200);

    return () => clearTimeout(timeout);
  }, [pathname, searchParams]);

  // Listen for clicks on links to start progress
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      const link = target.closest('a');

      if (link) {
        const href = link.getAttribute('href');
        // Only show progress for internal navigation
        if (href && href.startsWith('/') && href !== pathname) {
          setIsNavigating(true);
          setProgress(0);

          // Clear any existing interval
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
          }

          // Animate progress
          let currentProgress = 0;
          intervalRef.current = setInterval(() => {
            currentProgress += Math.random() * 15;
            if (currentProgress >= 90) {
              if (intervalRef.current) {
                clearInterval(intervalRef.current);
                intervalRef.current = null;
              }
              setProgress(90);
            } else {
              setProgress(currentProgress);
            }
          }, 100);
        }
      }
    };

    document.addEventListener('click', handleClick);
    return () => {
      document.removeEventListener('click', handleClick);
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [pathname]);

  if (progress === 0) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-[100] h-1 bg-transparent">
      <div
        className="h-full bg-primary transition-all duration-200 ease-out"
        style={{
          width: `${progress}%`,
          opacity: isNavigating ? 1 : 0,
          transition: isNavigating
            ? 'width 200ms ease-out'
            : 'width 200ms ease-out, opacity 200ms ease-out 100ms',
        }}
      />
    </div>
  );
}
