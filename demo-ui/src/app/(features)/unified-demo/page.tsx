'use client';

import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Sparkles,
  Upload,
  Camera,
  Video,
  FileStack,
  Play,
  Square,
  Settings2,
  Info,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ImageUploader } from '@/components/media/image-uploader';
import { WebcamCapture } from '@/components/media/webcam-capture';
import { EnhancedLiveStream } from '@/components/demo/enhanced-live-stream';
import { toast } from 'sonner';
import type { LiveAnalysisResult, AnalysisMode } from '@/hooks/use-live-camera-analysis';
import { AnalysisResultRenderer } from '@/components/demo/analysis-result-renderer';
import { API_CONFIG } from '@/config/api.config';

// Analysis mode configuration
const ANALYSIS_MODES: {
  value: AnalysisMode;
  label: string;
  description: string;
  icon: string;
  color: string;
}[] = [
  {
    value: 'face_detection',
    label: 'Face Detection',
    description: 'Detect and locate faces in images',
    icon: '👤',
    color: 'blue',
  },
  {
    value: 'quality',
    label: 'Quality Analysis',
    description: 'Assess image quality (blur, brightness, sharpness)',
    icon: '⭐',
    color: 'cyan',
  },
  {
    value: 'demographics',
    label: 'Demographics',
    description: 'Estimate age, gender, and emotion',
    icon: '📊',
    color: 'purple',
  },
  {
    value: 'liveness',
    label: 'Liveness Detection',
    description: 'Detect if face is real person or spoof',
    icon: '🔒',
    color: 'green',
  },
  {
    value: 'enrollment_ready',
    label: 'Enrollment Ready',
    description: 'Check if image is ready for enrollment',
    icon: '✅',
    color: 'emerald',
  },
  {
    value: 'verification',
    label: 'Face Verification (1:1)',
    description: 'Verify identity against enrolled user',
    icon: '🔑',
    color: 'indigo',
  },
  {
    value: 'search',
    label: 'Face Search (1:N)',
    description: 'Search for face in database',
    icon: '🔍',
    color: 'violet',
  },
  {
    value: 'landmarks',
    label: 'Facial Landmarks',
    description: 'Detect 468 facial landmark points',
    icon: '📍',
    color: 'pink',
  },
  {
    value: 'full',
    label: 'Full Analysis',
    description: 'Run all analyses (comprehensive)',
    icon: '🎯',
    color: 'orange',
  },
];

type InputMode = 'upload' | 'batch' | 'camera' | 'live';

export default function UnifiedDemoPage() {
  const { t } = useTranslation();

  // Analysis configuration
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>('quality');
  const [inputMode, setInputMode] = useState<InputMode>('upload');

  // Input states
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [batchImages, setBatchImages] = useState<File[]>([]);
  const [capturedImage, setCapturedImage] = useState<Blob | null>(null);
  const [liveResult, setLiveResult] = useState<LiveAnalysisResult | null>(null);

  // Processing states
  const [isProcessing, setIsProcessing] = useState(false);
  const [singleResult, setSingleResult] = useState<any>(null);
  const [batchResults, setBatchResults] = useState<any[]>([]);

  // Get current mode config
  const currentModeConfig = ANALYSIS_MODES.find((m) => m.value === analysisMode);

  // Handle live stream results
  const handleLiveResult = useCallback((result: LiveAnalysisResult) => {
    setLiveResult(result);
  }, []);

  // Handle single image analysis
  const handleAnalyzeSingle = async () => {
    const image = inputMode === 'upload' ? selectedImage : capturedImage;
    if (!image) {
      toast.error('Please select or capture an image');
      return;
    }

    setIsProcessing(true);
    setSingleResult(null);

    try {
      // Call appropriate API endpoint based on analysis mode
      const formData = new FormData();
      formData.append('file', image);

      const endpoint = getEndpointForMode(analysisMode);
      const response = await fetch(`${API_CONFIG.BASE_URL}${endpoint}`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const data = await response.json();
      setSingleResult(data);
      toast.success('Analysis complete!');
    } catch (error: any) {
      console.error('Analysis error:', error);
      toast.error(`Analysis failed: ${error.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  // Handle batch image analysis
  const handleAnalyzeBatch = async () => {
    if (batchImages.length === 0) {
      toast.error('Please select images for batch processing');
      return;
    }

    setIsProcessing(true);
    setBatchResults([]);

    const results = [];
    const total = batchImages.length;

    for (let i = 0; i < batchImages.length; i++) {
      const image = batchImages[i];
      toast.info(`Processing ${i + 1}/${total}: ${image.name}`);

      try {
        const formData = new FormData();
        formData.append('file', image);

        const endpoint = getEndpointForMode(analysisMode);
        const response = await fetch(`${API_CONFIG.BASE_URL}${endpoint}`, {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          throw new Error(`API error: ${response.statusText}`);
        }

        const data = await response.json();
        results.push({ image: image.name, result: data, success: true });
      } catch (error: any) {
        console.error(`Error processing ${image.name}:`, error);
        results.push({ image: image.name, error: error.message, success: false });
      }
    }

    setBatchResults(results);
    setIsProcessing(false);
    toast.success(`Batch processing complete! ${results.filter((r) => r.success).length}/${total} successful`);
  };

  // Get API endpoint for mode
  const getEndpointForMode = (mode: AnalysisMode): string => {
    switch (mode) {
      case 'face_detection':
        return '/api/v1/faces/detect-all';
      case 'quality':
        return '/api/v1/quality/analyze';
      case 'demographics':
        return '/api/v1/demographics/analyze';
      case 'liveness':
        return '/api/v1/liveness';
      case 'enrollment_ready':
        return '/api/v1/quality/analyze';
      case 'verification':
        return '/api/v1/verify';
      case 'search':
        return '/api/v1/search';
      case 'landmarks':
        return '/api/v1/landmarks/detect';
      case 'full':
        return '/api/v1/quality/analyze';
      default:
        return '/api/v1/quality/analyze';
    }
  };

  // Handle reset
  const handleReset = () => {
    setSelectedImage(null);
    setBatchImages([]);
    setCapturedImage(null);
    setLiveResult(null);
    setSingleResult(null);
    setBatchResults([]);
  };

  // Handle batch file selection
  const handleBatchFilesSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setBatchImages(Array.from(e.target.files));
    }
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
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-purple-500 to-pink-500">
            <Sparkles className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Unified Demo Center</h1>
            <p className="text-muted-foreground">
              All biometric features in one place - flexible input, comprehensive analysis
            </p>
          </div>
        </div>
      </motion.div>

      {/* Configuration Panel */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.1 }}
      >
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings2 className="h-5 w-5" />
              Analysis Configuration
            </CardTitle>
            <CardDescription>Select the type of analysis you want to perform</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Analysis Mode Selector */}
            <div className="space-y-2">
              <Label>Analysis Type</Label>
              <Select value={analysisMode} onValueChange={(v) => setAnalysisMode(v as AnalysisMode)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ANALYSIS_MODES.map((mode) => (
                    <SelectItem key={mode.value} value={mode.value}>
                      <div className="flex items-center gap-2">
                        <span>{mode.icon}</span>
                        <span>{mode.label}</span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Mode Info */}
            {currentModeConfig && (
              <div className="flex items-start gap-2 rounded-lg bg-muted/50 p-3 text-sm">
                <Info className="mt-0.5 h-4 w-4 shrink-0 text-blue-500" />
                <div>
                  <p className="font-medium">{currentModeConfig.label}</p>
                  <p className="text-muted-foreground">{currentModeConfig.description}</p>
                </div>
              </div>
            )}

            <Separator />

            {/* Input Mode Selector */}
            <div className="space-y-2">
              <Label>Input Method</Label>
              <Tabs value={inputMode} onValueChange={(v) => setInputMode(v as InputMode)}>
                <TabsList className="grid w-full grid-cols-4">
                  <TabsTrigger value="upload" className="flex items-center gap-1.5">
                    <Upload className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Single</span>
                  </TabsTrigger>
                  <TabsTrigger value="batch" className="flex items-center gap-1.5">
                    <FileStack className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Batch</span>
                  </TabsTrigger>
                  <TabsTrigger value="camera" className="flex items-center gap-1.5">
                    <Camera className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Camera</span>
                  </TabsTrigger>
                  <TabsTrigger value="live" className="flex items-center gap-1.5">
                    <Video className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Live</span>
                  </TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Main Content Grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Input Section */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.2 }}
        >
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Input</CardTitle>
              <CardDescription>
                {inputMode === 'upload' && 'Upload a single image'}
                {inputMode === 'batch' && 'Upload multiple images for batch processing'}
                {inputMode === 'camera' && 'Capture an image from your camera'}
                {inputMode === 'live' && 'Live stream from your camera'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Upload Single */}
              {inputMode === 'upload' && (
                <ImageUploader
                  onImageSelected={setSelectedImage}
                  selectedImage={selectedImage}
                  disabled={isProcessing}
                />
              )}

              {/* Upload Batch */}
              {inputMode === 'batch' && (
                <div className="space-y-3">
                  <input
                    type="file"
                    multiple
                    accept="image/*"
                    onChange={handleBatchFilesSelected}
                    className="block w-full text-sm file:mr-4 file:rounded-md file:border-0 file:bg-primary file:px-4 file:py-2 file:text-sm file:font-semibold file:text-primary-foreground hover:file:bg-primary/90"
                    disabled={isProcessing}
                  />
                  {batchImages.length > 0 && (
                    <div className="rounded-lg border p-3">
                      <p className="mb-2 text-sm font-medium">
                        Selected: {batchImages.length} image{batchImages.length !== 1 ? 's' : ''}
                      </p>
                      <div className="max-h-32 space-y-1 overflow-y-auto text-xs text-muted-foreground">
                        {batchImages.map((img, idx) => (
                          <div key={idx} className="truncate">
                            {idx + 1}. {img.name}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Camera Capture */}
              {inputMode === 'camera' && (
                <WebcamCapture
                  onCapture={setCapturedImage}
                  capturedImage={capturedImage}
                  disabled={isProcessing}
                />
              )}

              {/* Live Stream */}
              {inputMode === 'live' && (
                <EnhancedLiveStream mode={analysisMode} onResult={handleLiveResult} />
              )}

              {/* Action Buttons */}
              {inputMode !== 'live' && (
                <div className="flex gap-2 pt-2">
                  {inputMode === 'batch' ? (
                    <Button
                      onClick={handleAnalyzeBatch}
                      disabled={isProcessing || batchImages.length === 0}
                      className="flex-1"
                    >
                      {isProcessing ? (
                        <>
                          <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                          Processing...
                        </>
                      ) : (
                        <>
                          <Play className="mr-2 h-4 w-4" />
                          Process Batch
                        </>
                      )}
                    </Button>
                  ) : (
                    <Button
                      onClick={handleAnalyzeSingle}
                      disabled={isProcessing || (!selectedImage && !capturedImage)}
                      className="flex-1"
                    >
                      {isProcessing ? (
                        <>
                          <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                          Analyzing...
                        </>
                      ) : (
                        <>
                          <Play className="mr-2 h-4 w-4" />
                          Analyze
                        </>
                      )}
                    </Button>
                  )}
                  {(singleResult || batchResults.length > 0 || liveResult) && (
                    <Button variant="outline" onClick={handleReset}>
                      Reset
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
          transition={{ duration: 0.3, delay: 0.3 }}
        >
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Results</CardTitle>
              <CardDescription>
                {inputMode === 'live' && 'Real-time analysis results'}
                {inputMode === 'batch' && 'Batch processing results'}
                {(inputMode === 'upload' || inputMode === 'camera') && 'Analysis results'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <AnimatePresence mode="wait">
                {/* Live Results */}
                {inputMode === 'live' && liveResult && (
                  <motion.div
                    key="live"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                  >
                    <AnalysisResultRenderer mode={analysisMode} result={liveResult} isLive={true} />
                  </motion.div>
                )}

                {/* Single Result */}
                {inputMode !== 'live' && inputMode !== 'batch' && singleResult && (
                  <motion.div
                    key="single"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                  >
                    <AnalysisResultRenderer mode={analysisMode} result={singleResult} isLive={false} />
                  </motion.div>
                )}

                {/* Batch Results */}
                {inputMode === 'batch' && batchResults.length > 0 && (
                  <motion.div
                    key="batch"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="space-y-3"
                  >
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">
                        {batchResults.filter((r) => r.success).length}/{batchResults.length} Successful
                      </Badge>
                    </div>
                    <div className="max-h-96 space-y-4 overflow-y-auto">
                      {batchResults.map((result, idx) => (
                        <div
                          key={idx}
                          className={`rounded-lg border p-4 ${
                            result.success ? 'bg-green-50 dark:bg-green-950/20' : 'bg-red-50 dark:bg-red-950/20'
                          }`}
                        >
                          <div className="mb-3 flex items-center justify-between">
                            <span className="text-sm font-medium">{result.image}</span>
                            <Badge variant={result.success ? 'default' : 'destructive'}>
                              {result.success ? '✓' : '✗'}
                            </Badge>
                          </div>
                          {result.success ? (
                            <AnalysisResultRenderer mode={analysisMode} result={result.result} isLive={false} />
                          ) : (
                            <div className="rounded-lg bg-red-100 p-3 text-sm text-red-800 dark:bg-red-900/30 dark:text-red-200">
                              Error: {result.error}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </motion.div>
                )}

                {/* Empty State */}
                {!liveResult && !singleResult && batchResults.length === 0 && (
                  <div className="flex h-64 items-center justify-center text-center text-muted-foreground">
                    <div>
                      <Sparkles className="mx-auto mb-3 h-12 w-12 opacity-50" />
                      <p className="mb-1 font-medium">No results yet</p>
                      <p className="text-sm">
                        {inputMode === 'live' && 'Start live stream to see real-time results'}
                        {inputMode === 'batch' && 'Upload images and click "Process Batch"'}
                        {(inputMode === 'upload' || inputMode === 'camera') &&
                          'Select or capture an image and click "Analyze"'}
                      </p>
                    </div>
                  </div>
                )}
              </AnimatePresence>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Info Footer */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3, delay: 0.4 }}
      >
        <Card>
          <CardContent className="pt-6">
            <div className="grid gap-4 md:grid-cols-3">
              <div className="flex items-start gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-500/10">
                  <Upload className="h-4 w-4 text-blue-500" />
                </div>
                <div>
                  <p className="text-sm font-medium">Single & Batch Upload</p>
                  <p className="text-xs text-muted-foreground">Process one or multiple images at once</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-green-500/10">
                  <Camera className="h-4 w-4 text-green-500" />
                </div>
                <div>
                  <p className="text-sm font-medium">Camera Capture</p>
                  <p className="text-xs text-muted-foreground">Take a photo directly from your camera</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-purple-500/10">
                  <Video className="h-4 w-4 text-purple-500" />
                </div>
                <div>
                  <p className="text-sm font-medium">Live Streaming</p>
                  <p className="text-xs text-muted-foreground">Real-time continuous analysis via WebSocket</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
