/**
 * Error Display Component with Correlation ID
 *
 * Displays errors with correlation ID for debugging and support requests
 */

'use client';

import { AlertCircle, Copy, CheckCircle2 } from 'lucide-react';
import { useState } from 'react';
import { Button } from './button';
import { Card } from './card';
import { Badge } from './badge';
import { copyToClipboard } from '@/lib/utils';
import { toast } from 'sonner';
import type { ApiClientError } from '@/lib/api/client';

export interface ErrorDisplayProps {
  error: Error | ApiClientError | null;
  title?: string;
  className?: string;
  showCopyButton?: boolean;
}

export function ErrorDisplay({
  error,
  title = 'Error',
  className = '',
  showCopyButton = true,
}: ErrorDisplayProps) {
  const [copied, setCopied] = useState(false);

  if (!error) return null;

  const isApiError = error instanceof Error && 'requestId' in error;
  const apiError = isApiError ? (error as ApiClientError) : null;

  const handleCopyError = async () => {
    const errorDetails = apiError?.formatForSupport() || `Error: ${error.message}`;

    const success = await copyToClipboard(errorDetails);
    if (success) {
      setCopied(true);
      toast.success('Error details copied to clipboard');
      setTimeout(() => setCopied(false), 2000);
    } else {
      toast.error('Failed to copy error details');
    }
  };

  return (
    <Card
      className={`border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/50 ${className}`}
    >
      <div className="p-4 space-y-3">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3 flex-1">
            <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-600 dark:text-red-400 mt-0.5" />
            <div className="flex-1 space-y-1">
              <h4 className="font-medium text-red-900 dark:text-red-100">{title}</h4>
              <p className="text-sm text-red-800 dark:text-red-200">
                {apiError?.getUserMessage() || error.message}
              </p>
            </div>
          </div>

          {showCopyButton && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopyError}
              className="flex-shrink-0 border-red-300 text-red-700 hover:bg-red-100 dark:border-red-700 dark:text-red-300 dark:hover:bg-red-900"
            >
              {copied ? (
                <>
                  <CheckCircle2 className="h-4 w-4 mr-2" />
                  Copied!
                </>
              ) : (
                <>
                  <Copy className="h-4 w-4 mr-2" />
                  Copy Details
                </>
              )}
            </Button>
          )}
        </div>

        {/* Error Details */}
        {apiError && (
          <div className="rounded-lg bg-red-100 dark:bg-red-900/30 p-3 space-y-2 text-sm">
            {/* Error Code */}
            {apiError.errorCode && (
              <div className="flex items-center justify-between">
                <span className="text-red-700 dark:text-red-300 font-medium">
                  Error Code:
                </span>
                <Badge variant="destructive" className="font-mono">
                  {apiError.errorCode}
                </Badge>
              </div>
            )}

            {/* Correlation ID */}
            {apiError.requestId && (
              <div className="flex items-center justify-between">
                <span className="text-red-700 dark:text-red-300 font-medium">
                  Request ID:
                </span>
                <code className="text-xs bg-red-200 dark:bg-red-800 px-2 py-1 rounded font-mono text-red-900 dark:text-red-100">
                  {apiError.requestId}
                </code>
              </div>
            )}

            {/* Status Code */}
            {apiError.status && (
              <div className="flex items-center justify-between">
                <span className="text-red-700 dark:text-red-300 font-medium">
                  Status Code:
                </span>
                <Badge variant="outline" className="font-mono border-red-300 dark:border-red-700">
                  {apiError.status}
                </Badge>
              </div>
            )}

            {/* Timestamp */}
            {apiError.timestamp && (
              <div className="flex items-center justify-between">
                <span className="text-red-700 dark:text-red-300 font-medium">
                  Time:
                </span>
                <span className="text-xs text-red-800 dark:text-red-200 font-mono">
                  {new Date(apiError.timestamp).toLocaleString()}
                </span>
              </div>
            )}
          </div>
        )}

        {/* Support Message */}
        {apiError?.requestId && (
          <p className="text-xs text-red-700 dark:text-red-300">
            💡 <strong>Need help?</strong> Share the Request ID above with support to help us
            investigate this issue.
          </p>
        )}
      </div>
    </Card>
  );
}

/**
 * Inline Error Display (for smaller error messages)
 */
export interface InlineErrorDisplayProps {
  error: Error | ApiClientError | null;
  className?: string;
}

export function InlineErrorDisplay({ error, className = '' }: InlineErrorDisplayProps) {
  if (!error) return null;

  const isApiError = error instanceof Error && 'requestId' in error;
  const apiError = isApiError ? (error as ApiClientError) : null;

  return (
    <div
      className={`rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-800 dark:bg-red-950/50 dark:text-red-200 ${className}`}
    >
      <div className="flex items-start gap-2">
        <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <p>{apiError?.getUserMessage() || error.message}</p>
          {apiError?.requestId && (
            <p className="mt-1 text-xs opacity-75">
              Request ID: <code className="font-mono">{apiError.requestId}</code>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
