'use client';

import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import { Grid2X2, Upload, Trash2, AlertCircle, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Slider } from '@/components/ui/slider';
import { Label } from '@/components/ui/label';
import { useDropzone } from 'react-dropzone';
import { useSimilarityMatrix, validateImages } from '@/hooks/use-similarity-matrix';
import { toast } from 'sonner';
import { cn } from '@/lib/utils/cn';
import { formatPercent, toPercent } from '@/lib/utils/format';

interface FileItem {
  file: File;
  preview: string;
  label: string;
  validationStatus?: 'pending' | 'valid' | 'invalid';
  validationError?: string;
}

export default function SimilarityPage() {
  const { t } = useTranslation();
  const [files, setFiles] = useState<FileItem[]>([]);
  const [threshold, setThreshold] = useState(0.6);
  const [isValidating, setIsValidating] = useState(false);

  const { mutate: computeMatrix, isPending, isSuccess, isError, data, error } = useSimilarityMatrix();

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const newFiles = acceptedFiles.map((file) => ({
      file,
      preview: URL.createObjectURL(file),
      label: file.name.split('.')[0],
    }));
    setFiles((prev) => [...prev, ...newFiles].slice(0, 10)); // Max 10 files
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/jpeg': [], 'image/png': [] },
    disabled: isPending,
    maxFiles: 10,
  });

  const handleRemoveFile = (index: number) => {
    setFiles((prev) => {
      const newFiles = [...prev];
      URL.revokeObjectURL(newFiles[index].preview);
      newFiles.splice(index, 1);
      return newFiles;
    });
  };

  const handleValidate = async () => {
    if (files.length < 2) {
      toast.error('Error', { description: 'Add at least 2 images to validate' });
      return;
    }

    setIsValidating(true);

    // Mark all as pending
    setFiles((prev) => prev.map((f) => ({ ...f, validationStatus: 'pending' as const })));

    try {
      const results = await validateImages(
        files.map((f) => f.file),
        files.map((f) => f.label)
      );

      // Update files with validation results
      setFiles((prev) =>
        prev.map((f, index) => {
          const result = results[index];
          return {
            ...f,
            validationStatus: result?.valid ? 'valid' : 'invalid',
            validationError: result?.error,
          };
        })
      );

      const validCount = results.filter((r) => r.valid).length;
      const invalidCount = results.filter((r) => !r.valid).length;

      if (invalidCount > 0) {
        toast.warning('Validation Complete', {
          description: `${validCount} valid, ${invalidCount} invalid images. Remove invalid images to compute matrix.`,
        });
      } else {
        toast.success('Validation Complete', {
          description: `All ${validCount} images are valid. Ready to compute matrix.`,
        });
      }
    } catch (err) {
      toast.error('Validation failed', {
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    } finally {
      setIsValidating(false);
    }
  };

  const handleCompute = () => {
    if (files.length < 2) {
      toast.error('Error', { description: 'Add at least 2 images to compute similarity matrix' });
      return;
    }

    // Check if any files are invalid
    const invalidFiles = files.filter((f) => f.validationStatus === 'invalid');
    if (invalidFiles.length > 0) {
      toast.error('Invalid Images', {
        description: `Remove ${invalidFiles.length} invalid image(s) before computing matrix.`,
      });
      return;
    }

    computeMatrix(
      {
        files: files.map((f) => f.file),
        labels: files.map((f) => f.label),
        threshold,
      },
      {
        onSuccess: (result) => {
          toast.success('Matrix Computed', {
            description: `${result.clusters?.length || 0} cluster(s) found`,
          });
        },
        onError: (err) => {
          toast.error(t('common.error'), { description: err.message });
        },
      }
    );
  };

  const allValidated = files.length > 0 && files.every((f) => f.validationStatus === 'valid' || f.validationStatus === 'invalid');
  const hasInvalidFiles = files.some((f) => f.validationStatus === 'invalid');

  const getColor = (value: number) => {
    const pct = toPercent(value);
    if (pct >= 80) return 'bg-green-500 text-white';
    if (pct >= 60) return 'bg-green-300 text-black';
    if (pct >= 40) return 'bg-yellow-300 text-black';
    if (pct >= 20) return 'bg-orange-300 text-black';
    return 'bg-red-300 text-black';
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
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-fuchsia-500/10">
            <Grid2X2 className="h-5 w-5 text-fuchsia-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Similarity Matrix</h1>
            <p className="text-muted-foreground">Compute NxN similarity between multiple faces</p>
          </div>
        </div>
      </motion.div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Input Section */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
        >
          <Card>
            <CardHeader>
              <CardTitle>Input Images</CardTitle>
              <CardDescription>Add 2-10 face images to compare</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Threshold */}
              <div className="space-y-2">
                <div className="flex justify-between">
                  <Label>Cluster Threshold</Label>
                  <span className="text-sm font-mono">{formatPercent(threshold, 0)}</span>
                </div>
                <Slider
                  value={[threshold]}
                  onValueChange={([v]) => setThreshold(v)}
                  min={0}
                  max={1}
                  step={0.01}
                  disabled={isPending}
                />
              </div>

              {/* Dropzone */}
              <div
                {...getRootProps()}
                className={cn(
                  'border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors',
                  isDragActive ? 'border-primary bg-primary/5' : 'border-muted-foreground/25',
                  isPending && 'cursor-not-allowed opacity-50'
                )}
              >
                <input {...getInputProps()} />
                <Upload className="h-6 w-6 mx-auto mb-2 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  {files.length}/10 images
                </p>
              </div>

              {/* File Grid */}
              {files.length > 0 && (
                <div className="grid grid-cols-3 gap-2">
                  {files.map((item, index) => (
                    <div key={index} className="relative group">
                      <div className={cn(
                        'relative rounded border overflow-hidden',
                        item.validationStatus === 'invalid' && 'border-red-500 border-2',
                        item.validationStatus === 'valid' && 'border-green-500 border-2'
                      )}>
                        <img
                          src={item.preview}
                          alt={item.label}
                          className="w-full h-16 object-cover"
                        />
                        {/* Validation status indicator */}
                        {item.validationStatus === 'pending' && (
                          <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                            <Loader2 className="h-5 w-5 text-white animate-spin" />
                          </div>
                        )}
                        {item.validationStatus === 'valid' && (
                          <div className="absolute top-0.5 left-0.5">
                            <CheckCircle2 className="h-4 w-4 text-green-500 bg-white rounded-full" />
                          </div>
                        )}
                        {item.validationStatus === 'invalid' && (
                          <div className="absolute inset-0 bg-red-500/20 flex items-center justify-center">
                            <XCircle className="h-5 w-5 text-red-500" />
                          </div>
                        )}
                      </div>
                      <button
                        onClick={() => handleRemoveFile(index)}
                        className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity z-10"
                        disabled={isPending || isValidating}
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                      <p className={cn(
                        'text-xs truncate mt-1',
                        item.validationStatus === 'invalid' && 'text-red-500'
                      )}>
                        {item.validationStatus === 'invalid' ? item.validationError || 'Invalid' : item.label}
                      </p>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={handleValidate}
                  disabled={isPending || isValidating || files.length < 2}
                  className="flex-1"
                >
                  {isValidating ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Validating...
                    </>
                  ) : (
                    'Validate Images'
                  )}
                </Button>
                <Button
                  onClick={handleCompute}
                  disabled={isPending || isValidating || files.length < 2 || hasInvalidFiles}
                  className="flex-1"
                >
                  {isPending ? 'Computing...' : 'Compute Matrix'}
                </Button>
              </div>
              {hasInvalidFiles && (
                <p className="text-xs text-red-500 text-center">
                  Remove invalid images (marked in red) before computing matrix
                </p>
              )}
              {files.length >= 2 && !allValidated && !isValidating && (
                <p className="text-xs text-muted-foreground text-center">
                  Click "Validate Images" to check for face detection issues
                </p>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Matrix Visualization */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.2 }}
          className="lg:col-span-2"
        >
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Similarity Matrix</CardTitle>
              <CardDescription>
                {isSuccess && data
                  ? `${data.matrix.length}x${data.matrix.length} matrix`
                  : 'Matrix will be displayed here'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isSuccess && data && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="space-y-4"
                >
                  {/* Matrix Table */}
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr>
                          <th className="p-2"></th>
                          {data.labels.map((label: string, i: number) => (
                            <th key={i} className="p-2 font-medium truncate max-w-20">
                              {label}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {data.matrix.map((row: number[], i: number) => (
                          <tr key={i}>
                            <td className="p-2 font-medium truncate max-w-20">
                              {data.labels[i]}
                            </td>
                            {row.map((value: number, j: number) => (
                              <td key={j} className="p-1">
                                <div
                                  className={cn(
                                    'p-2 rounded text-center text-xs font-mono',
                                    getColor(value)
                                  )}
                                >
                                  {formatPercent(value, 0)}
                                </div>
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Clusters */}
                  {data.clusters && data.clusters.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-sm font-medium">Identified Clusters</p>
                      <div className="flex flex-wrap gap-2">
                        {data.clusters.map((cluster) => (
                          <Badge key={cluster.cluster_id} variant="outline">
                            Cluster {cluster.cluster_id + 1}: {cluster.members.join(', ')}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </motion.div>
              )}

              {isError && error && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-red-600">
                    <AlertCircle className="h-5 w-5" />
                    <span className="font-medium">An error occurred</span>
                  </div>
                  <div className="rounded-lg bg-red-50 p-4 text-red-800 dark:bg-red-950/50 dark:text-red-200">
                    <p>{error.message}</p>
                    {error.message.includes('face') && (
                      <p className="mt-2 text-sm opacity-80">
                        Tip: Remove images without clear, front-facing faces and try again.
                        All images must contain a detectable face.
                      </p>
                    )}
                  </div>
                </div>
              )}

              {!isSuccess && !isError && (
                <div className="flex h-64 flex-col items-center justify-center gap-4 text-muted-foreground">
                  <Grid2X2 className="h-12 w-12" />
                  <p>Add images and compute to see similarity matrix</p>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
