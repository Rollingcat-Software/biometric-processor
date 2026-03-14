/**
 * Client-side face detection use case.
 *
 * Mirrors: app/application/use_cases/detect_multi_face.py (single face variant)
 *
 * SRP: Only orchestrates detection — no quality or liveness logic.
 * DIP: Depends on IFaceDetector interface, not MediaPipe directly.
 */

import type { IFaceDetector } from '../../domain/interfaces/face-detector';
import type { DetectorInput } from '../../domain/types';
import { FaceDetectionResult } from '../../domain/entities/face-detection-result';
import { FaceNotDetectedError } from '../../domain/errors';

export class ClientDetectFaceUseCase {
  constructor(private readonly detector: IFaceDetector) {}

  async execute(image: DetectorInput): Promise<FaceDetectionResult> {
    const result = await this.detector.detect(image);

    if (!result.found) {
      throw new FaceNotDetectedError();
    }

    return result;
  }
}
