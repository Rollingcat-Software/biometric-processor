/**
 * Resilient face detector with automatic fallback.
 *
 * Decorator Pattern: Wraps a primary IFaceDetector and falls back
 * to a secondary implementation on failure.
 *
 * Example: MediaPipeFaceDetector (primary) -> ServerFaceDetector (fallback)
 */

import type { IFaceDetector } from '../../domain/interfaces/face-detector';
import type { ILogger } from '../../domain/interfaces/logger';
import type { DetectorInput } from '../../domain/types';
import type { FaceDetectionResult } from '../../domain/entities/face-detection-result';

export class FallbackFaceDetector implements IFaceDetector {
  constructor(
    private readonly primary: IFaceDetector,
    private readonly fallback: IFaceDetector,
    private readonly logger: ILogger,
  ) {}

  async detect(image: DetectorInput): Promise<FaceDetectionResult> {
    try {
      return await this.primary.detect(image);
    } catch (error) {
      this.logger.warn('Primary face detector failed, using fallback', {
        error: error instanceof Error ? error.message : String(error),
      });
      return this.fallback.detect(image);
    }
  }

  async dispose(): Promise<void> {
    await Promise.all([this.primary.dispose(), this.fallback.dispose()]);
  }
}
