/**
 * Real-time video frame analysis use case.
 *
 * Replaces WebSocket-based live analysis with client-side processing.
 * Designed to be called from requestAnimationFrame at target FPS.
 *
 * Returns null if processing exceeds the time budget to prevent
 * frame drops in the rendering pipeline.
 */

import type { IFaceDetector } from '../../domain/interfaces/face-detector';
import type { IQualityAssessor } from '../../domain/interfaces/quality-assessor';
import type { BiometricConfig, DetectorInput } from '../../domain/types';
import type { FaceDetectionResult } from '../../domain/entities/face-detection-result';
import type { QualityAssessment } from '../../domain/entities/quality-assessment';

export interface FrameAnalysis {
  readonly detection: FaceDetectionResult;
  readonly quality: QualityAssessment | null;
  readonly processingTimeMs: number;
  readonly timestamp: number;
}

export class RealTimeAnalysisUseCase {
  private canvas: HTMLCanvasElement | null = null;

  constructor(
    private readonly detector: IFaceDetector,
    private readonly qualityAssessor: IQualityAssessor,
    private readonly config: Pick<BiometricConfig, 'maxDetectionTimeMs'>,
  ) {}

  /**
   * Analyze a single frame.
   *
   * @returns FrameAnalysis or null if processing exceeded time budget.
   */
  async analyzeFrame(frame: DetectorInput): Promise<FrameAnalysis | null> {
    const startTime = performance.now();
    const timestamp = Date.now();

    try {
      // Step 1: Detect face
      const detection = await this.detector.detect(frame);

      const detectionTime = performance.now() - startTime;
      if (detectionTime > this.config.maxDetectionTimeMs) {
        return {
          detection,
          quality: null,
          processingTimeMs: Math.round(detectionTime),
          timestamp,
        };
      }

      // Step 2: Quality assessment (if face found and time permits)
      let quality: QualityAssessment | null = null;
      if (detection.found) {
        const canvas = this.getCanvas(frame);
        const faceImage = detection.getFaceRegion(canvas);
        if (faceImage) {
          quality = await this.qualityAssessor.assess(faceImage);
        }
      }

      return {
        detection,
        quality,
        processingTimeMs: Math.round(performance.now() - startTime),
        timestamp,
      };
    } catch {
      // On error, return null to skip this frame gracefully
      return null;
    }
  }

  /**
   * Get or create a scratch canvas for extracting face regions.
   */
  private getCanvas(source: DetectorInput): HTMLCanvasElement {
    if (!this.canvas) {
      this.canvas = document.createElement('canvas');
    }

    if (source instanceof HTMLVideoElement) {
      this.canvas.width = source.videoWidth;
      this.canvas.height = source.videoHeight;
      const ctx = this.canvas.getContext('2d');
      if (ctx) {
        ctx.drawImage(source, 0, 0);
      }
    } else if (source instanceof HTMLCanvasElement) {
      this.canvas.width = source.width;
      this.canvas.height = source.height;
      const ctx = this.canvas.getContext('2d');
      if (ctx) {
        ctx.drawImage(source, 0, 0);
      }
    } else {
      // ImageData
      this.canvas.width = source.width;
      this.canvas.height = source.height;
      const ctx = this.canvas.getContext('2d');
      if (ctx) {
        ctx.putImageData(source, 0, 0);
      }
    }

    return this.canvas;
  }
}
