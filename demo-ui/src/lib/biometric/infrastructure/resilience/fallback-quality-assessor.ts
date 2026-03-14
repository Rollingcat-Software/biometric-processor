/**
 * Resilient quality assessor with automatic fallback.
 *
 * Decorator Pattern: Wraps a primary IQualityAssessor and falls back
 * to a secondary implementation on failure.
 */

import type { IQualityAssessor } from '../../domain/interfaces/quality-assessor';
import type { ILogger } from '../../domain/interfaces/logger';
import type { QualityAssessment } from '../../domain/entities/quality-assessment';

export class FallbackQualityAssessor implements IQualityAssessor {
  constructor(
    private readonly primary: IQualityAssessor,
    private readonly fallback: IQualityAssessor,
    private readonly logger: ILogger,
  ) {}

  async assess(faceImage: ImageData): Promise<QualityAssessment> {
    try {
      return await this.primary.assess(faceImage);
    } catch (error) {
      this.logger.warn('Primary quality assessor failed, using fallback', {
        error: error instanceof Error ? error.message : String(error),
      });
      return this.fallback.assess(faceImage);
    }
  }

  getMinimumAcceptableScore(): number {
    return this.primary.getMinimumAcceptableScore();
  }
}
