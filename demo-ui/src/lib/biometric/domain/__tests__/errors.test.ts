import { describe, it, expect } from 'vitest';
import {
  BiometricError,
  FaceNotDetectedError,
  MultipleFacesError,
  PoorImageQualityError,
  LivenessCheckError,
  ModelNotLoadedError,
  ModelLoadError,
  DetectionTimeoutError,
  isBiometricError,
} from '../errors';

describe('BiometricError hierarchy', () => {
  it('FaceNotDetectedError has correct code and message', () => {
    const err = new FaceNotDetectedError();
    expect(err.code).toBe('FACE_NOT_DETECTED');
    expect(err.message).toBe('No face detected in the image');
    expect(err).toBeInstanceOf(BiometricError);
    expect(err).toBeInstanceOf(Error);
  });

  it('FaceNotDetectedError accepts custom message', () => {
    const err = new FaceNotDetectedError('Custom message');
    expect(err.message).toBe('Custom message');
  });

  it('MultipleFacesError includes count', () => {
    const err = new MultipleFacesError(3);
    expect(err.code).toBe('MULTIPLE_FACES');
    expect(err.count).toBe(3);
    expect(err.message).toContain('3');
  });

  it('PoorImageQualityError includes score and issues', () => {
    const issues = [
      { type: 'blur' as const, description: 'Too blurry', score: 50, threshold: 100 },
    ];
    const err = new PoorImageQualityError(30, 50, issues);
    expect(err.code).toBe('POOR_IMAGE_QUALITY');
    expect(err.qualityScore).toBe(30);
    expect(err.minThreshold).toBe(50);
    expect(err.issues).toHaveLength(1);
  });

  it('LivenessCheckError includes optional score', () => {
    const err = new LivenessCheckError(25);
    expect(err.code).toBe('LIVENESS_CHECK_FAILED');
    expect(err.livenessScore).toBe(25);
  });

  it('ModelNotLoadedError includes model name', () => {
    const err = new ModelNotLoadedError('mediapipe');
    expect(err.code).toBe('MODEL_NOT_LOADED');
    expect(err.modelName).toBe('mediapipe');
  });

  it('ModelLoadError includes model name and cause', () => {
    const cause = new Error('Network timeout');
    const err = new ModelLoadError('mediapipe', cause);
    expect(err.code).toBe('MODEL_LOAD_FAILED');
    expect(err.modelName).toBe('mediapipe');
    expect(err.cause).toBe(cause);
    expect(err.message).toContain('Network timeout');
  });

  it('DetectionTimeoutError includes timeout value', () => {
    const err = new DetectionTimeoutError(500);
    expect(err.code).toBe('DETECTION_TIMEOUT');
    expect(err.timeoutMs).toBe(500);
  });
});

describe('isBiometricError', () => {
  it('returns true for BiometricError subclasses', () => {
    expect(isBiometricError(new FaceNotDetectedError())).toBe(true);
    expect(isBiometricError(new MultipleFacesError(2))).toBe(true);
    expect(isBiometricError(new ModelLoadError('test'))).toBe(true);
  });

  it('returns false for regular errors', () => {
    expect(isBiometricError(new Error('test'))).toBe(false);
    expect(isBiometricError(new TypeError('test'))).toBe(false);
  });

  it('returns false for non-error values', () => {
    expect(isBiometricError('string')).toBe(false);
    expect(isBiometricError(null)).toBe(false);
    expect(isBiometricError(undefined)).toBe(false);
    expect(isBiometricError(42)).toBe(false);
  });
});
