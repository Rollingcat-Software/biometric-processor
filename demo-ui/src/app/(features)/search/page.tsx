'use client';

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import { Search, Upload, Camera, Users, AlertCircle, Video } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import { ImageUploader } from '@/components/media/image-uploader';
import { WebcamCapture } from '@/components/media/webcam-capture';
import { LiveCameraStream } from '@/components/media/live-camera-stream';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useFaceSearch } from '@/hooks/use-face-search';
import { toast } from 'sonner';
import { formatPercent, toPercent } from '@/lib/utils/format';
import type { LiveAnalysisResult } from '@/hooks/use-live-camera-analysis';

export default function SearchPage() {
  const { t } = useTranslation();
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [capturedImage, setCapturedImage] = useState<Blob | null>(null);
  const [inputMode, setInputMode] = useState<'upload' | 'camera' | 'live'>('upload');
  const [maxResults, setMaxResults] = useState(10);
  const [threshold, setThreshold] = useState(0.6);
  const [liveResult, setLiveResult] = useState<LiveAnalysisResult | null>(null);

  const { mutate: searchFace, isPending, isSuccess, isError, data, error, reset } = useFaceSearch();

  const handleSearch = () => {
    const image = inputMode === 'upload' ? selectedImage : capturedImage;

    if (!image) {
      toast.error(t('common.error'), {
        description: 'Please select or capture an image',
      });
      return;
    }

    searchFace(
      { image, max_results: maxResults, threshold },
      {
        onSuccess: (result) => {
          toast.success('Search Complete', {
            description: `Found ${result.matches.length} match(es)`,
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
    setLiveResult(null);
    reset();
  };

  const handleLiveResult = (result: LiveAnalysisResult) => {
    setLiveResult(result);
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
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-500/10">
            <Search className="h-5 w-5 text-purple-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">{t('search.title')}</h1>
            <p className="text-muted-foreground">{t('search.description')}</p>
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
              <CardTitle>Search Query</CardTitle>
              <CardDescription>
                Upload or capture a face to search in the database
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Search Parameters */}
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>Max Results: {maxResults}</Label>
                  <Slider
                    value={[maxResults]}
                    onValueChange={([v]) => setMaxResults(v)}
                    min={1}
                    max={100}
                    step={1}
                    disabled={isPending}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Threshold: {formatPercent(threshold, 0)}</Label>
                  <Slider
                    value={[threshold]}
                    onValueChange={([v]) => setThreshold(v)}
                    min={0}
                    max={1}
                    step={0.01}
                    disabled={isPending}
                  />
                </div>
              </div>

              {/* Image Input Tabs */}
              <Tabs
                value={inputMode}
                onValueChange={(v) => setInputMode(v as 'upload' | 'camera' | 'live')}
              >
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger value="upload" className="flex items-center gap-2">
                    <Upload className="h-4 w-4" />
                    Upload
                  </TabsTrigger>
                  <TabsTrigger value="camera" className="flex items-center gap-2">
                    <Camera className="h-4 w-4" />
                    Camera
                  </TabsTrigger>
                  <TabsTrigger value="live" className="flex items-center gap-2">
                    <Video className="h-4 w-4" />
                    Live Stream
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
                <TabsContent value="live" className="mt-4">
                  <LiveCameraStream
                    mode="search"
                    onResult={handleLiveResult}
                    disabled={isPending}
                  />
                </TabsContent>
              </Tabs>

              {/* Action Buttons */}
              {inputMode !== 'live' && (
                <div className="flex gap-2 pt-4">
                  <Button
                    onClick={handleSearch}
                    disabled={isPending || (!selectedImage && !capturedImage)}
                    className="flex-1"
                  >
                    {isPending ? (
                      <>
                        <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                        {t('search.searching')}
                      </>
                    ) : (
                      <>
                        <Search className="mr-2 h-4 w-4" />
                        {t('search.searchButton')}
                      </>
                    )}
                  </Button>
                  {(isSuccess || isError) && (
                    <Button variant="outline" onClick={handleReset}>
                      {t('common.reset')}
                    </Button>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Results Section */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.2 }}
        >
          <Card className="h-full">
            <CardHeader>
              <CardTitle>{t('search.results')}</CardTitle>
              <CardDescription>
                {isSuccess && data
                  ? `${data.matches.length} match(es) found`
                  : 'Matching faces will appear here'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {/* Live Stream Results */}
              {inputMode === 'live' && liveResult?.search && (
                <motion.div
                  key={liveResult.frame_number}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.2 }}
                  className="space-y-4"
                >
                  {/* Live Mode Indicator */}
                  <div className="flex items-center justify-between rounded-lg bg-blue-50 p-3 text-sm dark:bg-blue-950/50">
                    <div className="flex items-center gap-2">
                      <Video className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                      <span className="font-medium text-blue-900 dark:text-blue-100">Live Analysis</span>
                    </div>
                    <div className="text-blue-700 dark:text-blue-300">
                      Frame #{liveResult.frame_number} • {liveResult.processing_time_ms.toFixed(0)}ms
                    </div>
                  </div>

                  {/* Live Search Result */}
                  {liveResult.search.found ? (
                    <div className="rounded-lg bg-green-500/10 p-4">
                      <p className="text-2xl font-bold text-green-600">✓ Match Found</p>
                      <div className="mt-3 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-muted-foreground">User ID</span>
                          <span className="font-medium">{liveResult.search.user_id}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-muted-foreground">Confidence</span>
                          <span className={`font-semibold ${
                            toPercent(liveResult.search.confidence) >= 80 ? 'text-green-600' :
                            toPercent(liveResult.search.confidence) >= 60 ? 'text-yellow-600' :
                            'text-red-600'
                          }`}>
                            {formatPercent(liveResult.search.confidence)}
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-muted-foreground">Similarity</span>
                          <span className="font-mono text-sm">{formatPercent(liveResult.search.similarity)}</span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="rounded-lg bg-orange-500/10 p-4">
                      <p className="text-2xl font-bold text-orange-600">No Match</p>
                      <p className="mt-2 text-sm text-muted-foreground">
                        Searched {liveResult.search.num_candidates} candidate{liveResult.search.num_candidates !== 1 ? 's' : ''}
                      </p>
                    </div>
                  )}
                </motion.div>
              )}

              {/* Static Results */}
              {inputMode !== 'live' && isSuccess && data && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="space-y-3"
                >
                  {data.matches.length > 0 ? (
                    <div className="max-h-96 space-y-2 overflow-y-auto">
                      {data.matches.map((match, index) => (
                        <motion.div
                          key={`${match.user_id}-${index}`}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: index * 0.05 }}
                          className="flex items-center justify-between rounded-lg border p-3"
                        >
                          <div className="flex items-center gap-3">
                            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted">
                              <Users className="h-5 w-5 text-muted-foreground" />
                            </div>
                            <div>
                              <p className="font-medium">{match.user_id}</p>
                              <p className="text-xs text-muted-foreground">
                                Rank: #{match.rank}
                              </p>
                            </div>
                          </div>
                          <div className="text-right">
                            <p className={`font-semibold ${
                              toPercent(match.similarity) >= 80 ? 'text-green-600' :
                              toPercent(match.similarity) >= 60 ? 'text-yellow-600' :
                              'text-red-600'
                            }`}>
                              {formatPercent(match.similarity)}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              similarity
                            </p>
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex h-40 items-center justify-center text-muted-foreground">
                      <p>{t('search.noResults')}</p>
                    </div>
                  )}

                  {/* Stats */}
                  <div className="pt-2 text-sm text-muted-foreground">
                    Searched {data.total_searched} face{data.total_searched !== 1 ? 's' : ''}
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

              {!liveResult && !isSuccess && !isError && (
                <div className="flex h-64 items-center justify-center text-muted-foreground">
                  <p>
                    {inputMode === 'live'
                      ? 'Start live streaming to search for matching faces'
                      : 'Upload an image to search for matching faces'}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
