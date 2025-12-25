import { useCallback, useState } from 'react';
import { useWebSocket } from './use-websocket';
import { API_CONFIG } from '@/config/api.config';

export type AnalysisMode =
  | 'face_detection'
  | 'quality'
  | 'demographics'
  | 'liveness'
  | 'enrollment_ready'
  | 'full';

export interface LiveAnalysisConfig {
  mode: AnalysisMode;
  user_id?: string;
  tenant_id?: string;
  frame_skip?: number;
  quality_threshold?: number;
}

export interface FaceDetectionData {
  x: number;
  y: number;
  width: number;
  height: number;
  confidence: number;
  landmarks?: Record<string, [number, number]>;
}

export interface QualityData {
  overall_score: number;
  brightness: number;
  sharpness: number;
  face_size: number;
  centering: number;
  recommendation?: string;
}

export interface DemographicsData {
  age?: number;
  gender?: string;
  emotion?: string;
  race?: string;
}

export interface LivenessData {
  is_live: boolean;
  confidence: number;
  recommendation?: string;
}

export interface EnrollmentReadyData {
  is_ready: boolean;
  quality_score: number;
  liveness_score?: number;
  recommendation?: string;
}

export interface LiveAnalysisResult {
  frame_number: number;
  timestamp: number;
  processing_time_ms: number;
  face?: FaceDetectionData;
  quality?: QualityData;
  demographics?: DemographicsData;
  liveness?: LivenessData;
  enrollment_ready?: EnrollmentReadyData;
  error?: string;
  skipped?: boolean;
  recommendation?: string;
}

export interface SessionStats {
  total_frames: number;
  processed_frames: number;
  skipped_frames: number;
  average_processing_time_ms: number;
  average_fps: number;
}

interface LiveAnalysisMessage {
  type: 'result' | 'error' | 'stats' | 'config_ack';
  data: LiveAnalysisResult | SessionStats | { status: string; config: LiveAnalysisConfig } | { error: string };
}

export function useLiveCameraAnalysis() {
  const [config, setConfig] = useState<LiveAnalysisConfig>({
    mode: 'quality',
    frame_skip: 0,
    quality_threshold: 70.0,
  });
  const [currentResult, setCurrentResult] = useState<LiveAnalysisResult | null>(null);
  const [sessionStats, setSessionStats] = useState<SessionStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isConfigured, setIsConfigured] = useState(false);

  const handleMessage = useCallback((message: LiveAnalysisMessage) => {
    if (!message || !message.type) return;

    switch (message.type) {
      case 'result':
        setCurrentResult(message.data as LiveAnalysisResult);
        setError(null);
        break;
      case 'error':
        setError((message.data as { error: string }).error || 'Unknown error');
        break;
      case 'stats':
        setSessionStats(message.data as SessionStats);
        break;
      case 'config_ack':
        setIsConfigured(true);
        setError(null);
        break;
    }
  }, []);

  const ws = useWebSocket({
    url: API_CONFIG.buildWsUrl('/ws/live-analysis'),
    onMessage: handleMessage,
    reconnect: true,
    reconnectInterval: 2000,
    reconnectAttempts: 3,
  });

  const updateConfig = useCallback((newConfig: Partial<LiveAnalysisConfig>) => {
    const updatedConfig = { ...config, ...newConfig };
    setConfig(updatedConfig);

    if (ws.isConnected) {
      ws.send({
        type: 'config',
        data: updatedConfig,
      });
    }
  }, [config, ws]);

  const sendFrame = useCallback((imageData: string) => {
    if (!ws.isConnected) {
      setError('WebSocket not connected');
      return;
    }

    // Send config first if not configured
    if (!isConfigured) {
      ws.send({
        type: 'config',
        data: config,
      });
    }

    // Send frame
    ws.send({
      type: 'frame',
      data: imageData,
    });
  }, [ws, config, isConfigured]);

  const connect = useCallback(() => {
    setIsConfigured(false);
    setError(null);
    setCurrentResult(null);
    setSessionStats(null);
    ws.connect();
  }, [ws]);

  const disconnect = useCallback(() => {
    ws.disconnect();
    setIsConfigured(false);
    setError(null);
    setCurrentResult(null);
    setSessionStats(null);
  }, [ws]);

  return {
    // Connection
    connect,
    disconnect,
    status: ws.status,
    isConnected: ws.isConnected,

    // Configuration
    config,
    updateConfig,
    isConfigured,

    // Frame processing
    sendFrame,

    // Results
    currentResult,
    sessionStats,
    error,

    // Reconnection info
    reconnectCount: ws.reconnectCount,
  };
}
