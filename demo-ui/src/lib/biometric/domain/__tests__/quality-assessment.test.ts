import { describe, it, expect } from 'vitest';
import { QualityAssessment } from '../entities/quality-assessment';

describe('QualityAssessment', () => {
  describe('create', () => {
    it('creates a valid quality assessment', () => {
      const qa = QualityAssessment.create({
        score: 85,
        blurScore: 150,
        lightingScore: 70,
        faceSize: 200,
        isAcceptable: true,
      });

      expect(qa.score).toBe(85);
      expect(qa.isAcceptable).toBe(true);
    });

    it('throws when score is out of range', () => {
      expect(() =>
        QualityAssessment.create({
          score: 101,
          blurScore: 100,
          lightingScore: 50,
          faceSize: 100,
          isAcceptable: false,
        }),
      ).toThrow('Score must be between 0 and 100');
    });

    it('throws when score is negative', () => {
      expect(() =>
        QualityAssessment.create({
          score: -1,
          blurScore: 100,
          lightingScore: 50,
          faceSize: 100,
          isAcceptable: false,
        }),
      ).toThrow('Score must be between 0 and 100');
    });

    it('throws when blur score is negative', () => {
      expect(() =>
        QualityAssessment.create({
          score: 50,
          blurScore: -10,
          lightingScore: 50,
          faceSize: 100,
          isAcceptable: false,
        }),
      ).toThrow('Blur score cannot be negative');
    });

    it('throws when face size is negative', () => {
      expect(() =>
        QualityAssessment.create({
          score: 50,
          blurScore: 100,
          lightingScore: 50,
          faceSize: -1,
          isAcceptable: false,
        }),
      ).toThrow('Face size cannot be negative');
    });
  });

  describe('getQualityLevel', () => {
    it('returns "poor" for scores below 40', () => {
      const qa = QualityAssessment.create({
        score: 30,
        blurScore: 50,
        lightingScore: 30,
        faceSize: 60,
        isAcceptable: false,
      });
      expect(qa.getQualityLevel()).toBe('poor');
    });

    it('returns "fair" for scores 40-70', () => {
      const qa = QualityAssessment.create({
        score: 55,
        blurScore: 100,
        lightingScore: 50,
        faceSize: 100,
        isAcceptable: true,
      });
      expect(qa.getQualityLevel()).toBe('fair');
    });

    it('returns "good" for scores 71+', () => {
      const qa = QualityAssessment.create({
        score: 85,
        blurScore: 200,
        lightingScore: 80,
        faceSize: 200,
        isAcceptable: true,
      });
      expect(qa.getQualityLevel()).toBe('good');
    });
  });

  describe('issue detection', () => {
    it('detects blur issues', () => {
      const qa = QualityAssessment.create({
        score: 30,
        blurScore: 50,
        lightingScore: 70,
        faceSize: 200,
        isAcceptable: false,
      });
      expect(qa.isBlurry()).toBe(true);
      expect(qa.isBlurry(30)).toBe(false);
    });

    it('detects small face', () => {
      const qa = QualityAssessment.create({
        score: 30,
        blurScore: 150,
        lightingScore: 70,
        faceSize: 50,
        isAcceptable: false,
      });
      expect(qa.isTooSmall()).toBe(true);
      expect(qa.isTooSmall(40)).toBe(false);
    });

    it('detects poor lighting', () => {
      const qa = QualityAssessment.create({
        score: 30,
        blurScore: 150,
        lightingScore: 30,
        faceSize: 200,
        isAcceptable: false,
      });
      expect(qa.isPoorLighting()).toBe(true);
    });

    it('collects all issues', () => {
      const qa = QualityAssessment.create({
        score: 20,
        blurScore: 50,
        lightingScore: 30,
        faceSize: 50,
        isAcceptable: false,
      });
      const issues = qa.getIssues();
      expect(issues).toHaveLength(3);
      expect(issues.map((i) => i.type)).toEqual(['blur', 'face_size', 'lighting']);
    });

    it('returns empty issues for good quality', () => {
      const qa = QualityAssessment.create({
        score: 90,
        blurScore: 200,
        lightingScore: 80,
        faceSize: 200,
        isAcceptable: true,
      });
      expect(qa.getIssues()).toHaveLength(0);
    });
  });

  describe('toJSON', () => {
    it('includes quality level', () => {
      const qa = QualityAssessment.create({
        score: 85,
        blurScore: 200,
        lightingScore: 80,
        faceSize: 200,
        isAcceptable: true,
      });
      const json = qa.toJSON();
      expect(json.qualityLevel).toBe('good');
      expect(json.score).toBe(85);
    });
  });
});
