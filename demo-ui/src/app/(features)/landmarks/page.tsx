'use client';

import { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import { Eye, Upload, Camera, AlertCircle, Maximize2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { ImageUploader } from '@/components/media/image-uploader';
import { WebcamCapture } from '@/components/media/webcam-capture';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useLandmarkDetection } from '@/hooks/use-landmark-detection';
import { toast } from 'sonner';

export default function LandmarksPage() {
  const { t } = useTranslation();
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [capturedImage, setCapturedImage] = useState<Blob | null>(null);
  const [inputMode, setInputMode] = useState<'upload' | 'camera'>('upload');
  const [include3D, setInclude3D] = useState(false);
  const [showOverlay, setShowOverlay] = useState(true);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);

  const { mutate: detectLandmarks, isPending, isSuccess, isError, data, error, reset } = useLandmarkDetection();

  const handleDetect = () => {
    const image = inputMode === 'upload' ? selectedImage : capturedImage;

    if (!image) {
      toast.error(t('common.error'), {
        description: 'Please select or capture an image',
      });
      return;
    }

    detectLandmarks(
      { image, include_3d: include3D },
      {
        onSuccess: (result) => {
          toast.success('Detection Complete', {
            description: `Detected ${result.landmark_count} landmarks`,
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

  // Draw landmarks on canvas
  useEffect(() => {
    if (!isSuccess || !data || !canvasRef.current || !imageRef.current || !showOverlay) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const img = imageRef.current;

    if (!ctx) return;

    // Set canvas size to match image
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw landmarks
    ctx.fillStyle = '#22c55e';
    data.landmarks.forEach((point) => {
      ctx.beginPath();
      ctx.arc(point.x * canvas.width, point.y * canvas.height, 2, 0, Math.PI * 2);
      ctx.fill();
    });

    // Draw connections for facial regions
    const regionColors: Record<string, string> = {
      left_eye: '#3b82f6',
      right_eye: '#3b82f6',
      nose: '#f59e0b',
      mouth: '#ef4444',
      left_eyebrow: '#8b5cf6',
      right_eyebrow: '#8b5cf6',
      face_contour: '#6b7280',
    };

    if (data.regions) {
      Object.entries(data.regions).forEach(([region, points]) => {
        if (points && Array.isArray(points)) {
          ctx.strokeStyle = regionColors[region] || '#22c55e';
          ctx.lineWidth = 1;
          ctx.beginPath();
          points.forEach((point, i) => {
            if (point) {
              const x = point.x * canvas.width;
              const y = point.y * canvas.height;
              if (i === 0) ctx.moveTo(x, y);
              else ctx.lineTo(x, y);
            }
          });
          ctx.stroke();
        }
      });
    }
  }, [isSuccess, data, showOverlay]);

  const imageUrl = selectedImage
    ? URL.createObjectURL(selectedImage)
    : capturedImage
    ? URL.createObjectURL(capturedImage)
    : null;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-500/10">
            <Eye className="h-5 w-5 text-indigo-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Facial Landmarks</h1>
            <p className="text-muted-foreground">Detect 468 facial landmark points</p>
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
                Upload or capture an image for landmark detection
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Options */}
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Switch
                    id="include3d"
                    checked={include3D}
                    onCheckedChange={setInclude3D}
                    disabled={isPending}
                  />
                  <Label htmlFor="include3d">Include 3D coordinates</Label>
                </div>
              </div>

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
                  onClick={handleDetect}
                  disabled={isPending || (!selectedImage && !capturedImage)}
                  className="flex-1"
                >
                  {isPending ? (
                    <>
                      <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                      Detecting...
                    </>
                  ) : (
                    <>
                      <Eye className="mr-2 h-4 w-4" />
                      Detect Landmarks
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
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Landmark Visualization</CardTitle>
                  <CardDescription>
                    {isSuccess && data
                      ? `${data.landmark_count} landmarks detected`
                      : 'Detected points will be displayed here'}
                  </CardDescription>
                </div>
                {isSuccess && data && (
                  <div className="flex items-center space-x-2">
                    <Switch
                      id="showOverlay"
                      checked={showOverlay}
                      onCheckedChange={setShowOverlay}
                    />
                    <Label htmlFor="showOverlay">Show overlay</Label>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {isSuccess && data && imageUrl && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="space-y-4"
                >
                  {/* Image with overlay */}
                  <div className="relative overflow-hidden rounded-lg border">
                    <img
                      ref={imageRef}
                      src={imageUrl}
                      alt="Analyzed"
                      className="w-full"
                      onLoad={() => {
                        // Trigger re-render for canvas
                        if (canvasRef.current) {
                          const event = new Event('load');
                          canvasRef.current.dispatchEvent(event);
                        }
                      }}
                    />
                    <canvas
                      ref={canvasRef}
                      className={`absolute inset-0 w-full h-full ${showOverlay ? '' : 'hidden'}`}
                    />
                  </div>

                  {/* Stats */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="rounded-lg border p-3">
                      <p className="text-sm text-muted-foreground">Model</p>
                      <p className="font-semibold">{data.model || 'MediaPipe'}</p>
                    </div>
                    <div className="rounded-lg border p-3">
                      <p className="text-sm text-muted-foreground">Points</p>
                      <p className="font-semibold">{data.landmark_count}</p>
                    </div>
                  </div>

                  {/* Head Pose */}
                  {data.head_pose && (
                    <div className="rounded-lg border p-3">
                      <p className="text-sm font-medium mb-2">Head Pose</p>
                      <div className="grid grid-cols-3 gap-2 text-sm">
                        <div>
                          <span className="text-muted-foreground">Yaw:</span>{' '}
                          <span className="font-mono">{data.head_pose.yaw?.toFixed(1)}°</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Pitch:</span>{' '}
                          <span className="font-mono">{data.head_pose.pitch?.toFixed(1)}°</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Roll:</span>{' '}
                          <span className="font-mono">{data.head_pose.roll?.toFixed(1)}°</span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Regions */}
                  {data.regions && (
                    <div className="flex flex-wrap gap-2">
                      {Object.keys(data.regions).map((region) => (
                        <Badge key={region} variant="secondary">
                          {region.replace(/_/g, ' ')}
                        </Badge>
                      ))}
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
                <div className="flex h-64 flex-col items-center justify-center gap-4 text-muted-foreground">
                  <Maximize2 className="h-12 w-12" />
                  <p>Upload an image to detect facial landmarks</p>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
