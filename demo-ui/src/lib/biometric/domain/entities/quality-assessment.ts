/**
 * Quality assessment value object.
 *
 * Mirrors: app/domain/entities/quality_assessment.py → QualityAssessment
 *
 * Immutable — validated at construction via static factory.
 *
 * Quality Guidelines:
 *   - score 0-40:  Poor (reject)
 *   - score 41-70: Fair (warn user)
 *   - score 71-100: Good (accept)
 */

import type { QualityIssue } from '../types';

export interface QualityParams {
  readonly score: number;
  readonly blurScore: number;
  readonly lightingScore: number;
  readonly faceSize: number;
  readonly isAcceptable: boolean;
}

export type QualityLevel = 'poor' | 'fair' | 'good';

export class QualityAssessment {
  readonly score: number;
  readonly blurScore: number;
  readonly lightingScore: number;
  readonly faceSize: number;
  readonly isAcceptable: boolean;

  private constructor(params: QualityParams) {
    this.score = params.score;
    this.blurScore = params.blurScore;
    this.lightingScore = params.lightingScore;
    this.faceSize = params.faceSize;
    this.isAcceptable = params.isAcceptable;
  }

  /**
   * Create a validated QualityAssessment.
   *
   * @throws {Error} if invariants are violated:
   *   - score must be in [0, 100]
   *   - blurScore must be >= 0
   *   - faceSize must be >= 0
   */
  static create(params: QualityParams): QualityAssessment {
    if (params.score < 0 || params.score > 100) {
      throw new Error(`Score must be between 0 and 100, got ${params.score}`);
    }
    if (params.blurScore < 0) {
      throw new Error(`Blur score cannot be negative: ${params.blurScore}`);
    }
    if (params.faceSize < 0) {
      throw new Error(`Face size cannot be negative: ${params.faceSize}`);
    }
    return new QualityAssessment(params);
  }

  /** Get quality level based on score thresholds. */
  getQualityLevel(): QualityLevel {
    if (this.score < 40) return 'poor';
    if (this.score < 71) return 'fair';
    return 'good';
  }

  /** Check if the image is too blurry. */
  isBlurry(threshold = 100): boolean {
    return this.blurScore < threshold;
  }

  /** Check if the face is too small in the image. */
  isTooSmall(minSize = 80): boolean {
    return this.faceSize < minSize;
  }

  /** Check if lighting conditions are poor. */
  isPoorLighting(threshold = 50): boolean {
    return this.lightingScore < threshold;
  }

  /** Collect all detected quality issues. */
  getIssues(
    blurThreshold = 100,
    minFaceSize = 80,
    lightingThreshold = 50,
  ): QualityIssue[] {
    const issues: QualityIssue[] = [];

    if (this.isBlurry(blurThreshold)) {
      issues.push({
        type: 'blur',
        description: 'Image is too blurry',
        score: this.blurScore,
        threshold: blurThreshold,
      });
    }

    if (this.isTooSmall(minFaceSize)) {
      issues.push({
        type: 'face_size',
        description: 'Face is too small — move closer to camera',
        score: this.faceSize,
        threshold: minFaceSize,
      });
    }

    if (this.isPoorLighting(lightingThreshold)) {
      issues.push({
        type: 'lighting',
        description: 'Poor lighting conditions',
        score: this.lightingScore,
        threshold: lightingThreshold,
      });
    }

    return issues;
  }

  /** Convert to plain object for serialization. */
  toJSON(): QualityParams & { qualityLevel: QualityLevel } {
    return {
      score: this.score,
      blurScore: this.blurScore,
      lightingScore: this.lightingScore,
      faceSize: this.faceSize,
      isAcceptable: this.isAcceptable,
      qualityLevel: this.getQualityLevel(),
    };
  }
}
