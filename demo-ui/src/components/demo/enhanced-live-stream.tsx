'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Video, Square, Settings2, Eye, EyeOff, Activity } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Card, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { useLiveCameraAnalysis, type AnalysisMode, type LiveAnalysisResult } from '@/hooks/use-live-camera-analysis';
import { useAppStore } from '@/lib/store/app-store';
import { toast } from 'sonner';

interface EnhancedLiveStreamProps {
  mode: AnalysisMode;
  onResult?: (result: LiveAnalysisResult) => void;
  userId?: string;
  tenantId?: string;
}

interface VisualizationSettings {
  showBoundingBox: boolean;
  showLandmarks: boolean;
  showLabels: boolean;
  showQualityMetrics: boolean;
  showConfidence: boolean;
  showStats: boolean;
}

interface StreamStats {
  totalFrames: number;
  analyzedFrames: number;
  successfulFrames: number;
  errorFrames: number;
  avgProcessingTime: number;
  currentFPS: number;
  startTime: number;
}

export function EnhancedLiveStream({ mode, onResult, userId, tenantId }: EnhancedLiveStreamProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const animationFrameRef = useRef<number>();
  const fpsIntervalRef = useRef<NodeJS.Timeout>();

  const [isStreaming, setIsStreaming] = useState(false);
  const [currentResult, setCurrentResult] = useState<LiveAnalysisResult | null>(null);
  const [showSettings, setShowSettings] = useState(false);

  // Visualization settings
  const [vizSettings, setVizSettings] = useState<VisualizationSettings>({
    showBoundingBox: true,
    showLandmarks: mode === 'landmarks',
    showLabels: true,
    showQualityMetrics: mode === 'quality' || mode === 'enrollment_ready',
    showConfidence: true,
    showStats: true,
  });

  // Stream statistics
  const [stats, setStats] = useState<StreamStats>({
    totalFrames: 0,
    analyzedFrames: 0,
    successfulFrames: 0,
    errorFrames: 0,
    avgProcessingTime: 0,
    currentFPS: 0,
    startTime: 0,
  });

  const { cameraFacingMode, cameraResolution } = useAppStore();

  const {
    connect,
    disconnect,
    isConnected,
    sendFrame,
    currentResult: liveResult,
    error,
  } = useLiveCameraAnalysis();

  // Update settings when mode changes
  useEffect(() => {
    setVizSettings((prev) => ({
      ...prev,
      showLandmarks: mode === 'landmarks',
      showQualityMetrics: mode === 'quality' || mode === 'enrollment_ready',
    }));
  }, [mode]);

  // Handle result updates
  useEffect(() => {
    if (liveResult) {
      setCurrentResult(liveResult);
      onResult?.(liveResult);

      // Update stats
      setStats((prev) => {
        const newAnalyzed = prev.analyzedFrames + 1;
        const newSuccessful = liveResult.error ? prev.successfulFrames : prev.successfulFrames + 1;
        const newErrors = liveResult.error ? prev.errorFrames + 1 : prev.errorFrames;
        const newAvgTime =
          (prev.avgProcessingTime * prev.analyzedFrames + liveResult.processing_time_ms) / newAnalyzed;

        return {
          ...prev,
          analyzedFrames: newAnalyzed,
          successfulFrames: newSuccessful,
          errorFrames: newErrors,
          avgProcessingTime: newAvgTime,
        };
      });
    }
  }, [liveResult, onResult]);

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

        // Set canvas size to match video
        if (canvasRef.current && videoRef.current) {
          canvasRef.current.width = videoRef.current.videoWidth;
          canvasRef.current.height = videoRef.current.videoHeight;
        }
      }

      return true;
    } catch (err) {
      console.error('Camera error:', err);
      toast.error('Failed to access camera');
      return false;
    }
  }, [cameraFacingMode, cameraResolution]);

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }
    if (fpsIntervalRef.current) {
      clearInterval(fpsIntervalRef.current);
    }
  }, []);

  const captureAndSendFrame = useCallback(() => {
    if (!videoRef.current || !canvasRef.current || !isConnected) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');

    if (!ctx) return;

    // Update canvas size if video dimensions changed
    if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
    }

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw video frame
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Draw overlays
    if (currentResult) {
      drawOverlays(ctx, canvas.width, canvas.height, currentResult);
    }

    // Convert to base64 and send
    canvas.toBlob(
      (blob) => {
        if (blob) {
          const reader = new FileReader();
          reader.onloadend = () => {
            const base64data = reader.result as string;
            const base64Image = base64data.split(',')[1];
            sendFrame(base64Image);

            // Update frame count
            setStats((prev) => ({ ...prev, totalFrames: prev.totalFrames + 1 }));
          };
          reader.readAsDataURL(blob);
        }
      },
      'image/jpeg',
      0.85
    );

    // Schedule next frame
    animationFrameRef.current = requestAnimationFrame(captureAndSendFrame);
  }, [isConnected, currentResult, sendFrame]);

  const drawOverlays = (
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number,
    result: LiveAnalysisResult
  ) => {
    // Draw bounding box
    if (vizSettings.showBoundingBox && result.face?.bbox) {
      const bbox = result.face.bbox;
      ctx.strokeStyle = result.face.detected ? '#22c55e' : '#ef4444';
      ctx.lineWidth = 3;
      ctx.strokeRect(bbox.x, bbox.y, bbox.width, bbox.height);

      // Draw confidence
      if (vizSettings.showConfidence && result.face.confidence) {
        ctx.fillStyle = '#22c55e';
        ctx.fillRect(bbox.x, bbox.y - 25, 120, 25);
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 14px sans-serif';
        ctx.fillText(`${(result.face.confidence * 100).toFixed(0)}%`, bbox.x + 5, bbox.y - 7);
      }
    }

    // Draw landmarks
    if (vizSettings.showLandmarks && result.landmarks?.landmarks) {
      ctx.fillStyle = '#22c55e';
      Object.values(result.landmarks.landmarks).forEach((point: any) => {
        if (Array.isArray(point) && point.length >= 2) {
          ctx.beginPath();
          ctx.arc(point[0], point[1], 2, 0, Math.PI * 2);
          ctx.fill();
        }
      });
    }

    // Draw labels (demographics, verification, search results)
    if (vizSettings.showLabels) {
      let labelY = 30;

      // Demographics
      if (result.demographics) {
        const labels: string[] = [];
        if (result.demographics.age) labels.push(`Age: ${result.demographics.age}`);
        if (result.demographics.gender) labels.push(`Gender: ${result.demographics.gender}`);
        if (result.demographics.emotion) labels.push(`Emotion: ${result.demographics.emotion}`);

        labels.forEach((label) => {
          drawLabel(ctx, label, 10, labelY, '#3b82f6');
          labelY += 30;
        });
      }

      // Verification
      if (result.verification) {
        const label = result.verification.match
          ? `✓ Verified: ${result.verification.user_id}`
          : `✗ No Match`;
        drawLabel(ctx, label, 10, labelY, result.verification.match ? '#22c55e' : '#ef4444');
        labelY += 30;
      }

      // Search
      if (result.search?.found) {
        drawLabel(ctx, `Found: ${result.search.user_id}`, 10, labelY, '#22c55e');
        labelY += 30;
      }

      // Liveness
      if (result.liveness) {
        const label = result.liveness.is_live ? '✓ Live Person' : '✗ Spoof';
        drawLabel(ctx, label, 10, labelY, result.liveness.is_live ? '#22c55e' : '#ef4444');
        labelY += 30;
      }
    }

    // Draw quality metrics
    if (vizSettings.showQualityMetrics && result.quality) {
      const quality = result.quality;
      const metricsX = width - 200;
      let metricsY = 30;

      // Overall quality
      drawMetricBar(ctx, 'Quality', quality.score, metricsX, metricsY, width - 20);
      metricsY += 35;

      // Individual metrics
      if (quality.metrics) {
        Object.entries(quality.metrics).forEach(([key, value]) => {
          drawMetricBar(
            ctx,
            key.replace(/_/g, ' '),
            value as number,
            metricsX,
            metricsY,
            width - 20
          );
          metricsY += 35;
        });
      }
    }

    // Draw frame info
    if (vizSettings.showStats) {
      const infoY = height - 10;
      ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
      ctx.fillRect(0, height - 50, 350, 50);

      ctx.fillStyle = '#ffffff';
      ctx.font = '12px monospace';
      ctx.fillText(`Frame: ${result.frame_number}`, 10, infoY - 25);
      ctx.fillText(`Processing: ${result.processing_time_ms.toFixed(0)}ms`, 10, infoY - 10);
      ctx.fillText(`FPS: ${stats.currentFPS.toFixed(1)}`, 150, infoY - 25);
      ctx.fillText(`Success: ${stats.successfulFrames}/${stats.analyzedFrames}`, 150, infoY - 10);
    }
  };

  const drawLabel = (ctx: CanvasRenderingContext2D, text: string, x: number, y: number, color: string) => {
    ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
    const metrics = ctx.measureText(text);
    ctx.fillRect(x, y - 20, metrics.width + 20, 25);

    ctx.fillStyle = color;
    ctx.font = 'bold 14px sans-serif';
    ctx.fillText(text, x + 10, y - 3);
  };

  const drawMetricBar = (
    ctx: CanvasRenderingContext2D,
    label: string,
    value: number,
    x: number,
    y: number,
    maxX: number
  ) => {
    const barWidth = maxX - x - 20;
    const barHeight = 20;

    // Background
    ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
    ctx.fillRect(x, y - 25, barWidth + 20, 30);

    // Label
    ctx.fillStyle = '#ffffff';
    ctx.font = '11px sans-serif';
    ctx.fillText(label, x + 5, y - 10);

    // Bar background
    ctx.fillStyle = 'rgba(255, 255, 255, 0.2)';
    ctx.fillRect(x + 5, y, barWidth, barHeight);

    // Bar fill
    const fillWidth = (value * barWidth);
    const color = value >= 0.75 ? '#22c55e' : value >= 0.5 ? '#eab308' : '#ef4444';
    ctx.fillStyle = color;
    ctx.fillRect(x + 5, y, fillWidth, barHeight);

    // Value text
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 11px sans-serif';
    ctx.fillText(`${(value * 100).toFixed(0)}%`, x + barWidth - 30, y + 14);
  };

  const handleStart = async () => {
    const cameraStarted = await startCamera();
    if (!cameraStarted) return;

    // Connect to WebSocket
    connect();

    // Configure analysis
    // Note: Configuration is handled by the hook based on mode prop

    setIsStreaming(true);
    setStats({
      totalFrames: 0,
      analyzedFrames: 0,
      successfulFrames: 0,
      errorFrames: 0,
      avgProcessingTime: 0,
      currentFPS: 0,
      startTime: Date.now(),
    });

    // Start frame capture loop
    animationFrameRef.current = requestAnimationFrame(captureAndSendFrame);

    // FPS calculator
    let lastFrameCount = 0;
    fpsIntervalRef.current = setInterval(() => {
      setStats((prev) => {
        const frameDiff = prev.totalFrames - lastFrameCount;
        lastFrameCount = prev.totalFrames;
        return { ...prev, currentFPS: frameDiff };
      });
    }, 1000);
  };

  const handleStop = () => {
    setIsStreaming(false);
    disconnect();
    stopCamera();
    setCurrentResult(null);
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      handleStop();
    };
  }, []);

  const toggleSetting = (key: keyof VisualizationSettings) => {
    setVizSettings((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="space-y-4">
      {/* Video with Canvas Overlay */}
      <div className="relative overflow-hidden rounded-lg bg-black">
        <video
          ref={videoRef}
          className="h-auto w-full"
          autoPlay
          playsInline
          muted
          style={{ display: isStreaming ? 'block' : 'none' }}
        />
        <canvas
          ref={canvasRef}
          className="absolute inset-0 h-full w-full"
          style={{ display: isStreaming ? 'block' : 'none' }}
        />
        {!isStreaming && (
          <div className="flex h-64 items-center justify-center bg-muted">
            <Video className="h-16 w-16 text-muted-foreground" />
          </div>
        )}

        {/* Live Badge */}
        {isStreaming && (
          <div className="absolute left-3 top-3">
            <Badge variant="destructive" className="gap-1.5">
              <Activity className="h-3 w-3 animate-pulse" />
              LIVE
            </Badge>
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="flex gap-2">
        {!isStreaming ? (
          <Button onClick={handleStart} className="flex-1">
            <Video className="mr-2 h-4 w-4" />
            Start Stream
          </Button>
        ) : (
          <Button onClick={handleStop} variant="destructive" className="flex-1">
            <Square className="mr-2 h-4 w-4" />
            Stop
          </Button>
        )}
        <Button variant="outline" size="icon" onClick={() => setShowSettings(!showSettings)}>
          <Settings2 className="h-4 w-4" />
        </Button>
      </div>

      {/* Visualization Settings */}
      {showSettings && (
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
          <Card>
            <CardContent className="pt-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <Label htmlFor="bbox" className="text-sm">
                    Bounding Box
                  </Label>
                  <Switch
                    id="bbox"
                    checked={vizSettings.showBoundingBox}
                    onCheckedChange={() => toggleSetting('showBoundingBox')}
                  />
                </div>
                <Separator />
                <div className="flex items-center justify-between">
                  <Label htmlFor="landmarks" className="text-sm">
                    Facial Landmarks
                  </Label>
                  <Switch
                    id="landmarks"
                    checked={vizSettings.showLandmarks}
                    onCheckedChange={() => toggleSetting('showLandmarks')}
                  />
                </div>
                <Separator />
                <div className="flex items-center justify-between">
                  <Label htmlFor="labels" className="text-sm">
                    Info Labels
                  </Label>
                  <Switch
                    id="labels"
                    checked={vizSettings.showLabels}
                    onCheckedChange={() => toggleSetting('showLabels')}
                  />
                </div>
                <Separator />
                <div className="flex items-center justify-between">
                  <Label htmlFor="quality" className="text-sm">
                    Quality Metrics
                  </Label>
                  <Switch
                    id="quality"
                    checked={vizSettings.showQualityMetrics}
                    onCheckedChange={() => toggleSetting('showQualityMetrics')}
                  />
                </div>
                <Separator />
                <div className="flex items-center justify-between">
                  <Label htmlFor="confidence" className="text-sm">
                    Confidence Score
                  </Label>
                  <Switch
                    id="confidence"
                    checked={vizSettings.showConfidence}
                    onCheckedChange={() => toggleSetting('showConfidence')}
                  />
                </div>
                <Separator />
                <div className="flex items-center justify-between">
                  <Label htmlFor="stats" className="text-sm">
                    Frame Statistics
                  </Label>
                  <Switch
                    id="stats"
                    checked={vizSettings.showStats}
                    onCheckedChange={() => toggleSetting('showStats')}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Statistics Dashboard */}
      {isStreaming && vizSettings.showStats && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <Card>
            <CardContent className="pt-6">
              <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Total Frames</p>
                  <p className="text-2xl font-bold">{stats.totalFrames}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Analyzed</p>
                  <p className="text-2xl font-bold text-blue-600">{stats.analyzedFrames}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Success Rate</p>
                  <p className="text-2xl font-bold text-green-600">
                    {stats.analyzedFrames > 0
                      ? ((stats.successfulFrames / stats.analyzedFrames) * 100).toFixed(0)
                      : 0}
                    %
                  </p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Avg Time</p>
                  <p className="text-2xl font-bold">{stats.avgProcessingTime.toFixed(0)}ms</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Error Display */}
      {error && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950/50 dark:text-red-200">
          Error: {error}
        </div>
      )}
    </div>
  );
}
