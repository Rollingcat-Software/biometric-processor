// Public API for biometric module

// Domain
export {
  FaceDetectionResult,
  QualityAssessment,
  LivenessResult,
  DEFAULT_BIOMETRIC_CONFIG,
  BiometricError,
  FaceNotDetectedError,
  MultipleFacesError,
  PoorImageQualityError,
  LivenessCheckError,
  ModelNotLoadedError,
  ModelLoadError,
  DetectionTimeoutError,
  isBiometricError,
} from './domain';

export type {
  IFaceDetector,
  IQualityAssessor,
  ILivenessDetector,
  IModelLoader,
  IBiometricApiClient,
  IDeviceAuthenticator,
  ILogger,
  BiometricConfig,
  DetectorInput,
  BoundingBox,
  LandmarkPoint,
  Point,
  QualityIssue,
  BiometricErrorCode,
} from './domain';

// Application
export {
  ClientDetectFaceUseCase,
  ClientAssessQualityUseCase,
  HybridEnrollFaceUseCase,
  HybridVerifyFaceUseCase,
  RealTimeAnalysisUseCase,
} from './application';

export type {
  ClientQualityResult,
  HybridEnrollParams,
  HybridEnrollResult,
  HybridVerifyParams,
  HybridVerifyResult,
  FrameAnalysis,
} from './application';

// Container
export { createBiometricContainer } from './container';
export type { BiometricContainer } from './container';

// Provider
export { BiometricProvider, useBiometricContainer } from './provider';
