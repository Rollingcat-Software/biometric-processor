/**
 * Shared domain types for browser-side biometric processing.
 *
 * These types are used across all layers and have zero dependencies.
 * All types are immutable (readonly) to prevent accidental mutation.
 */

/** Input accepted by detector and assessor implementations. */
export type DetectorInput = ImageData | HTMLCanvasElement | HTMLVideoElement;

/** Bounding box in pixel coordinates. */
export interface BoundingBox {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

/** 2D/3D landmark point. */
export interface LandmarkPoint {
  readonly x: number;
  readonly y: number;
  readonly z?: number;
  readonly label?: string;
}

/** 2D point. */
export interface Point {
  readonly x: number;
  readonly y: number;
}

/** Quality issue descriptor. */
export interface QualityIssue {
  readonly type: 'blur' | 'lighting' | 'face_size' | 'occlusion' | 'pose';
  readonly description: string;
  readonly score: number;
  readonly threshold: number;
}

/** Biometric processing configuration. */
export interface BiometricConfig {
  readonly qualityThreshold: number;
  readonly blurThreshold: number;
  readonly minFaceSize: number;
  readonly livenessThreshold: number;
  readonly detectionConfidence: number;
  readonly maxDetectionTimeMs: number;
  readonly enableClientLiveness: boolean;
  readonly enableClientQuality: boolean;
  readonly serverFallbackEnabled: boolean;
}

/** Default configuration values. */
export const DEFAULT_BIOMETRIC_CONFIG: BiometricConfig = {
  qualityThreshold: 50,
  blurThreshold: 100,
  minFaceSize: 80,
  livenessThreshold: 50,
  detectionConfidence: 0.7,
  maxDetectionTimeMs: 500,
  enableClientLiveness: true,
  enableClientQuality: true,
  serverFallbackEnabled: true,
} as const;

/** Request types for server API communication. */
export interface EnrollFaceRequest {
  readonly personId: string;
  readonly image: Blob;
  readonly clientQualityScore?: number;
  readonly clientLivenessScore?: number;
  readonly clientDetectionTimeMs?: number;
  readonly metadata?: Record<string, unknown>;
}

export interface EnrollFaceResponse {
  readonly success: boolean;
  readonly userId: string;
  readonly embeddingId: string;
  readonly qualityScore: number;
  readonly message?: string;
}

export interface VerifyFaceRequest {
  readonly personId: string;
  readonly image: Blob;
  readonly threshold?: number;
}

export interface VerifyFaceResponse {
  readonly match: boolean;
  readonly similarity: number;
  readonly threshold: number;
  readonly processingTimeMs: number;
}

export interface SearchFaceRequest {
  readonly image: Blob;
  readonly maxResults?: number;
  readonly threshold?: number;
}

export interface SearchFaceResponse {
  readonly matches: ReadonlyArray<{
    readonly personId: string;
    readonly similarity: number;
  }>;
  readonly processingTimeMs: number;
}

export interface ServerLivenessResponse {
  readonly isLive: boolean;
  readonly livenessScore: number;
  readonly processingTimeMs: number;
}

export interface ServerQualityResponse {
  readonly score: number;
  readonly blurScore: number;
  readonly lightingScore: number;
  readonly faceSize: number;
  readonly isAcceptable: boolean;
}

/** WebAuthn types. */
export interface DeviceRegisterParams {
  readonly userId: string;
  readonly displayName: string;
}

export interface DeviceCredential {
  readonly credentialId: string;
  readonly publicKey: string;
  readonly userId: string;
  readonly createdAt: string;
}

export interface DeviceAuthParams {
  readonly userId: string;
}

export interface DeviceAuthResult {
  readonly success: boolean;
  readonly credentialId: string;
  readonly userId: string;
}
