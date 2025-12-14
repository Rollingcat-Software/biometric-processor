'use client';

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import { UserPlus, Upload, Camera, CheckCircle2, AlertCircle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ImageUploader } from '@/components/media/image-uploader';
import { WebcamCapture } from '@/components/media/webcam-capture';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useFaceEnrollment } from '@/hooks/use-face-enrollment';
import { toast } from 'sonner';

export default function EnrollmentPage() {
  const { t } = useTranslation();
  const [personId, setPersonId] = useState('');
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [capturedImage, setCapturedImage] = useState<Blob | null>(null);
  const [inputMode, setInputMode] = useState<'upload' | 'camera'>('upload');

  const { mutate: enrollFace, isPending, isSuccess, isError, data, error, reset } = useFaceEnrollment();

  const handleEnroll = () => {
    const image = inputMode === 'upload' ? selectedImage : capturedImage;

    if (!personId.trim()) {
      toast.error(t('enrollment.error'), {
        description: 'Person ID is required',
      });
      return;
    }

    if (!image) {
      toast.error(t('enrollment.error'), {
        description: 'Please select or capture an image',
      });
      return;
    }

    enrollFace(
      { person_id: personId, image },
      {
        onSuccess: (result) => {
          toast.success(t('enrollment.success'), {
            description: `Face enrolled with quality score: ${(result.quality_score * 100).toFixed(1)}%`,
          });
        },
        onError: (err) => {
          toast.error(t('enrollment.error'), {
            description: err.message,
          });
        },
      }
    );
  };

  const handleReset = () => {
    setPersonId('');
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
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/10">
            <UserPlus className="h-5 w-5 text-blue-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">{t('enrollment.title')}</h1>
            <p className="text-muted-foreground">{t('enrollment.description')}</p>
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
              <CardTitle>{t('enrollment.selectImage')}</CardTitle>
              <CardDescription>
                Upload an image or use your camera to capture a face
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Person ID Input */}
              <div className="space-y-2">
                <Label htmlFor="personId">{t('enrollment.personId')}</Label>
                <Input
                  id="personId"
                  value={personId}
                  onChange={(e) => setPersonId(e.target.value)}
                  placeholder={t('enrollment.personIdPlaceholder')}
                  disabled={isPending}
                />
              </div>

              {/* Image Input Tabs */}
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

              {/* Action Buttons */}
              <div className="flex gap-2 pt-4">
                <Button
                  onClick={handleEnroll}
                  disabled={isPending || (!selectedImage && !capturedImage)}
                  className="flex-1"
                >
                  {isPending ? (
                    <>
                      <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                      {t('enrollment.enrolling')}
                    </>
                  ) : (
                    <>
                      <UserPlus className="mr-2 h-4 w-4" />
                      {t('enrollment.enrollButton')}
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
              <CardTitle>Result</CardTitle>
              <CardDescription>
                Enrollment result will appear here
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isSuccess && data && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="space-y-4"
                >
                  <div className="flex items-center gap-2 text-green-600">
                    <CheckCircle2 className="h-5 w-5" />
                    <span className="font-medium">{t('enrollment.success')}</span>
                  </div>
                  <div className="space-y-2 rounded-lg bg-muted p-4">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Face ID</span>
                      <span className="font-mono text-sm">{data.face_id}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Person ID</span>
                      <span className="font-mono text-sm">{data.person_id}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Quality Score</span>
                      <span className="font-semibold">
                        {(data.quality_score * 100).toFixed(1)}%
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
                    <span className="font-medium">{t('enrollment.error')}</span>
                  </div>
                  <div className="rounded-lg bg-red-50 p-4 text-red-800 dark:bg-red-950/50 dark:text-red-200">
                    {error.message}
                  </div>
                </motion.div>
              )}

              {!isSuccess && !isError && (
                <div className="flex h-40 items-center justify-center text-muted-foreground">
                  <p>Enter details and click enroll to see results</p>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
