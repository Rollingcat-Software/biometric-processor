import { useCallback, useState, useRef } from 'react';
import { useWebSocket } from './use-websocket';
import { API_CONFIG } from '@/config/api.config';

export type AnalysisMode =
  | 'face_detection'
  | 'quality'
  | 'demographics'
  | 'liveness'
  | 'active_liveness'
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
  detected?: boolean;
  // Convenience alias for components that expect bbox
  bbox?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
}

export interface QualityData {
  overall_score: number;
  brightness: number;
  sharpness: number;
  face_size: number;
  centering: number;
  recommendation?: string;
  // Optional nested metrics for components expecting nested structure
  metrics?: Record<string, number>;
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
  method?: string;
  checks?: Record<string, boolean>;
  recommendation?: string;
}

export interface ActiveLivenessData {
  // Current challenge
  current_challenge: string | null;
  instruction: string;
  feedback: string;
  time_remaining: number;

  // Progress
  challenges_completed: number;
  challenges_total: number;
  challenge_progress: number;

  // Detection
  action_detected: boolean;
  action_confidence: number;

  // Session state
  session_complete: boolean;
  session_passed: boolean;
  overall_score: number;
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
  active_liveness?: ActiveLivenessData;
  enrollment_ready?: EnrollmentReadyData;
  verification?: VerificationData;
  search?: SearchData;
  landmarks?: LandmarksData;
  error?: string;
  skipped?: boolean;
  recommendation?: string;
}

export interface SessionStats {
  // Backend field names
  frames_received: number;
  frames_processed: number;
  frames_skipped: number;
  average_processing_time_ms: number;
  best_quality_score: number;
  enrollment_ready_count: number;
  // Computed for UI
  total_frames?: number;
  processed_frames?: number;
  skipped_frames?: number;
  average_fps?: number;
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

  // Use refs to avoid dependency cycles that cause infinite re-renders
  const configRef = useRef(config);
  configRef.current = config;
  const isConfiguredRef = useRef(isConfigured);
  isConfiguredRef.current = isConfigured;

  const handleMessage = useCallback((message: LiveAnalysisMessage) => {
    if (!message || !message.type) {
      console.warn('[LiveAnalysis] Invalid message received:', message);
      return;
    }

    // Debug logging for development
    if (process.env.NODE_ENV === 'development') {
      console.log('[LiveAnalysis] Message:', message.type, message.data);
    }

    switch (message.type) {
      case 'result':
        const result = message.data as LiveAnalysisResult;
        // Debug: log active liveness data
        if (result.active_liveness) {
          console.log('[LiveAnalysis] Active liveness:', result.active_liveness);
        }
        setCurrentResult(result);
        setError(null);
        break;
      case 'error':
        console.error('[LiveAnalysis] Error:', message.data);
        setError((message.data as { error: string }).error || 'Unknown error');
        break;
      case 'stats':
        setSessionStats(message.data as SessionStats);
        break;
      case 'config_ack':
        console.log('[LiveAnalysis] Config acknowledged');
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

  // Destructure to get stable references (these are memoized in useWebSocket)
  const { isConnected, send: wsSend, connect: wsConnect, disconnect: wsDisconnect } = ws;

  // updateConfig uses refs to avoid depending on config state
  const updateConfig = useCallback((newConfig: Partial<LiveAnalysisConfig>) => {
    const updatedConfig = { ...configRef.current, ...newConfig };
    setConfig(updatedConfig);

    if (isConnected) {
      wsSend({
        type: 'config',
        data: updatedConfig,
      });
    }
  }, [isConnected, wsSend]);

  const sendFrame = useCallback((imageData: string) => {
    if (!isConnected) {
      setError('WebSocket not connected');
      return;
    }

    // Send config first if not configured
    if (!isConfiguredRef.current) {
      wsSend({
        type: 'config',
        data: configRef.current,
      });
    }

    // Send frame
    wsSend({
      type: 'frame',
      data: imageData,
    });
  }, [isConnected, wsSend]);

  const connect = useCallback(() => {
    setIsConfigured(false);
    setError(null);
    setCurrentResult(null);
    setSessionStats(null);
    wsConnect();
  }, [wsConnect]);

  const disconnect = useCallback(() => {
    wsDisconnect();
    setIsConfigured(false);
    setError(null);
    setCurrentResult(null);
    setSessionStats(null);
  }, [wsDisconnect]);

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
