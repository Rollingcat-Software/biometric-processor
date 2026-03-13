/**
 * Port for server-side biometric API communication.
 *
 * Abstracts the HTTP client so use cases don't depend on fetch/axios.
 * Enables testing with mock API responses.
 */

import type {
  EnrollFaceRequest,
  EnrollFaceResponse,
  SearchFaceRequest,
  SearchFaceResponse,
  ServerLivenessResponse,
  ServerQualityResponse,
  VerifyFaceRequest,
  VerifyFaceResponse,
} from '../types';

export interface IBiometricApiClient {
  /** Enroll a face with pre-validated image. */
  enrollFace(params: EnrollFaceRequest): Promise<EnrollFaceResponse>;

  /** Verify a face against stored embedding. */
  verifyFace(params: VerifyFaceRequest): Promise<VerifyFaceResponse>;

  /** Search for matching faces. */
  searchFace(params: SearchFaceRequest): Promise<SearchFaceResponse>;

  /** Server-side liveness check (for high-security flows). */
  checkLiveness(image: Blob): Promise<ServerLivenessResponse>;

  /** Server-side quality check (fallback when client-side is unavailable). */
  assessQuality(image: Blob): Promise<ServerQualityResponse>;
}
