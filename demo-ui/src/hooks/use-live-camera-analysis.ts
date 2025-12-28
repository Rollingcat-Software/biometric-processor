import { useCallback, useState, useRef, useEffect } from 'react';
import { useWebSocket } from './use-websocket';
import { API_CONFIG } from '@/config/api.config';

export type AnalysisMode =
  | 'face_detection'
  | 'quality'
  | 'demographics'
  | 'liveness'
  | 'enrollment_ready'
  | 'verification'
  | 'search'
  | 'landmarks'
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

export interface VerificationData {
  match: boolean;
  confidence: number;
  similarity: number;
  threshold: number;
  user_id: string;
}

export interface SearchData {
  found: boolean;
  user_id?: string;
  confidence: number;
  similarity: number;
  num_candidates: number;
}

export interface LandmarksData {
  landmarks: Record<string, number[]>;
  num_landmarks: number;
  confidence: number;
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
  verification?: VerificationData;
  search?: SearchData;
  landmarks?: LandmarksData;
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

  // Refs for stable access without re-renders
  const wsRef = useRef<any>(null);
  const pendingFramesRef = useRef(0);
  const maxPendingFrames = 2; // Backpressure limit

  // Throttle result updates to reduce re-renders
  const lastResultUpdateRef = useRef(0);
  const resultUpdateInterval = 50; // Update UI max 20 FPS

  const handleMessage = useCallback((message: LiveAnalysisMessage) => {
    if (!message || !message.type) return;

    switch (message.type) {
      case 'result':
        // Decrement pending frames (backpressure)
        if (pendingFramesRef.current > 0) {
          pendingFramesRef.current--;
        }

        // Throttle result updates to reduce re-renders
        const now = Date.now();
        if (now - lastResultUpdateRef.current > resultUpdateInterval) {
          setCurrentResult(message.data as LiveAnalysisResult);
          lastResultUpdateRef.current = now;
        }
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

  // Store ws in ref for stable access
  useEffect(() => {
    wsRef.current = ws;
  }, [ws]);

  // Fix infinite loop: use functional setState and no deps
  const updateConfig = useCallback((newConfig: Partial<LiveAnalysisConfig>) => {
    setConfig((prev) => {
      const updatedConfig = { ...prev, ...newConfig };

      // Send to server if connected
      if (wsRef.current?.isConnected) {
        wsRef.current.send({
          type: 'config',
          data: updatedConfig,
        });
      }

      return updatedConfig;
    });
  }, []); // Empty deps - stable reference!

  const sendFrame = useCallback((imageData: string) => {
    if (!wsRef.current?.isConnected) {
      setError('WebSocket not connected');
      return;
    }

    // Backpressure: skip frame if too many pending
    if (pendingFramesRef.current >= maxPendingFrames) {
      console.warn('Skipping frame - server is behind');
      return;
    }

    // Send config first if not configured
    if (!isConfigured) {
      setConfig((currentConfig) => {
        wsRef.current.send({
          type: 'config',
          data: currentConfig,
        });
        return currentConfig;
      });
    }

    // Send frame
    wsRef.current.send({
      type: 'frame',
      data: imageData,
    });

    // Increment pending frames (backpressure tracking)
    pendingFramesRef.current++;
  }, [isConfigured]);

  const connect = useCallback(() => {
    setIsConfigured(false);
    setError(null);
    setCurrentResult(null);
    setSessionStats(null);
    pendingFramesRef.current = 0; // Reset backpressure
    ws.connect();
  }, [ws]);

  const disconnect = useCallback(() => {
    ws.disconnect();
    setIsConfigured(false);
    setError(null);
    setCurrentResult(null);
    setSessionStats(null);
    pendingFramesRef.current = 0; // Reset backpressure
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

    // Backpressure stats
    pendingFrames: pendingFramesRef.current,
  };
}
