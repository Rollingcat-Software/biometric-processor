'use client';

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import { GitCompare, AlertCircle, CheckCircle2, XCircle, ArrowLeftRight } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { Label } from '@/components/ui/label';
import { ImageUploader } from '@/components/media/image-uploader';
import { SimilarityGauge } from '@/components/biometric/similarity-gauge';
import { useFaceComparison } from '@/hooks/use-face-comparison';
import { toast } from 'sonner';

export default function ComparisonPage() {
  const { t } = useTranslation();
  const [image1, setImage1] = useState<File | null>(null);
  const [image2, setImage2] = useState<File | null>(null);
  const [threshold, setThreshold] = useState(0.6);

  const { mutate: compareFaces, isPending, isSuccess, isError, data, error, reset } = useFaceComparison();

  const handleCompare = () => {
    if (!image1 || !image2) {
      toast.error(t('common.error'), {
        description: 'Please select both images',
      });
      return;
    }

    compareFaces(
      { image1, image2, threshold },
      {
        onSuccess: (result) => {
          if (result.match) {
            toast.success('Match Found', {
              description: `Similarity: ${(result.similarity * 100).toFixed(1)}%`,
            });
          } else {
            toast.info('No Match', {
              description: `Similarity: ${(result.similarity * 100).toFixed(1)}%`,
            });
          }
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
    setImage1(null);
    setImage2(null);
    reset();
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
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-violet-500/10">
            <GitCompare className="h-5 w-5 text-violet-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Face Comparison</h1>
            <p className="text-muted-foreground">Compare two face images directly without enrollment</p>
          </div>
        </div>
      </motion.div>

      {/* Threshold Setting */}
      <Card>
        <CardContent className="pt-6">
          <div className="space-y-2">
            <div className="flex justify-between">
              <Label>Match Threshold</Label>
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
            <p className="text-xs text-muted-foreground">
              Faces with similarity above this threshold are considered a match
            </p>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Image 1 */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
        >
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Image 1</CardTitle>
              <CardDescription>First face image</CardDescription>
            </CardHeader>
            <CardContent>
              <ImageUploader
                onImageSelected={setImage1}
                selectedImage={image1}
                disabled={isPending}
              />
            </CardContent>
          </Card>
        </motion.div>

        {/* Result / Compare Button */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.2 }}
          className="flex flex-col items-center justify-center"
        >
          {isSuccess && data ? (
            <div className="space-y-4 text-center">
              {/* Match Status */}
              <div className={`flex items-center justify-center gap-2 ${
                data.match ? 'text-green-600' : 'text-red-600'
              }`}>
                {data.match ? (
                  <CheckCircle2 className="h-8 w-8" />
                ) : (
                  <XCircle className="h-8 w-8" />
                )}
                <span className="text-xl font-bold">
                  {data.match ? 'MATCH' : 'NO MATCH'}
                </span>
              </div>

              {/* Similarity Gauge */}
              <SimilarityGauge
                value={data.similarity}
                threshold={threshold}
                size="lg"
              />

              {/* Details */}
              <div className="space-y-1 text-sm">
                <p>
                  <span className="text-muted-foreground">Similarity:</span>{' '}
                  <span className="font-semibold">{(data.similarity * 100).toFixed(2)}%</span>
                </p>
                <p>
                  <span className="text-muted-foreground">Threshold:</span>{' '}
                  <span className="font-mono">{(threshold * 100).toFixed(0)}%</span>
                </p>
              </div>

              <Button variant="outline" onClick={handleReset} className="mt-4">
                Compare Again
              </Button>
            </div>
          ) : (
            <div className="space-y-4 text-center">
              <ArrowLeftRight className="h-16 w-16 text-muted-foreground mx-auto" />
              <Button
                onClick={handleCompare}
                disabled={isPending || !image1 || !image2}
                size="lg"
              >
                {isPending ? (
                  <>
                    <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                    Comparing...
                  </>
                ) : (
                  <>
                    <GitCompare className="mr-2 h-4 w-4" />
                    Compare Faces
                  </>
                )}
              </Button>
              <p className="text-sm text-muted-foreground">
                Select both images to compare
              </p>
            </div>
          )}

          {isError && error && (
            <div className="space-y-4 text-center">
              <div className="flex items-center justify-center gap-2 text-red-600">
                <AlertCircle className="h-6 w-6" />
                <span className="font-medium">Error</span>
              </div>
              <p className="text-sm text-red-600">{error.message}</p>
              <Button variant="outline" onClick={handleReset}>
                Try Again
              </Button>
            </div>
          )}
        </motion.div>

        {/* Image 2 */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.3 }}
        >
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Image 2</CardTitle>
              <CardDescription>Second face image</CardDescription>
            </CardHeader>
            <CardContent>
              <ImageUploader
                onImageSelected={setImage2}
                selectedImage={image2}
                disabled={isPending}
              />
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
