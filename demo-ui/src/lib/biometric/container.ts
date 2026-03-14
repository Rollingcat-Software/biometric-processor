/**
 * Dependency injection container for browser biometric processing.
 *
 * Mirrors: app/core/container.py
 *
 * Wires together all interfaces and implementations:
 * - Creates lazy-loaded model loaders (singleton per container)
 * - Applies decorator pattern for fallback resilience
 * - Exposes fully-configured use cases
 *
 * Usage:
 *   const container = createBiometricContainer(config);
 *   const result = await container.hybridEnroll.execute(params);
 */

import type { BiometricConfig } from './domain/types';
import type { IBiometricApiClient } from './domain/interfaces/biometric-api-client';
import { DEFAULT_BIOMETRIC_CONFIG } from './domain/types';

// Application use cases
import {
  ClientDetectFaceUseCase,
  ClientAssessQualityUseCase,
  HybridEnrollFaceUseCase,
  HybridVerifyFaceUseCase,
  RealTimeAnalysisUseCase,
} from './application';

// Infrastructure
import { MediaPipeFaceDetector } from './infrastructure/ml/mediapipe-face-detector';
import { OpenCVQualityAssessor } from './infrastructure/ml/opencv-quality-assessor';
import { MediaPipeLivenessDetector } from './infrastructure/ml/mediapipe-liveness-detector';
import { MediaPipeModelLoader } from './infrastructure/ml/loaders/mediapipe-model-loader';
import { OpenCVModelLoader } from './infrastructure/ml/loaders/opencv-model-loader';
import { ServerFaceDetector } from './infrastructure/server/server-face-detector';
import { ServerQualityAssessor } from './infrastructure/server/server-quality-assessor';
import { BiometricApiClientImpl } from './infrastructure/server/biometric-api-client-impl';
import { FallbackFaceDetector } from './infrastructure/resilience/fallback-face-detector';
import { FallbackQualityAssessor } from './infrastructure/resilience/fallback-quality-assessor';
import { ConsoleLogger } from './infrastructure/logging/console-logger';

/**
 * Container interface — exposes use cases and lifecycle management.
 */
export interface BiometricContainer {
  readonly clientDetectFace: ClientDetectFaceUseCase;
  readonly clientAssessQuality: ClientAssessQualityUseCase;
  readonly hybridEnroll: HybridEnrollFaceUseCase;
  readonly hybridVerify: HybridVerifyFaceUseCase;
  readonly realtimeAnalysis: RealTimeAnalysisUseCase;

  /** Release all loaded models and resources. */
  dispose(): Promise<void>;
}

/**
 * Create a fully-wired biometric container.
 *
 * @param config - Override default biometric config values
 * @param apiClient - Optional custom API client (useful for testing)
 */
export function createBiometricContainer(
  config: Partial<BiometricConfig> = {},
  apiClient?: IBiometricApiClient,
): BiometricContainer {
  const cfg: BiometricConfig = { ...DEFAULT_BIOMETRIC_CONFIG, ...config };
  const logger = new ConsoleLogger('Container');
  const api = apiClient ?? new BiometricApiClientImpl();

  // ── Model Loaders (singleton, lazy) ──────────────────────────────

  const mediapipeDetectorLoader = new MediaPipeModelLoader(
    async () => {
      const vision = await import('@mediapipe/tasks-vision');
      const { FaceDetector, FilesetResolver } = vision;
      const filesetResolver = await FilesetResolver.forVisionTasks(
        'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm',
      );
      return FaceDetector.createFromOptions(filesetResolver, {
        baseOptions: {
          modelAssetPath:
            'https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite',
          delegate: 'GPU',
        },
        runningMode: 'IMAGE',
        minDetectionConfidence: cfg.detectionConfidence,
      });
    },
    'mediapipe-face-detector',
  );

  const mediapipeMeshLoader = new MediaPipeModelLoader(
    async () => {
      const vision = await import('@mediapipe/tasks-vision');
      const { FaceLandmarker, FilesetResolver } = vision;
      const filesetResolver = await FilesetResolver.forVisionTasks(
        'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm',
      );
      return FaceLandmarker.createFromOptions(filesetResolver, {
        baseOptions: {
          modelAssetPath:
            'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
          delegate: 'GPU',
        },
        runningMode: 'IMAGE',
        numFaces: 1,
        outputFaceBlendshapes: false,
        outputFacialTransformationMatrixes: false,
      });
    },
    'mediapipe-face-mesh',
  );

  const opencvLoader = new OpenCVModelLoader();

  // ── Infrastructure Adapters ──────────────────────────────────────

  const clientDetector = new MediaPipeFaceDetector(mediapipeDetectorLoader, cfg);
  const serverDetector = new ServerFaceDetector(api);

  const detector = cfg.serverFallbackEnabled
    ? new FallbackFaceDetector(clientDetector, serverDetector, logger)
    : clientDetector;

  const clientQuality = new OpenCVQualityAssessor(opencvLoader, cfg);
  const serverQuality = new ServerQualityAssessor(api);

  const qualityAssessor = cfg.serverFallbackEnabled
    ? new FallbackQualityAssessor(clientQuality, serverQuality, logger)
    : clientQuality;

  const livenessDetector = new MediaPipeLivenessDetector(mediapipeMeshLoader, cfg);

  // ── Application Use Cases ────────────────────────────────────────

  return {
    clientDetectFace: new ClientDetectFaceUseCase(detector),
    clientAssessQuality: new ClientAssessQualityUseCase(detector, qualityAssessor),
    hybridEnroll: new HybridEnrollFaceUseCase(
      detector,
      qualityAssessor,
      livenessDetector,
      api,
    ),
    hybridVerify: new HybridVerifyFaceUseCase(detector, qualityAssessor, api),
    realtimeAnalysis: new RealTimeAnalysisUseCase(detector, qualityAssessor, cfg),

    async dispose() {
      logger.info('Disposing biometric container...');
      await Promise.all([
        mediapipeDetectorLoader.unload(),
        mediapipeMeshLoader.unload(),
        opencvLoader.unload(),
      ]);
      logger.info('Biometric container disposed');
    },
  };
}
