'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import {
  Video,
  Play,
  Pause,
  Square,
  AlertTriangle,
  User,
  Clock,
  Activity,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useProctoringSession } from '@/hooks/use-proctoring-session';
import { toast } from 'sonner';
import { formatPercent } from '@/lib/utils/format';

interface Incident {
  id: string;
  type: string;
  severity: 'low' | 'medium' | 'high';
  timestamp: string;
  message: string;
}

export default function ProctoringSessionPage() {
  const { t } = useTranslation();
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Generate unique IDs for demo to avoid "session already exists" errors
  const [examId, setExamId] = useState(() => `EXAM-${Date.now().toString(36).toUpperCase()}`);
  const [userId, setUserId] = useState(() => `USER-${Math.random().toString(36).slice(2, 8).toUpperCase()}`);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isVideoReady, setIsVideoReady] = useState(false);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [stats, setStats] = useState({
    framesAnalyzed: 0,
    verificationSuccess: 0,
    riskScore: 0,
    duration: 0,
  });

  const {
    sessionId,
    sessionStatus,
    createSession,
    startSession,
    pauseSession,
    endSession,
    submitFrame,
    isCreating,
    isStarting,
    isEnding,
    createError,
    startError,
  } = useProctoringSession({
    onIncident: (incident) => {
      setIncidents((prev) => [incident, ...prev].slice(0, 50));
      if (incident.severity === 'high') {
        toast.error('High Severity Incident', {
          description: incident.message,
        });
      }
    },
    onFrameResult: (result) => {
      setStats((prev) => ({
        ...prev,
        framesAnalyzed: prev.framesAnalyzed + 1,
        verificationSuccess: (result.face_verified || result.face_matched)
          ? prev.verificationSuccess + 1
          : prev.verificationSuccess,
        riskScore: result.risk_score,
      }));
    },
  });

  // Show errors via toast
  useEffect(() => {
    if (createError) {
      toast.error('Failed to create session', {
        description: createError instanceof Error ? createError.message : 'Unknown error',
      });
    }
  }, [createError]);

  useEffect(() => {
    if (startError) {
      toast.error('Failed to start session', {
        description: startError instanceof Error ? startError.message : 'Unknown error',
      });
    }
  }, [startError]);

  // Start camera
  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 1280, height: 720, facingMode: 'user' },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        // Wait for video metadata to load before marking as ready
        videoRef.current.onloadedmetadata = () => {
          console.log('Video metadata loaded:', videoRef.current?.videoWidth, 'x', videoRef.current?.videoHeight);
          setIsVideoReady(true);
        };
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
      videoRef.current.onloadedmetadata = null;
    }
    setIsStreaming(false);
    setIsVideoReady(false);
  }, []);

  // Capture and submit frame
  const captureFrame = useCallback(() => {
    if (!videoRef.current || !canvasRef.current || !sessionId) return;

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
            const reader = new FileReader();
            reader.onloadend = () => {
              const base64 = (reader.result as string).split(',')[1];
              submitFrame(base64);
            };
            reader.readAsDataURL(blob);
          }
        },
        'image/jpeg',
        0.8
      );
    }
  }, [sessionId, submitFrame]);

  // Frame capture interval
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (sessionStatus === 'active' && isStreaming) {
      interval = setInterval(captureFrame, 1000); // Capture every second
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [sessionStatus, isStreaming, captureFrame]);

  // Duration timer
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (sessionStatus === 'active') {
      interval = setInterval(() => {
        setStats((prev) => ({ ...prev, duration: prev.duration + 1 }));
      }, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [sessionStatus]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, [stopCamera]);

  const handleCreateSession = async () => {
    if (!examId.trim()) {
      toast.error('Error', { description: 'Exam ID is required' });
      return;
    }
    if (!userId.trim()) {
      toast.error('Error', { description: 'User ID is required' });
      return;
    }
    try {
      await createSession(userId, examId);
      await startCamera();
    } catch {
      toast.error('Failed to create session', {
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  };

  const handleStartSession = async () => {
    try {
      // Capture baseline image from camera if available
      let baselineImage: string | undefined;
      if (videoRef.current && canvasRef.current) {
        const video = videoRef.current;
        const canvas = canvasRef.current;

        // Ensure video has valid dimensions (is fully loaded)
        if (video.videoWidth > 0 && video.videoHeight > 0) {
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
          const ctx = canvas.getContext('2d');
          if (ctx) {
            ctx.drawImage(video, 0, 0);
            baselineImage = canvas.toDataURL('image/jpeg', 0.8).split(',')[1];
            console.log('Captured baseline image:', baselineImage.length, 'chars');
          }
        } else {
          console.warn('Video not ready, dimensions:', video.videoWidth, 'x', video.videoHeight);
          toast.warning('Camera not ready', {
            description: 'Please wait for the camera to fully load before starting the session.',
          });
          return;
        }
      } else {
        console.warn('Video or canvas ref not available');
        toast.warning('Camera not available', {
          description: 'Please ensure the camera is active before starting the session.',
        });
        return;
      }

      if (!baselineImage) {
        console.error('Failed to capture baseline image');
        toast.error('Capture failed', {
          description: 'Could not capture baseline image from camera.',
        });
        return;
      }

      await startSession(baselineImage);
    } catch {
      toast.error('Failed to start session', {
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  };

  const handlePauseSession = async () => {
    console.log('handlePauseSession called, sessionId:', sessionId, 'status:', sessionStatus);
    // Stop frame capture immediately to prevent race conditions
    setIsStreaming(false);
    try {
      await pauseSession();
      console.log('Pause successful');
      toast.success('Session paused');
    } catch {
      console.error('Pause failed:', err);
      // Re-enable streaming if pause failed and session is still active
      if (sessionStatus === 'active') {
        setIsStreaming(true);
      }
      toast.error('Failed to pause session', {
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  };

  const handleEndSession = async () => {
    console.log('handleEndSession called, sessionId:', sessionId, 'status:', sessionStatus);
    // Stop frame capture immediately to prevent race conditions
    setIsStreaming(false);
    try {
      await endSession();
      console.log('End successful');
      stopCamera();
      toast.success('Session ended');
    } catch {
      console.error('End failed:', err);
      toast.error('Failed to end session', {
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  };

  const formatDuration = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const severityColors = {
    low: 'bg-yellow-500/10 text-yellow-600 border-yellow-500/20',
    medium: 'bg-orange-500/10 text-orange-600 border-orange-500/20',
    high: 'bg-red-500/10 text-red-600 border-red-500/20',
  };

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
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-500/10">
              <Video className="h-5 w-5 text-red-500" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">{t('proctoring.title')}</h1>
              <p className="text-muted-foreground">{t('proctoring.description')}</p>
            </div>
          </div>
          {sessionId && (
            <Badge variant={sessionStatus === 'active' ? 'default' : 'secondary'}>
              {sessionStatus === 'active' ? t('proctoring.status.active') : t('proctoring.status.inactive')}
            </Badge>
          )}
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
              <CardTitle>Camera Feed</CardTitle>
              <CardDescription>
                {isStreaming ? 'Live video monitoring' : 'Camera not active'}
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
                      <Video className="h-12 w-12 mx-auto mb-2 opacity-50" />
                      <p>Camera not active</p>
                    </div>
                  </div>
                )}

                {/* Status overlay */}
                {sessionStatus === 'active' && (
                  <div className="absolute top-2 left-2 flex items-center gap-2">
                    <span className="flex h-3 w-3">
                      <span className="animate-ping absolute h-3 w-3 rounded-full bg-red-400 opacity-75" />
                      <span className="relative rounded-full h-3 w-3 bg-red-500" />
                    </span>
                    <span className="text-white text-sm font-medium">LIVE</span>
                  </div>
                )}

                {/* Risk Score */}
                {sessionStatus === 'active' && (
                  <div className="absolute top-2 right-2">
                    <Badge
                      variant={
                        stats.riskScore < 0.3
                          ? 'default'
                          : stats.riskScore < 0.6
                          ? 'warning'
                          : 'destructive'
                      }
                    >
                      Risk: {formatPercent(stats.riskScore, 0)}
                    </Badge>
                  </div>
                )}
              </div>

              {/* Controls */}
              {!sessionId ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="examId">Exam ID</Label>
                      <Input
                        id="examId"
                        value={examId}
                        onChange={(e) => setExamId(e.target.value)}
                        placeholder="Enter exam ID"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="userId">User ID</Label>
                      <Input
                        id="userId"
                        value={userId}
                        onChange={(e) => setUserId(e.target.value)}
                        placeholder="Enter user ID"
                      />
                    </div>
                  </div>
                  <Button
                    onClick={handleCreateSession}
                    disabled={isCreating}
                    className="w-full"
                  >
                    {isCreating ? (
                      <>
                        <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                        Creating Session...
                      </>
                    ) : (
                      <>
                        <Play className="mr-2 h-4 w-4" />
                        Create Session
                      </>
                    )}
                  </Button>
                  {createError && (
                    <div className="rounded-lg bg-red-50 p-3 text-red-800 dark:bg-red-950/50 dark:text-red-200 text-sm">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="h-4 w-4" />
                        <span className="font-medium">Error creating session</span>
                      </div>
                      <p className="mt-1 text-xs">
                        {createError instanceof Error ? createError.message : 'Unknown error'}
                      </p>
                      {createError instanceof Error && createError.message.includes('already exists') && (
                        <p className="mt-2 text-xs font-medium">
                          Tip: Change the Exam ID or User ID to create a new session, or use unique identifiers.
                        </p>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="flex gap-2">
                    {sessionStatus !== 'active' ? (
                      <Button
                        onClick={handleStartSession}
                        disabled={isStarting || !isVideoReady}
                        className="flex-1"
                      >
                        {isStarting ? (
                          <>
                            <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                            Starting...
                          </>
                        ) : !isVideoReady ? (
                          <>
                            <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                            Waiting for camera...
                          </>
                        ) : (
                          <>
                            <Play className="mr-2 h-4 w-4" />
                            {t('proctoring.startSession')}
                          </>
                        )}
                      </Button>
                    ) : (
                      <>
                        <Button
                          variant="outline"
                          onClick={handlePauseSession}
                          className="flex-1"
                        >
                          <Pause className="mr-2 h-4 w-4" />
                          Pause
                        </Button>
                        <Button
                          variant="destructive"
                          onClick={handleEndSession}
                          disabled={isEnding}
                          className="flex-1"
                        >
                          <Square className="mr-2 h-4 w-4" />
                          {t('proctoring.endSession')}
                        </Button>
                      </>
                    )}
                  </div>
                  {startError && (
                    <div className="rounded-lg bg-red-50 p-3 text-red-800 dark:bg-red-950/50 dark:text-red-200 text-sm">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="h-4 w-4" />
                        <span className="font-medium">Error starting session</span>
                      </div>
                      <p className="mt-1 text-xs">
                        {startError instanceof Error ? startError.message : 'Unknown error'}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Stats & Incidents */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.2 }}
          className="space-y-6"
        >
          {/* Stats */}
          <Card>
            <CardHeader>
              <CardTitle>Session Stats</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-lg border p-3">
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Clock className="h-4 w-4" />
                    <span className="text-xs">Duration</span>
                  </div>
                  <p className="text-lg font-mono font-semibold">
                    {formatDuration(stats.duration)}
                  </p>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Activity className="h-4 w-4" />
                    <span className="text-xs">Frames</span>
                  </div>
                  <p className="text-lg font-semibold">{stats.framesAnalyzed}</p>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <User className="h-4 w-4" />
                    <span className="text-xs">Verification</span>
                  </div>
                  <p className="text-lg font-semibold">
                    {stats.framesAnalyzed > 0
                      ? formatPercent(stats.verificationSuccess / stats.framesAnalyzed, 0)
                      : '0%'}
                  </p>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <AlertTriangle className="h-4 w-4" />
                    <span className="text-xs">Incidents</span>
                  </div>
                  <p className="text-lg font-semibold">{incidents.length}</p>
                </div>
              </div>

              {/* Risk Score Bar */}
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Risk Score</span>
                  <span className="font-semibold">{formatPercent(stats.riskScore, 0)}</span>
                </div>
                <Progress
                  value={stats.riskScore * 100}
                  className={
                    stats.riskScore < 0.3
                      ? 'bg-green-200'
                      : stats.riskScore < 0.6
                      ? 'bg-yellow-200'
                      : 'bg-red-200'
                  }
                />
              </div>
            </CardContent>
          </Card>

          {/* Incidents */}
          <Card>
            <CardHeader>
              <CardTitle>Recent Incidents</CardTitle>
              <CardDescription>
                {incidents.length} incident{incidents.length !== 1 ? 's' : ''} recorded
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-64">
                {incidents.length > 0 ? (
                  <div className="space-y-2">
                    {incidents.map((incident) => (
                      <div
                        key={incident.id}
                        className={`rounded-lg border p-2 ${severityColors[incident.severity]}`}
                      >
                        <div className="flex items-center justify-between">
                          <Badge variant="outline" className="text-xs">
                            {incident.type.replace(/_/g, ' ')}
                          </Badge>
                          <span className="text-xs opacity-70">
                            {new Date(incident.timestamp).toLocaleTimeString()}
                          </span>
                        </div>
                        <p className="text-sm mt-1">{incident.message}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex h-full items-center justify-center text-muted-foreground">
                    <p className="text-sm">No incidents recorded</p>
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
