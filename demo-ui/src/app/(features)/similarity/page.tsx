'use client';

import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import { Grid2X2, Upload, Trash2, AlertCircle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Slider } from '@/components/ui/slider';
import { Label } from '@/components/ui/label';
import { useDropzone } from 'react-dropzone';
import { useSimilarityMatrix } from '@/hooks/use-similarity-matrix';
import { toast } from 'sonner';
import { cn } from '@/lib/utils/cn';

interface FileItem {
  file: File;
  preview: string;
  label: string;
}

export default function SimilarityPage() {
  const { t } = useTranslation();
  const [files, setFiles] = useState<FileItem[]>([]);
  const [threshold, setThreshold] = useState(0.6);

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

  const handleCompute = () => {
    if (files.length < 2) {
      toast.error('Error', { description: 'Add at least 2 images to compute similarity matrix' });
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

  const getColor = (value: number) => {
    if (value >= 0.8) return 'bg-green-500 text-white';
    if (value >= 0.6) return 'bg-green-300 text-black';
    if (value >= 0.4) return 'bg-yellow-300 text-black';
    if (value >= 0.2) return 'bg-orange-300 text-black';
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
                  <span className="text-sm font-mono">{(threshold * 100).toFixed(0)}%</span>
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
                      <img
                        src={item.preview}
                        alt={item.label}
                        className="w-full h-16 object-cover rounded border"
                      />
                      <button
                        onClick={() => handleRemoveFile(index)}
                        className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                        disabled={isPending}
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                      <p className="text-xs truncate mt-1">{item.label}</p>
                    </div>
                  ))}
                </div>
              )}

              <Button
                onClick={handleCompute}
                disabled={isPending || files.length < 2}
                className="w-full"
              >
                {isPending ? 'Computing...' : 'Compute Matrix'}
              </Button>
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
                                  {(value * 100).toFixed(0)}%
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
                        {data.clusters.map((cluster: string[], index: number) => (
                          <Badge key={index} variant="outline">
                            Cluster {index + 1}: {cluster.join(', ')}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </motion.div>
              )}

              {isError && error && (
                <div className="flex items-center gap-2 text-red-600">
                  <AlertCircle className="h-5 w-5" />
                  <span>{error.message}</span>
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
