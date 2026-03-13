import { describe, it, expect } from 'vitest';
import { FaceDetectionResult } from '../entities/face-detection-result';

describe('FaceDetectionResult', () => {
  describe('create', () => {
    it('creates a valid detection result', () => {
      const result = FaceDetectionResult.create({
        found: true,
        boundingBox: { x: 10, y: 20, width: 100, height: 120 },
        landmarks: null,
        confidence: 0.95,
      });

      expect(result.found).toBe(true);
      expect(result.boundingBox).toEqual({ x: 10, y: 20, width: 100, height: 120 });
      expect(result.confidence).toBe(0.95);
    });

    it('throws when confidence is out of range', () => {
      expect(() =>
        FaceDetectionResult.create({
          found: false,
          boundingBox: null,
          landmarks: null,
          confidence: 1.5,
        }),
      ).toThrow('Confidence must be between 0 and 1');
    });

    it('throws when confidence is negative', () => {
      expect(() =>
        FaceDetectionResult.create({
          found: false,
          boundingBox: null,
          landmarks: null,
          confidence: -0.1,
        }),
      ).toThrow('Confidence must be between 0 and 1');
    });

    it('throws when found is true but boundingBox is null', () => {
      expect(() =>
        FaceDetectionResult.create({
          found: true,
          boundingBox: null,
          landmarks: null,
          confidence: 0.9,
        }),
      ).toThrow('Bounding box is required when face is found');
    });

    it('throws when bounding box has zero width', () => {
      expect(() =>
        FaceDetectionResult.create({
          found: true,
          boundingBox: { x: 10, y: 20, width: 0, height: 100 },
          landmarks: null,
          confidence: 0.9,
        }),
      ).toThrow('Invalid bounding box dimensions');
    });

    it('throws when bounding box has negative height', () => {
      expect(() =>
        FaceDetectionResult.create({
          found: true,
          boundingBox: { x: 10, y: 20, width: 100, height: -5 },
          landmarks: null,
          confidence: 0.9,
        }),
      ).toThrow('Invalid bounding box dimensions');
    });
  });

  describe('notFound', () => {
    it('creates a not-found result with defaults', () => {
      const result = FaceDetectionResult.notFound();

      expect(result.found).toBe(false);
      expect(result.boundingBox).toBeNull();
      expect(result.landmarks).toBeNull();
      expect(result.confidence).toBe(0);
    });
  });

  describe('getFaceCenter', () => {
    it('returns center point of bounding box', () => {
      const result = FaceDetectionResult.create({
        found: true,
        boundingBox: { x: 100, y: 200, width: 50, height: 80 },
        landmarks: null,
        confidence: 0.9,
      });

      expect(result.getFaceCenter()).toEqual({ x: 125, y: 240 });
    });

    it('returns null when no bounding box', () => {
      const result = FaceDetectionResult.notFound();
      expect(result.getFaceCenter()).toBeNull();
    });
  });

  describe('getFaceMinDimension', () => {
    it('returns the smaller dimension', () => {
      const result = FaceDetectionResult.create({
        found: true,
        boundingBox: { x: 0, y: 0, width: 150, height: 100 },
        landmarks: null,
        confidence: 0.9,
      });

      expect(result.getFaceMinDimension()).toBe(100);
    });

    it('returns 0 when no bounding box', () => {
      const result = FaceDetectionResult.notFound();
      expect(result.getFaceMinDimension()).toBe(0);
    });
  });
});
