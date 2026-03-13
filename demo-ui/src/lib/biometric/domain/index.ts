// Entities
export {
  FaceDetectionResult,
  QualityAssessment,
  LivenessResult,
} from './entities';
export type {
  FaceDetectionParams,
  QualityParams,
  QualityLevel,
  LivenessParams,
  ConfidenceLevel,
} from './entities';

// Interfaces
export type {
  IFaceDetector,
  IQualityAssessor,
  ILivenessDetector,
  IModelLoader,
  IBiometricApiClient,
  IDeviceAuthenticator,
  ILogger,
} from './interfaces';

// Errors
export {
  BiometricError,
  FaceNotDetectedError,
  MultipleFacesError,
  PoorImageQualityError,
  LivenessCheckError,
  ModelNotLoadedError,
  ModelLoadError,
  DetectionTimeoutError,
  isBiometricError,
} from './errors';
export type { BiometricErrorCode } from './errors';

// Types
export type {
  DetectorInput,
  BoundingBox,
  LandmarkPoint,
  Point,
  QualityIssue,
  BiometricConfig,
  EnrollFaceRequest,
  EnrollFaceResponse,
  VerifyFaceRequest,
  VerifyFaceResponse,
  SearchFaceRequest,
  SearchFaceResponse,
  ServerLivenessResponse,
  ServerQualityResponse,
  DeviceRegisterParams,
  DeviceCredential,
  DeviceAuthParams,
  DeviceAuthResult,
} from './types';
export { DEFAULT_BIOMETRIC_CONFIG } from './types';
