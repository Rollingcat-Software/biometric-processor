'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import { MonitorPlay, Wifi, WifiOff, Activity, Eye } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useWebSocket } from '@/hooks/use-websocket';
import { toast } from 'sonner';
import { formatPercent } from '@/lib/utils/format';

interface FrameResult {
  timestamp: string;
  face_detected: boolean;
  face_verified: boolean;
  risk_score: number;
  processing_time_ms: number;
}

export default function RealtimePage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [sessionId, setSessionId] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [frameResults, setFrameResults] = useState<FrameResult[]>([]);
  const [fps, setFps] = useState(0);
  const frameCountRef = useRef(0);
  const [wsUrl, setWsUrl] = useState<string>('');

  const {
    status,
    connect,
    disconnect,
    send,
    lastMessage,
  } = useWebSocket({
    url: wsUrl,
    reconnect: true,
  });

  const isConnected = status === 'connected';

  const sendBinaryFrame = useCallback((buffer: ArrayBuffer) => {
    send(buffer);
  }, [send]);

  // Handle incoming WebSocket messages
  useEffect(() => {
    if (lastMessage) {
      if (lastMessage.type === 'result') {
        setFrameResults((prev) => [lastMessage.data, ...prev].slice(0, 100));
      } else if (lastMessage.type === 'incident') {
        toast.warning('Incident Detected', {
          description: lastMessage.data.message,
        });
      }
    }
  }, [lastMessage]);

  // FPS counter
  useEffect(() => {
    const interval = setInterval(() => {
      setFps(frameCountRef.current);
      frameCountRef.current = 0;
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  // Start camera
  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setIsStreaming(true);
      }
    } catch {
      toast.error('Camera Error', {
        description: 'Failed to access camera',
      });
    }
  }, []);

  // Stop camera
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

  // Capture and send frame
  const captureAndSendFrame = useCallback(() => {
    if (!videoRef.current || !canvasRef.current || !isConnected) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.drawImage(video, 0, 0);
      canvas.toBlob(
        (blob) => {
          if (blob) {
            blob.arrayBuffer().then((buffer) => {
              sendBinaryFrame(buffer);
              frameCountRef.current++;
            });
          }
        },
        'image/jpeg',
        0.7
      );
    }
  }, [isConnected, sendBinaryFrame]);

  // Frame capture loop
  useEffect(() => {
    let animationId: number;
    let lastTime = 0;
    const targetFps = 10; // 10 FPS for real-time streaming
    const frameInterval = 1000 / targetFps;

    const loop = (currentTime: number) => {
      if (currentTime - lastTime >= frameInterval) {
        captureAndSendFrame();
        lastTime = currentTime;
      }
      animationId = requestAnimationFrame(loop);
    };

    if (isConnected && isStreaming) {
      animationId = requestAnimationFrame(loop);
    }

    return () => {
      if (animationId) cancelAnimationFrame(animationId);
    };
  }, [isConnected, isStreaming, captureAndSendFrame]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopCamera();
      disconnect();
    };
  }, [stopCamera, disconnect]);

  const handleConnect = async () => {
    if (!sessionId.trim()) {
      toast.error('Error', { description: 'Please enter a session ID' });
      return;
    }
    await startCamera();
    const baseUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';
    setWsUrl(`${baseUrl}/api/v1/proctoring/sessions/${sessionId}/stream`);
    connect();
  };

  const handleDisconnect = () => {
    disconnect();
    stopCamera();
    setFrameResults([]);
  };

  const latestResult = frameResults[0];
  const avgProcessingTime =
    frameResults.length > 0
      ? frameResults.reduce((sum, r) => sum + r.processing_time_ms, 0) / frameResults.length
      : 0;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/10">
              <MonitorPlay className="h-5 w-5 text-emerald-500" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Real-time Streaming</h1>
              <p className="text-muted-foreground">WebSocket-based real-time face analysis</p>
            </div>
          </div>
          <Badge variant={isConnected ? 'default' : 'secondary'}>
            {isConnected ? (
              <>
                <Wifi className="mr-1 h-3 w-3" /> Connected
              </>
            ) : (
              <>
                <WifiOff className="mr-1 h-3 w-3" /> Disconnected
              </>
            )}
          </Badge>
        </div>
      </motion.div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Video Feed */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
          className="lg:col-span-2"
        >
          <Card>
            <CardHeader>
              <CardTitle>Live Stream</CardTitle>
              <CardDescription>
                {isStreaming ? `Streaming at ${fps} FPS` : 'Camera not active'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Video Container */}
              <div className="relative aspect-video rounded-lg bg-black overflow-hidden">
                <video
                  ref={videoRef}
                  className="w-full h-full object-cover"
                  autoPlay
                  playsInline
                  muted
                />
                <canvas ref={canvasRef} className="hidden" />

                {!isStreaming && (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="text-center text-white">
                      <MonitorPlay className="h-12 w-12 mx-auto mb-2 opacity-50" />
                      <p>Stream not active</p>
                    </div>
                  </div>
                )}

                {/* Live indicator */}
                {isConnected && isStreaming && (
                  <div className="absolute top-2 left-2 flex items-center gap-2">
                    <span className="flex h-3 w-3">
                      <span className="animate-ping absolute h-3 w-3 rounded-full bg-red-400 opacity-75" />
                      <span className="relative rounded-full h-3 w-3 bg-red-500" />
                    </span>
                    <span className="text-white text-sm font-medium">STREAMING</span>
                  </div>
                )}

                {/* Stats overlay */}
                {isConnected && latestResult && (
                  <div className="absolute bottom-2 left-2 right-2 flex justify-between text-white text-xs bg-black/50 rounded p-2">
                    <span>Face: {latestResult.face_detected ? 'Yes' : 'No'}</span>
                    <span>Verified: {latestResult.face_verified ? 'Yes' : 'No'}</span>
                    <span>Risk: {formatPercent(latestResult.risk_score, 0)}</span>
                    <span>{latestResult.processing_time_ms}ms</span>
                  </div>
                )}
              </div>

              {/* Connection Controls */}
              {!isConnected ? (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="sessionId">Session ID</Label>
                    <Input
                      id="sessionId"
                      value={sessionId}
                      onChange={(e) => setSessionId(e.target.value)}
                      placeholder="Enter existing session ID"
                    />
                  </div>
                  <Button onClick={handleConnect} className="w-full">
                    <Wifi className="mr-2 h-4 w-4" />
                    Connect & Start Streaming
                  </Button>
                </div>
              ) : (
                <Button variant="destructive" onClick={handleDisconnect} className="w-full">
                  <WifiOff className="mr-2 h-4 w-4" />
                  Disconnect
                </Button>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Stats & Results */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.2 }}
          className="space-y-6"
        >
          {/* Connection Stats */}
          <Card>
            <CardHeader>
              <CardTitle>Stream Statistics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-lg border p-3 text-center">
                  <Activity className="h-5 w-5 mx-auto mb-1 text-muted-foreground" />
                  <p className="text-2xl font-bold">{fps}</p>
                  <p className="text-xs text-muted-foreground">FPS</p>
                </div>
                <div className="rounded-lg border p-3 text-center">
                  <Eye className="h-5 w-5 mx-auto mb-1 text-muted-foreground" />
                  <p className="text-2xl font-bold">{frameResults.length}</p>
                  <p className="text-xs text-muted-foreground">Frames</p>
                </div>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-sm text-muted-foreground">Avg Processing Time</p>
                <p className="text-xl font-semibold">{avgProcessingTime.toFixed(1)}ms</p>
              </div>
            </CardContent>
          </Card>

          {/* Recent Results */}
          <Card>
            <CardHeader>
              <CardTitle>Recent Results</CardTitle>
              <CardDescription>Last 100 frame results</CardDescription>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-64">
                {frameResults.length > 0 ? (
                  <div className="space-y-1">
                    {frameResults.slice(0, 20).map((result, index) => (
                      <div
                        key={index}
                        className={`text-xs p-2 rounded ${
                          result.face_verified
                            ? 'bg-green-500/10'
                            : result.face_detected
                            ? 'bg-yellow-500/10'
                            : 'bg-red-500/10'
                        }`}
                      >
                        <div className="flex justify-between">
                          <span>
                            {result.face_detected ? (result.face_verified ? '✓ Verified' : '? Not Verified') : '✗ No Face'}
                          </span>
                          <span className="font-mono">{result.processing_time_ms}ms</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex h-full items-center justify-center text-muted-foreground">
                    <p className="text-sm">No results yet</p>
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
