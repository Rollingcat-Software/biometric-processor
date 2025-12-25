import { useCallback, useEffect, useRef, useState } from 'react';
import { API_CONFIG } from '@/config/api.config';

const WS_URL = API_CONFIG.WS_URL;

type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error' | 'reconnecting';

interface UseWebSocketOptions {
  url: string;
  onMessage?: (data: any) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  reconnect?: boolean;
  reconnectInterval?: number;
  reconnectAttempts?: number;
  heartbeatInterval?: number; // Ping interval in ms
  heartbeatMessage?: string; // Custom ping message
}

interface UseWebSocketReturn {
  status: WebSocketStatus;
  send: (data: any) => void;
  connect: () => void;
  disconnect: () => void;
  lastMessage: any;
  reconnectCount: number;
  isConnected: boolean;
}

export function useWebSocket({
  url,
  onMessage,
  onOpen,
  onClose,
  onError,
  reconnect = true,
  reconnectInterval = 3000,
  reconnectAttempts = 5,
  heartbeatInterval = 30000, // Default: 30 seconds
  heartbeatMessage = 'ping',
}: UseWebSocketOptions): UseWebSocketReturn {
  const [status, setStatus] = useState<WebSocketStatus>('disconnected');
  const [lastMessage, setLastMessage] = useState<any>(null);
  const [reconnectCount, setReconnectCount] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const heartbeatTimeoutRef = useRef<NodeJS.Timeout>();

  // Start heartbeat
  const startHeartbeat = useCallback(() => {
    if (heartbeatTimeoutRef.current) {
      clearInterval(heartbeatTimeoutRef.current);
    }

    heartbeatTimeoutRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(heartbeatMessage);
      }
    }, heartbeatInterval);
  }, [heartbeatInterval, heartbeatMessage]);

  // Stop heartbeat
  const stopHeartbeat = useCallback(() => {
    if (heartbeatTimeoutRef.current) {
      clearInterval(heartbeatTimeoutRef.current);
    }
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    setStatus(reconnectCountRef.current > 0 ? 'reconnecting' : 'connecting');

    try {
      wsRef.current = new WebSocket(url);

      wsRef.current.onopen = () => {
        setStatus('connected');
        setReconnectCount(0);
        reconnectCountRef.current = 0;
        startHeartbeat(); // Start heartbeat on connection
        onOpen?.();
      };

      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          // Ignore pong responses
          if (data !== 'pong' && event.data !== 'pong') {
            setLastMessage(data);
            onMessage?.(data);
          }
        } catch {
          // Handle non-JSON messages
          if (event.data !== 'pong') {
            setLastMessage(event.data);
            onMessage?.(event.data);
          }
        }
      };

      wsRef.current.onclose = () => {
        setStatus('disconnected');
        stopHeartbeat(); // Stop heartbeat on disconnect
        onClose?.();

        if (reconnect && reconnectCountRef.current < reconnectAttempts) {
          reconnectCountRef.current++;
          setReconnectCount(reconnectCountRef.current);

          // Exponential backoff: 3s, 6s, 12s, 24s, 48s
          const backoffDelay = reconnectInterval * Math.pow(2, reconnectCountRef.current - 1);
          const maxDelay = 30000; // Cap at 30 seconds
          const delay = Math.min(backoffDelay, maxDelay);

          setStatus('reconnecting');
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        }
      };

      wsRef.current.onerror = (error) => {
        setStatus('error');
        stopHeartbeat();
        onError?.(error);
      };
    } catch {
      setStatus('error');
      stopHeartbeat();
    }
  }, [url, onMessage, onOpen, onClose, onError, reconnect, reconnectInterval, reconnectAttempts, startHeartbeat, stopHeartbeat]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    stopHeartbeat(); // Stop heartbeat
    reconnectCountRef.current = reconnectAttempts; // Prevent reconnection
    wsRef.current?.close();
    setStatus('disconnected');
    setReconnectCount(0);
  }, [reconnectAttempts, stopHeartbeat]);

  const send = useCallback((data: string | ArrayBuffer | Blob | object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      // Handle binary data (ArrayBuffer, Blob) directly
      if (data instanceof ArrayBuffer || data instanceof Blob) {
        wsRef.current.send(data);
      } else if (typeof data === 'string') {
        wsRef.current.send(data);
      } else {
        // Objects get JSON serialized
        wsRef.current.send(JSON.stringify(data));
      }
    }
  }, []);

  useEffect(() => {
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (heartbeatTimeoutRef.current) {
        clearInterval(heartbeatTimeoutRef.current);
      }
      wsRef.current?.close();
    };
  }, []);

  return {
    status,
    send,
    connect,
    disconnect,
    lastMessage,
    reconnectCount,
    isConnected: status === 'connected',
  };
}

// Specialized hook for proctoring streaming
interface ProctoringFrame {
  type: 'frame_result';
  session_id: string;
  timestamp: string;
  face_detected: boolean;
  liveness_score?: number;
  alerts?: Array<{
    type: string;
    severity: string;
    message: string;
  }>;
}

export function useProctoringStream(sessionId: string) {
  const baseUrl = WS_URL;
  const [frames, setFrames] = useState<ProctoringFrame[]>([]);
  const [currentFrame, setCurrentFrame] = useState<ProctoringFrame | null>(null);

  const handleMessage = useCallback((data: ProctoringFrame) => {
    if (data.type === 'frame_result') {
      setCurrentFrame(data);
      setFrames((prev) => [...prev.slice(-99), data]); // Keep last 100 frames
    }
  }, []);

  const ws = useWebSocket({
    url: `${baseUrl}/api/v1/proctoring/sessions/${sessionId}/stream`,
    onMessage: handleMessage,
  });

  const sendFrame = useCallback(
    (imageData: string) => {
      ws.send({
        type: 'frame',
        session_id: sessionId,
        image: imageData,
        timestamp: new Date().toISOString(),
      });
    },
    [ws, sessionId]
  );

  return {
    ...ws,
    frames,
    currentFrame,
    sendFrame,
  };
}
