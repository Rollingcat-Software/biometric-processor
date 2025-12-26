'use client';

import { useCallback, useRef, useState, useEffect } from 'react';
import { Camera, CameraOff, RefreshCw, Check, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils/cn';
import { Button } from '@/components/ui/button';
import { useAppStore } from '@/lib/store/app-store';
import { compressImage, getCompressionStats } from '@/lib/utils/image-compression';

interface WebcamCaptureProps {
  onCapture: (image: Blob | null) => void;
  capturedImage: Blob | null;
  disabled?: boolean;
}

export function WebcamCapture({
  onCapture,
  capturedImage,
  disabled = false,
}: WebcamCaptureProps) {
  const { t } = useTranslation();
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [capturedPreview, setCapturedPreview] = useState<string | null>(null);

  const { cameraFacingMode, cameraResolution } = useAppStore();

  const getResolutionConstraints = () => {
    switch (cameraResolution) {
      case 'fhd':
        return { width: 1920, height: 1080 };
      case '4k':
        return { width: 3840, height: 2160 };
      default:
        return { width: 1280, height: 720 };
    }
  };

  const startCamera = useCallback(async () => {
    setError(null);

    // Check if mediaDevices is available
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setError('Camera API not available. Please use a modern browser with HTTPS.');
      return;
    }

    try {
      const { width, height } = getResolutionConstraints();

      // Try with ideal resolution first, fallback to basic constraints
      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: cameraFacingMode,
            width: { ideal: width },
            height: { ideal: height },
          },
          audio: false,
        });
      } catch {
        // Fallback to basic video constraints if specific resolution fails
        stream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: false,
        });
      }

      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setIsStreaming(true);
      }
    } catch (err) {
      if (err instanceof Error) {
        if (err.name === 'NotAllowedError') {
          setError(t('camera.permissionDenied'));
        } else if (err.name === 'NotFoundError') {
          setError(t('camera.notSupported'));
        } else if (err.name === 'NotReadableError' || err.message.includes('video source')) {
          setError('Camera is in use by another application. Please close other apps using the camera and try again.');
        } else if (err.name === 'OverconstrainedError') {
          setError('Camera does not support requested resolution. Please try different camera settings.');
        } else {
          setError(`Camera error: ${err.message}`);
        }
      }
    }
  }, [cameraFacingMode, cameraResolution, t]);

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsStreaming(false);
  }, []);

  const captureImage = useCallback(async () => {
    if (!videoRef.current || !canvasRef.current) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.drawImage(video, 0, 0);

      try {
        // First, convert canvas to blob
        const rawBlob = await new Promise<Blob>((resolve, reject) => {
          canvas.toBlob(
            (blob) => {
              if (blob) {
                resolve(blob);
              } else {
                reject(new Error('Failed to capture image'));
              }
            },
            'image/jpeg',
            1.0
          );
        });

        // Then compress the blob (reduces 5-10MB to ~500KB)
        const compressedBlob = await compressImage(
          new File([rawBlob], 'webcam-capture.jpg', { type: 'image/jpeg' }),
          {
            maxWidth: 1920,
            maxHeight: 1080,
            quality: 0.85,
            mimeType: 'image/jpeg',
          }
        );

        // Log compression stats in development
        if (process.env.NODE_ENV === 'development') {
          const stats = getCompressionStats(rawBlob.size, compressedBlob.size);
          console.log('[Webcam Compression]', {
            original: `${(rawBlob.size / 1024).toFixed(1)} KB`,
            compressed: `${(compressedBlob.size / 1024).toFixed(1)} KB`,
            reduction: `${stats.reduction}%`,
          });
        }

        onCapture(compressedBlob);
        setCapturedPreview(URL.createObjectURL(compressedBlob));
        stopCamera();
      } catch (err) {
        console.error('Image capture/compression failed:', err);
        setError('Failed to capture image. Please try again.');
      }
    }
  }, [onCapture, stopCamera]);

  const handleRetake = () => {
    onCapture(null);
    setCapturedPreview(null);
    startCamera();
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopCamera();
      if (capturedPreview) {
        URL.revokeObjectURL(capturedPreview);
      }
    };
  }, [stopCamera, capturedPreview]);

  return (
    <div className="space-y-4">
      <div className="relative overflow-hidden rounded-lg bg-black">
        {!capturedImage ? (
          <>
            <video
              ref={videoRef}
              className={cn(
                'h-64 w-full object-cover',
                !isStreaming && 'hidden'
              )}
              autoPlay
              playsInline
              muted
            />
            {!isStreaming && (
              <div className="flex h-64 flex-col items-center justify-center gap-4 bg-muted">
                {error ? (
                  <>
                    <CameraOff className="h-12 w-12 text-muted-foreground" />
                    <p className="text-sm text-red-500">{error}</p>
                    <Button onClick={startCamera} disabled={disabled}>
                      <RefreshCw className="mr-2 h-4 w-4" />
                      {t('common.retry')}
                    </Button>
                  </>
                ) : (
                  <>
                    <Camera className="h-12 w-12 text-muted-foreground" />
                    <Button onClick={startCamera} disabled={disabled}>
                      <Camera className="mr-2 h-4 w-4" />
                      {t('camera.start')}
                    </Button>
                  </>
                )}
              </div>
            )}
          </>
        ) : (
          <img
            src={capturedPreview || ''}
            alt="Captured"
            className="h-64 w-full object-cover"
          />
        )}
      </div>

      <canvas ref={canvasRef} className="hidden" />

      <div className="flex gap-2">
        {isStreaming && !capturedImage && (
          <>
            <Button
              onClick={captureImage}
              disabled={disabled}
              className="flex-1"
            >
              <Check className="mr-2 h-4 w-4" />
              {t('camera.capture')}
            </Button>
            <Button
              variant="outline"
              onClick={stopCamera}
              disabled={disabled}
            >
              <X className="mr-2 h-4 w-4" />
              {t('camera.stop')}
            </Button>
          </>
        )}

        {capturedImage && (
          <Button
            variant="outline"
            onClick={handleRetake}
            disabled={disabled}
            className="flex-1"
          >
            <RefreshCw className="mr-2 h-4 w-4" />
            {t('camera.retake')}
          </Button>
        )}
      </div>
    </div>
  );
}
