'use client';

import { useCallback, useRef, useState, useEffect } from 'react';
import { Video, VideoOff, Play, StopCircle, Settings, Activity, Zap } from 'lucide-react';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Label } from '@/components/ui/label';

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

  const [isStreaming, setIsStreaming] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [frameSkip, setFrameSkip] = useState(0);
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

  // Update config when props change (FIX: removed updateConfig from deps to prevent loop)
  useEffect(() => {
    updateConfig({
      mode,
      user_id: userId,
      tenant_id: tenantId,
      frame_skip: frameSkip,
      quality_threshold: qualityThreshold,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, userId, tenantId, frameSkip, qualityThreshold]);

  // Call onResult when we get a new result
  useEffect(() => {
    if (currentResult && onResult) {
      onResult(currentResult);
    }
  }, [currentResult, onResult]);

  // Update FPS display
  useEffect(() => {
    if (sessionStats) {
      setFps(Math.round(sessionStats.average_fps));
    }
  }, [sessionStats]);

  const getResolutionConstraints = () => {
    switch (cameraResolution) {
      case 'fhd':
        return { width: 1920, height: 1080 };
      case '4k':
        return { width: 3840, height: 2160 };
      default:
        return { width: 1280, height: 720 };
    }
  };

  const startCamera = useCallback(async () => {
    setCameraError(null);

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setCameraError('Camera API not available. Please use a modern browser with HTTPS.');
      return;
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
      }
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
    }
  }, [cameraFacingMode, cameraResolution, t]);

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

    // Set canvas size only if changed (avoid layout reflow)
    if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
    }

    const ctx = canvas.getContext('2d');
    if (ctx) {
      // Draw current video frame to canvas
      ctx.drawImage(video, 0, 0);

      // Use synchronous toDataURL instead of async toBlob (fixes race conditions)
      const base64data = canvas.toDataURL('image/jpeg', 0.85);
      const base64Image = base64data.split(',')[1];
      sendFrame(base64Image);
    }
  }, [isConnected, sendFrame]);

  const startStreaming = useCallback(async () => {
    if (!isStreaming) {
      await startCamera();
    }

    // Connect WebSocket (interval will start automatically when connected via useEffect)
    connect();
  }, [isStreaming, startCamera, connect]);

  const stopStreaming = useCallback(() => {
    if (frameIntervalRef.current) {
      clearInterval(frameIntervalRef.current);
      frameIntervalRef.current = null;
    }

    disconnect();
    stopCamera();
  }, [disconnect, stopCamera]);

  // Start/stop frame capture interval based on WebSocket connection status
  useEffect(() => {
    if (isConnected && isStreaming) {
      // Start sending frames at ~10 FPS (adjust based on performance)
      const frameInterval = 100; // 100ms = 10 FPS
      frameIntervalRef.current = setInterval(() => {
        captureAndSendFrame();
      }, frameInterval);

      return () => {
        if (frameIntervalRef.current) {
          clearInterval(frameIntervalRef.current);
          frameIntervalRef.current = null;
        }
      };
    }
  }, [isConnected, isStreaming, captureAndSendFrame]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopStreaming();
    };
  }, [stopStreaming]);

  const isProcessing = isConnected && isStreaming;
  const connectionStatus = status === 'connected' ? 'Connected' : status === 'connecting' ? 'Connecting...' : status === 'reconnecting' ? 'Reconnecting...' : 'Disconnected';

  // Draw bounding box on video if face detected
  useEffect(() => {
    if (!videoRef.current || !currentResult?.face) return;

    const video = videoRef.current;
    const overlay = document.getElementById('face-overlay');
    if (!overlay) return;

    const face = currentResult.face;
    const scaleX = video.offsetWidth / video.videoWidth;
    const scaleY = video.offsetHeight / video.videoHeight;

    // Position overlay
    overlay.style.left = `${face.x * scaleX}px`;
    overlay.style.top = `${face.y * scaleY}px`;
    overlay.style.width = `${face.width * scaleX}px`;
    overlay.style.height = `${face.height * scaleY}px`;
    overlay.style.display = 'block';
  }, [currentResult]);

  return (
    <div className="space-y-4">
      {/* Settings */}
      <div className="flex items-center justify-between rounded-lg border bg-card p-3">
        <div className="flex items-center gap-2">
          <Settings className="h-4 w-4 text-muted-foreground" />
          <Label className="text-sm">Frame Skip</Label>
        </div>
        <Select
          value={frameSkip.toString()}
          onValueChange={(v) => setFrameSkip(parseInt(v))}
          disabled={isProcessing}
        >
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="0">None (Slower)</SelectItem>
            <SelectItem value="1">Skip 1</SelectItem>
            <SelectItem value="2">Skip 2</SelectItem>
            <SelectItem value="3">Skip 3 (Faster)</SelectItem>
            <SelectItem value="5">Skip 5 (Fastest)</SelectItem>
          </SelectContent>
        </Select>
      </div>

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

        {/* Face Detection Overlay */}
        {isStreaming && (
          <div
            id="face-overlay"
            className="pointer-events-none absolute hidden border-2 border-green-500"
            style={{ display: 'none' }}
          />
        )}

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
