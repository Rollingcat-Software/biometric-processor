/**
 * Mock implementations for testing.
 *
 * Each mock implements the domain interface and returns configurable results.
 * Used in use case, hook, and component tests.
 */

import type { IFaceDetector } from '../domain/interfaces/face-detector';
import type { IQualityAssessor } from '../domain/interfaces/quality-assessor';
import type { ILivenessDetector } from '../domain/interfaces/liveness-detector';
import type { IBiometricApiClient } from '../domain/interfaces/biometric-api-client';
import type { ILogger } from '../domain/interfaces/logger';
import type { DetectorInput } from '../domain/types';
import { FaceDetectionResult } from '../domain/entities/face-detection-result';
import { QualityAssessment } from '../domain/entities/quality-assessment';
import { LivenessResult } from '../domain/entities/liveness-result';
import type { BiometricContainer } from '../container';

// ── Default mock values ────────────────────────────────────────────

const DEFAULT_DETECTION = FaceDetectionResult.create({
  found: true,
  boundingBox: { x: 50, y: 50, width: 200, height: 200 },
  landmarks: null,
  confidence: 0.95,
});

const DEFAULT_QUALITY = QualityAssessment.create({
  score: 85,
  blurScore: 150,
  lightingScore: 70,
  faceSize: 200,
  isAcceptable: true,
});

const DEFAULT_LIVENESS = LivenessResult.create({
  isLive: true,
  livenessScore: 90,
  challenge: 'passive_depth',
  challengeCompleted: true,
});

// ── Mock factories ─────────────────────────────────────────────────

export function createMockFaceDetector(
  result: FaceDetectionResult = DEFAULT_DETECTION,
): IFaceDetector {
  return {
    detect: async (_image: DetectorInput) => result,
    dispose: async () => {},
  };
}

export function createMockQualityAssessor(
  result: QualityAssessment = DEFAULT_QUALITY,
  minScore = 50,
): IQualityAssessor {
  return {
    assess: async (_faceImage: ImageData) => result,
    getMinimumAcceptableScore: () => minScore,
  };
}

export function createMockLivenessDetector(
  result: LivenessResult = DEFAULT_LIVENESS,
): ILivenessDetector {
  return {
    checkLiveness: async (_image: DetectorInput) => result,
    getChallengeType: () => result.challenge,
    getLivenessThreshold: () => 50,
  };
}

export function createMockApiClient(
  overrides: Partial<IBiometricApiClient> = {},
): IBiometricApiClient {
  return {
    enrollFace: async () => ({
      success: true,
      userId: 'user-1',
      embeddingId: 'emb-1',
      qualityScore: 85,
      message: 'Enrolled successfully',
    }),
    verifyFace: async () => ({
      match: true,
      similarity: 0.92,
      threshold: 0.6,
      processingTimeMs: 150,
    }),
    searchFace: async () => ({
      matches: [{ personId: 'user-1', similarity: 0.92 }],
      processingTimeMs: 200,
    }),
    checkLiveness: async () => ({
      isLive: true,
      livenessScore: 90,
      processingTimeMs: 100,
    }),
    assessQuality: async () => ({
      score: 85,
      blurScore: 150,
      lightingScore: 70,
      faceSize: 200,
      isAcceptable: true,
    }),
    ...overrides,
  };
}

export function createMockLogger(): ILogger {
  return {
    debug: () => {},
    info: () => {},
    warn: () => {},
    error: () => {},
  };
}

/**
 * Create a fully-configured container with all mocks.
 * Useful for integration testing hooks and components.
 */
export function createMockBiometricContainer(
  overrides: Partial<BiometricContainer> = {},
): BiometricContainer {
  const { ClientDetectFaceUseCase } = require('../application/use-cases/client-detect-face');
  const { ClientAssessQualityUseCase } = require('../application/use-cases/client-assess-quality');
  const { HybridEnrollFaceUseCase } = require('../application/use-cases/hybrid-enroll-face');
  const { HybridVerifyFaceUseCase } = require('../application/use-cases/hybrid-verify-face');
  const { RealTimeAnalysisUseCase } = require('../application/use-cases/realtime-analysis');

  const detector = createMockFaceDetector();
  const quality = createMockQualityAssessor();
  const liveness = createMockLivenessDetector();
  const api = createMockApiClient();

  return {
    clientDetectFace: new ClientDetectFaceUseCase(detector),
    clientAssessQuality: new ClientAssessQualityUseCase(detector, quality),
    hybridEnroll: new HybridEnrollFaceUseCase(detector, quality, liveness, api),
    hybridVerify: new HybridVerifyFaceUseCase(detector, quality, api),
    realtimeAnalysis: new RealTimeAnalysisUseCase(detector, quality, {
      maxDetectionTimeMs: 500,
    }),
    dispose: async () => {},
    ...overrides,
  };
}
