/**
 * Port for face detection implementations.
 *
 * Mirrors: app/domain/interfaces/face_detector.py → IFaceDetector
 *
 * Implementations can use different algorithms (MediaPipe, TFLite, Server API)
 * without changing client code (Open/Closed Principle).
 */

import type { FaceDetectionResult } from '../entities/face-detection-result';
import type { DetectorInput } from '../types';

export interface IFaceDetector {
  /**
   * Detect a face in an image.
   *
   * @param image - Image data source
   * @returns Face detection result with bounding box and confidence
   * @throws {FaceNotDetectedError} when no face is found
   * @throws {MultipleFacesError} when multiple faces are detected
   */
  detect(image: DetectorInput): Promise<FaceDetectionResult>;

  /** Release resources (WASM memory, GPU textures). */
  dispose(): Promise<void>;
}
