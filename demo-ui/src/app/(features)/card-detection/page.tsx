'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { CreditCard, Play, Square, CheckCircle2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { useCardDetection } from '@/hooks/use-card-detection';
import { toast } from 'sonner';
import { formatPercent, toPercent } from '@/lib/utils/format';

const cardTypes: Record<string, { label: string; color: string }> = {
  tc_kimlik: { label: 'TR National ID', color: 'bg-blue-500' },
  ehliyet: { label: "Driver's License", color: 'bg-green-500' },
  pasaport: { label: 'Passport', color: 'bg-purple-500' },
  ogrenci_karti: { label: 'Student ID', color: 'bg-orange-500' },
  unknown: { label: 'Unknown', color: 'bg-gray-500' },
};

export default function CardDetectionPage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [isStreaming, setIsStreaming] = useState(false);
  const [isDetecting, setIsDetecting] = useState(false);
  const [detectionResults, setDetectionResults] = useState<any[]>([]);
  const [lastDetected, setLastDetected] = useState<any>(null);

  const { mutate: detectCard } = useCardDetection();

  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 1280, height: 720, facingMode: 'environment' },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setIsStreaming(true);
      }
    } catch (err) {
      toast.error('Camera Error', { description: 'Failed to access camera' });
    }
  }, []);

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsStreaming(false);
    setIsDetecting(false);
  }, []);

  const captureAndDetect = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) return;

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
            detectCard(
              { image: blob },
              {
                onSuccess: (result) => {
                  setDetectionResults((prev) => [result, ...prev].slice(0, 20));
                  if (result.card_type !== 'unknown' && result.confidence > 0.7) {
                    setLastDetected(result);
                    toast.success('Card Detected', {
                      description: `${cardTypes[result.card_type]?.label || result.card_type} (${formatPercent(result.confidence, 0)})`,
                    });
                  }
                },
              }
            );
          }
        },
        'image/jpeg',
        0.8
      );
    }
  }, [detectCard]);

  // Detection loop
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isDetecting && isStreaming) {
      interval = setInterval(captureAndDetect, 1000); // Every 1 second
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isDetecting, isStreaming, captureAndDetect]);

  // Cleanup
  useEffect(() => {
    return () => stopCamera();
  }, [stopCamera]);

  const handleStartDetection = async () => {
    if (!isStreaming) {
      await startCamera();
    }
    setIsDetecting(true);
  };

  const handleStopDetection = () => {
    setIsDetecting(false);
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
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-sky-500/10">
            <CreditCard className="h-5 w-5 text-sky-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Card Type Detection</h1>
            <p className="text-muted-foreground">Real-time ID card detection</p>
          </div>
        </div>
      </motion.div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Camera Feed */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
          className="lg:col-span-2"
        >
          <Card>
            <CardHeader>
              <CardTitle>Camera Feed</CardTitle>
              <CardDescription>
                Point camera at an ID card
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
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
                  <div className="absolute inset-0 flex items-center justify-center text-white">
                    <div className="text-center">
                      <CreditCard className="h-12 w-12 mx-auto mb-2 opacity-50" />
                      <p>Camera not active</p>
                    </div>
                  </div>
                )}

                {isDetecting && (
                  <div className="absolute top-2 left-2 flex items-center gap-2">
                    <span className="flex h-3 w-3">
                      <span className="animate-ping absolute h-3 w-3 rounded-full bg-green-400 opacity-75" />
                      <span className="relative rounded-full h-3 w-3 bg-green-500" />
                    </span>
                    <span className="text-white text-sm">Detecting...</span>
                  </div>
                )}

                {/* Card overlay guide */}
                {isStreaming && (
                  <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                    <div className="w-80 h-52 border-2 border-dashed border-white/50 rounded-lg" />
                  </div>
                )}
              </div>

              <div className="flex gap-2">
                {!isDetecting ? (
                  <Button onClick={handleStartDetection} className="flex-1">
                    <Play className="mr-2 h-4 w-4" />
                    Start Detection
                  </Button>
                ) : (
                  <Button variant="destructive" onClick={handleStopDetection} className="flex-1">
                    <Square className="mr-2 h-4 w-4" />
                    Stop Detection
                  </Button>
                )}
                {isStreaming && !isDetecting && (
                  <Button variant="outline" onClick={stopCamera}>
                    Stop Camera
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Detection Results */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.2 }}
        >
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Detection Results</CardTitle>
              <CardDescription>
                Detected card type and confidence
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Last Detected */}
              {lastDetected && (
                <div className="rounded-lg border p-4 space-y-3">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                    <span className="font-medium">Last Detected</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge className={cardTypes[lastDetected.card_type]?.color}>
                      {cardTypes[lastDetected.card_type]?.label || lastDetected.card_type}
                    </Badge>
                  </div>
                  <div className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span>Confidence</span>
                      <span className="font-mono">
                        {formatPercent(lastDetected.confidence)}
                      </span>
                    </div>
                    <Progress value={toPercent(lastDetected.confidence)} />
                  </div>
                </div>
              )}

              {/* Supported Card Types */}
              <div className="space-y-2">
                <p className="text-sm font-medium">Supported Cards</p>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(cardTypes).map(([key, value]) => (
                    key !== 'unknown' && (
                      <Badge key={key} variant="outline">
                        {value.label}
                      </Badge>
                    )
                  ))}
                </div>
              </div>

              {/* Recent Detections */}
              {detectionResults.length > 0 && (
                <div className="space-y-2">
                  <p className="text-sm font-medium">Recent Scans</p>
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {detectionResults.slice(0, 10).map((result, i) => (
                      <div
                        key={i}
                        className={`text-xs p-2 rounded ${
                          result.card_type !== 'unknown'
                            ? 'bg-green-50 dark:bg-green-950/20'
                            : 'bg-muted'
                        }`}
                      >
                        <span className="font-medium">
                          {cardTypes[result.card_type]?.label || result.card_type}
                        </span>
                        <span className="ml-2 text-muted-foreground">
                          {formatPercent(result.confidence, 0)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {!lastDetected && detectionResults.length === 0 && (
                <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                  <CreditCard className="h-10 w-10 mb-2" />
                  <p className="text-sm">No cards detected yet</p>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
