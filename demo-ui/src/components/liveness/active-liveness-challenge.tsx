'use client';

import { useEffect, useState } from 'react';
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
} from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils/cn';
import type { ActiveLivenessData } from '@/hooks/use-live-camera-analysis';

interface ActiveLivenessChallengeProps {
  data: ActiveLivenessData;
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

export function ActiveLivenessChallenge({
  data,
  className,
}: ActiveLivenessChallengeProps) {
  const [pulseAnimation, setPulseAnimation] = useState(false);

  // Trigger pulse animation when action is detected
  useEffect(() => {
    if (data.action_detected) {
      setPulseAnimation(true);
      const timer = setTimeout(() => setPulseAnimation(false), 500);
      return () => clearTimeout(timer);
    }
  }, [data.action_detected]);

  // Session complete view
  if (data.session_complete) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className={cn(
          'rounded-xl p-6 text-center',
          data.session_passed
            ? 'bg-green-50 dark:bg-green-950/30'
            : 'bg-red-50 dark:bg-red-950/30',
          className
        )}
      >
        <div className="flex flex-col items-center gap-4">
          {data.session_passed ? (
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
                Please try again
              </p>
            </>
          )}
          <div className="mt-2 text-sm text-muted-foreground">
            Score: {data.overall_score.toFixed(0)}% ({data.challenges_completed}/{data.challenges_total} challenges)
          </div>
        </div>
      </motion.div>
    );
  }

  // Active challenge view
  return (
    <div className={cn('space-y-4', className)}>
      {/* Progress bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Progress</span>
          <span className="font-medium">
            {data.challenges_completed}/{data.challenges_total} challenges
          </span>
        </div>
        <Progress
          value={(data.challenges_completed / data.challenges_total) * 100}
          className="h-2"
        />
      </div>

      {/* Current challenge card */}
      <AnimatePresence mode="wait">
        {data.current_challenge && (
          <motion.div
            key={data.current_challenge}
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
                data.action_detected
                  ? 'bg-green-500/20 text-green-600'
                  : 'bg-primary/10 text-primary'
              )}
            >
              {CHALLENGE_ICONS[data.current_challenge] || (
                <CircleDot className="h-12 w-12" />
              )}
            </motion.div>

            {/* Instruction */}
            <h3 className="mb-2 text-xl font-bold">{data.instruction}</h3>

            {/* Feedback */}
            <AnimatePresence mode="wait">
              {data.feedback && (
                <motion.p
                  key={data.feedback}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className={cn(
                    'text-sm',
                    data.action_detected
                      ? 'text-green-600 dark:text-green-400'
                      : 'text-muted-foreground'
                  )}
                >
                  {data.feedback}
                </motion.p>
              )}
            </AnimatePresence>

            {/* Timer */}
            <div className="mt-4 flex items-center justify-center gap-2">
              <Timer className="h-4 w-4 text-muted-foreground" />
              <span
                className={cn(
                  'font-mono text-lg',
                  data.time_remaining < 2
                    ? 'text-red-600'
                    : 'text-muted-foreground'
                )}
              >
                {data.time_remaining.toFixed(1)}s
              </span>
            </div>

            {/* Confidence indicator */}
            {data.action_confidence > 0 && (
              <div className="mt-3">
                <Progress
                  value={data.action_confidence * 100}
                  className="h-1"
                />
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Completed challenges */}
      {data.challenges_completed > 0 && (
        <div className="flex justify-center gap-2">
          {Array.from({ length: data.challenges_total }).map((_, i) => (
            <div
              key={i}
              className={cn(
                'flex h-8 w-8 items-center justify-center rounded-full',
                i < data.challenges_completed
                  ? 'bg-green-500 text-white'
                  : i === data.challenges_completed
                  ? 'bg-primary text-white'
                  : 'bg-muted'
              )}
            >
              {i < data.challenges_completed ? (
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
