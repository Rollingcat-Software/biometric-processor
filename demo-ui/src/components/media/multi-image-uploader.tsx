/**
 * Multi-image uploader component for enrollment
 *
 * Allows selecting 2-5 images with preview and management
 */

'use client';

import { useCallback, useState } from 'react';
import { Upload, X, AlertCircle, CheckCircle2, Image as ImageIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';

export interface MultiImageUploaderProps {
  onImagesSelected: (files: File[]) => void;
  selectedImages: File[];
  disabled?: boolean;
  minImages?: number;
  maxImages?: number;
}

export function MultiImageUploader({
  onImagesSelected,
  selectedImages,
  disabled = false,
  minImages = 2,
  maxImages = 5,
}: MultiImageUploaderProps) {
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const validateAndAddFiles = useCallback(
    (newFiles: File[]) => {
      setError(null);

      // Filter for images only
      const imageFiles = newFiles.filter((file) =>
        file.type.startsWith('image/')
      );

      if (imageFiles.length !== newFiles.length) {
        setError('Only image files are allowed');
      }

      // Check total count
      const totalFiles = selectedImages.length + imageFiles.length;
      if (totalFiles > maxImages) {
        setError(`Maximum ${maxImages} images allowed. You can add ${maxImages - selectedImages.length} more.`);
        return;
      }

      // Validate file sizes (max 10MB per image)
      const oversizedFiles = imageFiles.filter((file) => file.size > 10 * 1024 * 1024);
      if (oversizedFiles.length > 0) {
        setError('Some files exceed 10MB size limit');
        return;
      }

      // Add new files
      onImagesSelected([...selectedImages, ...imageFiles]);
    },
    [selectedImages, maxImages, onImagesSelected]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragActive(false);

      if (disabled) return;

      const files = Array.from(e.dataTransfer.files);
      validateAndAddFiles(files);
    },
    [disabled, validateAndAddFiles]
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (disabled) return;

      const files = Array.from(e.target.files || []);
      validateAndAddFiles(files);

      // Reset input
      e.target.value = '';
    },
    [disabled, validateAndAddFiles]
  );

  const removeImage = useCallback(
    (index: number) => {
      const newImages = selectedImages.filter((_, i) => i !== index);
      onImagesSelected(newImages);
      setError(null);
    },
    [selectedImages, onImagesSelected]
  );

  const isValidCount = selectedImages.length >= minImages && selectedImages.length <= maxImages;
  const canAddMore = selectedImages.length < maxImages;

  return (
    <div className="space-y-4">
      {/* Upload area */}
      <div
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        className={cn(
          'relative rounded-lg border-2 border-dashed p-8 text-center transition-colors',
          dragActive && !disabled && 'border-primary bg-primary/5',
          !dragActive && !disabled && 'border-muted-foreground/25 hover:border-primary/50',
          disabled && 'cursor-not-allowed opacity-50',
          !canAddMore && 'opacity-50'
        )}
      >
        <input
          type="file"
          multiple
          accept="image/*"
          onChange={handleChange}
          disabled={disabled || !canAddMore}
          className="absolute inset-0 cursor-pointer opacity-0"
          id="multi-image-input"
        />

        <div className="flex flex-col items-center gap-2">
          <div className={cn(
            'rounded-full p-3',
            canAddMore ? 'bg-primary/10' : 'bg-muted'
          )}>
            <Upload className={cn(
              'h-8 w-8',
              canAddMore ? 'text-primary' : 'text-muted-foreground'
            )} />
          </div>

          {canAddMore ? (
            <>
              <div className="space-y-1">
                <p className="text-sm font-medium">
                  Drop images here or click to browse
                </p>
                <p className="text-xs text-muted-foreground">
                  Select {minImages}-{maxImages} face images ({selectedImages.length}/{maxImages} selected)
                </p>
              </div>

              <p className="text-xs text-muted-foreground mt-2">
                Supports: JPG, PNG, WEBP (max 10MB each)
              </p>
            </>
          ) : (
            <p className="text-sm font-medium text-muted-foreground">
              Maximum {maxImages} images reached
            </p>
          )}
        </div>
      </div>

      {/* Status message */}
      {selectedImages.length > 0 && (
        <div className={cn(
          'flex items-center gap-2 rounded-lg border p-3 text-sm',
          isValidCount
            ? 'border-green-200 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200'
            : 'border-orange-200 bg-orange-50 text-orange-800 dark:border-orange-800 dark:bg-orange-950 dark:text-orange-200'
        )}>
          {isValidCount ? (
            <>
              <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
              <span>
                {selectedImages.length} images selected. Ready to enroll!
              </span>
            </>
          ) : (
            <>
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              <span>
                Select at least {minImages} images to continue ({selectedImages.length}/{minImages})
              </span>
            </>
          )}
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Image previews */}
      {selectedImages.length > 0 && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-5">
          {selectedImages.map((file, index) => (
            <ImagePreview
              key={`${file.name}-${index}`}
              file={file}
              index={index}
              onRemove={() => removeImage(index)}
              disabled={disabled}
            />
          ))}

          {/* Add more placeholder */}
          {canAddMore && !disabled && (
            <label
              htmlFor="multi-image-input"
              className="group relative flex aspect-square cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/25 bg-muted/20 transition-colors hover:border-primary hover:bg-primary/5"
            >
              <Upload className="h-8 w-8 text-muted-foreground transition-colors group-hover:text-primary" />
              <p className="mt-2 text-xs text-muted-foreground">Add more</p>
            </label>
          )}
        </div>
      )}

      {/* Instructions */}
      {selectedImages.length === 0 && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-800 dark:bg-blue-950">
          <h4 className="mb-2 font-medium text-blue-900 dark:text-blue-100">
            Tips for best results:
          </h4>
          <ul className="space-y-1 text-sm text-blue-800 dark:text-blue-200">
            <li>• Use 3-5 images for optimal accuracy</li>
            <li>• Capture different angles (front, slight left, slight right)</li>
            <li>• Ensure good lighting and clear face visibility</li>
            <li>• Use neutral expressions</li>
            <li>• Avoid glasses, hats, or face coverings</li>
          </ul>
        </div>
      )}
    </div>
  );
}

/**
 * Image preview component with remove button
 */
interface ImagePreviewProps {
  file: File;
  index: number;
  onRemove: () => void;
  disabled: boolean;
}

function ImagePreview({ file, index, onRemove, disabled }: ImagePreviewProps) {
  const [preview, setPreview] = useState<string>('');

  // Generate preview URL
  useState(() => {
    const objectUrl = URL.createObjectURL(file);
    setPreview(objectUrl);

    return () => URL.revokeObjectURL(objectUrl);
  });

  return (
    <Card className="group relative overflow-hidden">
      <div className="aspect-square">
        {preview ? (
          <img
            src={preview}
            alt={`Preview ${index + 1}`}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center bg-muted">
            <ImageIcon className="h-12 w-12 text-muted-foreground" />
          </div>
        )}
      </div>

      {/* Image number badge */}
      <div className="absolute left-2 top-2 flex h-6 w-6 items-center justify-center rounded-full bg-black/60 text-xs font-medium text-white">
        {index + 1}
      </div>

      {/* Remove button */}
      {!disabled && (
        <Button
          type="button"
          variant="destructive"
          size="icon"
          className="absolute right-2 top-2 h-7 w-7 opacity-0 transition-opacity group-hover:opacity-100"
          onClick={onRemove}
        >
          <X className="h-4 w-4" />
        </Button>
      )}

      {/* File name tooltip */}
      <div className="absolute bottom-0 left-0 right-0 bg-black/60 px-2 py-1 opacity-0 transition-opacity group-hover:opacity-100">
        <p className="truncate text-xs text-white" title={file.name}>
          {file.name}
        </p>
      </div>
    </Card>
  );
}
