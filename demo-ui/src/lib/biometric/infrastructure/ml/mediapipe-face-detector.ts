/**
 * MediaPipe Face Detection adapter.
 *
 * Implements IFaceDetector using MediaPipe Face Detection WASM.
 * Runs entirely in-browser with no server round-trip.
 *
 * Liskov Substitution: Can replace ServerFaceDetector transparently.
 */

import type { IFaceDetector } from '../../domain/interfaces/face-detector';
import type { IModelLoader } from '../../domain/interfaces/model-loader';
import type { BiometricConfig, DetectorInput, BoundingBox, LandmarkPoint } from '../../domain/types';
import { FaceDetectionResult } from '../../domain/entities/face-detection-result';
import { FaceNotDetectedError, MultipleFacesError } from '../../domain/errors';

/**
 * Minimal type for MediaPipe FaceDetector to avoid hard dependency
 * on @mediapipe/tasks-vision at the interface level.
 */
interface MediaPipeFaceDetection {
  detect(
    image: DetectorInput,
  ): {
    detections: Array<{
      boundingBox?: { originX: number; originY: number; width: number; height: number };
      categories: Array<{ score: number }>;
      keypoints?: Array<{ x: number; y: number; z?: number; label?: string }>;
    }>;
  };
  close(): void;
}

export class MediaPipeFaceDetector implements IFaceDetector {
  constructor(
    private readonly modelLoader: IModelLoader<MediaPipeFaceDetection>,
    private readonly config: Pick<BiometricConfig, 'detectionConfidence'>,
  ) {}

  async detect(image: DetectorInput): Promise<FaceDetectionResult> {
    const detector = await this.modelLoader.load();
    const result = detector.detect(image);

    // Filter by confidence threshold
    const validDetections = result.detections.filter(
      (d) => d.categories.length > 0 && d.categories[0].score >= this.config.detectionConfidence,
    );

    if (validDetections.length === 0) {
      throw new FaceNotDetectedError();
    }

    if (validDetections.length > 1) {
      throw new MultipleFacesError(validDetections.length);
    }

    const detection = validDetections[0];
    const category = detection.categories[0];

    let boundingBox: BoundingBox | null = null;
    if (detection.boundingBox) {
      boundingBox = {
        x: Math.round(detection.boundingBox.originX),
        y: Math.round(detection.boundingBox.originY),
        width: Math.round(detection.boundingBox.width),
        height: Math.round(detection.boundingBox.height),
      };
    }

    let landmarks: LandmarkPoint[] | null = null;
    if (detection.keypoints) {
      landmarks = detection.keypoints.map((kp) => ({
        x: kp.x,
        y: kp.y,
        z: kp.z,
        label: kp.label,
      }));
    }

    return FaceDetectionResult.create({
      found: true,
      boundingBox,
      landmarks,
      confidence: category.score,
    });
  }

  async dispose(): Promise<void> {
    await this.modelLoader.unload();
  }
}
