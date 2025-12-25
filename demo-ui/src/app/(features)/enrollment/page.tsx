'use client';

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import { UserPlus, Upload, Camera, CheckCircle2, AlertCircle, Images, User } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ImageUploader } from '@/components/media/image-uploader';
import { WebcamCapture } from '@/components/media/webcam-capture';
import { MultiImageUploader } from '@/components/media/multi-image-uploader';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Switch } from '@/components/ui/switch';
import { Progress } from '@/components/ui/progress';
import { useFaceEnrollment } from '@/hooks/use-face-enrollment';
import { useMultiImageEnrollment } from '@/hooks/use-multi-image-enrollment';
import { toast } from 'sonner';

type EnrollmentMode = 'single' | 'multi';
type InputMode = 'upload' | 'camera';

export default function EnrollmentPage() {
  const { t } = useTranslation();
  const [personId, setPersonId] = useState('');
  const [enrollmentMode, setEnrollmentMode] = useState<EnrollmentMode>('single');
  const [inputMode, setInputMode] = useState<InputMode>('upload');

  // Single image state
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [capturedImage, setCapturedImage] = useState<Blob | null>(null);

  // Multi-image state
  const [selectedImages, setSelectedImages] = useState<File[]>([]);

  // Hooks
  const {
    mutate: enrollSingle,
    isPending: isSinglePending,
    isSuccess: isSingleSuccess,
    isError: isSingleError,
    data: singleData,
    error: singleError,
    reset: resetSingle,
  } = useFaceEnrollment();

  const {
    mutate: enrollMulti,
    isPending: isMultiPending,
    isSuccess: isMultiSuccess,
    isError: isMultiError,
    data: multiData,
    error: multiError,
    reset: resetMulti,
  } = useMultiImageEnrollment();

  const isPending = isSinglePending || isMultiPending;
  const isSuccess = isSingleSuccess || isMultiSuccess;
  const isError = isSingleError || isMultiError;
  const error = singleError || multiError;

  const handleEnrollSingle = () => {
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

    enrollSingle(
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

  const handleEnrollMulti = () => {
    if (!personId.trim()) {
      toast.error('Enrollment Error', {
        description: 'Person ID is required',
      });
      return;
    }

    if (selectedImages.length < 2) {
      toast.error('Enrollment Error', {
        description: 'Please select at least 2 images',
      });
      return;
    }

    enrollMulti(
      {
        user_id: personId,
        files: selectedImages,
      },
      {
        onSuccess: (result) => {
          toast.success('Multi-Image Enrollment Successful!', {
            description: `Enrolled with ${result.images_processed} images. Aggregate quality: ${(result.aggregate_quality_score * 100).toFixed(1)}%`,
          });
        },
        onError: (err) => {
          toast.error('Enrollment Error', {
            description: err.message,
          });
        },
      }
    );
  };

  const handleEnroll = () => {
    if (enrollmentMode === 'single') {
      handleEnrollSingle();
    } else {
      handleEnrollMulti();
    }
  };

  const handleReset = () => {
    setPersonId('');
    setSelectedImage(null);
    setCapturedImage(null);
    setSelectedImages([]);
    resetSingle();
    resetMulti();
  };

  const handleModeChange = (checked: boolean) => {
    setEnrollmentMode(checked ? 'multi' : 'single');
    // Reset state when switching modes
    setSelectedImage(null);
    setCapturedImage(null);
    setSelectedImages([]);
    resetSingle();
    resetMulti();
  };

  const canEnroll = enrollmentMode === 'single'
    ? (selectedImage !== null || capturedImage !== null)
    : selectedImages.length >= 2;

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
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/10">
              <UserPlus className="h-5 w-5 text-blue-500" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">{t('enrollment.title')}</h1>
              <p className="text-muted-foreground">{t('enrollment.description')}</p>
            </div>
          </div>

          {/* Mode Toggle */}
          <div className="flex items-center gap-3 rounded-lg border bg-card p-3">
            <User className={enrollmentMode === 'single' ? 'h-5 w-5 text-primary' : 'h-5 w-5 text-muted-foreground'} />
            <Switch
              checked={enrollmentMode === 'multi'}
              onCheckedChange={handleModeChange}
              disabled={isPending}
            />
            <Images className={enrollmentMode === 'multi' ? 'h-5 w-5 text-primary' : 'h-5 w-5 text-muted-foreground'} />
            <div className="ml-2">
              <p className="text-sm font-medium">
                {enrollmentMode === 'multi' ? 'Multi-Image' : 'Single Image'}
              </p>
              <p className="text-xs text-muted-foreground">
                {enrollmentMode === 'multi' ? 'Higher accuracy' : 'Quick enrollment'}
              </p>
            </div>
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
              <CardTitle>
                {enrollmentMode === 'multi' ? 'Select Multiple Images' : t('enrollment.selectImage')}
              </CardTitle>
              <CardDescription>
                {enrollmentMode === 'multi'
                  ? 'Upload 2-5 face images for improved accuracy'
                  : 'Upload an image or use your camera to capture a face'}
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

              {/* Image Input */}
              {enrollmentMode === 'single' ? (
                <Tabs
                  value={inputMode}
                  onValueChange={(v) => setInputMode(v as InputMode)}
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
              ) : (
                <MultiImageUploader
                  onImagesSelected={setSelectedImages}
                  selectedImages={selectedImages}
                  disabled={isPending}
                  minImages={2}
                  maxImages={5}
                />
              )}

              {/* Action Buttons */}
              <div className="flex gap-2 pt-4">
                <Button
                  onClick={handleEnroll}
                  disabled={isPending || !canEnroll}
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
                      {enrollmentMode === 'multi' ? 'Enroll with Multi-Image' : t('enrollment.enrollButton')}
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
              {/* Single Image Success */}
              {isSingleSuccess && singleData && (
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
                      <span className="font-mono text-sm">{singleData.face_id}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Person ID</span>
                      <span className="font-mono text-sm">{singleData.person_id}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Quality Score</span>
                      <span className="font-semibold">
                        {(singleData.quality_score * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </motion.div>
              )}

              {/* Multi-Image Success */}
              {isMultiSuccess && multiData && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="space-y-4"
                >
                  <div className="flex items-center gap-2 text-green-600">
                    <CheckCircle2 className="h-5 w-5" />
                    <span className="font-medium">Multi-Image Enrollment Successful!</span>
                  </div>

                  <div className="space-y-3 rounded-lg bg-muted p-4">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Person ID</span>
                      <span className="font-mono text-sm">{multiData.user_id}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Images Processed</span>
                      <span className="font-semibold">{multiData.images_processed}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Aggregate Quality</span>
                      <span className="font-semibold">
                        {(multiData.aggregate_quality_score * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Best Image</span>
                      <span className="font-semibold">#{multiData.best_embedding_index + 1}</span>
                    </div>
                  </div>

                  {/* Per-image quality scores */}
                  <div className="space-y-2">
                    <p className="text-sm font-medium">Individual Image Quality:</p>
                    <div className="space-y-2">
                      {multiData.image_results.map((result) => (
                        <div key={result.index} className="space-y-1">
                          <div className="flex items-center justify-between text-sm">
                            <span className="text-muted-foreground">
                              Image {result.index + 1}
                              {result.index === multiData.best_embedding_index && (
                                <span className="ml-1 text-xs text-green-600">(Best)</span>
                              )}
                            </span>
                            <span className="font-mono">
                              {(result.quality_score * 100).toFixed(1)}%
                            </span>
                          </div>
                          <Progress value={result.quality_score * 100} className="h-1.5" />
                          {result.issues.length > 0 && (
                            <p className="text-xs text-orange-600">
                              {result.issues.join(', ')}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </motion.div>
              )}

              {/* Error State */}
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

              {/* Empty State */}
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
