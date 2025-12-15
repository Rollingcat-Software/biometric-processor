'use client';

import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Play,
  CheckCircle2,
  XCircle,
  ChevronRight,
  ChevronLeft,
  Upload,
  User,
  Search,
  Shield,
  Sparkles,
  BarChart3,
  Users,
  RotateCcw,
  Loader2,
  AlertCircle,
  Info,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ImageUploader } from '@/components/media/image-uploader';
import { WebcamCapture } from '@/components/media/webcam-capture';
import { SimilarityGauge } from '@/components/biometric/similarity-gauge';
import { useFaceEnrollment } from '@/hooks/use-face-enrollment';
import { useFaceVerification } from '@/hooks/use-face-verification';
import { useFaceSearch } from '@/hooks/use-face-search';
import { useQualityAnalysis } from '@/hooks/use-quality-analysis';
import { useLivenessCheck } from '@/hooks/use-liveness-check';
import { useDemographicsAnalysis } from '@/hooks/use-demographics-analysis';
import { useFaceComparison } from '@/hooks/use-face-comparison';
import { toast } from 'sonner';
import { toPercent, formatPercent } from '@/lib/utils/format';

// Demo steps configuration
const DEMO_STEPS = [
  {
    id: 'intro',
    title: 'Welcome to FIVUCSAS Demo',
    description: 'Experience our biometric verification system',
    icon: Play,
    color: 'blue',
  },
  {
    id: 'enroll',
    title: 'Step 1: Face Enrollment',
    description: 'Register a face in the system',
    icon: User,
    color: 'green',
  },
  {
    id: 'verify',
    title: 'Step 2: Face Verification',
    description: 'Verify identity against enrolled face',
    icon: Shield,
    color: 'purple',
  },
  {
    id: 'search',
    title: 'Step 3: Face Search',
    description: 'Search for similar faces in database',
    icon: Search,
    color: 'orange',
  },
  {
    id: 'quality',
    title: 'Step 4: Quality Analysis',
    description: 'Analyze image quality for biometrics',
    icon: BarChart3,
    color: 'cyan',
  },
  {
    id: 'liveness',
    title: 'Step 5: Liveness Detection',
    description: 'Detect if face is real or spoofed',
    icon: Sparkles,
    color: 'pink',
  },
  {
    id: 'demographics',
    title: 'Step 6: Demographics Analysis',
    description: 'Estimate age, gender, and emotion',
    icon: Users,
    color: 'indigo',
  },
  {
    id: 'summary',
    title: 'Demo Complete',
    description: 'Review all results',
    icon: CheckCircle2,
    color: 'green',
  },
];

interface StepResult {
  success: boolean;
  data?: Record<string, unknown>;
  error?: string;
  timestamp: Date;
}

export default function DemoPage() {
  const [currentStep, setCurrentStep] = useState(0);
  const [inputMode, setInputMode] = useState<'upload' | 'camera'>('upload');
  const [enrollImage, setEnrollImage] = useState<File | Blob | null>(null);
  const [verifyImage, setVerifyImage] = useState<File | Blob | null>(null);
  const [enrolledUserId, setEnrolledUserId] = useState<string>('');
  const [results, setResults] = useState<Record<string, StepResult>>({});
  const [isAutoMode, setIsAutoMode] = useState(false);

  // Hooks for API calls
  const enrollMutation = useFaceEnrollment();
  const verifyMutation = useFaceVerification();
  const searchMutation = useFaceSearch();
  const qualityMutation = useQualityAnalysis();
  const livenessMutation = useLivenessCheck();
  const demographicsMutation = useDemographicsAnalysis();
  const comparisonMutation = useFaceComparison();

  // Generate unique user ID for demo
  const generateUserId = useCallback(() => {
    return `demo_user_${Date.now()}_${Math.random().toString(36).substring(7)}`;
  }, []);

  // Reset demo
  const resetDemo = useCallback(() => {
    setCurrentStep(0);
    setEnrollImage(null);
    setVerifyImage(null);
    setEnrolledUserId('');
    setResults({});
    setIsAutoMode(false);
    enrollMutation.reset();
    verifyMutation.reset();
    searchMutation.reset();
    qualityMutation.reset();
    livenessMutation.reset();
    demographicsMutation.reset();
    comparisonMutation.reset();
    toast.info('Demo reset', { description: 'Ready to start fresh' });
  }, [enrollMutation, verifyMutation, searchMutation, qualityMutation, livenessMutation, demographicsMutation, comparisonMutation]);

  // Save step result
  const saveResult = useCallback((stepId: string, success: boolean, data?: Record<string, unknown>, error?: string) => {
    setResults(prev => ({
      ...prev,
      [stepId]: { success, data, error, timestamp: new Date() }
    }));
  }, []);

  // Execute enrollment
  const executeEnroll = useCallback(async () => {
    if (!enrollImage) {
      toast.error('Please select an image first');
      return;
    }

    const userId = generateUserId();
    setEnrolledUserId(userId);

    enrollMutation.mutate(
      { person_id: userId, image: enrollImage },
      {
        onSuccess: (data) => {
          saveResult('enroll', true, { userId, ...data });
          toast.success('Face enrolled successfully!');
          if (isAutoMode) setTimeout(() => setCurrentStep(3), 1500);
        },
        onError: (err) => {
          saveResult('enroll', false, undefined, err.message);
          toast.error('Enrollment failed', { description: err.message });
        },
      }
    );
  }, [enrollImage, generateUserId, enrollMutation, saveResult, isAutoMode]);

  // Execute verification
  const executeVerify = useCallback(async () => {
    const image = verifyImage || enrollImage;
    if (!image || !enrolledUserId) {
      toast.error('Please complete enrollment first');
      return;
    }

    verifyMutation.mutate(
      { image, user_id: enrolledUserId },
      {
        onSuccess: (data) => {
          saveResult('verify', data.match, data as unknown as Record<string, unknown>);
          if (data.match) {
            toast.success('Identity verified!', { description: `Similarity: ${formatPercent(data.similarity)}` });
          } else {
            toast.warning('Verification failed', { description: 'Face does not match enrolled user' });
          }
          if (isAutoMode) setTimeout(() => setCurrentStep(4), 1500);
        },
        onError: (err) => {
          saveResult('verify', false, undefined, err.message);
          toast.error('Verification failed', { description: err.message });
        },
      }
    );
  }, [verifyImage, enrollImage, enrolledUserId, verifyMutation, saveResult, isAutoMode]);

  // Execute search
  const executeSearch = useCallback(async () => {
    const image = verifyImage || enrollImage;
    if (!image) {
      toast.error('Please provide an image');
      return;
    }

    searchMutation.mutate(
      { image, max_results: 5 },
      {
        onSuccess: (data) => {
          const hasMatch = data.matches && data.matches.length > 0;
          saveResult('search', hasMatch, data as unknown as Record<string, unknown>);
          if (hasMatch) {
            toast.success('Faces found!', { description: `Found ${data.matches.length} match(es)` });
          } else {
            toast.info('No matches found');
          }
          if (isAutoMode) setTimeout(() => setCurrentStep(5), 1500);
        },
        onError: (err) => {
          saveResult('search', false, undefined, err.message);
          toast.error('Search failed', { description: err.message });
        },
      }
    );
  }, [verifyImage, enrollImage, searchMutation, saveResult, isAutoMode]);

  // Execute quality analysis
  const executeQuality = useCallback(async () => {
    const image = verifyImage || enrollImage;
    if (!image) {
      toast.error('Please provide an image');
      return;
    }

    qualityMutation.mutate(
      { image },
      {
        onSuccess: (data) => {
          // Consider quality good if score >= 70%, even if backend flags some issues
          const isGoodQuality = data.overall_score >= 70;
          saveResult('quality', isGoodQuality, data as unknown as Record<string, unknown>);

          // Smarter messaging based on actual score
          if (data.overall_score >= 90) {
            toast.success('Excellent quality!', { description: `Score: ${data.overall_score.toFixed(1)}%` });
          } else if (data.overall_score >= 70) {
            const suggestion = data.recommendations?.length > 0
              ? data.recommendations[0]
              : 'Minor improvements possible';
            toast.success('Good quality', { description: `Score: ${data.overall_score.toFixed(1)}% - ${suggestion}` });
          } else if (data.overall_score >= 50) {
            toast.warning('Acceptable quality', { description: data.recommendations?.join(', ') || 'Some improvements needed' });
          } else {
            toast.error('Poor quality', { description: data.recommendations?.join(', ') || 'Please retake the image' });
          }
          if (isAutoMode) setTimeout(() => setCurrentStep(6), 1500);
        },
        onError: (err) => {
          saveResult('quality', false, undefined, err.message);
          toast.error('Quality analysis failed', { description: err.message });
        },
      }
    );
  }, [verifyImage, enrollImage, qualityMutation, saveResult, isAutoMode]);

  // Execute liveness check
  const executeLiveness = useCallback(async () => {
    const image = verifyImage || enrollImage;
    if (!image) {
      toast.error('Please provide an image');
      return;
    }

    livenessMutation.mutate(
      { image },
      {
        onSuccess: (data) => {
          saveResult('liveness', data.is_live, data as unknown as Record<string, unknown>);
          if (data.is_live) {
            toast.success('Real face detected!', { description: `Confidence: ${formatPercent(data.confidence)}` });
          } else {
            toast.warning('Possible spoof detected');
          }
          if (isAutoMode) setTimeout(() => setCurrentStep(7), 1500);
        },
        onError: (err) => {
          saveResult('liveness', false, undefined, err.message);
          toast.error('Liveness check failed', { description: err.message });
        },
      }
    );
  }, [verifyImage, enrollImage, livenessMutation, saveResult, isAutoMode]);

  // Execute demographics
  const executeDemographics = useCallback(async () => {
    const image = verifyImage || enrollImage;
    if (!image) {
      toast.error('Please provide an image');
      return;
    }

    demographicsMutation.mutate(
      { image },
      {
        onSuccess: (data) => {
          saveResult('demographics', true, data as unknown as Record<string, unknown>);
          toast.success('Demographics analyzed!', {
            description: `Age: ${data.age}, Gender: ${data.gender}`,
          });
          if (isAutoMode) setTimeout(() => setCurrentStep(8), 1500);
        },
        onError: (err) => {
          saveResult('demographics', false, undefined, err.message);
          toast.error('Demographics analysis failed', { description: err.message });
        },
      }
    );
  }, [verifyImage, enrollImage, demographicsMutation, saveResult, isAutoMode]);

  // Check if step is loading
  const isStepLoading = (stepId: string): boolean => {
    switch (stepId) {
      case 'enroll': return enrollMutation.isPending;
      case 'verify': return verifyMutation.isPending;
      case 'search': return searchMutation.isPending;
      case 'quality': return qualityMutation.isPending;
      case 'liveness': return livenessMutation.isPending;
      case 'demographics': return demographicsMutation.isPending;
      default: return false;
    }
  };

  // Get step status
  const getStepStatus = (stepId: string): 'pending' | 'loading' | 'success' | 'error' => {
    if (isStepLoading(stepId)) return 'loading';
    if (results[stepId]?.success) return 'success';
    if (results[stepId]?.error) return 'error';
    return 'pending';
  };

  // Current step object
  const step = DEMO_STEPS[currentStep];

  // Progress percentage
  const progressPercent = ((currentStep) / (DEMO_STEPS.length - 1)) * 100;

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/30">
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-8"
        >
          <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
            FIVUCSAS Biometric Demo
          </h1>
          <p className="text-muted-foreground mt-2">
            Interactive demonstration of our facial recognition capabilities
          </p>
        </motion.div>

        {/* Progress Bar */}
        <motion.div
          initial={{ opacity: 0, scaleX: 0 }}
          animate={{ opacity: 1, scaleX: 1 }}
          className="mb-8"
        >
          <div className="flex justify-between mb-2 text-sm">
            <span className="text-muted-foreground">Progress</span>
            <span className="font-medium">{Math.round(progressPercent)}%</span>
          </div>
          <Progress value={progressPercent} className="h-2" />

          {/* Step indicators */}
          <div className="flex justify-between mt-4">
            {DEMO_STEPS.map((s, idx) => {
              const status = getStepStatus(s.id);
              const Icon = s.icon;
              const isActive = idx === currentStep;
              const isPast = idx < currentStep;

              return (
                <button
                  key={s.id}
                  onClick={() => setCurrentStep(idx)}
                  disabled={idx > currentStep + 1}
                  className={`
                    flex flex-col items-center gap-1 transition-all
                    ${isActive ? 'scale-110' : 'scale-100'}
                    ${idx > currentStep + 1 ? 'opacity-30 cursor-not-allowed' : 'cursor-pointer hover:opacity-80'}
                  `}
                >
                  <div className={`
                    w-10 h-10 rounded-full flex items-center justify-center transition-all
                    ${isActive ? `bg-${s.color}-500 text-white shadow-lg` : ''}
                    ${isPast && status === 'success' ? 'bg-green-500 text-white' : ''}
                    ${isPast && status === 'error' ? 'bg-red-500 text-white' : ''}
                    ${!isActive && !isPast ? 'bg-muted text-muted-foreground' : ''}
                    ${status === 'loading' ? 'animate-pulse bg-blue-500 text-white' : ''}
                  `}>
                    {status === 'loading' ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : status === 'success' && isPast ? (
                      <CheckCircle2 className="h-5 w-5" />
                    ) : status === 'error' && isPast ? (
                      <XCircle className="h-5 w-5" />
                    ) : (
                      <Icon className="h-5 w-5" />
                    )}
                  </div>
                  <span className={`text-xs hidden md:block ${isActive ? 'font-semibold' : ''}`}>
                    {idx === 0 ? 'Start' : idx === DEMO_STEPS.length - 1 ? 'Done' : `Step ${idx}`}
                  </span>
                </button>
              );
            })}
          </div>
        </motion.div>

        {/* Main Content */}
        <AnimatePresence mode="wait">
          <motion.div
            key={step.id}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.3 }}
          >
            <Card className="border-2">
              <CardHeader className="text-center border-b bg-muted/30">
                <div className="flex justify-center mb-4">
                  <div className={`w-16 h-16 rounded-full bg-${step.color}-500/10 flex items-center justify-center`}>
                    <step.icon className={`h-8 w-8 text-${step.color}-500`} />
                  </div>
                </div>
                <CardTitle className="text-2xl">{step.title}</CardTitle>
                <CardDescription className="text-base">{step.description}</CardDescription>
              </CardHeader>

              <CardContent className="p-6">
                {/* Intro Step */}
                {step.id === 'intro' && (
                  <div className="space-y-6">
                    <Alert>
                      <Info className="h-4 w-4" />
                      <AlertTitle>How this demo works</AlertTitle>
                      <AlertDescription>
                        This guided demo will walk you through all features of our biometric system.
                        Upload or capture a face image, and we&apos;ll demonstrate enrollment, verification,
                        search, quality analysis, liveness detection, and demographics analysis.
                      </AlertDescription>
                    </Alert>

                    <div className="grid md:grid-cols-2 gap-6">
                      <Card>
                        <CardHeader>
                          <CardTitle className="text-lg flex items-center gap-2">
                            <Upload className="h-5 w-5" />
                            Choose Input Method
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <Tabs value={inputMode} onValueChange={(v) => setInputMode(v as 'upload' | 'camera')}>
                            <TabsList className="grid w-full grid-cols-2">
                              <TabsTrigger value="upload">Upload Image</TabsTrigger>
                              <TabsTrigger value="camera">Use Camera</TabsTrigger>
                            </TabsList>
                            <TabsContent value="upload" className="mt-4">
                              <ImageUploader
                                onImageSelected={setEnrollImage}
                                selectedImage={enrollImage instanceof File ? enrollImage : null}
                              />
                            </TabsContent>
                            <TabsContent value="camera" className="mt-4">
                              <WebcamCapture
                                onCapture={(blob) => setEnrollImage(blob)}
                                capturedImage={enrollImage instanceof Blob && !(enrollImage instanceof File) ? enrollImage : null}
                              />
                            </TabsContent>
                          </Tabs>
                        </CardContent>
                      </Card>

                      <Card>
                        <CardHeader>
                          <CardTitle className="text-lg">Demo Features</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <ul className="space-y-3">
                            {DEMO_STEPS.slice(1, -1).map((s) => (
                              <li key={s.id} className="flex items-center gap-3">
                                <div className={`w-8 h-8 rounded-full bg-${s.color}-500/10 flex items-center justify-center`}>
                                  <s.icon className={`h-4 w-4 text-${s.color}-500`} />
                                </div>
                                <div>
                                  <p className="font-medium text-sm">{s.title.replace(/Step \d+: /, '')}</p>
                                  <p className="text-xs text-muted-foreground">{s.description}</p>
                                </div>
                              </li>
                            ))}
                          </ul>
                        </CardContent>
                      </Card>
                    </div>

                    <div className="flex justify-center gap-4">
                      <Button
                        size="lg"
                        onClick={() => setCurrentStep(1)}
                        disabled={!enrollImage}
                        className="gap-2"
                      >
                        Start Demo
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                )}

                {/* Enrollment Step */}
                {step.id === 'enroll' && (
                  <div className="space-y-6">
                    <div className="grid md:grid-cols-2 gap-6">
                      <div>
                        <h3 className="font-semibold mb-4">Enrollment Image</h3>
                        {enrollImage ? (
                          <div className="relative rounded-lg overflow-hidden border">
                            <img
                              src={URL.createObjectURL(enrollImage)}
                              alt="Enrollment"
                              className="w-full aspect-square object-cover"
                            />
                            <Badge className="absolute top-2 right-2">Ready</Badge>
                          </div>
                        ) : (
                          <div className="aspect-square bg-muted rounded-lg flex items-center justify-center">
                            <p className="text-muted-foreground">No image selected</p>
                          </div>
                        )}
                      </div>

                      <div className="space-y-4">
                        <h3 className="font-semibold">Enrollment Status</h3>
                        {enrollMutation.isPending && (
                          <Alert>
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <AlertTitle>Processing...</AlertTitle>
                            <AlertDescription>
                              Extracting facial features and creating enrollment...
                            </AlertDescription>
                          </Alert>
                        )}
                        {results.enroll?.success && (
                          <Alert className="border-green-500 bg-green-50 dark:bg-green-950/20">
                            <CheckCircle2 className="h-4 w-4 text-green-500" />
                            <AlertTitle className="text-green-700 dark:text-green-400">Enrolled Successfully!</AlertTitle>
                            <AlertDescription>
                              User ID: <code className="text-xs">{enrolledUserId}</code>
                            </AlertDescription>
                          </Alert>
                        )}
                        {results.enroll?.error && (
                          <Alert variant="destructive">
                            <XCircle className="h-4 w-4" />
                            <AlertTitle>Enrollment Failed</AlertTitle>
                            <AlertDescription>{results.enroll.error}</AlertDescription>
                          </Alert>
                        )}
                        {!enrollMutation.isPending && !results.enroll && (
                          <Alert>
                            <Info className="h-4 w-4" />
                            <AlertTitle>Ready to Enroll</AlertTitle>
                            <AlertDescription>
                              Click the button below to register this face in the system.
                              A unique user ID will be generated automatically.
                            </AlertDescription>
                          </Alert>
                        )}

                        <Button
                          onClick={executeEnroll}
                          disabled={!enrollImage || enrollMutation.isPending}
                          className="w-full gap-2"
                          size="lg"
                        >
                          {enrollMutation.isPending ? (
                            <>
                              <Loader2 className="h-4 w-4 animate-spin" />
                              Enrolling...
                            </>
                          ) : results.enroll?.success ? (
                            <>
                              <CheckCircle2 className="h-4 w-4" />
                              Enrolled
                            </>
                          ) : (
                            <>
                              <User className="h-4 w-4" />
                              Enroll Face
                            </>
                          )}
                        </Button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Verification Step */}
                {step.id === 'verify' && (
                  <div className="space-y-6">
                    <div className="grid md:grid-cols-2 gap-6">
                      <div>
                        <h3 className="font-semibold mb-4">Verification Image</h3>
                        <p className="text-sm text-muted-foreground mb-4">
                          Use the same image or upload/capture a different one to test verification.
                        </p>
                        <Tabs defaultValue="same">
                          <TabsList className="grid w-full grid-cols-2">
                            <TabsTrigger value="same" onClick={() => setVerifyImage(null)}>Same Image</TabsTrigger>
                            <TabsTrigger value="different">Different Image</TabsTrigger>
                          </TabsList>
                          <TabsContent value="same" className="mt-4">
                            {enrollImage && (
                              <div className="rounded-lg overflow-hidden border">
                                <img
                                  src={URL.createObjectURL(enrollImage)}
                                  alt="Verification"
                                  className="w-full aspect-square object-cover"
                                />
                              </div>
                            )}
                          </TabsContent>
                          <TabsContent value="different" className="mt-4">
                            <ImageUploader
                              onImageSelected={setVerifyImage}
                              selectedImage={verifyImage instanceof File ? verifyImage : null}
                            />
                          </TabsContent>
                        </Tabs>
                      </div>

                      <div className="space-y-4">
                        <h3 className="font-semibold">Verification Result</h3>
                        {verifyMutation.isPending && (
                          <Alert>
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <AlertTitle>Verifying...</AlertTitle>
                            <AlertDescription>
                              Comparing face against enrolled user...
                            </AlertDescription>
                          </Alert>
                        )}
                        {results.verify && (
                          <div className="space-y-4">
                            <div className="flex justify-center">
                              <SimilarityGauge
                                value={(results.verify.data as { similarity?: number })?.similarity || 0}
                                threshold={0.6}
                                size="lg"
                              />
                            </div>
                            <Alert className={results.verify.success ? 'border-green-500 bg-green-50 dark:bg-green-950/20' : 'border-red-500 bg-red-50 dark:bg-red-950/20'}>
                              {results.verify.success ? (
                                <CheckCircle2 className="h-4 w-4 text-green-500" />
                              ) : (
                                <XCircle className="h-4 w-4 text-red-500" />
                              )}
                              <AlertTitle className={results.verify.success ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400'}>
                                {results.verify.success ? 'Identity Verified!' : 'Verification Failed'}
                              </AlertTitle>
                              <AlertDescription>
                                Similarity: {formatPercent((results.verify.data as { similarity?: number })?.similarity || 0)}
                              </AlertDescription>
                            </Alert>
                          </div>
                        )}
                        {!verifyMutation.isPending && !results.verify && (
                          <Alert>
                            <Shield className="h-4 w-4" />
                            <AlertTitle>Ready to Verify</AlertTitle>
                            <AlertDescription>
                              Verify if the current image matches the enrolled user: <code className="text-xs">{enrolledUserId}</code>
                            </AlertDescription>
                          </Alert>
                        )}

                        <Button
                          onClick={executeVerify}
                          disabled={!enrolledUserId || verifyMutation.isPending}
                          className="w-full gap-2"
                          size="lg"
                        >
                          {verifyMutation.isPending ? (
                            <>
                              <Loader2 className="h-4 w-4 animate-spin" />
                              Verifying...
                            </>
                          ) : (
                            <>
                              <Shield className="h-4 w-4" />
                              Verify Identity
                            </>
                          )}
                        </Button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Search Step */}
                {step.id === 'search' && (
                  <div className="space-y-6">
                    <div className="grid md:grid-cols-2 gap-6">
                      <div>
                        <h3 className="font-semibold mb-4">Search Image</h3>
                        {(verifyImage || enrollImage) && (
                          <div className="rounded-lg overflow-hidden border">
                            <img
                              src={URL.createObjectURL(verifyImage || enrollImage!)}
                              alt="Search"
                              className="w-full aspect-square object-cover"
                            />
                          </div>
                        )}
                      </div>

                      <div className="space-y-4">
                        <h3 className="font-semibold">Search Results</h3>
                        {searchMutation.isPending && (
                          <Alert>
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <AlertTitle>Searching...</AlertTitle>
                            <AlertDescription>
                              Scanning database for similar faces...
                            </AlertDescription>
                          </Alert>
                        )}
                        {results.search && (
                          <div className="space-y-3">
                            {((results.search.data as { matches?: Array<{ user_id: string; similarity: number }> })?.matches || []).map((match, idx) => (
                              <div key={idx} className="flex items-center justify-between p-3 border rounded-lg">
                                <div>
                                  <p className="font-medium">Match #{idx + 1}</p>
                                  <p className="text-sm text-muted-foreground">{match.user_id}</p>
                                </div>
                                <Badge variant={toPercent(match.similarity) > 80 ? 'default' : 'secondary'}>
                                  {formatPercent(match.similarity)}
                                </Badge>
                              </div>
                            ))}
                            {((results.search.data as { matches?: unknown[] })?.matches || []).length === 0 && (
                              <Alert>
                                <Info className="h-4 w-4" />
                                <AlertTitle>No Matches Found</AlertTitle>
                                <AlertDescription>No similar faces found in the database.</AlertDescription>
                              </Alert>
                            )}
                          </div>
                        )}
                        {!searchMutation.isPending && !results.search && (
                          <Alert>
                            <Search className="h-4 w-4" />
                            <AlertTitle>Ready to Search</AlertTitle>
                            <AlertDescription>
                              Search the database for faces similar to the current image.
                            </AlertDescription>
                          </Alert>
                        )}

                        <Button
                          onClick={executeSearch}
                          disabled={(!enrollImage && !verifyImage) || searchMutation.isPending}
                          className="w-full gap-2"
                          size="lg"
                        >
                          {searchMutation.isPending ? (
                            <>
                              <Loader2 className="h-4 w-4 animate-spin" />
                              Searching...
                            </>
                          ) : (
                            <>
                              <Search className="h-4 w-4" />
                              Search Faces
                            </>
                          )}
                        </Button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Quality Step */}
                {step.id === 'quality' && (
                  <div className="space-y-6">
                    <div className="grid md:grid-cols-2 gap-6">
                      <div>
                        <h3 className="font-semibold mb-4">Analysis Image</h3>
                        {(verifyImage || enrollImage) && (
                          <div className="rounded-lg overflow-hidden border">
                            <img
                              src={URL.createObjectURL(verifyImage || enrollImage!)}
                              alt="Quality"
                              className="w-full aspect-square object-cover"
                            />
                          </div>
                        )}
                      </div>

                      <div className="space-y-4">
                        <h3 className="font-semibold">Quality Metrics</h3>
                        {qualityMutation.isPending && (
                          <Alert>
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <AlertTitle>Analyzing...</AlertTitle>
                            <AlertDescription>
                              Evaluating image quality metrics...
                            </AlertDescription>
                          </Alert>
                        )}
                        {results.quality && (
                          <div className="space-y-4">
                            {/* Overall Score with Color */}
                            <div className="text-center p-4 border rounded-lg">
                              {(() => {
                                const score = (results.quality.data as { overall_score?: number })?.overall_score || 0;
                                const colorClass = score >= 90 ? 'text-green-500' :
                                                   score >= 70 ? 'text-emerald-500' :
                                                   score >= 50 ? 'text-yellow-500' : 'text-red-500';
                                return (
                                  <>
                                    <p className={`text-4xl font-bold ${colorClass}`}>
                                      {score.toFixed(1)}%
                                    </p>
                                    <p className="text-muted-foreground">Overall Quality Score</p>
                                    <Progress value={score} className="mt-2 h-2" />
                                  </>
                                );
                              })()}
                            </div>
                            {/* Individual Metrics with Progress Bars */}
                            <div className="grid gap-3">
                              {Object.entries((results.quality.data as { metrics?: Record<string, number> })?.metrics || {}).map(([key, value]) => {
                                const numValue = typeof value === 'number' ? value : 0;
                                const colorClass = numValue >= 80 ? 'bg-green-500' :
                                                   numValue >= 60 ? 'bg-yellow-500' :
                                                   numValue >= 40 ? 'bg-orange-500' : 'bg-red-500';
                                return (
                                  <div key={key} className="p-3 border rounded-lg">
                                    <div className="flex justify-between items-center mb-1">
                                      <p className="text-sm text-muted-foreground capitalize">{key.replace(/_/g, ' ')}</p>
                                      <p className="text-sm font-semibold">{numValue.toFixed(1)}</p>
                                    </div>
                                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                                      <div
                                        className={`h-full ${colorClass} transition-all duration-300`}
                                        style={{ width: `${Math.min(100, numValue)}%` }}
                                      />
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                            {/* Recommendations */}
                            {((results.quality.data as { recommendations?: string[] })?.recommendations?.length ?? 0) > 0 && (
                              <Alert>
                                <Info className="h-4 w-4" />
                                <AlertTitle>Suggestions</AlertTitle>
                                <AlertDescription>
                                  <ul className="list-disc list-inside text-sm">
                                    {(results.quality.data as { recommendations?: string[] })?.recommendations?.map((rec, idx) => (
                                      <li key={idx}>{rec}</li>
                                    ))}
                                  </ul>
                                </AlertDescription>
                              </Alert>
                            )}
                          </div>
                        )}
                        {!qualityMutation.isPending && !results.quality && (
                          <Alert>
                            <BarChart3 className="h-4 w-4" />
                            <AlertTitle>Ready to Analyze</AlertTitle>
                            <AlertDescription>
                              Analyze image quality including sharpness, brightness, face size, and pose.
                            </AlertDescription>
                          </Alert>
                        )}

                        <Button
                          onClick={executeQuality}
                          disabled={(!enrollImage && !verifyImage) || qualityMutation.isPending}
                          className="w-full gap-2"
                          size="lg"
                        >
                          {qualityMutation.isPending ? (
                            <>
                              <Loader2 className="h-4 w-4 animate-spin" />
                              Analyzing...
                            </>
                          ) : (
                            <>
                              <BarChart3 className="h-4 w-4" />
                              Analyze Quality
                            </>
                          )}
                        </Button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Liveness Step */}
                {step.id === 'liveness' && (
                  <div className="space-y-6">
                    <div className="grid md:grid-cols-2 gap-6">
                      <div>
                        <h3 className="font-semibold mb-4">Liveness Check Image</h3>
                        {(verifyImage || enrollImage) && (
                          <div className="rounded-lg overflow-hidden border">
                            <img
                              src={URL.createObjectURL(verifyImage || enrollImage!)}
                              alt="Liveness"
                              className="w-full aspect-square object-cover"
                            />
                          </div>
                        )}
                      </div>

                      <div className="space-y-4">
                        <h3 className="font-semibold">Liveness Result</h3>
                        {livenessMutation.isPending && (
                          <Alert>
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <AlertTitle>Checking...</AlertTitle>
                            <AlertDescription>
                              Analyzing for signs of spoofing...
                            </AlertDescription>
                          </Alert>
                        )}
                        {results.liveness && (
                          <div className="space-y-4">
                            <div className={`text-center p-6 border rounded-lg ${results.liveness.success ? 'bg-green-50 dark:bg-green-950/20 border-green-500' : 'bg-red-50 dark:bg-red-950/20 border-red-500'}`}>
                              {results.liveness.success ? (
                                <CheckCircle2 className="h-12 w-12 text-green-500 mx-auto mb-2" />
                              ) : (
                                <XCircle className="h-12 w-12 text-red-500 mx-auto mb-2" />
                              )}
                              <p className="text-xl font-bold">
                                {results.liveness.success ? 'REAL FACE' : 'POSSIBLE SPOOF'}
                              </p>
                              <p className="text-muted-foreground">
                                Confidence: {formatPercent((results.liveness.data as { confidence?: number })?.confidence || 0)}
                              </p>
                            </div>
                          </div>
                        )}
                        {!livenessMutation.isPending && !results.liveness && (
                          <Alert>
                            <Sparkles className="h-4 w-4" />
                            <AlertTitle>Ready to Check</AlertTitle>
                            <AlertDescription>
                              Detect if the face is from a real person or a photo/video spoof attempt.
                            </AlertDescription>
                          </Alert>
                        )}

                        <Button
                          onClick={executeLiveness}
                          disabled={(!enrollImage && !verifyImage) || livenessMutation.isPending}
                          className="w-full gap-2"
                          size="lg"
                        >
                          {livenessMutation.isPending ? (
                            <>
                              <Loader2 className="h-4 w-4 animate-spin" />
                              Checking...
                            </>
                          ) : (
                            <>
                              <Sparkles className="h-4 w-4" />
                              Check Liveness
                            </>
                          )}
                        </Button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Demographics Step */}
                {step.id === 'demographics' && (
                  <div className="space-y-6">
                    <div className="grid md:grid-cols-2 gap-6">
                      <div>
                        <h3 className="font-semibold mb-4">Demographics Image</h3>
                        {(verifyImage || enrollImage) && (
                          <div className="rounded-lg overflow-hidden border">
                            <img
                              src={URL.createObjectURL(verifyImage || enrollImage!)}
                              alt="Demographics"
                              className="w-full aspect-square object-cover"
                            />
                          </div>
                        )}
                      </div>

                      <div className="space-y-4">
                        <h3 className="font-semibold">Demographics Analysis</h3>
                        {demographicsMutation.isPending && (
                          <Alert>
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <AlertTitle>Analyzing...</AlertTitle>
                            <AlertDescription>
                              Estimating age, gender, and emotion... This may take a moment.
                            </AlertDescription>
                          </Alert>
                        )}
                        {results.demographics && (
                          <div className="grid grid-cols-2 gap-4">
                            <div className="p-4 border rounded-lg text-center">
                              <p className="text-3xl font-bold">{(results.demographics.data as { age?: number })?.age}</p>
                              <p className="text-muted-foreground">Estimated Age</p>
                            </div>
                            <div className="p-4 border rounded-lg text-center">
                              <p className="text-3xl font-bold capitalize">{(results.demographics.data as { gender?: string })?.gender}</p>
                              <p className="text-muted-foreground">Gender</p>
                            </div>
                            <div className="p-4 border rounded-lg text-center col-span-2">
                              <p className="text-2xl font-bold capitalize">{(results.demographics.data as { dominant_emotion?: string })?.dominant_emotion}</p>
                              <p className="text-muted-foreground">Dominant Emotion</p>
                            </div>
                          </div>
                        )}
                        {!demographicsMutation.isPending && !results.demographics && (
                          <Alert>
                            <Users className="h-4 w-4" />
                            <AlertTitle>Ready to Analyze</AlertTitle>
                            <AlertDescription>
                              Estimate age, gender, and emotional expression from the face.
                            </AlertDescription>
                          </Alert>
                        )}

                        <Button
                          onClick={executeDemographics}
                          disabled={(!enrollImage && !verifyImage) || demographicsMutation.isPending}
                          className="w-full gap-2"
                          size="lg"
                        >
                          {demographicsMutation.isPending ? (
                            <>
                              <Loader2 className="h-4 w-4 animate-spin" />
                              Analyzing...
                            </>
                          ) : (
                            <>
                              <Users className="h-4 w-4" />
                              Analyze Demographics
                            </>
                          )}
                        </Button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Summary Step */}
                {step.id === 'summary' && (
                  <div className="space-y-6">
                    <Alert className="border-green-500 bg-green-50 dark:bg-green-950/20">
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                      <AlertTitle className="text-green-700 dark:text-green-400">Demo Complete!</AlertTitle>
                      <AlertDescription>
                        You&apos;ve experienced all the key features of the FIVUCSAS biometric system.
                      </AlertDescription>
                    </Alert>

                    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {DEMO_STEPS.slice(1, -1).map((s) => {
                        const result = results[s.id];
                        const Icon = s.icon;

                        // Determine status and message
                        const wasExecuted = result !== undefined;
                        const isSuccess = result?.success === true;
                        const hasError = result?.error !== undefined;

                        let statusMessage = 'Skipped';
                        let statusIcon = <AlertCircle className="h-4 w-4 text-muted-foreground" />;
                        let borderClass = 'border-muted';

                        if (wasExecuted) {
                          if (isSuccess) {
                            statusMessage = 'Completed successfully';
                            statusIcon = <CheckCircle2 className="h-4 w-4 text-green-500" />;
                            borderClass = 'border-green-500';
                          } else if (hasError) {
                            statusMessage = result.error || 'Failed';
                            statusIcon = <XCircle className="h-4 w-4 text-red-500" />;
                            borderClass = 'border-red-500';
                          } else {
                            // Executed but not marked as success (e.g., quality below threshold)
                            statusMessage = 'Completed with warnings';
                            statusIcon = <AlertCircle className="h-4 w-4 text-yellow-500" />;
                            borderClass = 'border-yellow-500';
                          }
                        }

                        // Get additional result info
                        let resultDetail = '';
                        if (wasExecuted && result.data) {
                          const data = result.data as Record<string, unknown>;
                          if (s.id === 'enroll') resultDetail = `User: ${(data.userId as string)?.slice(-8) || 'N/A'}`;
                          if (s.id === 'verify') resultDetail = `Similarity: ${formatPercent((data.similarity as number) || 0, 0)}`;
                          if (s.id === 'search') resultDetail = `Found: ${(data.matches as unknown[])?.length || 0} matches`;
                          if (s.id === 'quality') resultDetail = `Score: ${formatPercent((data.overall_score as number) || 0, 0)}`;
                          if (s.id === 'liveness') resultDetail = `Confidence: ${formatPercent((data.confidence as number) || 0, 0)}`;
                          if (s.id === 'demographics') resultDetail = `Age: ${data.age || 'N/A'}, ${data.gender || 'N/A'}`;
                        }

                        return (
                          <Card key={s.id} className={borderClass}>
                            <CardHeader className="pb-2">
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <Icon className={`h-4 w-4 text-${s.color}-500`} />
                                  <CardTitle className="text-sm">{s.title.replace(/Step \d+: /, '')}</CardTitle>
                                </div>
                                {statusIcon}
                              </div>
                            </CardHeader>
                            <CardContent className="space-y-1">
                              <p className="text-xs text-muted-foreground">{statusMessage}</p>
                              {resultDetail && (
                                <p className="text-xs font-medium">{resultDetail}</p>
                              )}
                            </CardContent>
                          </Card>
                        );
                      })}
                    </div>

                    <div className="flex justify-center">
                      <Button onClick={resetDemo} variant="outline" className="gap-2">
                        <RotateCcw className="h-4 w-4" />
                        Start New Demo
                      </Button>
                    </div>
                  </div>
                )}

                {/* Navigation */}
                <div className="flex justify-between mt-8 pt-6 border-t">
                  <Button
                    variant="outline"
                    onClick={() => setCurrentStep(Math.max(0, currentStep - 1))}
                    disabled={currentStep === 0}
                    className="gap-2"
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Previous
                  </Button>

                  <Button variant="outline" onClick={resetDemo} className="gap-2">
                    <RotateCcw className="h-4 w-4" />
                    Reset
                  </Button>

                  <Button
                    onClick={() => setCurrentStep(Math.min(DEMO_STEPS.length - 1, currentStep + 1))}
                    disabled={currentStep === DEMO_STEPS.length - 1 || (currentStep === 0 && !enrollImage)}
                    className="gap-2"
                  >
                    {currentStep === DEMO_STEPS.length - 2 ? 'View Summary' : 'Next'}
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </AnimatePresence>

        {/* Storage Notice */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="mt-6"
        >
          <Alert variant="default" className="bg-amber-50 dark:bg-amber-950/20 border-amber-500">
            <AlertCircle className="h-4 w-4 text-amber-500" />
            <AlertTitle className="text-amber-700 dark:text-amber-400">Demo Mode Notice</AlertTitle>
            <AlertDescription className="text-amber-600 dark:text-amber-300">
              This demo uses in-memory storage. Enrolled faces will be cleared when the server restarts.
              For production use, configure persistent database storage.
            </AlertDescription>
          </Alert>
        </motion.div>
      </div>
    </div>
  );
}
