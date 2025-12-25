'use client';

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import { ShieldCheck, Upload, Camera, CheckCircle2, XCircle, AlertCircle, Video } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ImageUploader } from '@/components/media/image-uploader';
import { WebcamCapture } from '@/components/media/webcam-capture';
import { LiveCameraStream } from '@/components/media/live-camera-stream';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { SimilarityGauge } from '@/components/biometric/similarity-gauge';
import { useFaceVerification } from '@/hooks/use-face-verification';
import { toast } from 'sonner';
import { formatPercent } from '@/lib/utils/format';
import type { LiveAnalysisResult } from '@/hooks/use-live-camera-analysis';

export default function VerificationPage() {
  const { t } = useTranslation();
  const [userId, setUserId] = useState('');
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [capturedImage, setCapturedImage] = useState<Blob | null>(null);
  const [inputMode, setInputMode] = useState<'upload' | 'camera' | 'live'>('upload');
  const [liveResult, setLiveResult] = useState<LiveAnalysisResult | null>(null);

  const { mutate: verifyFace, isPending, isSuccess, isError, data, error, reset } = useFaceVerification();

  const handleVerify = () => {
    const image = inputMode === 'upload' ? selectedImage : capturedImage;

    if (!userId.trim()) {
      toast.error(t('common.error'), {
        description: 'User ID is required',
      });
      return;
    }

    if (!image) {
      toast.error(t('common.error'), {
        description: 'Please select or capture an image',
      });
      return;
    }

    verifyFace(
      { user_id: userId, image },
      {
        onSuccess: (result) => {
          if (result.match) {
            toast.success('Identity Verified', {
              description: `Confidence: ${formatPercent(result.confidence)}`,
            });
          } else {
            toast.warning('Verification Failed', {
              description: 'Face does not match enrolled user',
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
    setUserId('');
    setSelectedImage(null);
    setCapturedImage(null);
    setLiveResult(null);
    reset();
  };

  const handleLiveResult = (result: LiveAnalysisResult) => {
    setLiveResult(result);
  };

  // Use live result if in live mode
  const displayData = inputMode === 'live' && liveResult?.verification ? liveResult.verification : data;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-500/10">
            <ShieldCheck className="h-5 w-5 text-green-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">{t('verification.title')}</h1>
            <p className="text-muted-foreground">{t('verification.description')}</p>
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
              <CardTitle>Verify Identity</CardTitle>
              <CardDescription>
                Compare a face against an enrolled user
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* User ID Input */}
              <div className="space-y-2">
                <Label htmlFor="userId">Enrolled User ID</Label>
                <Input
                  id="userId"
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                  placeholder="Enter the enrolled user ID"
                  disabled={isPending}
                />
              </div>

              {/* Image Input Tabs */}
              <Tabs
                value={inputMode}
                onValueChange={(v) => setInputMode(v as 'upload' | 'camera' | 'live')}
              >
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger value="upload" className="flex items-center gap-2">
                    <Upload className="h-4 w-4" />
                    Upload
                  </TabsTrigger>
                  <TabsTrigger value="camera" className="flex items-center gap-2">
                    <Camera className="h-4 w-4" />
                    Camera
                  </TabsTrigger>
                  <TabsTrigger value="live" className="flex items-center gap-2">
                    <Video className="h-4 w-4" />
                    Live Stream
                  </TabsTrigger>
                </TabsList>
                <TabsContent value="upload" className="mt-4">
                  <ImageUploader
                    onImageSelected={setSelectedImage}
                    selectedImage={selectedImage}
                    disabled={isPending}
                  />
                </TabsContent>
                <TabsContent value="camera" className="mt-4">
                  <WebcamCapture
                    onCapture={setCapturedImage}
                    capturedImage={capturedImage}
                    disabled={isPending}
                  />
                </TabsContent>
                <TabsContent value="live" className="mt-4">
                  <LiveCameraStream
                    mode="verification"
                    onResult={handleLiveResult}
                    disabled={isPending || !userId.trim()}
                    userId={userId}
                  />
                </TabsContent>
              </Tabs>

              {/* Action Buttons */}
              {inputMode !== 'live' && (
                <div className="flex gap-2 pt-4">
                  <Button
                    onClick={handleVerify}
                    disabled={isPending || (!selectedImage && !capturedImage)}
                    className="flex-1"
                  >
                    {isPending ? (
                      <>
                        <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                        {t('verification.verifying')}
                      </>
                    ) : (
                      <>
                        <ShieldCheck className="mr-2 h-4 w-4" />
                        {t('verification.verifyButton')}
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
              <CardTitle>Verification Result</CardTitle>
              <CardDescription>
                Match result and confidence score
              </CardDescription>
            </CardHeader>
            <CardContent>
              {/* Live Mode Indicator */}
              {inputMode === 'live' && liveResult && (
                <div className="mb-4 flex items-center justify-between rounded-lg bg-blue-50 p-3 text-sm dark:bg-blue-950/50">
                  <div className="flex items-center gap-2">
                    <Video className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                    <span className="font-medium text-blue-900 dark:text-blue-100">Live Verification</span>
                  </div>
                  <div className="text-blue-700 dark:text-blue-300">
                    Frame #{liveResult.frame_number} • {liveResult.processing_time_ms.toFixed(0)}ms
                  </div>
                </div>
              )}

              {((inputMode === 'live' && liveResult?.verification) || (isSuccess && data)) && displayData && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="space-y-6"
                >
                  {/* Match Status */}
                  <div className={`flex items-center gap-3 rounded-lg p-4 ${
                    displayData.match
                      ? 'bg-green-500/10 text-green-600'
                      : 'bg-red-500/10 text-red-600'
                  }`}>
                    {displayData.match ? (
                      <CheckCircle2 className="h-8 w-8" />
                    ) : (
                      <XCircle className="h-8 w-8" />
                    )}
                    <div>
                      <p className="text-lg font-semibold">
                        {displayData.match ? 'Identity Verified ✓' : 'No Match ✗'}
                      </p>
                      <p className="text-sm opacity-80">
                        {displayData.match
                          ? 'Identity successfully verified'
                          : 'Face does not match enrolled user'}
                      </p>
                    </div>
                  </div>

                  {/* Similarity Gauge */}
                  <div className="flex justify-center py-4">
                    <SimilarityGauge
                      value={displayData.confidence}
                      threshold={displayData.threshold}
                    />
                  </div>

                  {/* Details */}
                  <div className="space-y-2 rounded-lg bg-muted p-4">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Similarity Score</span>
                      <span className="font-semibold">
                        {formatPercent(displayData.confidence)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Match Threshold</span>
                      <span className="font-mono text-sm">
                        {formatPercent(displayData.threshold)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">User ID</span>
                      <span className="font-mono text-sm">
                        {displayData.user_id}
                      </span>
                    </div>
                  </div>
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

              {!isSuccess && !isError && !liveResult && (
                <div className="flex h-64 items-center justify-center text-muted-foreground">
                  <p>
                    {inputMode === 'live'
                      ? 'Enter user ID and start live streaming for real-time verification'
                      : 'Enter user ID and image to verify identity'}
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
