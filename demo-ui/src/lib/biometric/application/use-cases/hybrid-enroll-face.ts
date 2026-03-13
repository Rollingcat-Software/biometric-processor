/**
 * Hybrid enrollment use case — client pre-processing + server enrollment.
 *
 * Client side:
 * 1. Detect face (MediaPipe WASM)
 * 2. Assess quality (OpenCV.js)
 * 3. Passive liveness check (MediaPipe)
 * 4. Reject poor images BEFORE upload
 *
 * Server side:
 * 5. Extract embedding (DeepFace — requires GPU/CPU-intensive models)
 * 6. Store in pgvector database
 * 7. Return enrollment result
 *
 * Security: Embeddings never leave the server. Client scores are advisory.
 */

import type { IFaceDetector } from '../../domain/interfaces/face-detector';
import type { IQualityAssessor } from '../../domain/interfaces/quality-assessor';
import type { ILivenessDetector } from '../../domain/interfaces/liveness-detector';
import type { IBiometricApiClient } from '../../domain/interfaces/biometric-api-client';
import type { DetectorInput, EnrollFaceResponse } from '../../domain/types';
import type { FaceDetectionResult } from '../../domain/entities/face-detection-result';
import type { QualityAssessment } from '../../domain/entities/quality-assessment';
import type { LivenessResult } from '../../domain/entities/liveness-result';
import {
  FaceNotDetectedError,
  PoorImageQualityError,
  LivenessCheckError,
} from '../../domain/errors';

export interface HybridEnrollParams {
  readonly personId: string;
  readonly image: DetectorInput;
  readonly canvas: HTMLCanvasElement;
  readonly metadata?: Record<string, unknown>;
}

export interface HybridEnrollResult extends EnrollFaceResponse {
  readonly clientSide: {
    readonly detection: FaceDetectionResult;
    readonly quality: QualityAssessment;
    readonly liveness: LivenessResult;
    readonly processingTimeMs: number;
  };
}

export class HybridEnrollFaceUseCase {
  constructor(
    private readonly detector: IFaceDetector,
    private readonly qualityAssessor: IQualityAssessor,
    private readonly livenessDetector: ILivenessDetector,
    private readonly apiClient: IBiometricApiClient,
  ) {}

  async execute(params: HybridEnrollParams): Promise<HybridEnrollResult> {
    const startTime = performance.now();

    // Phase 1 — Client-side pre-processing (instant feedback)
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

    const liveness = await this.livenessDetector.checkLiveness(params.image);
    if (liveness.isSpoofSuspected()) {
      throw new LivenessCheckError(liveness.livenessScore);
    }

    const clientProcessingTime = Math.round(performance.now() - startTime);

    // Phase 2 — Server-side enrollment (security-critical)
    const imageBlob = await this.canvasToBlob(params.canvas);

    const serverResult = await this.apiClient.enrollFace({
      personId: params.personId,
      image: imageBlob,
      clientQualityScore: quality.score,
      clientLivenessScore: liveness.livenessScore,
      clientDetectionTimeMs: clientProcessingTime,
      metadata: params.metadata,
    });

    return {
      ...serverResult,
      clientSide: {
        detection,
        quality,
        liveness,
        processingTimeMs: clientProcessingTime,
      },
    };
  }

  private canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
    return new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (blob) => (blob ? resolve(blob) : reject(new Error('Failed to create blob from canvas'))),
        'image/jpeg',
        0.9,
      );
    });
  }
}
