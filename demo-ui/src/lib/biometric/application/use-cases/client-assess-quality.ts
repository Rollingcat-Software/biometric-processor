/**
 * Client-side quality assessment use case.
 *
 * Mirrors: app/application/use_cases/analyze_quality.py
 *
 * Orchestrates:
 * 1. Detect face (to get face region)
 * 2. Assess quality on cropped region
 * 3. Return combined result
 *
 * SRP: Only orchestrates quality assessment pipeline.
 */

import type { IFaceDetector } from '../../domain/interfaces/face-detector';
import type { IQualityAssessor } from '../../domain/interfaces/quality-assessor';
import type { DetectorInput } from '../../domain/types';
import type { FaceDetectionResult } from '../../domain/entities/face-detection-result';
import type { QualityAssessment } from '../../domain/entities/quality-assessment';
import { FaceNotDetectedError } from '../../domain/errors';

export interface ClientQualityResult {
  readonly detection: FaceDetectionResult;
  readonly quality: QualityAssessment;
}

export class ClientAssessQualityUseCase {
  constructor(
    private readonly detector: IFaceDetector,
    private readonly qualityAssessor: IQualityAssessor,
  ) {}

  async execute(
    image: DetectorInput,
    canvas: HTMLCanvasElement,
  ): Promise<ClientQualityResult> {
    // Step 1: Detect face
    const detection = await this.detector.detect(image);
    if (!detection.found) {
      throw new FaceNotDetectedError();
    }

    // Step 2: Crop face region
    const faceImage = detection.getFaceRegion(canvas);
    if (!faceImage) {
      throw new FaceNotDetectedError('Face detected but region could not be extracted');
    }

    // Step 3: Assess quality
    const quality = await this.qualityAssessor.assess(faceImage);

    return { detection, quality };
  }
}
