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

  const [examId, setExamId] = useState('EXAM-001');
  const [userId, setUserId] = useState('USER-001');
  const [isStreaming, setIsStreaming] = useState(false);
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
        verificationSuccess: result.face_verified
          ? prev.verificationSuccess + 1
          : prev.verificationSuccess,
        riskScore: result.risk_score,
      }));
    },
  });

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
        await videoRef.current.play();
        setIsStreaming(true);
      }
    } catch (err) {
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
    await createSession(userId, examId);
    await startCamera();
  };

  const handleStartSession = async () => {
    await startSession();
  };

  const handleEndSession = async () => {
    await endSession();
    stopCamera();
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
                      Risk: {(stats.riskScore * 100).toFixed(0)}%
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
                </div>
              ) : (
                <div className="flex gap-2">
                  {sessionStatus !== 'active' ? (
                    <Button
                      onClick={handleStartSession}
                      disabled={isStarting}
                      className="flex-1"
                    >
                      <Play className="mr-2 h-4 w-4" />
                      {t('proctoring.startSession')}
                    </Button>
                  ) : (
                    <>
                      <Button
                        variant="outline"
                        onClick={pauseSession}
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
                      ? ((stats.verificationSuccess / stats.framesAnalyzed) * 100).toFixed(0)
                      : 0}
                    %
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
                  <span className="font-semibold">{(stats.riskScore * 100).toFixed(0)}%</span>
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
