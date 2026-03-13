/**
 * Server-side quality assessment fallback adapter.
 *
 * Implements IQualityAssessor by delegating to the backend API.
 * Used when OpenCV.js is not available or fails to load.
 */

import type { IQualityAssessor } from '../../domain/interfaces/quality-assessor';
import type { IBiometricApiClient } from '../../domain/interfaces/biometric-api-client';
import { QualityAssessment } from '../../domain/entities/quality-assessment';

export class ServerQualityAssessor implements IQualityAssessor {
  constructor(private readonly apiClient: IBiometricApiClient) {}

  async assess(faceImage: ImageData): Promise<QualityAssessment> {
    // Convert ImageData to Blob for upload
    const canvas = document.createElement('canvas');
    canvas.width = faceImage.width;
    canvas.height = faceImage.height;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Cannot create canvas context');
    ctx.putImageData(faceImage, 0, 0);

    const blob = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (b) => (b ? resolve(b) : reject(new Error('Failed to create blob'))),
        'image/jpeg',
        0.9,
      );
    });

    const response = await this.apiClient.assessQuality(blob);

    return QualityAssessment.create({
      score: response.score,
      blurScore: response.blurScore,
      lightingScore: response.lightingScore,
      faceSize: response.faceSize,
      isAcceptable: response.isAcceptable,
    });
  }

  getMinimumAcceptableScore(): number {
    return 50;
  }
}
