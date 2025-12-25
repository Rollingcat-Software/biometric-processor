/**
 * Connection Status Indicator
 *
 * Shows WebSocket connection status with visual feedback
 */

'use client';

import { Wifi, WifiOff, RefreshCw, AlertCircle } from 'lucide-react';
import { Badge } from './badge';
import { cn } from '@/lib/utils';

export interface ConnectionStatusProps {
  status: 'connecting' | 'connected' | 'disconnected' | 'error' | 'reconnecting';
  reconnectCount?: number;
  className?: string;
  showText?: boolean;
}

export function ConnectionStatus({
  status,
  reconnectCount = 0,
  className = '',
  showText = true,
}: ConnectionStatusProps) {
  const getStatusConfig = () => {
    switch (status) {
      case 'connected':
        return {
          icon: <Wifi className="h-3 w-3" />,
          label: 'Connected',
          variant: 'default' as const,
          color: 'bg-green-500',
        };
      case 'connecting':
        return {
          icon: <RefreshCw className="h-3 w-3 animate-spin" />,
          label: 'Connecting...',
          variant: 'secondary' as const,
          color: 'bg-blue-500',
        };
      case 'reconnecting':
        return {
          icon: <RefreshCw className="h-3 w-3 animate-spin" />,
          label: `Reconnecting...${reconnectCount > 0 ? ` (${reconnectCount})` : ''}`,
          variant: 'secondary' as const,
          color: 'bg-orange-500',
        };
      case 'disconnected':
        return {
          icon: <WifiOff className="h-3 w-3" />,
          label: 'Disconnected',
          variant: 'outline' as const,
          color: 'bg-gray-500',
        };
      case 'error':
        return {
          icon: <AlertCircle className="h-3 w-3" />,
          label: 'Connection Error',
          variant: 'destructive' as const,
          color: 'bg-red-500',
        };
      default:
        return {
          icon: <WifiOff className="h-3 w-3" />,
          label: 'Unknown',
          variant: 'outline' as const,
          color: 'bg-gray-500',
        };
    }
  };

  const config = getStatusConfig();

  return (
    <Badge variant={config.variant} className={cn('flex items-center gap-1.5', className)}>
      {config.icon}
      {showText && <span>{config.label}</span>}
    </Badge>
  );
}

/**
 * Minimal connection indicator (dot only)
 */
export function ConnectionDot({
  status,
  className = '',
}: Pick<ConnectionStatusProps, 'status' | 'className'>) {
  const getColor = () => {
    switch (status) {
      case 'connected':
        return 'bg-green-500';
      case 'connecting':
        return 'bg-blue-500 animate-pulse';
      case 'reconnecting':
        return 'bg-orange-500 animate-pulse';
      case 'disconnected':
        return 'bg-gray-500';
      case 'error':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  return (
    <div
      className={cn('h-2 w-2 rounded-full', getColor(), className)}
      title={status}
    />
  );
}
