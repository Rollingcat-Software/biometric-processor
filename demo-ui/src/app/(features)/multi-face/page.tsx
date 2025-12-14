'use client';

import { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import { Users2, Upload, Camera, AlertCircle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Slider } from '@/components/ui/slider';
import { Label } from '@/components/ui/label';
import { ImageUploader } from '@/components/media/image-uploader';
import { WebcamCapture } from '@/components/media/webcam-capture';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useMultiFaceDetection } from '@/hooks/use-multi-face-detection';
import { toast } from 'sonner';

export default function MultiFacePage() {
  const { t } = useTranslation();
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [capturedImage, setCapturedImage] = useState<Blob | null>(null);
  const [inputMode, setInputMode] = useState<'upload' | 'camera'>('upload');
  const [maxFaces, setMaxFaces] = useState(10);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);

  const { mutate: detectFaces, isPending, isSuccess, isError, data, error, reset } = useMultiFaceDetection();

  const handleDetect = () => {
    const image = inputMode === 'upload' ? selectedImage : capturedImage;

    if (!image) {
      toast.error(t('common.error'), {
        description: 'Please select or capture an image',
      });
      return;
    }

    detectFaces(
      { image, max_faces: maxFaces },
      {
        onSuccess: (result) => {
          toast.success('Detection Complete', {
            description: `Found ${result.faces.length} face(s)`,
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

  // Draw bounding boxes on canvas
  useEffect(() => {
    if (!isSuccess || !data || !canvasRef.current || !imageRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const img = imageRef.current;

    if (!ctx) return;

    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw bounding boxes
    data.faces.forEach((face: any, index: number) => {
      const { x, y, width, height } = face.bounding_box;
      const scaledX = x * canvas.width;
      const scaledY = y * canvas.height;
      const scaledWidth = width * canvas.width;
      const scaledHeight = height * canvas.height;

      // Box
      ctx.strokeStyle = '#22c55e';
      ctx.lineWidth = 3;
      ctx.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight);

      // Label background
      ctx.fillStyle = '#22c55e';
      ctx.fillRect(scaledX, scaledY - 25, 80, 25);

      // Label text
      ctx.fillStyle = '#ffffff';
      ctx.font = '14px sans-serif';
      ctx.fillText(`Face ${index + 1}`, scaledX + 5, scaledY - 8);

      // Confidence
      ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
      ctx.fillRect(scaledX, scaledY + scaledHeight, 80, 20);
      ctx.fillStyle = '#ffffff';
      ctx.font = '12px sans-serif';
      ctx.fillText(`${(face.confidence * 100).toFixed(0)}%`, scaledX + 5, scaledY + scaledHeight + 15);
    });
  }, [isSuccess, data]);

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
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-rose-500/10">
            <Users2 className="h-5 w-5 text-rose-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Multi-Face Detection</h1>
            <p className="text-muted-foreground">Detect all faces in an image</p>
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
              <CardDescription>Upload an image with multiple faces</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Max Faces Slider */}
              <div className="space-y-2">
                <div className="flex justify-between">
                  <Label>Max Faces to Detect</Label>
                  <span className="text-sm font-mono">{maxFaces}</span>
                </div>
                <Slider
                  value={[maxFaces]}
                  onValueChange={([v]) => setMaxFaces(v)}
                  min={1}
                  max={50}
                  step={1}
                  disabled={isPending}
                />
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
                      <Users2 className="mr-2 h-4 w-4" />
                      Detect Faces
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
              <CardTitle>Detection Results</CardTitle>
              <CardDescription>
                {isSuccess && data
                  ? `${data.faces.length} face(s) detected`
                  : 'Detected faces will be shown here'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isSuccess && data && imageUrl && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="space-y-4"
                >
                  {/* Image with bounding boxes */}
                  <div className="relative overflow-hidden rounded-lg border">
                    <img
                      ref={imageRef}
                      src={imageUrl}
                      alt="Analyzed"
                      className="w-full"
                    />
                    <canvas
                      ref={canvasRef}
                      className="absolute inset-0 w-full h-full"
                    />
                  </div>

                  {/* Face List */}
                  <div className="space-y-2">
                    <p className="text-sm font-medium">Detected Faces</p>
                    <div className="grid grid-cols-2 gap-2">
                      {data.faces.map((face: any, index: number) => (
                        <div
                          key={index}
                          className="rounded-lg border p-2 text-sm"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-medium">Face {index + 1}</span>
                            <Badge variant="outline">
                              {(face.confidence * 100).toFixed(0)}%
                            </Badge>
                          </div>
                          {face.quality_score && (
                            <p className="text-xs text-muted-foreground">
                              Quality: {(face.quality_score * 100).toFixed(0)}%
                            </p>
                          )}
                        </div>
                      ))}
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

              {!isSuccess && !isError && (
                <div className="flex h-64 flex-col items-center justify-center gap-4 text-muted-foreground">
                  <Users2 className="h-12 w-12" />
                  <p>Upload an image to detect multiple faces</p>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
