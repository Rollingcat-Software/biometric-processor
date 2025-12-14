'use client';

import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils/cn';
import { Button } from '@/components/ui/button';

interface ImageUploaderProps {
  onImageSelected: (file: File | null) => void;
  selectedImage: File | null;
  disabled?: boolean;
  maxSize?: number; // in MB
  acceptedFormats?: string[];
}

export function ImageUploader({
  onImageSelected,
  selectedImage,
  disabled = false,
  maxSize = 10,
  acceptedFormats = ['image/jpeg', 'image/png', 'image/webp'],
}: ImageUploaderProps) {
  const { t } = useTranslation();
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(
    (acceptedFiles: File[], rejectedFiles: unknown[]) => {
      setError(null);

      if (rejectedFiles.length > 0) {
        setError(t('upload.invalidFormat'));
        return;
      }

      const file = acceptedFiles[0];
      if (file) {
        if (file.size > maxSize * 1024 * 1024) {
          setError(t('upload.fileTooLarge'));
          return;
        }

        onImageSelected(file);
        const reader = new FileReader();
        reader.onloadend = () => {
          setPreview(reader.result as string);
        };
        reader.readAsDataURL(file);
      }
    },
    [onImageSelected, maxSize, t]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: acceptedFormats.reduce(
      (acc, format) => ({ ...acc, [format]: [] }),
      {}
    ),
    maxFiles: 1,
    disabled,
  });

  const handleRemove = () => {
    onImageSelected(null);
    setPreview(null);
    setError(null);
  };

  return (
    <div className="space-y-4">
      {!selectedImage ? (
        <div
          {...getRootProps()}
          className={cn(
            'relative cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors',
            isDragActive
              ? 'border-primary bg-primary/5'
              : 'border-muted-foreground/25 hover:border-primary/50',
            disabled && 'cursor-not-allowed opacity-50',
            error && 'border-red-500'
          )}
        >
          <input {...getInputProps()} />
          <div className="flex flex-col items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
              <Upload className="h-6 w-6 text-muted-foreground" />
            </div>
            <div>
              <p className="font-medium">{t('upload.dragDrop')}</p>
              <p className="text-sm text-muted-foreground">
                {t('upload.or')}{' '}
                <span className="text-primary">{t('upload.browse')}</span>
              </p>
            </div>
            <p className="text-xs text-muted-foreground">
              {t('upload.maxSize', { size: maxSize })}
            </p>
          </div>
        </div>
      ) : (
        <div className="relative overflow-hidden rounded-lg border">
          <img
            src={preview || ''}
            alt="Selected"
            className="h-64 w-full object-contain bg-muted"
          />
          <Button
            variant="destructive"
            size="icon"
            className="absolute right-2 top-2"
            onClick={handleRemove}
            disabled={disabled}
          >
            <X className="h-4 w-4" />
          </Button>
          <div className="absolute bottom-0 left-0 right-0 bg-black/50 p-2 text-xs text-white">
            <p className="truncate">{selectedImage.name}</p>
            <p>{(selectedImage.size / 1024).toFixed(1)} KB</p>
          </div>
        </div>
      )}

      {error && (
        <p className="text-sm text-red-500">{error}</p>
      )}
    </div>
  );
}
