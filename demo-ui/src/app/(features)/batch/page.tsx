'use client';

import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import { Grid3X3, Upload, AlertCircle, CheckCircle2, XCircle, Play, Trash2, FileImage } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { useDropzone } from 'react-dropzone';
import { useBatchProcess } from '@/hooks/use-batch-process';
import { toast } from 'sonner';
import { cn } from '@/lib/utils/cn';

type BatchOperation = 'enroll' | 'verify' | 'quality' | 'demographics';

interface FileItem {
  file: File;
  preview: string;
  status: 'pending' | 'processing' | 'success' | 'error';
  result?: unknown;
  error?: string;
}

export default function BatchPage() {
  const { t } = useTranslation();
  const [files, setFiles] = useState<FileItem[]>([]);
  const [operation, setOperation] = useState<BatchOperation>('quality');
  const [skipDuplicates, setSkipDuplicates] = useState(true);

  const { mutate: processBatch, isPending, isSuccess, data, reset } = useBatchProcess();

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const newFiles = acceptedFiles.map((file) => ({
      file,
      preview: URL.createObjectURL(file),
      status: 'pending' as const,
    }));
    setFiles((prev) => [...prev, ...newFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/jpeg': [],
      'image/png': [],
      'image/webp': [],
    },
    disabled: isPending,
  });

  const handleRemoveFile = (index: number) => {
    setFiles((prev) => {
      const newFiles = [...prev];
      URL.revokeObjectURL(newFiles[index].preview);
      newFiles.splice(index, 1);
      return newFiles;
    });
  };

  const handleClearAll = () => {
    files.forEach((f) => URL.revokeObjectURL(f.preview));
    setFiles([]);
    reset();
  };

  const handleProcess = () => {
    if (files.length === 0) {
      toast.error(t('common.error'), {
        description: 'Please add images to process',
      });
      return;
    }

    processBatch(
      {
        files: files.map((f) => f.file),
        operation,
        skip_duplicates: skipDuplicates,
      },
      {
        onSuccess: (result) => {
          toast.success('Batch Processing Complete', {
            description: `${result.successful} successful, ${result.failed} failed`,
          });
          // Update file statuses
          setFiles((prev) =>
            prev.map((f, i) => ({
              ...f,
              status: result.results?.[i]?.success ? 'success' : 'error',
              result: result.results?.[i]?.result,
              error: result.errors?.find((e) => e.index === i)?.error,
            }))
          );
        },
        onError: (err) => {
          toast.error(t('common.error'), {
            description: err.message,
          });
        },
      }
    );
  };

  const successCount = files.filter((f) => f.status === 'success').length;
  const errorCount = files.filter((f) => f.status === 'error').length;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-yellow-500/10">
            <Grid3X3 className="h-5 w-5 text-yellow-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Batch Processing</h1>
            <p className="text-muted-foreground">Process multiple images at once</p>
          </div>
        </div>
      </motion.div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Settings */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
        >
          <Card>
            <CardHeader>
              <CardTitle>Settings</CardTitle>
              <CardDescription>Configure batch operation</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Operation</Label>
                <Select
                  value={operation}
                  onValueChange={(v) => setOperation(v as BatchOperation)}
                  disabled={isPending}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="enroll">Enrollment</SelectItem>
                    <SelectItem value="verify">Verification</SelectItem>
                    <SelectItem value="quality">Quality Analysis</SelectItem>
                    <SelectItem value="demographics">Demographics</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {operation === 'enroll' && (
                <div className="flex items-center space-x-2">
                  <Switch
                    id="skipDuplicates"
                    checked={skipDuplicates}
                    onCheckedChange={setSkipDuplicates}
                    disabled={isPending}
                  />
                  <Label htmlFor="skipDuplicates">Skip duplicates</Label>
                </div>
              )}

              <div className="pt-4 space-y-2">
                <Button
                  onClick={handleProcess}
                  disabled={isPending || files.length === 0}
                  className="w-full"
                >
                  {isPending ? (
                    <>
                      <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                      Processing...
                    </>
                  ) : (
                    <>
                      <Play className="mr-2 h-4 w-4" />
                      Process {files.length} Image{files.length !== 1 ? 's' : ''}
                    </>
                  )}
                </Button>
                <Button
                  variant="outline"
                  onClick={handleClearAll}
                  disabled={isPending || files.length === 0}
                  className="w-full"
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Clear All
                </Button>
              </div>

              {/* Stats */}
              {files.length > 0 && (
                <div className="space-y-2 pt-4 border-t">
                  <p className="text-sm font-medium">Progress</p>
                  <Progress
                    value={((successCount + errorCount) / files.length) * 100}
                    className="h-2"
                  />
                  <div className="flex justify-between text-sm">
                    <span className="text-green-600">{successCount} success</span>
                    <span className="text-red-600">{errorCount} failed</span>
                    <span className="text-muted-foreground">
                      {files.length - successCount - errorCount} pending
                    </span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* File Upload & Grid */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.2 }}
          className="lg:col-span-2"
        >
          <Card>
            <CardHeader>
              <CardTitle>Images</CardTitle>
              <CardDescription>
                {files.length > 0
                  ? `${files.length} image${files.length !== 1 ? 's' : ''} selected`
                  : 'Drag and drop images or click to browse'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Dropzone */}
              <div
                {...getRootProps()}
                className={cn(
                  'border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors',
                  isDragActive
                    ? 'border-primary bg-primary/5'
                    : 'border-muted-foreground/25 hover:border-primary/50',
                  isPending && 'cursor-not-allowed opacity-50'
                )}
              >
                <input {...getInputProps()} />
                <Upload className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  {isDragActive
                    ? 'Drop images here...'
                    : 'Drag & drop images, or click to select'}
                </p>
              </div>

              {/* File Grid */}
              {files.length > 0 && (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 max-h-96 overflow-y-auto">
                  {files.map((item, index) => (
                    <div
                      key={index}
                      className="relative group rounded-lg border overflow-hidden"
                    >
                      <img
                        src={item.preview}
                        alt={`Image ${index + 1}`}
                        className="w-full h-24 object-cover"
                      />
                      <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                        <Button
                          variant="destructive"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => handleRemoveFile(index)}
                          disabled={isPending}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                      {/* Status Badge */}
                      <div className="absolute top-1 right-1">
                        {item.status === 'success' && (
                          <Badge variant="success" className="h-5 w-5 p-0 flex items-center justify-center">
                            <CheckCircle2 className="h-3 w-3" />
                          </Badge>
                        )}
                        {item.status === 'error' && (
                          <Badge variant="destructive" className="h-5 w-5 p-0 flex items-center justify-center">
                            <XCircle className="h-3 w-3" />
                          </Badge>
                        )}
                        {item.status === 'processing' && (
                          <Badge className="h-5 w-5 p-0 flex items-center justify-center">
                            <span className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
                          </Badge>
                        )}
                      </div>
                      {/* Filename */}
                      <div className="absolute bottom-0 left-0 right-0 bg-black/60 px-1 py-0.5">
                        <p className="text-xs text-white truncate">
                          {item.file.name}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {files.length === 0 && (
                <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                  <FileImage className="h-12 w-12 mb-2" />
                  <p>No images selected</p>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
