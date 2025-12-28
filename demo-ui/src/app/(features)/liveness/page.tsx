'use client';

import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import { ScanFace, Upload, Camera, CheckCircle2, XCircle, AlertCircle, Shield, Video, Fingerprint, Puzzle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge as _Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { ImageUploader } from '@/components/media/image-uploader';
import { WebcamCapture } from '@/components/media/webcam-capture';
import { LiveCameraStream } from '@/components/media/live-camera-stream';
import { ActiveLivenessChallenge } from '@/components/liveness/active-liveness-challenge';
import { PuzzleLivenessChallenge } from '@/components/liveness/puzzle-liveness-challenge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useLivenessCheck } from '@/hooks/use-liveness-check';
import { toast } from 'sonner';
import { formatPercent, toPercent } from '@/lib/utils/format';
import type { LiveAnalysisResult } from '@/hooks/use-live-camera-analysis';

export default function LivenessPage() {
  const { t } = useTranslation();
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [capturedImage, setCapturedImage] = useState<Blob | null>(null);
  const [inputMode, setInputMode] = useState<'upload' | 'camera' | 'live' | 'active' | 'puzzle'>('camera');
  const [puzzleResult, setPuzzleResult] = useState<{ success: boolean; score: number } | null>(null);
  const [liveResult, setLiveResult] = useState<LiveAnalysisResult | null>(null);

  const { mutate: checkLiveness, isPending, isSuccess, isError, data, error, reset } = useLivenessCheck();

  const handleCheck = () => {
    const image = inputMode === 'upload' ? selectedImage : capturedImage;

    if (!image) {
      toast.error(t('common.error'), {
        description: 'Please select or capture an image',
      });
      return;
    }

    checkLiveness(
      { image },
      {
        onSuccess: (result) => {
          if (result.is_live) {
            toast.success(t('liveness.result.live'), {
              description: `Liveness score: ${formatPercent(result.confidence)}`,
            });
          } else {
            toast.warning(t('liveness.result.spoof'), {
              description: result.message || 'Potential spoof detected',
            });
          }
        },
        onError: (err) => {
          toast.error(t('common.error'), {
            description: err.message,
          });
        },
      }
    );
  };

  const handleReset = () => {
    setSelectedImage(null);
    setCapturedImage(null);
    setLiveResult(null);
    setPuzzleResult(null);
    reset();
  };

  const handlePuzzleComplete = useCallback((success: boolean, score: number) => {
    setPuzzleResult({ success, score });
    if (success) {
      toast.success('Liveness Verified!', {
        description: `Puzzle completed with score: ${score.toFixed(0)}%`,
      });
    } else {
      toast.warning('Verification Failed', {
        description: 'Please try again',
      });
    }
  }, []);

  const handleLiveResult = useCallback((result: LiveAnalysisResult) => {
    setLiveResult(result);
  }, []);

  // Use live result if in live mode, add recommendation if missing
  const displayData = (() => {
    if (inputMode === 'live' && liveResult?.liveness) {
      const liveness = liveResult.liveness;
      // Generate recommendation if not provided
      if (!liveness.recommendation) {
        if (liveness.is_live) {
          liveness.recommendation = 'Liveness verified. Face appears to be a real person.';
        } else if (liveness.confidence < 0.3) {
          liveness.recommendation = 'Low confidence. Please ensure good lighting and face the camera directly.';
        } else {
          liveness.recommendation = 'Liveness check failed. Please try again with better lighting.';
        }
      }
      return liveness;
    }
    return data;
  })();

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-orange-500/10">
            <ScanFace className="h-5 w-5 text-orange-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">{t('liveness.title')}</h1>
            <p className="text-muted-foreground">{t('liveness.description')}</p>
          </div>
        </div>
      </motion.div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Input Section */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
        >
          <Card>
            <CardHeader>
              <CardTitle>Capture Face</CardTitle>
              <CardDescription>
                Use camera for best liveness detection results
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Image Input Tabs */}
              <Tabs
                value={inputMode}
                onValueChange={(v) => setInputMode(v as 'upload' | 'camera' | 'live' | 'active' | 'puzzle')}
              >
                <TabsList className="grid w-full grid-cols-5">
                  <TabsTrigger value="camera" className="flex items-center gap-1 text-xs">
                    <Camera className="h-3 w-3" />
                    Camera
                  </TabsTrigger>
                  <TabsTrigger value="upload" className="flex items-center gap-1 text-xs">
                    <Upload className="h-3 w-3" />
                    Upload
                  </TabsTrigger>
                  <TabsTrigger value="live" className="flex items-center gap-1 text-xs">
                    <Video className="h-3 w-3" />
                    Passive
                  </TabsTrigger>
                  <TabsTrigger value="active" className="flex items-center gap-1 text-xs">
                    <Fingerprint className="h-3 w-3" />
                    Active
                  </TabsTrigger>
                  <TabsTrigger value="puzzle" className="flex items-center gap-1 text-xs">
                    <Puzzle className="h-3 w-3" />
                    Puzzle
                  </TabsTrigger>
                </TabsList>
                <TabsContent value="camera" className="mt-4">
                  <WebcamCapture
                    onCapture={setCapturedImage}
                    capturedImage={capturedImage}
                    disabled={isPending}
                  />
                </TabsContent>
                <TabsContent value="upload" className="mt-4">
                  <ImageUploader
                    onImageSelected={setSelectedImage}
                    selectedImage={selectedImage}
                    disabled={isPending}
                  />
                </TabsContent>
                <TabsContent value="live" className="mt-4">
                  <LiveCameraStream
                    mode="liveness"
                    onResult={handleLiveResult}
                    disabled={isPending}
                  />
                </TabsContent>
                <TabsContent value="active" className="mt-4">
                  <LiveCameraStream
                    mode="active_liveness"
                    onResult={handleLiveResult}
                    disabled={isPending}
                  />
                </TabsContent>
                <TabsContent value="puzzle" className="mt-4">
                  <PuzzleLivenessChallenge
                    difficulty="standard"
                    onComplete={handlePuzzleComplete}
                    onError={(err) => toast.error('Puzzle Error', { description: err })}
                  />
                </TabsContent>
              </Tabs>

              {/* Action Buttons */}
              {inputMode !== 'live' && inputMode !== 'active' && inputMode !== 'puzzle' && (
                <div className="flex gap-2 pt-4">
                  <Button
                    onClick={handleCheck}
                    disabled={isPending || (!selectedImage && !capturedImage)}
                    className="flex-1"
                  >
                    {isPending ? (
                      <>
                        <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                        {t('liveness.checking')}
                      </>
                    ) : (
                      <>
                        <ScanFace className="mr-2 h-4 w-4" />
                        {t('liveness.checkButton')}
                      </>
                    )}
                  </Button>
                  {(isSuccess || isError) && (
                    <Button variant="outline" onClick={handleReset}>
                      {t('common.reset')}
                    </Button>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Result Section */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.2 }}
        >
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Liveness Result</CardTitle>
              <CardDescription>
                Anti-spoofing analysis results
              </CardDescription>
            </CardHeader>
            <CardContent>
              {/* Active Liveness Mode */}
              {inputMode === 'active' && (
                <>
                  {liveResult?.active_liveness ? (
                    <ActiveLivenessChallenge data={liveResult.active_liveness} />
                  ) : liveResult ? (
                    <div className="flex h-64 flex-col items-center justify-center gap-4">
                      <Fingerprint className="h-12 w-12 animate-pulse text-primary" />
                      <p className="text-center text-muted-foreground">
                        Initializing challenges...
                      </p>
                      {liveResult.error && (
                        <p className="text-sm text-red-500">{liveResult.error}</p>
                      )}
                    </div>
                  ) : null}
                </>
              )}

              {/* Puzzle Mode Info */}
              {inputMode === 'puzzle' && (
                <div className="flex h-64 flex-col items-center justify-center gap-4 text-muted-foreground">
                  <Puzzle className="h-12 w-12 text-primary" />
                  <div className="text-center">
                    <p className="font-medium text-foreground">Puzzle Liveness Mode</p>
                    <p className="text-sm mt-1">
                      Complete randomized challenges to verify liveness.
                    </p>
                    <p className="text-xs mt-2">
                      Uses backend-generated puzzles with anti-replay protection.
                    </p>
                  </div>
                </div>
              )}

              {/* Live Mode Indicator */}
              {inputMode === 'live' && liveResult && (
                <div className="mb-4 flex items-center justify-between rounded-lg bg-blue-50 p-3 text-sm dark:bg-blue-950/50">
                  <div className="flex items-center gap-2">
                    <Video className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                    <span className="font-medium text-blue-900 dark:text-blue-100">Passive Liveness Detection</span>
                  </div>
                  <div className="text-blue-700 dark:text-blue-300">
                    Frame #{liveResult.frame_number} • {liveResult.processing_time_ms.toFixed(0)}ms
                  </div>
                </div>
              )}

              {inputMode !== 'active' && inputMode !== 'puzzle' && ((inputMode === 'live' && liveResult?.liveness) || (isSuccess && data)) && displayData && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="space-y-6"
                >
                  {/* Status Badge */}
                  <div className={`flex items-center gap-3 rounded-lg p-4 ${
                    displayData.is_live
                      ? 'bg-green-500/10 text-green-600'
                      : 'bg-red-500/10 text-red-600'
                  }`}>
                    {displayData.is_live ? (
                      <CheckCircle2 className="h-8 w-8" />
                    ) : (
                      <XCircle className="h-8 w-8" />
                    )}
                    <div>
                      <p className="text-lg font-semibold">
                        {displayData.is_live ? 'Live Person ✓' : 'Potential Spoof ⚠️'}
                      </p>
                    </div>
                  </div>

                  {/* Liveness Score */}
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>Liveness Score</span>
                      <span className="font-semibold">
                        {formatPercent(displayData.confidence)}
                      </span>
                    </div>
                    <Progress
                      value={toPercent(displayData.confidence)}
                      className={displayData.is_live ? 'bg-green-200' : 'bg-red-200'}
                    />
                  </div>

                  {/* Liveness Method & Checks (from WebSocket) */}
                  {'method' in displayData && displayData.method && (
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span>Detection Method</span>
                        <span className="font-semibold capitalize">{displayData.method}</span>
                      </div>
                    </div>
                  )}

                  {'checks' in displayData && displayData.checks && Object.keys(displayData.checks).length > 0 && (
                    <div className="space-y-2">
                      <p className="text-sm font-medium">Liveness Checks</p>
                      <div className="grid grid-cols-2 gap-2">
                        {Object.entries(displayData.checks).map(([check, passed]) => (
                          <div
                            key={check}
                            className={`flex items-center gap-2 rounded-lg p-2 text-sm ${
                              passed ? 'bg-green-50 dark:bg-green-950/30' : 'bg-red-50 dark:bg-red-950/30'
                            }`}
                          >
                            {passed ? (
                              <CheckCircle2 className="h-4 w-4 text-green-600" />
                            ) : (
                              <XCircle className="h-4 w-4 text-red-600" />
                            )}
                            <span className="capitalize">{check.replace(/_/g, ' ')}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Recommendation */}
                  {displayData.recommendation && (
                    <div className="rounded-lg bg-muted p-4">
                      <p className="text-sm font-medium mb-2">Recommendation</p>
                      <p className="text-sm text-muted-foreground">
                        {displayData.recommendation}
                      </p>
                    </div>
                  )}

                </motion.div>
              )}

              {isError && error && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="space-y-4"
                >
                  <div className="flex items-center gap-2 text-red-600">
                    <AlertCircle className="h-5 w-5" />
                    <span className="font-medium">{t('common.error')}</span>
                  </div>
                  <div className="rounded-lg bg-red-50 p-4 text-red-800 dark:bg-red-950/50 dark:text-red-200">
                    {error.message}
                  </div>
                </motion.div>
              )}

              {/* Live stream error or no face */}
              {inputMode === 'live' && liveResult && !liveResult.liveness && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="space-y-4"
                >
                  <div className="flex items-center gap-3 rounded-lg bg-yellow-500/10 p-4 text-yellow-600">
                    <AlertCircle className="h-8 w-8" />
                    <div>
                      <p className="text-lg font-semibold">
                        {liveResult.error || 'Waiting for face detection...'}
                      </p>
                      {liveResult.face && !liveResult.face.detected && (
                        <p className="text-sm">No face detected in frame</p>
                      )}
                    </div>
                  </div>
                  {liveResult.error && (
                    <div className="rounded-lg bg-muted p-4 text-sm text-muted-foreground">
                      Tip: Ensure your face is well-lit and centered in the camera frame.
                    </div>
                  )}
                </motion.div>
              )}

              {!isSuccess && !isError && !liveResult && inputMode !== 'puzzle' && (
                <div className="flex h-64 flex-col items-center justify-center gap-4 text-muted-foreground">
                  <Shield className="h-12 w-12" />
                  <p className="text-center">
                    {inputMode === 'active'
                      ? 'Start active liveness to complete challenges'
                      : inputMode === 'live'
                      ? 'Start live streaming for real-time liveness detection'
                      : 'Capture or upload a face image to check liveness'}
                  </p>
                </div>
              )}

              {/* Active mode waiting for challenges */}
              {inputMode === 'active' && liveResult && !liveResult.active_liveness && (
                <div className="flex h-64 flex-col items-center justify-center gap-4 text-muted-foreground">
                  <Fingerprint className="h-12 w-12 animate-pulse" />
                  <p className="text-center">
                    Preparing liveness challenges...
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
