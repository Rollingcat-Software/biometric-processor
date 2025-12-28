/**
 * Puzzle Liveness Hook
 *
 * Manages the complete puzzle liveness flow:
 * 1. Generate puzzle from backend
 * 2. Guide user through challenges
 * 3. Collect step evidence
 * 4. Verify completion with backend
 *
 * Uses explicit state machine for predictable state transitions.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { generatePuzzle, verifyPuzzle, getChallengeInstruction } from '@/lib/api/puzzle';
import type {
  PuzzleState,
  GeneratePuzzleRequest,
  GeneratePuzzleResponse,
  StepEvidence,
  VerifyPuzzleResponse,
  PuzzleStep,
  ChallengeType,
} from '@/types/api';

interface PuzzleLivenessState {
  state: PuzzleState;
  puzzle: GeneratePuzzleResponse | null;
  currentStepIndex: number;
  stepResults: StepEvidence[];
  error: string | null;
  verificationResult: VerifyPuzzleResponse | null;
  timeRemaining: number;
  currentInstruction: string;
  actionDetected: boolean;
  actionConfidence: number;
}

interface UsePuzzleLivenessOptions {
  difficulty?: 'easy' | 'standard' | 'hard';
  onStepComplete?: (step: PuzzleStep, evidence: StepEvidence) => void;
  onComplete?: (result: VerifyPuzzleResponse) => void;
  onError?: (error: string) => void;
}

const initialState: PuzzleLivenessState = {
  state: 'idle',
  puzzle: null,
  currentStepIndex: 0,
  stepResults: [],
  error: null,
  verificationResult: null,
  timeRemaining: 0,
  currentInstruction: '',
  actionDetected: false,
  actionConfidence: 0,
};

export function usePuzzleLiveness(options: UsePuzzleLivenessOptions = {}) {
  const [session, setSession] = useState<PuzzleLivenessState>(initialState);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const stepStartTimeRef = useRef<number>(0);
  const optionsRef = useRef(options);
  optionsRef.current = options;

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  // Start a new puzzle session
  const startPuzzle = useCallback(async (request?: GeneratePuzzleRequest) => {
    setSession((prev) => ({ ...prev, state: 'loading', error: null }));

    try {
      const puzzle = await generatePuzzle({
        difficulty: optionsRef.current.difficulty || 'standard',
        ...request,
      });

      setSession({
        ...initialState,
        state: 'ready',
        puzzle,
        currentInstruction: 'Get ready! Position your face in the camera.',
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to generate puzzle';
      setSession((prev) => ({
        ...prev,
        state: 'error',
        error: message,
      }));
      optionsRef.current.onError?.(message);
    }
  }, []);

  // Begin running the challenges
  const beginChallenges = useCallback(() => {
    setSession((prev) => {
      if (!prev.puzzle || prev.state !== 'ready') return prev;

      const firstStep = prev.puzzle.steps[0];
      stepStartTimeRef.current = Date.now() / 1000;

      return {
        ...prev,
        state: 'running',
        currentStepIndex: 0,
        timeRemaining: firstStep.duration_seconds,
        currentInstruction: getChallengeInstruction(firstStep.action),
        actionDetected: false,
        actionConfidence: 0,
      };
    });

    // Start countdown timer
    timerRef.current = setInterval(() => {
      setSession((prev) => {
        if (prev.state !== 'running' || !prev.puzzle) {
          if (timerRef.current) clearInterval(timerRef.current);
          return prev;
        }

        const newTimeRemaining = Math.max(0, prev.timeRemaining - 0.1);

        // Time's up for this step
        if (newTimeRemaining <= 0) {
          // If action was detected, complete step
          if (prev.actionDetected) {
            return handleStepCompleteInternal(prev);
          }

          // Step failed - timeout
          if (timerRef.current) clearInterval(timerRef.current);
          return {
            ...prev,
            state: 'failed',
            error: `Timeout on challenge: ${prev.puzzle.steps[prev.currentStepIndex].action}`,
          };
        }

        return { ...prev, timeRemaining: newTimeRemaining };
      });
    }, 100);
  }, []);

  // Internal function to handle step completion
  const handleStepCompleteInternal = (prev: PuzzleLivenessState): PuzzleLivenessState => {
    if (!prev.puzzle) return prev;

    const currentStep = prev.puzzle.steps[prev.currentStepIndex];
    const endTime = Date.now() / 1000;

    // Create evidence for this step
    const evidence: StepEvidence = {
      action: currentStep.action,
      start_timestamp: stepStartTimeRef.current,
      end_timestamp: endTime,
      confidence: prev.actionConfidence,
      metrics: {},
    };

    const newResults = [...prev.stepResults, evidence];
    const nextIndex = prev.currentStepIndex + 1;

    // Notify callback
    optionsRef.current.onStepComplete?.(currentStep, evidence);

    // Check if all steps completed
    if (nextIndex >= prev.puzzle.steps.length) {
      if (timerRef.current) clearInterval(timerRef.current);
      return {
        ...prev,
        state: 'step_complete',
        stepResults: newResults,
        currentInstruction: 'All challenges completed! Verifying...',
      };
    }

    // Move to next step
    const nextStep = prev.puzzle.steps[nextIndex];
    stepStartTimeRef.current = Date.now() / 1000;

    return {
      ...prev,
      currentStepIndex: nextIndex,
      stepResults: newResults,
      timeRemaining: nextStep.duration_seconds,
      currentInstruction: getChallengeInstruction(nextStep.action),
      actionDetected: false,
      actionConfidence: 0,
    };
  };

  // Report action detection from camera/MediaPipe
  const reportActionDetected = useCallback(
    (action: ChallengeType, confidence: number, metrics?: Record<string, number>) => {
      setSession((prev) => {
        if (prev.state !== 'running' || !prev.puzzle) return prev;

        const currentStep = prev.puzzle.steps[prev.currentStepIndex];

        // Check if detected action matches current step
        if (action !== currentStep.action) {
          return prev;
        }

        // Update detection state
        const newState = {
          ...prev,
          actionDetected: true,
          actionConfidence: Math.max(prev.actionConfidence, confidence),
        };

        // Auto-complete step if confidence is high enough
        if (confidence >= 0.7) {
          return handleStepCompleteInternal(newState);
        }

        return newState;
      });
    },
    []
  );

  // Manually complete current step (for testing or fallback)
  const completeCurrentStep = useCallback(() => {
    setSession((prev) => {
      if (prev.state !== 'running') return prev;
      return handleStepCompleteInternal({
        ...prev,
        actionDetected: true,
        actionConfidence: 0.8,
      });
    });
  }, []);

  // Verify puzzle with backend
  const verify = useCallback(async (finalFrame?: string) => {
    setSession((prev) => {
      if (!prev.puzzle || prev.stepResults.length === 0) return prev;
      return { ...prev, state: 'verifying' };
    });

    // Get current state for verification
    const currentSession = await new Promise<PuzzleLivenessState>((resolve) => {
      setSession((prev) => {
        resolve(prev);
        return prev;
      });
    });

    if (!currentSession.puzzle) return;

    try {
      const result = await verifyPuzzle({
        puzzle_id: currentSession.puzzle.puzzle_id,
        results: currentSession.stepResults,
        final_frame: finalFrame,
        client_meta: {
          browser: navigator.userAgent,
          device: /Mobile|Android|iPhone/i.test(navigator.userAgent) ? 'mobile' : 'desktop',
        },
      });

      setSession((prev) => ({
        ...prev,
        state: result.liveness_confirmed ? 'success' : 'failed',
        verificationResult: result,
        currentInstruction: result.message,
      }));

      optionsRef.current.onComplete?.(result);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to verify puzzle';
      setSession((prev) => ({
        ...prev,
        state: 'error',
        error: message,
      }));
      optionsRef.current.onError?.(message);
    }
  }, []);

  // Auto-verify when all steps completed
  useEffect(() => {
    if (session.state === 'step_complete') {
      verify();
    }
  }, [session.state, verify]);

  // Reset to initial state
  const reset = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    setSession(initialState);
  }, []);

  // Get current step info
  const currentStep = session.puzzle?.steps[session.currentStepIndex] || null;

  return {
    // State
    state: session.state,
    puzzle: session.puzzle,
    currentStep,
    currentStepIndex: session.currentStepIndex,
    stepResults: session.stepResults,
    error: session.error,
    verificationResult: session.verificationResult,
    timeRemaining: session.timeRemaining,
    currentInstruction: session.currentInstruction,
    actionDetected: session.actionDetected,
    actionConfidence: session.actionConfidence,

    // Computed
    isIdle: session.state === 'idle',
    isLoading: session.state === 'loading',
    isReady: session.state === 'ready',
    isRunning: session.state === 'running',
    isVerifying: session.state === 'verifying',
    isSuccess: session.state === 'success',
    isFailed: session.state === 'failed' || session.state === 'timeout',
    isComplete: session.state === 'success' || session.state === 'failed',
    progress: session.puzzle
      ? (session.currentStepIndex / session.puzzle.steps.length) * 100
      : 0,
    stepsCompleted: session.stepResults.length,
    totalSteps: session.puzzle?.steps.length || 0,

    // Actions
    startPuzzle,
    beginChallenges,
    reportActionDetected,
    completeCurrentStep,
    verify,
    reset,
  };
}

export type { PuzzleLivenessState, UsePuzzleLivenessOptions };
