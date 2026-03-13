/**
 * Hybrid verification use case — client pre-check + server verification.
 *
 * Client: detect + quality gate (reject early)
 * Server: embedding extraction + similarity computation
 */

import type { IFaceDetector } from '../../domain/interfaces/face-detector';
import type { IQualityAssessor } from '../../domain/interfaces/quality-assessor';
import type { IBiometricApiClient } from '../../domain/interfaces/biometric-api-client';
import type { DetectorInput, VerifyFaceResponse } from '../../domain/types';
import type { FaceDetectionResult } from '../../domain/entities/face-detection-result';
import type { QualityAssessment } from '../../domain/entities/quality-assessment';
import {
  FaceNotDetectedError,
  PoorImageQualityError,
} from '../../domain/errors';

export interface HybridVerifyParams {
  readonly personId: string;
  readonly image: DetectorInput;
  readonly canvas: HTMLCanvasElement;
  readonly threshold?: number;
}

export interface HybridVerifyResult extends VerifyFaceResponse {
  readonly clientSide: {
    readonly detection: FaceDetectionResult;
    readonly quality: QualityAssessment;
    readonly processingTimeMs: number;
  };
}

export class HybridVerifyFaceUseCase {
  constructor(
    private readonly detector: IFaceDetector,
    private readonly qualityAssessor: IQualityAssessor,
    private readonly apiClient: IBiometricApiClient,
  ) {}

  async execute(params: HybridVerifyParams): Promise<HybridVerifyResult> {
    const startTime = performance.now();

    // Phase 1 — Client-side quality gate
    const detection = await this.detector.detect(params.image);
    if (!detection.found) {
      throw new FaceNotDetectedError();
    }

    const faceImage = detection.getFaceRegion(params.canvas);
    if (!faceImage) {
      throw new FaceNotDetectedError('Face detected but region could not be extracted');
    }

    const quality = await this.qualityAssessor.assess(faceImage);
    if (!quality.isAcceptable) {
      throw new PoorImageQualityError(
        quality.score,
        this.qualityAssessor.getMinimumAcceptableScore(),
        quality.getIssues(),
      );
    }

    const clientProcessingTime = Math.round(performance.now() - startTime);

    // Phase 2 — Server-side verification
    const imageBlob = await new Promise<Blob>((resolve, reject) => {
      params.canvas.toBlob(
        (blob) => (blob ? resolve(blob) : reject(new Error('Failed to create blob'))),
        'image/jpeg',
        0.9,
      );
    });

    const serverResult = await this.apiClient.verifyFace({
      personId: params.personId,
      image: imageBlob,
      threshold: params.threshold,
    });

    return {
      ...serverResult,
      clientSide: {
        detection,
        quality,
        processingTimeMs: clientProcessingTime,
      },
    };
  }
}
