'use client';

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import { Activity, Upload, Camera, AlertCircle, CheckCircle2, AlertTriangle, XCircle, Video } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { ImageUploader } from '@/components/media/image-uploader';
import { WebcamCapture } from '@/components/media/webcam-capture';
import { LiveCameraStream } from '@/components/media/live-camera-stream';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useQualityAnalysis } from '@/hooks/use-quality-analysis';
import { toast } from 'sonner';
import { formatPercent, toPercent } from '@/lib/utils/format';
import type { LiveAnalysisResult } from '@/hooks/use-live-camera-analysis';

const qualityGradeConfig = {
  excellent: { color: 'text-green-600', bg: 'bg-green-500/10', icon: CheckCircle2 },
  good: { color: 'text-blue-600', bg: 'bg-blue-500/10', icon: CheckCircle2 },
  acceptable: { color: 'text-yellow-600', bg: 'bg-yellow-500/10', icon: AlertTriangle },
  poor: { color: 'text-orange-600', bg: 'bg-orange-500/10', icon: AlertTriangle },
  failed: { color: 'text-red-600', bg: 'bg-red-500/10', icon: XCircle },
};

export default function QualityPage() {
  const { t } = useTranslation();
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [capturedImage, setCapturedImage] = useState<Blob | null>(null);
  const [inputMode, setInputMode] = useState<'upload' | 'camera' | 'live'>('upload');
  const [liveResult, setLiveResult] = useState<LiveAnalysisResult | null>(null);

  const { mutate: analyzeQuality, isPending, isSuccess, isError, data, error, reset } = useQualityAnalysis();

  const handleAnalyze = () => {
    const image = inputMode === 'upload' ? selectedImage : capturedImage;

    if (!image) {
      toast.error(t('common.error'), {
        description: 'Please select or capture an image',
      });
      return;
    }

    analyzeQuality(
      { image },
      {
        onSuccess: (result) => {
          toast.success('Analysis Complete', {
            description: `Quality Score: ${formatPercent(result.overall_score)}`,
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

  const getGradeFromScore = (score: number) => {
    if (score >= 0.9) return 'excellent';
    if (score >= 0.75) return 'good';
    if (score >= 0.6) return 'acceptable';
    if (score >= 0.4) return 'poor';
    return 'failed';
  };

  // Use live result if in live mode, otherwise use static result
  const displayData = inputMode === 'live' && liveResult?.quality ? liveResult.quality : data;
  const grade = displayData ? getGradeFromScore(displayData.overall_score) : null;
  const gradeConfig = grade ? qualityGradeConfig[grade as keyof typeof qualityGradeConfig] : null;
  const GradeIcon = gradeConfig?.icon || CheckCircle2;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-500/10">
            <Activity className="h-5 w-5 text-cyan-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">{t('quality.title')}</h1>
            <p className="text-muted-foreground">{t('quality.description')}</p>
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
                Upload or capture an image for quality analysis
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
                    mode="quality"
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
                        {t('quality.analyzing')}
                      </>
                    ) : (
                      <>
                        <Activity className="mr-2 h-4 w-4" />
                        {t('quality.analyzeButton')}
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
              <CardTitle>Quality Analysis</CardTitle>
              <CardDescription>
                Detailed quality metrics and recommendations
              </CardDescription>
            </CardHeader>
            <CardContent>
              {/* Live Stream or Static Result */}
              {((inputMode === 'live' && liveResult?.quality) || (isSuccess && data)) && displayData && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="space-y-6"
                >
                  {/* Live Mode Indicator */}
                  {inputMode === 'live' && liveResult && (
                    <div className="flex items-center justify-between rounded-lg bg-blue-50 p-3 text-sm dark:bg-blue-950/50">
                      <div className="flex items-center gap-2">
                        <Video className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                        <span className="font-medium text-blue-900 dark:text-blue-100">Live Analysis</span>
                      </div>
                      <div className="text-blue-700 dark:text-blue-300">
                        Frame #{liveResult.frame_number} • {liveResult.processing_time_ms.toFixed(0)}ms
                      </div>
                    </div>
                  )}

                  {/* Overall Grade */}
                  <div className={`flex items-center gap-3 rounded-lg p-4 ${gradeConfig?.bg}`}>
                    <GradeIcon className={`h-8 w-8 ${gradeConfig?.color}`} />
                    <div>
                      <p className={`text-lg font-semibold ${gradeConfig?.color}`}>
                        {grade ? t(`quality.levels.${grade}`) : 'Quality Result'}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        Overall Score: {formatPercent(displayData.overall_score)}
                      </p>
                    </div>
                  </div>

                  {/* Quality Metrics */}
                  {displayData.brightness !== undefined && (
                    <div className="space-y-3">
                      <p className="text-sm font-medium">Quality Metrics</p>
                      <div className="space-y-1">
                        <div className="flex justify-between text-sm">
                          <span className="capitalize">Brightness</span>
                          <span className="font-mono">{formatPercent(displayData.brightness, 0)}</span>
                        </div>
                        <Progress value={toPercent(displayData.brightness)} className="h-2" />
                      </div>
                      {displayData.sharpness !== undefined && (
                        <div className="space-y-1">
                          <div className="flex justify-between text-sm">
                            <span className="capitalize">Sharpness</span>
                            <span className="font-mono">{formatPercent(displayData.sharpness, 0)}</span>
                          </div>
                          <Progress value={toPercent(displayData.sharpness)} className="h-2" />
                        </div>
                      )}
                      {displayData.face_size !== undefined && (
                        <div className="space-y-1">
                          <div className="flex justify-between text-sm">
                            <span className="capitalize">Face Size</span>
                            <span className="font-mono">{formatPercent(displayData.face_size, 0)}</span>
                          </div>
                          <Progress value={toPercent(displayData.face_size)} className="h-2" />
                        </div>
                      )}
                      {displayData.centering !== undefined && (
                        <div className="space-y-1">
                          <div className="flex justify-between text-sm">
                            <span className="capitalize">Centering</span>
                            <span className="font-mono">{formatPercent(displayData.centering, 0)}</span>
                          </div>
                          <Progress value={toPercent(displayData.centering)} className="h-2" />
                        </div>
                      )}
                    </div>
                  )}

                  {/* Recommendation */}
                  {(displayData.recommendation || (liveResult && liveResult.recommendation)) && (
                    <div className="space-y-2">
                      <p className="text-sm font-medium">Recommendation</p>
                      <div className="flex items-start gap-2 rounded-lg bg-muted p-3 text-sm">
                        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-yellow-500" />
                        <span>{displayData.recommendation || liveResult?.recommendation}</span>
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
                <div className="flex h-64 items-center justify-center text-muted-foreground">
                  <p>
                    {inputMode === 'live'
                      ? 'Start live streaming to see real-time quality analysis'
                      : 'Upload an image to analyze its quality'}
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
