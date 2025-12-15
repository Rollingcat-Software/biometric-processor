'use client';

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import { Users, Upload, Camera, AlertCircle, User } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { ImageUploader } from '@/components/media/image-uploader';
import { WebcamCapture } from '@/components/media/webcam-capture';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useDemographicsAnalysis } from '@/hooks/use-demographics-analysis';
import { toast } from 'sonner';
import { formatPercent, toPercent } from '@/lib/utils/format';

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
  const [inputMode, setInputMode] = useState<'upload' | 'camera'>('upload');

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
    reset();
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
              {isSuccess && data && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="space-y-6"
                >
                  {/* Age */}
                  <div className="rounded-lg border p-4">
                    <div className="flex items-center gap-3">
                      <User className="h-8 w-8 text-primary" />
                      <div>
                        <p className="text-sm text-muted-foreground">{t('demographics.results.age')}</p>
                        <p className="text-2xl font-bold">{data.age} years</p>
                        <p className="text-sm text-muted-foreground">
                          Range: {data.age_range.min} - {data.age_range.max}
                        </p>
                      </div>
                    </div>
                    <div className="mt-2">
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>Confidence</span>
                        <span>{formatPercent(data.age_confidence, 0)}</span>
                      </div>
                      <Progress value={toPercent(data.age_confidence)} className="h-1 mt-1" />
                    </div>
                  </div>

                  {/* Gender */}
                  <div className="rounded-lg border p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-muted-foreground">{t('demographics.results.gender')}</p>
                        <p className="text-2xl font-bold capitalize">{data.gender}</p>
                      </div>
                      <Badge variant={data.gender === 'male' ? 'default' : 'secondary'}>
                        {formatPercent(data.gender_confidence, 0)} confident
                      </Badge>
                    </div>
                  </div>

                  {/* Emotion */}
                  <div className="rounded-lg border p-4">
                    <p className="text-sm text-muted-foreground mb-3">{t('demographics.results.emotion')}</p>
                    <div className="flex items-center gap-3 mb-4">
                      <span className="text-4xl">{emotionEmojis[data.dominant_emotion] || '😐'}</span>
                      <div>
                        <p className="text-xl font-bold capitalize">{data.dominant_emotion}</p>
                        <p className="text-sm text-muted-foreground">
                          {formatPercent(data.emotion_confidence, 0)} confident
                        </p>
                      </div>
                    </div>

                    {/* Emotion Breakdown */}
                    {data.emotion_scores && (
                      <div className="space-y-2">
                        {Object.entries(data.emotion_scores)
                          .sort(([, a], [, b]) => (b as number) - (a as number))
                          .map(([emotion, score]) => (
                            <div key={emotion} className="flex items-center gap-2">
                              <span className="w-6">{emotionEmojis[emotion] || '😐'}</span>
                              <span className="w-20 text-sm capitalize">{emotion}</span>
                              <Progress value={toPercent(score as number)} className="h-2 flex-1" />
                              <span className="w-12 text-right text-sm">
                                {formatPercent(score as number, 0)}
                              </span>
                            </div>
                          ))}
                      </div>
                    )}
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

              {!isSuccess && !isError && (
                <div className="flex h-64 flex-col items-center justify-center gap-4 text-muted-foreground">
                  <Users className="h-12 w-12" />
                  <p>Upload an image to analyze demographics</p>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
