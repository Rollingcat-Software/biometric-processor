'use client';

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import { Activity, Upload, Camera, AlertCircle, CheckCircle2, AlertTriangle, XCircle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { ImageUploader } from '@/components/media/image-uploader';
import { WebcamCapture } from '@/components/media/webcam-capture';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useQualityAnalysis } from '@/hooks/use-quality-analysis';
import { toast } from 'sonner';

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
  const [inputMode, setInputMode] = useState<'upload' | 'camera'>('upload');

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
            description: `Quality Grade: ${result.grade.toUpperCase()}`,
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
    reset();
  };

  const gradeConfig = data?.grade ? qualityGradeConfig[data.grade as keyof typeof qualityGradeConfig] : null;
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
                onValueChange={(v) => setInputMode(v as 'upload' | 'camera')}
              >
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="upload" className="flex items-center gap-2">
                    <Upload className="h-4 w-4" />
                    Upload
                  </TabsTrigger>
                  <TabsTrigger value="camera" className="flex items-center gap-2">
                    <Camera className="h-4 w-4" />
                    Camera
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
              </Tabs>

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
              {isSuccess && data && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="space-y-6"
                >
                  {/* Overall Grade */}
                  <div className={`flex items-center gap-3 rounded-lg p-4 ${gradeConfig?.bg}`}>
                    <GradeIcon className={`h-8 w-8 ${gradeConfig?.color}`} />
                    <div>
                      <p className={`text-lg font-semibold ${gradeConfig?.color}`}>
                        {t(`quality.levels.${data.grade}`)}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        Overall Score: {(data.overall_score * 100).toFixed(1)}%
                      </p>
                    </div>
                  </div>

                  {/* Quality Metrics */}
                  <div className="space-y-3">
                    <p className="text-sm font-medium">Quality Metrics</p>
                    {data.metrics && Object.entries(data.metrics).map(([key, value]) => (
                      <div key={key} className="space-y-1">
                        <div className="flex justify-between text-sm">
                          <span className="capitalize">{t(`quality.metrics.${key}`) || key.replace(/_/g, ' ')}</span>
                          <span className="font-mono">{((value as number) * 100).toFixed(0)}%</span>
                        </div>
                        <Progress value={(value as number) * 100} className="h-2" />
                      </div>
                    ))}
                  </div>

                  {/* Recommendations */}
                  {data.recommendations && data.recommendations.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-sm font-medium">Recommendations</p>
                      <ul className="space-y-1">
                        {data.recommendations.map((rec, index) => (
                          <li key={index} className="flex items-start gap-2 text-sm text-muted-foreground">
                            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-yellow-500" />
                            {rec}
                          </li>
                        ))}
                      </ul>
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

              {!isSuccess && !isError && (
                <div className="flex h-64 items-center justify-center text-muted-foreground">
                  <p>Upload an image to analyze its quality</p>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
