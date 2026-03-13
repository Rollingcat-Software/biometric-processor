/**
 * Face detection result value object.
 *
 * Mirrors: app/domain/entities/face_detection.py → FaceDetectionResult
 *
 * Immutable — all fields are readonly and validated at construction.
 * Uses a static factory method to enforce invariants.
 */

import type { BoundingBox, LandmarkPoint, Point } from '../types';

export interface FaceDetectionParams {
  readonly found: boolean;
  readonly boundingBox: BoundingBox | null;
  readonly landmarks: ReadonlyArray<LandmarkPoint> | null;
  readonly confidence: number;
}

export class FaceDetectionResult {
  readonly found: boolean;
  readonly boundingBox: BoundingBox | null;
  readonly landmarks: ReadonlyArray<LandmarkPoint> | null;
  readonly confidence: number;

  private constructor(params: FaceDetectionParams) {
    this.found = params.found;
    this.boundingBox = params.boundingBox;
    this.landmarks = params.landmarks;
    this.confidence = params.confidence;
  }

  /**
   * Create a validated FaceDetectionResult.
   *
   * @throws {Error} if invariants are violated:
   *   - confidence must be in [0, 1]
   *   - boundingBox required when found = true
   *   - boundingBox dimensions must be > 0
   */
  static create(params: FaceDetectionParams): FaceDetectionResult {
    if (params.confidence < 0 || params.confidence > 1) {
      throw new Error(
        `Confidence must be between 0 and 1, got ${params.confidence}`,
      );
    }

    if (params.found && !params.boundingBox) {
      throw new Error('Bounding box is required when face is found');
    }

    if (params.found && params.boundingBox) {
      if (params.boundingBox.width <= 0 || params.boundingBox.height <= 0) {
        throw new Error(
          `Invalid bounding box dimensions: ${params.boundingBox.width}x${params.boundingBox.height}`,
        );
      }
    }

    return new FaceDetectionResult(params);
  }

  /** Create a "not found" result. */
  static notFound(): FaceDetectionResult {
    return new FaceDetectionResult({
      found: false,
      boundingBox: null,
      landmarks: null,
      confidence: 0,
    });
  }

  /**
   * Extract the face region from a canvas as ImageData.
   *
   * @returns ImageData of the cropped face region, or null if no bounding box.
   */
  getFaceRegion(canvas: HTMLCanvasElement): ImageData | null {
    if (!this.boundingBox) return null;

    const ctx = canvas.getContext('2d');
    if (!ctx) return null;

    const { x, y, width, height } = this.boundingBox;

    const clampedX = Math.max(0, Math.round(x));
    const clampedY = Math.max(0, Math.round(y));
    const clampedW = Math.min(Math.round(width), canvas.width - clampedX);
    const clampedH = Math.min(Math.round(height), canvas.height - clampedY);

    if (clampedW <= 0 || clampedH <= 0) return null;

    return ctx.getImageData(clampedX, clampedY, clampedW, clampedH);
  }

  /** Get the center point of the detected face. */
  getFaceCenter(): Point | null {
    if (!this.boundingBox) return null;

    return {
      x: Math.round(this.boundingBox.x + this.boundingBox.width / 2),
      y: Math.round(this.boundingBox.y + this.boundingBox.height / 2),
    };
  }

  /** Get the minimum dimension of the face bounding box (for size checks). */
  getFaceMinDimension(): number {
    if (!this.boundingBox) return 0;
    return Math.min(this.boundingBox.width, this.boundingBox.height);
  }
}
