'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Eye,
  Smile,
  ArrowLeft,
  ArrowRight,
  MoveVertical,
  CircleDot,
  CheckCircle2,
  XCircle,
  Timer,
  Trophy,
  Play,
  RotateCcw,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils/cn';
import { usePuzzleLiveness } from '@/hooks/use-puzzle-liveness';
import type { ChallengeType, PuzzleDifficulty } from '@/types/api';

interface PuzzleLivenessChallengeProps {
  difficulty?: PuzzleDifficulty;
  onComplete?: (success: boolean, score: number) => void;
  onError?: (error: string) => void;
  className?: string;
}

const CHALLENGE_ICONS: Record<string, React.ReactNode> = {
  blink: <Eye className="h-12 w-12" />,
  smile: <Smile className="h-12 w-12" />,
  turn_left: <ArrowLeft className="h-12 w-12" />,
  turn_right: <ArrowRight className="h-12 w-12" />,
  nod: <MoveVertical className="h-12 w-12" />,
  open_mouth: <CircleDot className="h-12 w-12" />,
  raise_eyebrows: <Eye className="h-12 w-12" />,
};

export function PuzzleLivenessChallenge({
  difficulty = 'standard',
  onComplete,
  onError,
  className,
}: PuzzleLivenessChallengeProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [cameraReady, setCameraReady] = useState(false);
  const [pulseAnimation, setPulseAnimation] = useState(false);

  const puzzle = usePuzzleLiveness({
    difficulty,
    onComplete: (result) => {
      onComplete?.(result.liveness_confirmed, result.overall_score);
    },
    onError: (error) => {
      onError?.(error);
    },
  });

  // Initialize camera on mount
  useEffect(() => {
    const initCamera = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: 'user',
            width: { ideal: 640 },
            height: { ideal: 480 },
          },
        });
        streamRef.current = stream;
        setCameraReady(true);
        setCameraError(null);
      } catch (error) {
        console.error('Camera error:', error);
        setCameraError('Failed to access camera. Please grant permission.');
      }
    };

    initCamera();

    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  // Callback ref to attach stream to video element whenever it mounts
  const videoRefCallback = useCallback((videoElement: HTMLVideoElement | null) => {
    if (videoElement && streamRef.current) {
      videoElement.srcObject = streamRef.current;
    }
  }, [cameraReady]); // Re-create callback when camera becomes ready

  // Trigger pulse animation when action is detected
  useEffect(() => {
    if (puzzle.actionDetected) {
      setPulseAnimation(true);
      const timer = setTimeout(() => setPulseAnimation(false), 500);
      return () => clearTimeout(timer);
    }
  }, [puzzle.actionDetected]);

  // Simulate action detection (in production, this would use MediaPipe)
  // For now, we'll provide a manual button to simulate detection
  const handleSimulateAction = useCallback(() => {
    if (puzzle.currentStep) {
      puzzle.reportActionDetected(puzzle.currentStep.action as ChallengeType, 0.85);
    }
  }, [puzzle]);

  // Render loading state
  if (puzzle.isLoading) {
    return (
      <div className={cn('flex flex-col items-center justify-center gap-4 py-12', className)}>
        <Loader2 className="h-12 w-12 animate-spin text-primary" />
        <p className="text-muted-foreground">Generating liveness puzzle...</p>
      </div>
    );
  }

  // Render idle state - start button
  if (puzzle.isIdle) {
    return (
      <div className={cn('flex flex-col items-center justify-center gap-6 py-8', className)}>
        <div className="text-center">
          <h3 className="text-xl font-semibold mb-2">Puzzle Liveness Check</h3>
          <p className="text-muted-foreground">
            Complete a series of challenges to verify you&apos;re a real person.
          </p>
        </div>

        {cameraError ? (
          <div className="rounded-lg bg-red-50 p-4 text-red-800 dark:bg-red-950/50 dark:text-red-200">
            {cameraError}
          </div>
        ) : !cameraReady ? (
          <div className="relative aspect-video w-full max-w-md overflow-hidden rounded-xl bg-black flex items-center justify-center">
            <div className="text-center text-white">
              <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2" />
              <p className="text-sm">Initializing camera...</p>
            </div>
          </div>
        ) : (
          <div className="relative aspect-video w-full max-w-md overflow-hidden rounded-xl bg-black">
            <video
              ref={videoRefCallback}
              autoPlay
              playsInline
              muted
              className="h-full w-full object-cover"
            />
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="h-48 w-36 rounded-full border-4 border-dashed border-white/50" />
            </div>
          </div>
        )}

        <Button
          onClick={() => puzzle.startPuzzle({ difficulty })}
          disabled={!!cameraError || !cameraReady}
          size="lg"
          className="gap-2"
        >
          <Play className="h-5 w-5" />
          Start Liveness Check
        </Button>
      </div>
    );
  }

  // Render ready state - begin challenges
  if (puzzle.isReady) {
    return (
      <div className={cn('flex flex-col items-center justify-center gap-6 py-8', className)}>
        <div className="text-center">
          <h3 className="text-xl font-semibold mb-2">Ready!</h3>
          <p className="text-muted-foreground">
            {puzzle.totalSteps} challenges to complete. Position your face in the camera.
          </p>
        </div>

        <div className="relative aspect-video w-full max-w-md overflow-hidden rounded-xl bg-black">
          <video
            ref={videoRefCallback}
            autoPlay
            playsInline
            muted
            className="h-full w-full object-cover"
          />
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="h-48 w-36 rounded-full border-4 border-green-500" />
          </div>
        </div>

        {/* Step preview */}
        <div className="flex gap-2">
          {puzzle.puzzle?.steps.map((step, i) => (
            <div
              key={i}
              className="flex h-10 w-10 items-center justify-center rounded-full bg-muted"
            >
              {CHALLENGE_ICONS[step.action] ? (
                <div className="scale-50">{CHALLENGE_ICONS[step.action]}</div>
              ) : (
                <span className="text-xs">{i + 1}</span>
              )}
            </div>
          ))}
        </div>

        <Button onClick={puzzle.beginChallenges} size="lg" className="gap-2">
          <Play className="h-5 w-5" />
          Begin Challenges
        </Button>
      </div>
    );
  }

  // Render verifying state
  if (puzzle.isVerifying) {
    return (
      <div className={cn('flex flex-col items-center justify-center gap-4 py-12', className)}>
        <Loader2 className="h-12 w-12 animate-spin text-primary" />
        <p className="text-muted-foreground">Verifying liveness...</p>
      </div>
    );
  }

  // Render success/failed state
  if (puzzle.isComplete) {
    const isSuccess = puzzle.isSuccess;
    const result = puzzle.verificationResult;

    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className={cn(
          'rounded-xl p-6 text-center',
          isSuccess
            ? 'bg-green-50 dark:bg-green-950/30'
            : 'bg-red-50 dark:bg-red-950/30',
          className
        )}
      >
        <div className="flex flex-col items-center gap-4">
          {isSuccess ? (
            <>
              <div className="flex h-20 w-20 items-center justify-center rounded-full bg-green-500/20">
                <Trophy className="h-10 w-10 text-green-600" />
              </div>
              <h3 className="text-2xl font-bold text-green-700 dark:text-green-300">
                Liveness Verified!
              </h3>
              <p className="text-green-600 dark:text-green-400">
                All challenges completed successfully
              </p>
            </>
          ) : (
            <>
              <div className="flex h-20 w-20 items-center justify-center rounded-full bg-red-500/20">
                <XCircle className="h-10 w-10 text-red-600" />
              </div>
              <h3 className="text-2xl font-bold text-red-700 dark:text-red-300">
                Verification Failed
              </h3>
              <p className="text-red-600 dark:text-red-400">
                {result?.message || puzzle.error || 'Please try again'}
              </p>
            </>
          )}

          {result && (
            <div className="mt-2 text-sm text-muted-foreground">
              Score: {result.overall_score.toFixed(0)}% ({result.steps_completed}/
              {result.total_steps} challenges)
              {result.completion_time_seconds > 0 && (
                <span> in {result.completion_time_seconds.toFixed(1)}s</span>
              )}
            </div>
          )}

          {result?.reason_codes && result.reason_codes.length > 0 && (
            <div className="mt-2 text-xs text-muted-foreground">
              {result.reason_codes.join(', ')}
            </div>
          )}

          <Button onClick={puzzle.reset} variant="outline" className="mt-4 gap-2">
            <RotateCcw className="h-4 w-4" />
            Try Again
          </Button>
        </div>
      </motion.div>
    );
  }

  // Render running state - active challenge
  return (
    <div className={cn('space-y-4', className)}>
      {/* Progress bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Progress</span>
          <span className="font-medium">
            {puzzle.stepsCompleted}/{puzzle.totalSteps} challenges
          </span>
        </div>
        <Progress value={puzzle.progress} className="h-2" />
      </div>

      {/* Camera feed */}
      <div className="relative aspect-video w-full overflow-hidden rounded-xl bg-black">
        <video
          ref={videoRefCallback}
          autoPlay
          playsInline
          muted
          className="h-full w-full object-cover"
        />
        <canvas ref={canvasRef} className="hidden" />

        {/* Face guide overlay */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div
            className={cn(
              'h-48 w-36 rounded-full border-4 transition-colors',
              pulseAnimation
                ? 'border-green-500 shadow-lg shadow-green-500/50'
                : 'border-white/50'
            )}
          />
        </div>
      </div>

      {/* Current challenge card */}
      <AnimatePresence mode="wait">
        {puzzle.currentStep && (
          <motion.div
            key={puzzle.currentStep.action}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className={cn(
              'rounded-xl border-2 p-6 text-center transition-colors',
              pulseAnimation
                ? 'border-green-500 bg-green-50 dark:bg-green-950/30'
                : 'border-primary/20 bg-card'
            )}
          >
            {/* Challenge icon */}
            <motion.div
              animate={pulseAnimation ? { scale: [1, 1.2, 1] } : {}}
              className={cn(
                'mx-auto mb-4 flex h-24 w-24 items-center justify-center rounded-full',
                puzzle.actionDetected
                  ? 'bg-green-500/20 text-green-600'
                  : 'bg-primary/10 text-primary'
              )}
            >
              {CHALLENGE_ICONS[puzzle.currentStep.action] || (
                <CircleDot className="h-12 w-12" />
              )}
            </motion.div>

            {/* Instruction */}
            <h3 className="mb-2 text-xl font-bold">{puzzle.currentInstruction}</h3>

            {/* Timer */}
            <div className="mt-4 flex items-center justify-center gap-2">
              <Timer className="h-4 w-4 text-muted-foreground" />
              <span
                className={cn(
                  'font-mono text-lg',
                  puzzle.timeRemaining < 2 ? 'text-red-600' : 'text-muted-foreground'
                )}
              >
                {puzzle.timeRemaining.toFixed(1)}s
              </span>
            </div>

            {/* Confidence indicator */}
            {puzzle.actionConfidence > 0 && (
              <div className="mt-3">
                <Progress value={puzzle.actionConfidence * 100} className="h-1" />
              </div>
            )}

            {/* Simulate button for testing */}
            <div className="mt-4">
              <Button
                onClick={handleSimulateAction}
                variant="outline"
                size="sm"
                className="text-xs"
              >
                Simulate Action (Dev)
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Completed challenges */}
      {puzzle.stepsCompleted > 0 && (
        <div className="flex justify-center gap-2">
          {Array.from({ length: puzzle.totalSteps }).map((_, i) => (
            <div
              key={i}
              className={cn(
                'flex h-8 w-8 items-center justify-center rounded-full',
                i < puzzle.stepsCompleted
                  ? 'bg-green-500 text-white'
                  : i === puzzle.currentStepIndex
                  ? 'bg-primary text-white'
                  : 'bg-muted'
              )}
            >
              {i < puzzle.stepsCompleted ? (
                <CheckCircle2 className="h-4 w-4" />
              ) : (
                <span className="text-xs">{i + 1}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
