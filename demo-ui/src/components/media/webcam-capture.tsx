'use client';

import { useCallback, useRef, useState, useEffect } from 'react';
import { Camera, CameraOff, RefreshCw, Check, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils/cn';
import { Button } from '@/components/ui/button';
import { useAppStore } from '@/lib/store/app-store';

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
    try {
      const { width, height } = getResolutionConstraints();
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: cameraFacingMode,
          width: { ideal: width },
          height: { ideal: height },
        },
        audio: false,
      });

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
        } else {
          setError(err.message);
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

  const captureImage = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.drawImage(video, 0, 0);
      canvas.toBlob(
        (blob) => {
          if (blob) {
            onCapture(blob);
            setCapturedPreview(URL.createObjectURL(blob));
            stopCamera();
          }
        },
        'image/jpeg',
        0.9
      );
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
