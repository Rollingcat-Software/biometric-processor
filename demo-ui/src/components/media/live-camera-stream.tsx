'use client';

import { useCallback, useRef, useState, useEffect } from 'react';
import { Video, VideoOff, Play, StopCircle, Activity, Zap } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils/cn';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useAppStore } from '@/lib/store/app-store';
import {
  useLiveCameraAnalysis,
  type AnalysisMode,
  type LiveAnalysisResult,
} from '@/hooks/use-live-camera-analysis';

interface LiveCameraStreamProps {
  mode: AnalysisMode;
  onResult?: (result: LiveAnalysisResult) => void;
  disabled?: boolean;
  userId?: string;
  tenantId?: string;
  qualityThreshold?: number;
}

export function LiveCameraStream({
  mode,
  onResult,
  disabled = false,
  userId,
  tenantId,
  qualityThreshold = 70.0,
}: LiveCameraStreamProps) {
  const { t } = useTranslation();
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const frameIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const onResultRef = useRef(onResult);
  const configSentRef = useRef(false);

  const [isStreaming, setIsStreaming] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [fps, setFps] = useState(0);

  const { cameraFacingMode, cameraResolution } = useAppStore();

  const {
    connect,
    disconnect,
    isConnected,
    status,
    sendFrame,
    currentResult,
    sessionStats,
    error: wsError,
    updateConfig,
  } = useLiveCameraAnalysis();

  // Store updateConfig in a ref to avoid dependency issues
  const updateConfigRef = useRef(updateConfig);
  updateConfigRef.current = updateConfig;

  // Keep onResult ref up to date (no effect, just assignment)
  onResultRef.current = onResult;

  // Store current config props in a ref
  const configPropsRef = useRef({ mode, userId, tenantId, qualityThreshold });
  configPropsRef.current = { mode, userId, tenantId, qualityThreshold };

  // Update config only once on mount and when connection becomes active
  useEffect(() => {
    // Only send config if connected and not already sent
    if (isConnected && !configSentRef.current) {
      const config = {
        mode: configPropsRef.current.mode,
        user_id: configPropsRef.current.userId,
        tenant_id: configPropsRef.current.tenantId,
        frame_skip: 0,
        quality_threshold: configPropsRef.current.qualityThreshold,
      };
      console.log('[LiveCameraStream] Sending config:', config);
      updateConfigRef.current(config);
      configSentRef.current = true;
    }

    // Reset when disconnected
    if (!isConnected) {
      configSentRef.current = false;
    }
  }, [isConnected]);

  // Call onResult when we get a new result
  useEffect(() => {
    if (currentResult && onResultRef.current) {
      onResultRef.current(currentResult);
    }
  }, [currentResult]);

  // Update FPS display - calculate from processing time
  useEffect(() => {
    if (sessionStats && sessionStats.average_processing_time_ms > 0) {
      // Calculate FPS: 1000ms / avg_processing_time = theoretical max FPS
      const calculatedFps = Math.min(10, Math.round(1000 / sessionStats.average_processing_time_ms));
      setFps(calculatedFps);
    }
  }, [sessionStats]);

  const getResolutionConstraints = useCallback(() => {
    switch (cameraResolution) {
      case 'fhd':
        return { width: 1920, height: 1080 };
      case '4k':
        return { width: 3840, height: 2160 };
      default:
        return { width: 1280, height: 720 };
    }
  }, [cameraResolution]);

  const startCamera = useCallback(async () => {
    setCameraError(null);

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setCameraError('Camera API not available. Please use a modern browser with HTTPS.');
      return false;
    }

    try {
      const { width, height } = getResolutionConstraints();

      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: cameraFacingMode,
            width: { ideal: width },
            height: { ideal: height },
          },
          audio: false,
        });
      } catch {
        stream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: false,
        });
      }

      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setIsStreaming(true);
        return true;
      }
      return false;
    } catch (err) {
      if (err instanceof Error) {
        if (err.name === 'NotAllowedError') {
          setCameraError(t('camera.permissionDenied'));
        } else if (err.name === 'NotFoundError') {
          setCameraError(t('camera.notSupported'));
        } else if (err.name === 'NotReadableError') {
          setCameraError('Camera is in use by another application.');
        } else {
          setCameraError(`Camera error: ${err.message}`);
        }
      }
      return false;
    }
  }, [cameraFacingMode, getResolutionConstraints, t]);

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsStreaming(false);
  }, []);

  const captureAndSendFrame = useCallback(() => {
    if (!videoRef.current || !canvasRef.current || !isConnected) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;

    // Set canvas size to match video
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext('2d');
    if (ctx) {
      // Draw current video frame to canvas
      ctx.drawImage(video, 0, 0);

      // Convert to base64 and send to WebSocket
      canvas.toBlob(
        (blob) => {
          if (blob) {
            const reader = new FileReader();
            reader.onloadend = () => {
              const base64data = reader.result as string;
              // Remove data:image/jpeg;base64, prefix
              const base64Image = base64data.split(',')[1];
              sendFrame(base64Image);
            };
            reader.readAsDataURL(blob);
          }
        },
        'image/jpeg',
        0.85 // Quality
      );
    }
  }, [isConnected, sendFrame]);

  const startStreaming = useCallback(async () => {
    const cameraStarted = await startCamera();
    if (!cameraStarted) return;

    // Connect WebSocket
    connect();

    // Start sending frames at ~10 FPS
    const frameInterval = 100; // 100ms = 10 FPS
    frameIntervalRef.current = setInterval(() => {
      captureAndSendFrame();
    }, frameInterval);
  }, [startCamera, connect, captureAndSendFrame]);

  const stopStreaming = useCallback(() => {
    if (frameIntervalRef.current) {
      clearInterval(frameIntervalRef.current);
      frameIntervalRef.current = null;
    }

    disconnect();
    stopCamera();
  }, [disconnect, stopCamera]);

  // Cleanup on unmount only
  useEffect(() => {
    return () => {
      if (frameIntervalRef.current) {
        clearInterval(frameIntervalRef.current);
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  const isProcessing = isConnected && isStreaming;
  const connectionStatus = status === 'connected' ? 'Connected' : status === 'connecting' ? 'Connecting...' : status === 'reconnecting' ? 'Reconnecting...' : 'Disconnected';

  return (
    <div className="space-y-4">
      {/* Video Preview */}
      <div className="relative overflow-hidden rounded-lg bg-black">
        <video
          ref={videoRef}
          className={cn(
            'h-96 w-full object-cover',
            !isStreaming && 'hidden'
          )}
          autoPlay
          playsInline
          muted
        />

        {!isStreaming && (
          <div className="flex h-96 flex-col items-center justify-center gap-4 bg-muted">
            {cameraError ? (
              <>
                <VideoOff className="h-12 w-12 text-muted-foreground" />
                <p className="text-sm text-red-500">{cameraError}</p>
              </>
            ) : (
              <>
                <Video className="h-12 w-12 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">Click Start to begin live analysis</p>
              </>
            )}
          </div>
        )}

        {/* Status Overlay */}
        {isStreaming && (
          <div className="absolute right-3 top-3 flex flex-col gap-2">
            <Badge variant={isConnected ? 'default' : 'secondary'} className="gap-1">
              <Activity className="h-3 w-3" />
              {connectionStatus}
            </Badge>
            {sessionStats && (
              <Badge variant="outline" className="gap-1 bg-black/50">
                <Zap className="h-3 w-3" />
                {fps} FPS
              </Badge>
            )}
          </div>
        )}
      </div>

      <canvas ref={canvasRef} className="hidden" />

      {/* Controls */}
      <div className="flex gap-2">
        {!isProcessing ? (
          <Button
            onClick={startStreaming}
            disabled={disabled}
            className="flex-1"
          >
            <Play className="mr-2 h-4 w-4" />
            Start Live Analysis
          </Button>
        ) : (
          <Button
            onClick={stopStreaming}
            disabled={disabled}
            variant="destructive"
            className="flex-1"
          >
            <StopCircle className="mr-2 h-4 w-4" />
            Stop Streaming
          </Button>
        )}
      </div>

      {/* Error Display */}
      {wsError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950/50 dark:text-red-200">
          {wsError}
        </div>
      )}

      {/* Stats */}
      {sessionStats && (
        <div className="grid grid-cols-3 gap-2 rounded-lg border bg-card p-3 text-sm">
          <div>
            <p className="text-muted-foreground">Processed</p>
            <p className="font-semibold">{sessionStats.processed_frames}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Skipped</p>
            <p className="font-semibold">{sessionStats.skipped_frames}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Avg Time</p>
            <p className="font-semibold">{sessionStats.average_processing_time_ms.toFixed(0)}ms</p>
          </div>
        </div>
      )}
    </div>
  );
}
