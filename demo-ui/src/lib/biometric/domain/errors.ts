/**
 * Domain error hierarchy for browser-side biometric processing.
 *
 * Mirrors: app/domain/exceptions/face_errors.py
 *
 * Each error has a unique code for programmatic handling and
 * a human-readable message for display.
 */

import type { QualityIssue } from './types';

/**
 * Base class for all biometric domain errors.
 *
 * Provides a stable `code` field for switch/match handling
 * without relying on `instanceof` across module boundaries.
 */
export abstract class BiometricError extends Error {
  abstract readonly code: string;

  constructor(message: string) {
    super(message);
    this.name = this.constructor.name;
  }
}

/** No face detected in the provided image. */
export class FaceNotDetectedError extends BiometricError {
  readonly code = 'FACE_NOT_DETECTED' as const;

  constructor(message = 'No face detected in the image') {
    super(message);
  }
}

/** Multiple faces detected when exactly one was expected. */
export class MultipleFacesError extends BiometricError {
  readonly code = 'MULTIPLE_FACES' as const;

  constructor(readonly count: number) {
    super(`Expected 1 face, found ${count}`);
  }
}

/** Image quality is below the acceptable threshold. */
export class PoorImageQualityError extends BiometricError {
  readonly code = 'POOR_IMAGE_QUALITY' as const;

  constructor(
    readonly qualityScore: number,
    readonly minThreshold: number,
    readonly issues: ReadonlyArray<QualityIssue>,
  ) {
    super(
      `Quality score ${qualityScore.toFixed(1)} is below minimum threshold ${minThreshold}`,
    );
  }
}

/** Liveness check indicates a potential spoof. */
export class LivenessCheckError extends BiometricError {
  readonly code = 'LIVENESS_CHECK_FAILED' as const;

  constructor(
    readonly livenessScore?: number,
    message = 'Liveness check failed — possible spoof detected',
  ) {
    super(message);
  }
}

/** ML model is not loaded when inference was attempted. */
export class ModelNotLoadedError extends BiometricError {
  readonly code = 'MODEL_NOT_LOADED' as const;

  constructor(readonly modelName: string) {
    super(`Model "${modelName}" is not loaded. Call load() first.`);
  }
}

/** ML model failed to load (network, WASM, or initialization error). */
export class ModelLoadError extends BiometricError {
  readonly code = 'MODEL_LOAD_FAILED' as const;

  constructor(
    readonly modelName: string,
    readonly cause?: Error,
  ) {
    super(`Failed to load model "${modelName}"${cause ? `: ${cause.message}` : ''}`);
  }
}

/** Detection timed out (exceeded maxDetectionTimeMs budget). */
export class DetectionTimeoutError extends BiometricError {
  readonly code = 'DETECTION_TIMEOUT' as const;

  constructor(readonly timeoutMs: number) {
    super(`Face detection timed out after ${timeoutMs}ms`);
  }
}

/** Type guard: check if an unknown error is a BiometricError. */
export function isBiometricError(error: unknown): error is BiometricError {
  return error instanceof BiometricError;
}

/** All possible biometric error codes for exhaustive switch handling. */
export type BiometricErrorCode =
  | 'FACE_NOT_DETECTED'
  | 'MULTIPLE_FACES'
  | 'POOR_IMAGE_QUALITY'
  | 'LIVENESS_CHECK_FAILED'
  | 'MODEL_NOT_LOADED'
  | 'MODEL_LOAD_FAILED'
  | 'DETECTION_TIMEOUT';
