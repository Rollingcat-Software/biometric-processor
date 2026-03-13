/**
 * HTTP implementation of IBiometricApiClient.
 *
 * Wraps the existing apiClient from demo-ui to satisfy the domain interface.
 * Acts as an anti-corruption layer between the domain and HTTP infrastructure.
 */

import type { IBiometricApiClient } from '../../domain/interfaces/biometric-api-client';
import type {
  EnrollFaceRequest,
  EnrollFaceResponse,
  VerifyFaceRequest,
  VerifyFaceResponse,
  SearchFaceRequest,
  SearchFaceResponse,
  ServerLivenessResponse,
  ServerQualityResponse,
} from '../../domain/types';
import { apiClient } from '@/lib/api/client';

export class BiometricApiClientImpl implements IBiometricApiClient {
  async enrollFace(params: EnrollFaceRequest): Promise<EnrollFaceResponse> {
    const formData = new FormData();
    formData.append('user_id', params.personId);
    formData.append('file', params.image, 'capture.jpg');

    if (params.clientQualityScore !== undefined) {
      formData.append('client_quality_score', String(params.clientQualityScore));
    }
    if (params.clientLivenessScore !== undefined) {
      formData.append('client_liveness_score', String(params.clientLivenessScore));
    }
    if (params.clientDetectionTimeMs !== undefined) {
      formData.append('client_detection_time_ms', String(params.clientDetectionTimeMs));
    }

    const data = await apiClient.upload<{
      user_id: string;
      embedding_id: string;
      success: boolean;
      quality_score: number;
      message?: string;
    }>('/api/v1/enroll', formData);

    return {
      success: data.success,
      userId: data.user_id,
      embeddingId: data.embedding_id,
      qualityScore: data.quality_score,
      message: data.message,
    };
  }

  async verifyFace(params: VerifyFaceRequest): Promise<VerifyFaceResponse> {
    const formData = new FormData();
    formData.append('user_id', params.personId);
    formData.append('file', params.image, 'capture.jpg');
    if (params.threshold !== undefined) {
      formData.append('threshold', String(params.threshold));
    }

    const data = await apiClient.upload<{
      match: boolean;
      similarity: number;
      threshold: number;
      processing_time_ms: number;
    }>('/api/v1/verify', formData);

    return {
      match: data.match,
      similarity: data.similarity,
      threshold: data.threshold,
      processingTimeMs: data.processing_time_ms,
    };
  }

  async searchFace(params: SearchFaceRequest): Promise<SearchFaceResponse> {
    const formData = new FormData();
    formData.append('file', params.image, 'capture.jpg');
    if (params.maxResults !== undefined) {
      formData.append('max_results', String(params.maxResults));
    }
    if (params.threshold !== undefined) {
      formData.append('threshold', String(params.threshold));
    }

    const data = await apiClient.upload<{
      matches: Array<{ person_id: string; similarity: number }>;
      processing_time_ms: number;
    }>('/api/v1/search', formData);

    return {
      matches: data.matches.map((m) => ({
        personId: m.person_id,
        similarity: m.similarity,
      })),
      processingTimeMs: data.processing_time_ms,
    };
  }

  async checkLiveness(image: Blob): Promise<ServerLivenessResponse> {
    const formData = new FormData();
    formData.append('file', image, 'capture.jpg');

    const data = await apiClient.upload<{
      is_live: boolean;
      liveness_score: number;
      processing_time_ms: number;
    }>('/api/v1/liveness', formData);

    return {
      isLive: data.is_live,
      livenessScore: data.liveness_score,
      processingTimeMs: data.processing_time_ms,
    };
  }

  async assessQuality(image: Blob): Promise<ServerQualityResponse> {
    const formData = new FormData();
    formData.append('file', image, 'capture.jpg');

    const data = await apiClient.upload<{
      score: number;
      blur_score: number;
      lighting_score: number;
      face_size: number;
      is_acceptable: boolean;
    }>('/api/v1/quality', formData);

    return {
      score: data.score,
      blurScore: data.blur_score,
      lightingScore: data.lighting_score,
      faceSize: data.face_size,
      isAcceptable: data.is_acceptable,
    };
  }
}
