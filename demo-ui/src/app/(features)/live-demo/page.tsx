'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import { Video, Play, Square, Camera, Activity } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { useAppStore } from '@/lib/store/app-store';
import { API_CONFIG } from '@/config/api.config';
import { toast } from 'sonner';
import { formatPercent } from '@/lib/utils/format';

type AnalysisType =
  | 'quality'
  | 'demographics'
  | 'liveness'
  | 'verification'
  | 'search'
  | 'landmarks';

export default function LiveDemoPage() {
  const { t } = useTranslation();
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const [analysisType, setAnalysisType] = useState<AnalysisType>('quality');
  const [isRunning, setIsRunning] = useState(false);
  const [fps, setFps] = useState(2); // Frames per second to analyze
  const [result, setResult] = useState<any>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [frameCount, setFrameCount] = useState(0);
  const [userId, setUserId] = useState(''); // For verification/search

  const { cameraFacingMode, cameraResolution } = useAppStore();

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
      }
    } catch (err) {
      console.error('Camera error:', err);
      toast.error('Failed to access camera');
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
  }, []);

  const captureFrame = useCallback(async (): Promise<Blob | null> => {
    if (!videoRef.current || !canvasRef.current) return null;

    const video = videoRef.current;
    const canvas = canvasRef.current;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext('2d');
    if (!ctx) return null;

    ctx.drawImage(video, 0, 0);

    return new Promise((resolve) => {
      canvas.toBlob((blob) => {
        resolve(blob);
      }, 'image/jpeg', 0.85);
    });
  }, []);

  const analyzeFrame = useCallback(async () => {
    if (isAnalyzing) return; // Skip if still analyzing previous frame

    setIsAnalyzing(true);
    setFrameCount(prev => prev + 1);

    try {
      const frameBlob = await captureFrame();
      if (!frameBlob) {
        setIsAnalyzing(false);
        return;
      }

      const formData = new FormData();
      formData.append('file', frameBlob, 'frame.jpg');

      let endpoint = '';
      let additionalParams: Record<string, string> = {};

      switch (analysisType) {
        case 'quality':
          endpoint = '/quality';
          break;
        case 'demographics':
          endpoint = '/demographics';
          break;
        case 'liveness':
          endpoint = '/liveness';
          break;
        case 'verification':
          if (!userId.trim()) {
            toast.error('User ID required for verification');
            setIsAnalyzing(false);
            return;
          }
          endpoint = '/verification';
          additionalParams.user_id = userId;
          break;
        case 'search':
          endpoint = '/search';
          if (userId.trim()) {
            additionalParams.tenant_id = userId;
          }
          break;
        case 'landmarks':
          endpoint = '/landmarks';
          break;
      }

      // Build URL with query params
      const url = new URL(API_CONFIG.buildUrl(endpoint));
      Object.entries(additionalParams).forEach(([key, value]) => {
        url.searchParams.append(key, value);
      });

      const response = await fetch(url.toString(), {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const data = await response.json();
      setResult(data);
    } catch (error) {
      console.error('Analysis error:', error);
      // Don't show toast for every frame error, just log it
    } finally {
      setIsAnalyzing(false);
    }
  }, [analysisType, userId, captureFrame, isAnalyzing]);

  const handleStart = useCallback(async () => {
    await startCamera();
    setIsRunning(true);
    setFrameCount(0);

    // Start analyzing frames
    const intervalMs = 1000 / fps;
    intervalRef.current = setInterval(() => {
      analyzeFrame();
    }, intervalMs);
  }, [startCamera, fps, analyzeFrame]);

  const handleStop = useCallback(() => {
    setIsRunning(false);
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    stopCamera();
    setResult(null);
    setFrameCount(0);
  }, [stopCamera]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      handleStop();
    };
  }, [handleStop]);

  const renderResult = () => {
    if (!result) return null;

    switch (analysisType) {
      case 'quality':
        return (
          <div className="space-y-4">
            <div className="text-center">
              <p className="text-3xl font-bold">{formatPercent(result.overall_score)}</p>
              <p className="text-sm text-muted-foreground">Overall Quality</p>
            </div>
            {result.metrics && Object.entries(result.metrics).map(([key, value]) => (
              <div key={key} className="space-y-1">
                <div className="flex justify-between text-sm">
                  <span className="capitalize">{key.replace(/_/g, ' ')}</span>
                  <span>{formatPercent(value as number, 0)}</span>
                </div>
                <Progress value={(value as number) * 100} className="h-2" />
              </div>
            ))}
          </div>
        );

      case 'demographics':
        return (
          <div className="space-y-4">
            {result.age && (
              <div>
                <p className="text-sm text-muted-foreground">Age</p>
                <p className="text-2xl font-bold">{result.age} years</p>
              </div>
            )}
            {result.gender && (
              <div>
                <p className="text-sm text-muted-foreground">Gender</p>
                <p className="text-2xl font-bold capitalize">{result.gender}</p>
              </div>
            )}
            {result.dominant_emotion && (
              <div>
                <p className="text-sm text-muted-foreground">Emotion</p>
                <p className="text-2xl font-bold capitalize">{result.dominant_emotion}</p>
              </div>
            )}
          </div>
        );

      case 'liveness':
        return (
          <div className="space-y-4">
            <div className={`rounded-lg p-4 ${result.is_live ? 'bg-green-500/10' : 'bg-red-500/10'}`}>
              <p className={`text-2xl font-bold ${result.is_live ? 'text-green-600' : 'text-red-600'}`}>
                {result.is_live ? '✓ Live Person' : '✗ Spoof Detected'}
              </p>
              <p className="text-sm mt-2">Confidence: {formatPercent(result.confidence)}</p>
            </div>
          </div>
        );

      case 'verification':
        return (
          <div className="space-y-4">
            <div className={`rounded-lg p-4 ${result.match ? 'bg-green-500/10' : 'bg-red-500/10'}`}>
              <p className={`text-2xl font-bold ${result.match ? 'text-green-600' : 'text-red-600'}`}>
                {result.match ? '✓ Identity Verified' : '✗ No Match'}
              </p>
              <p className="text-sm mt-2">Similarity: {formatPercent(result.confidence)}</p>
              <p className="text-sm">Threshold: {formatPercent(result.threshold)}</p>
            </div>
          </div>
        );

      case 'search':
        return (
          <div className="space-y-4">
            {result.found ? (
              <div className="rounded-lg bg-green-500/10 p-4">
                <p className="text-2xl font-bold text-green-600">✓ Match Found</p>
                <p className="text-sm mt-2">User ID: {result.best_match?.user_id}</p>
                <p className="text-sm">Confidence: {formatPercent(result.best_match?.confidence)}</p>
              </div>
            ) : (
              <div className="rounded-lg bg-orange-500/10 p-4">
                <p className="text-2xl font-bold text-orange-600">No Match</p>
                <p className="text-sm mt-2">Searched {result.total_searched} users</p>
              </div>
            )}
          </div>
        );

      case 'landmarks':
        return (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">Detected Landmarks</p>
            <p className="text-3xl font-bold">{result.landmarks ? Object.keys(result.landmarks).length : 0}</p>
            <div className="text-xs text-muted-foreground">
              {result.landmarks && Object.keys(result.landmarks).slice(0, 5).join(', ')}
              {result.landmarks && Object.keys(result.landmarks).length > 5 && '...'}
            </div>
          </div>
        );

      default:
        return <pre className="text-xs">{JSON.stringify(result, null, 2)}</pre>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-500/10">
            <Video className="h-5 w-5 text-purple-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Live Analysis Demo</h1>
            <p className="text-muted-foreground">Real-time frame-by-frame analysis from your camera</p>
          </div>
        </div>
      </motion.div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Camera Section */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
        >
          <Card>
            <CardHeader>
              <CardTitle>Camera Feed</CardTitle>
              <CardDescription>Live video from your camera</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Configuration */}
              <div className="grid gap-4">
                <div className="space-y-2">
                  <Label>Analysis Type</Label>
                  <Select
                    value={analysisType}
                    onValueChange={(v) => setAnalysisType(v as AnalysisType)}
                    disabled={isRunning}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="quality">Quality Analysis</SelectItem>
                      <SelectItem value="demographics">Demographics</SelectItem>
                      <SelectItem value="liveness">Liveness Detection</SelectItem>
                      <SelectItem value="verification">Face Verification (1:1)</SelectItem>
                      <SelectItem value="search">Face Search (1:N)</SelectItem>
                      <SelectItem value="landmarks">Facial Landmarks</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {(analysisType === 'verification' || analysisType === 'search') && (
                  <div className="space-y-2">
                    <Label>{analysisType === 'verification' ? 'User ID to Verify' : 'Tenant ID (optional)'}</Label>
                    <Input
                      value={userId}
                      onChange={(e) => setUserId(e.target.value)}
                      placeholder={analysisType === 'verification' ? 'Enter user ID...' : 'Enter tenant ID...'}
                      disabled={isRunning}
                    />
                  </div>
                )}

                <div className="space-y-2">
                  <Label>Analysis Speed (FPS)</Label>
                  <Select
                    value={fps.toString()}
                    onValueChange={(v) => setFps(parseInt(v))}
                    disabled={isRunning}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1">1 FPS (Slow)</SelectItem>
                      <SelectItem value="2">2 FPS (Normal)</SelectItem>
                      <SelectItem value="3">3 FPS (Fast)</SelectItem>
                      <SelectItem value="5">5 FPS (Very Fast)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Video */}
              <div className="relative overflow-hidden rounded-lg bg-black">
                <video
                  ref={videoRef}
                  className="h-96 w-full object-cover"
                  autoPlay
                  playsInline
                  muted
                />
                {isRunning && (
                  <div className="absolute right-3 top-3 flex flex-col gap-2">
                    <Badge variant="default" className="gap-1">
                      <Activity className="h-3 w-3" />
                      Analyzing
                    </Badge>
                    <Badge variant="outline" className="bg-black/50">
                      Frame {frameCount}
                    </Badge>
                  </div>
                )}
              </div>

              <canvas ref={canvasRef} className="hidden" />

              {/* Controls */}
              <div className="flex gap-2">
                {!isRunning ? (
                  <Button onClick={handleStart} className="flex-1">
                    <Play className="mr-2 h-4 w-4" />
                    Start Analysis
                  </Button>
                ) : (
                  <Button onClick={handleStop} variant="destructive" className="flex-1">
                    <Square className="mr-2 h-4 w-4" />
                    Stop
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Results Section */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.2 }}
        >
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Analysis Results</CardTitle>
              <CardDescription>
                Real-time results from frame analysis
              </CardDescription>
            </CardHeader>
            <CardContent>
              {result ? (
                <motion.div
                  key={frameCount}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.2 }}
                >
                  {renderResult()}
                </motion.div>
              ) : (
                <div className="flex h-64 items-center justify-center text-muted-foreground">
                  <p className="text-center">
                    {isRunning ? 'Waiting for analysis results...' : 'Click "Start Analysis" to begin'}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
