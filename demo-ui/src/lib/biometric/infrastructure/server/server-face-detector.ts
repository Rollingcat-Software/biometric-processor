/**
 * Server-side face detection fallback adapter.
 *
 * Implements IFaceDetector by delegating to the backend API.
 * Used when WASM is not supported or client-side detection fails.
 *
 * Open/Closed Principle: Added without changing existing code.
 */

import type { IFaceDetector } from '../../domain/interfaces/face-detector';
import type { IBiometricApiClient } from '../../domain/interfaces/biometric-api-client';
import type { DetectorInput } from '../../domain/types';
import { FaceDetectionResult } from '../../domain/entities/face-detection-result';
import { FaceNotDetectedError } from '../../domain/errors';

export class ServerFaceDetector implements IFaceDetector {
  constructor(private readonly apiClient: IBiometricApiClient) {}

  async detect(image: DetectorInput): Promise<FaceDetectionResult> {
    const blob = await this.inputToBlob(image);
    const response = await this.apiClient.assessQuality(blob);

    // The server quality endpoint includes face detection information.
    // If faceSize is 0, no face was found.
    if (response.faceSize === 0) {
      throw new FaceNotDetectedError();
    }

    // Server response gives us limited detection info (quality-focused).
    // We construct a minimal detection result.
    return FaceDetectionResult.create({
      found: true,
      boundingBox: {
        x: 0,
        y: 0,
        width: response.faceSize,
        height: response.faceSize,
      },
      landmarks: null,
      confidence: response.isAcceptable ? 0.9 : 0.5,
    });
  }

  async dispose(): Promise<void> {
    // No-op — server resources managed by backend
  }

  private async inputToBlob(image: DetectorInput): Promise<Blob> {
    if (image instanceof ImageData) {
      const canvas = document.createElement('canvas');
      canvas.width = image.width;
      canvas.height = image.height;
      const ctx = canvas.getContext('2d');
      if (!ctx) throw new Error('Cannot create canvas context');
      ctx.putImageData(image, 0, 0);
      return new Promise<Blob>((resolve, reject) => {
        canvas.toBlob(
          (blob) => (blob ? resolve(blob) : reject(new Error('Failed to create blob'))),
          'image/jpeg',
          0.9,
        );
      });
    }

    if (image instanceof HTMLCanvasElement) {
      return new Promise<Blob>((resolve, reject) => {
        image.toBlob(
          (blob) => (blob ? resolve(blob) : reject(new Error('Failed to create blob'))),
          'image/jpeg',
          0.9,
        );
      });
    }

    // HTMLVideoElement — capture current frame
    const canvas = document.createElement('canvas');
    canvas.width = image.videoWidth;
    canvas.height = image.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Cannot create canvas context');
    ctx.drawImage(image, 0, 0);
    return new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (blob) => (blob ? resolve(blob) : reject(new Error('Failed to create blob'))),
        'image/jpeg',
        0.9,
      );
    });
  }
}
