/**
 * OpenCV.js quality assessment adapter.
 *
 * Implements IQualityAssessor using OpenCV.js for:
 * - Blur detection (Laplacian variance)
 * - Lighting assessment (mean brightness + histogram spread)
 * - Face size validation
 *
 * Mirrors: app/infrastructure/ml/quality/quality_assessor.py
 */

import type { IQualityAssessor } from '../../domain/interfaces/quality-assessor';
import type { IModelLoader } from '../../domain/interfaces/model-loader';
import type { BiometricConfig } from '../../domain/types';
import { QualityAssessment } from '../../domain/entities/quality-assessment';

/* eslint-disable @typescript-eslint/no-explicit-any */
type CV = any;
/* eslint-enable @typescript-eslint/no-explicit-any */

export class OpenCVQualityAssessor implements IQualityAssessor {
  constructor(
    private readonly modelLoader: IModelLoader<CV>,
    private readonly config: Pick<BiometricConfig, 'qualityThreshold' | 'blurThreshold' | 'minFaceSize'>,
  ) {}

  async assess(faceImage: ImageData): Promise<QualityAssessment> {
    const cv = await this.modelLoader.load();

    // Convert ImageData to OpenCV Mat
    const mat = cv.matFromImageData(faceImage);

    try {
      const blurScore = this.computeBlurScore(cv, mat);
      const lightingScore = this.computeLightingScore(cv, mat);
      const faceSize = Math.min(faceImage.width, faceImage.height);

      // Compute overall score as weighted average
      const blurWeight = 0.4;
      const lightingWeight = 0.3;
      const sizeWeight = 0.3;

      const normalizedBlur = Math.min(blurScore / (this.config.blurThreshold * 2), 1) * 100;
      const normalizedSize = Math.min(faceSize / (this.config.minFaceSize * 2), 1) * 100;

      const score = Math.round(
        normalizedBlur * blurWeight +
        lightingScore * lightingWeight +
        normalizedSize * sizeWeight,
      );

      const clampedScore = Math.max(0, Math.min(100, score));
      const isAcceptable = clampedScore >= this.config.qualityThreshold;

      return QualityAssessment.create({
        score: clampedScore,
        blurScore,
        lightingScore,
        faceSize,
        isAcceptable,
      });
    } finally {
      mat.delete();
    }
  }

  getMinimumAcceptableScore(): number {
    return this.config.qualityThreshold;
  }

  /**
   * Compute blur score using Laplacian variance.
   * Higher value = sharper image.
   */
  private computeBlurScore(cv: CV, mat: CV): number {
    const gray = new cv.Mat();
    const laplacian = new cv.Mat();

    try {
      cv.cvtColor(mat, gray, cv.COLOR_RGBA2GRAY);
      cv.Laplacian(gray, laplacian, cv.CV_64F);

      const mean = new cv.Mat();
      const stddev = new cv.Mat();
      cv.meanStdDev(laplacian, mean, stddev);

      // Variance = stddev^2
      const variance = Math.pow(stddev.doubleAt(0, 0), 2);
      mean.delete();
      stddev.delete();

      return Math.round(variance * 100) / 100;
    } finally {
      gray.delete();
      laplacian.delete();
    }
  }

  /**
   * Compute lighting score from brightness distribution.
   * Scores 0-100 based on mean brightness and histogram spread.
   */
  private computeLightingScore(cv: CV, mat: CV): number {
    const gray = new cv.Mat();

    try {
      cv.cvtColor(mat, gray, cv.COLOR_RGBA2GRAY);

      const mean = new cv.Mat();
      const stddev = new cv.Mat();
      cv.meanStdDev(gray, mean, stddev);

      const brightness = mean.doubleAt(0, 0);
      const contrast = stddev.doubleAt(0, 0);
      mean.delete();
      stddev.delete();

      // Ideal brightness is around 120-140 (on 0-255 scale)
      // Score decreases as brightness deviates from ideal
      const idealBrightness = 130;
      const brightnessPenalty = Math.abs(brightness - idealBrightness) / idealBrightness;
      const brightnessScore = Math.max(0, 1 - brightnessPenalty) * 100;

      // Good contrast means stddev > 40
      const contrastScore = Math.min(contrast / 60, 1) * 100;

      // Combined score
      return Math.round(brightnessScore * 0.6 + contrastScore * 0.4);
    } finally {
      gray.delete();
    }
  }
}
