'use client';

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import { Users, Upload, Camera, AlertCircle, User, Video } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { ImageUploader } from '@/components/media/image-uploader';
import { WebcamCapture } from '@/components/media/webcam-capture';
import { LiveCameraStream } from '@/components/media/live-camera-stream';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useDemographicsAnalysis } from '@/hooks/use-demographics-analysis';
import { toast } from 'sonner';
import { formatPercent, toPercent } from '@/lib/utils/format';
import type { LiveAnalysisResult } from '@/hooks/use-live-camera-analysis';

const emotionEmojis: Record<string, string> = {
  happy: '😊',
  sad: '😢',
  angry: '😠',
  surprise: '😲',
  fear: '😨',
  disgust: '🤢',
  neutral: '😐',
};

export default function DemographicsPage() {
  const { t } = useTranslation();
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [capturedImage, setCapturedImage] = useState<Blob | null>(null);
  const [inputMode, setInputMode] = useState<'upload' | 'camera' | 'live'>('upload');
  const [liveResult, setLiveResult] = useState<LiveAnalysisResult | null>(null);

  const { mutate: analyzeDemographics, isPending, isSuccess, isError, data, error, reset } = useDemographicsAnalysis();

  const handleAnalyze = () => {
    const image = inputMode === 'upload' ? selectedImage : capturedImage;

    if (!image) {
      toast.error(t('common.error'), {
        description: 'Please select or capture an image',
      });
      return;
    }

    analyzeDemographics(
      { image },
      {
        onSuccess: (result) => {
          toast.success('Analysis Complete', {
            description: `Age: ${result.age}, Gender: ${result.gender}`,
          });
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
    reset();
  };

  const handleLiveResult = (result: LiveAnalysisResult) => {
    setLiveResult(result);
  };

  // Use live result if in live mode
  const displayData = inputMode === 'live' && liveResult?.demographics ? liveResult.demographics : data;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-pink-500/10">
            <Users className="h-5 w-5 text-pink-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">{t('demographics.title')}</h1>
            <p className="text-muted-foreground">{t('demographics.description')}</p>
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
              <CardTitle>Image Input</CardTitle>
              <CardDescription>
                Upload or capture an image for demographics analysis
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
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
                    mode="demographics"
                    onResult={handleLiveResult}
                    disabled={isPending}
                  />
                </TabsContent>
              </Tabs>

              {inputMode !== 'live' && (
                <div className="flex gap-2 pt-4">
                  <Button
                    onClick={handleAnalyze}
                    disabled={isPending || (!selectedImage && !capturedImage)}
                    className="flex-1"
                  >
                    {isPending ? (
                      <>
                        <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                        {t('demographics.analyzing')}
                      </>
                    ) : (
                      <>
                        <Users className="mr-2 h-4 w-4" />
                        {t('demographics.analyzeButton')}
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
              <CardTitle>Demographics Analysis</CardTitle>
              <CardDescription>
                Estimated age, gender, and emotion
              </CardDescription>
            </CardHeader>
            <CardContent>
              {/* Live Mode Indicator */}
              {inputMode === 'live' && liveResult && (
                <div className="mb-4 flex items-center justify-between rounded-lg bg-blue-50 p-3 text-sm dark:bg-blue-950/50">
                  <div className="flex items-center gap-2">
                    <Video className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                    <span className="font-medium text-blue-900 dark:text-blue-100">Live Analysis</span>
                  </div>
                  <div className="text-blue-700 dark:text-blue-300">
                    Frame #{liveResult.frame_number} • {liveResult.processing_time_ms.toFixed(0)}ms
                  </div>
                </div>
              )}

              {((inputMode === 'live' && liveResult?.demographics) || (isSuccess && data)) && displayData && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="space-y-6"
                >
                  {/* Age */}
                  {displayData.age !== undefined && (
                    <div className="rounded-lg border p-4">
                      <div className="flex items-center gap-3">
                        <User className="h-8 w-8 text-primary" />
                        <div>
                          <p className="text-sm text-muted-foreground">{t('demographics.results.age')}</p>
                          <p className="text-2xl font-bold">{displayData.age} years</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Gender */}
                  {displayData.gender && (
                    <div className="rounded-lg border p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm text-muted-foreground">{t('demographics.results.gender')}</p>
                          <p className="text-2xl font-bold capitalize">{displayData.gender}</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Emotion */}
                  {displayData.emotion && (
                    <div className="rounded-lg border p-4">
                      <p className="text-sm text-muted-foreground mb-3">{t('demographics.results.emotion')}</p>
                      <div className="flex items-center gap-3 mb-4">
                        <span className="text-4xl">{emotionEmojis[displayData.emotion] || '😐'}</span>
                        <div>
                          <p className="text-xl font-bold capitalize">{displayData.emotion}</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Race */}
                  {displayData.race && (
                    <div className="rounded-lg border p-4">
                      <div>
                        <p className="text-sm text-muted-foreground">Race</p>
                        <p className="text-2xl font-bold capitalize">{displayData.race}</p>
                      </div>
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

              {!isSuccess && !isError && !liveResult && (
                <div className="flex h-64 flex-col items-center justify-center gap-4 text-muted-foreground">
                  <Users className="h-12 w-12" />
                  <p>
                    {inputMode === 'live'
                      ? 'Start live streaming to see real-time demographics analysis'
                      : 'Upload an image to analyze demographics'}
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
