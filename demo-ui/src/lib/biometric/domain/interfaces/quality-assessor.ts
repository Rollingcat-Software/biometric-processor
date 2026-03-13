/**
 * Port for image quality assessment.
 *
 * Mirrors: app/domain/interfaces/quality_assessor.py → IQualityAssessor
 */

import type { QualityAssessment } from '../entities/quality-assessment';

export interface IQualityAssessor {
  /**
   * Assess the quality of a face image.
   *
   * @param faceImage - Cropped face region as ImageData
   * @returns Quality assessment with metrics and overall score
   */
  assess(faceImage: ImageData): Promise<QualityAssessment>;

  /** Get minimum acceptable quality score (0-100). */
  getMinimumAcceptableScore(): number;
}
