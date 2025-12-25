/**
 * Error Boundary Component
 *
 * Catches React errors and displays a fallback UI instead of crashing
 */

'use client';

import { Component, ReactNode } from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return {
      hasError: true,
      error,
    };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log error to console in development
    if (process.env.NODE_ENV === 'development') {
      console.error('Error Boundary caught an error:', error, errorInfo);
    }

    this.setState({
      error,
      errorInfo,
    });

    // You could also log to an error reporting service here
    // logErrorToService(error, errorInfo);
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  handleGoHome = () => {
    window.location.href = '/';
  };

  render() {
    if (this.state.hasError) {
      // Custom fallback UI
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Default fallback UI
      return (
        <div className="flex min-h-screen items-center justify-center p-4">
          <Card className="w-full max-w-2xl border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/50">
            <div className="p-8 space-y-6">
              {/* Icon and Title */}
              <div className="flex items-start gap-4">
                <div className="flex-shrink-0">
                  <div className="rounded-full bg-red-100 p-3 dark:bg-red-900">
                    <AlertTriangle className="h-8 w-8 text-red-600 dark:text-red-400" />
                  </div>
                </div>
                <div className="flex-1">
                  <h1 className="text-2xl font-bold text-red-900 dark:text-red-100">
                    Oops! Something went wrong
                  </h1>
                  <p className="mt-2 text-red-800 dark:text-red-200">
                    We're sorry, but something unexpected happened. The error has been logged
                    and we'll look into it.
                  </p>
                </div>
              </div>

              {/* Error Details (Development only) */}
              {process.env.NODE_ENV === 'development' && this.state.error && (
                <div className="rounded-lg bg-red-100 dark:bg-red-900/50 p-4 space-y-2">
                  <h3 className="font-semibold text-red-900 dark:text-red-100">
                    Error Details (Development Only)
                  </h3>
                  <div className="space-y-2 text-sm">
                    <div>
                      <span className="font-medium text-red-800 dark:text-red-200">Message:</span>
                      <pre className="mt-1 overflow-auto rounded bg-red-200 dark:bg-red-800 p-2 text-xs text-red-900 dark:text-red-100">
                        {this.state.error.message}
                      </pre>
                    </div>
                    {this.state.error.stack && (
                      <div>
                        <span className="font-medium text-red-800 dark:text-red-200">Stack Trace:</span>
                        <pre className="mt-1 max-h-48 overflow-auto rounded bg-red-200 dark:bg-red-800 p-2 text-xs text-red-900 dark:text-red-100">
                          {this.state.error.stack}
                        </pre>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex flex-wrap gap-3">
                <Button
                  onClick={this.handleReset}
                  className="flex items-center gap-2"
                >
                  <RefreshCw className="h-4 w-4" />
                  Try Again
                </Button>
                <Button
                  variant="outline"
                  onClick={this.handleGoHome}
                  className="flex items-center gap-2"
                >
                  <Home className="h-4 w-4" />
                  Go to Home
                </Button>
                {process.env.NODE_ENV === 'development' && (
                  <Button
                    variant="outline"
                    onClick={() => window.location.reload()}
                    className="flex items-center gap-2"
                  >
                    <RefreshCw className="h-4 w-4" />
                    Reload Page
                  </Button>
                )}
              </div>

              {/* Support Message */}
              <div className="rounded-lg border border-red-300 dark:border-red-700 bg-red-100/50 dark:bg-red-900/20 p-4">
                <p className="text-sm text-red-800 dark:text-red-200">
                  <strong>Need help?</strong> If this problem persists, please contact support
                  with the error details above. We apologize for the inconvenience.
                </p>
              </div>
            </div>
          </Card>
        </div>
      );
    }

    return this.props.children;
  }
}

/**
 * Hook to use error boundary programmatically
 */
export function useErrorHandler() {
  const handleError = (error: Error) => {
    // Throw error to be caught by nearest Error Boundary
    throw error;
  };

  return { handleError };
}
