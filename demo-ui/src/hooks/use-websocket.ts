import { useCallback, useEffect, useRef, useState } from 'react';

type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

interface UseWebSocketOptions {
  url: string;
  onMessage?: (data: any) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  reconnect?: boolean;
  reconnectInterval?: number;
  reconnectAttempts?: number;
}

interface UseWebSocketReturn {
  status: WebSocketStatus;
  send: (data: any) => void;
  connect: () => void;
  disconnect: () => void;
  lastMessage: any;
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
}: UseWebSocketOptions): UseWebSocketReturn {
  const [status, setStatus] = useState<WebSocketStatus>('disconnected');
  const [lastMessage, setLastMessage] = useState<any>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    setStatus('connecting');

    try {
      wsRef.current = new WebSocket(url);

      wsRef.current.onopen = () => {
        setStatus('connected');
        reconnectCountRef.current = 0;
        onOpen?.();
      };

      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setLastMessage(data);
          onMessage?.(data);
        } catch {
          setLastMessage(event.data);
          onMessage?.(event.data);
        }
      };

      wsRef.current.onclose = () => {
        setStatus('disconnected');
        onClose?.();

        if (reconnect && reconnectCountRef.current < reconnectAttempts) {
          reconnectCountRef.current++;
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, reconnectInterval);
        }
      };

      wsRef.current.onerror = (error) => {
        setStatus('error');
        onError?.(error);
      };
    } catch (error) {
      setStatus('error');
    }
  }, [url, onMessage, onOpen, onClose, onError, reconnect, reconnectInterval, reconnectAttempts]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    reconnectCountRef.current = reconnectAttempts; // Prevent reconnection
    wsRef.current?.close();
    setStatus('disconnected');
  }, [reconnectAttempts]);

  const send = useCallback((data: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const message = typeof data === 'string' ? data : JSON.stringify(data);
      wsRef.current.send(message);
    }
  }, []);

  useEffect(() => {
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
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
  const baseUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8001';
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
