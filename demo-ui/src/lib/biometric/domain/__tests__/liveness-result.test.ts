import { describe, it, expect } from 'vitest';
import { LivenessResult } from '../entities/liveness-result';

describe('LivenessResult', () => {
  describe('create', () => {
    it('creates a valid liveness result', () => {
      const result = LivenessResult.create({
        isLive: true,
        livenessScore: 90,
        challenge: 'passive_depth',
        challengeCompleted: true,
      });

      expect(result.isLive).toBe(true);
      expect(result.livenessScore).toBe(90);
      expect(result.challenge).toBe('passive_depth');
    });

    it('throws when liveness score is out of range', () => {
      expect(() =>
        LivenessResult.create({
          isLive: false,
          livenessScore: 101,
          challenge: 'passive_depth',
          challengeCompleted: false,
        }),
      ).toThrow('Liveness score must be between 0 and 100');
    });

    it('throws when liveness score is negative', () => {
      expect(() =>
        LivenessResult.create({
          isLive: false,
          livenessScore: -5,
          challenge: 'passive_depth',
          challengeCompleted: false,
        }),
      ).toThrow('Liveness score must be between 0 and 100');
    });

    it('throws when challenge is empty', () => {
      expect(() =>
        LivenessResult.create({
          isLive: false,
          livenessScore: 50,
          challenge: '',
          challengeCompleted: false,
        }),
      ).toThrow('Challenge type cannot be empty');
    });

    it('throws when challenge is whitespace only', () => {
      expect(() =>
        LivenessResult.create({
          isLive: false,
          livenessScore: 50,
          challenge: '   ',
          challengeCompleted: false,
        }),
      ).toThrow('Challenge type cannot be empty');
    });
  });

  describe('getConfidenceLevel', () => {
    it('returns "low" for scores below 50', () => {
      const result = LivenessResult.create({
        isLive: false,
        livenessScore: 30,
        challenge: 'passive_depth',
        challengeCompleted: false,
      });
      expect(result.getConfidenceLevel()).toBe('low');
    });

    it('returns "medium" for scores 50-80', () => {
      const result = LivenessResult.create({
        isLive: true,
        livenessScore: 65,
        challenge: 'passive_depth',
        challengeCompleted: true,
      });
      expect(result.getConfidenceLevel()).toBe('medium');
    });

    it('returns "high" for scores 81+', () => {
      const result = LivenessResult.create({
        isLive: true,
        livenessScore: 95,
        challenge: 'passive_depth',
        challengeCompleted: true,
      });
      expect(result.getConfidenceLevel()).toBe('high');
    });
  });

  describe('isSpoofSuspected', () => {
    it('returns true when score is below threshold', () => {
      const result = LivenessResult.create({
        isLive: false,
        livenessScore: 30,
        challenge: 'passive_depth',
        challengeCompleted: false,
      });
      expect(result.isSpoofSuspected()).toBe(true);
    });

    it('returns false when score is above threshold', () => {
      const result = LivenessResult.create({
        isLive: true,
        livenessScore: 80,
        challenge: 'passive_depth',
        challengeCompleted: true,
      });
      expect(result.isSpoofSuspected()).toBe(false);
    });

    it('supports custom threshold', () => {
      const result = LivenessResult.create({
        isLive: true,
        livenessScore: 60,
        challenge: 'passive_depth',
        challengeCompleted: true,
      });
      expect(result.isSpoofSuspected(70)).toBe(true);
      expect(result.isSpoofSuspected(50)).toBe(false);
    });
  });

  describe('requiresAdditionalVerification', () => {
    it('returns true for uncertain range (50-80)', () => {
      const result = LivenessResult.create({
        isLive: true,
        livenessScore: 65,
        challenge: 'passive_depth',
        challengeCompleted: true,
      });
      expect(result.requiresAdditionalVerification()).toBe(true);
    });

    it('returns false for high scores', () => {
      const result = LivenessResult.create({
        isLive: true,
        livenessScore: 90,
        challenge: 'passive_depth',
        challengeCompleted: true,
      });
      expect(result.requiresAdditionalVerification()).toBe(false);
    });

    it('returns false for low scores (spoof detected)', () => {
      const result = LivenessResult.create({
        isLive: false,
        livenessScore: 20,
        challenge: 'passive_depth',
        challengeCompleted: false,
      });
      expect(result.requiresAdditionalVerification()).toBe(false);
    });
  });

  describe('toJSON', () => {
    it('includes computed fields', () => {
      const result = LivenessResult.create({
        isLive: true,
        livenessScore: 90,
        challenge: 'passive_depth',
        challengeCompleted: true,
      });
      const json = result.toJSON();

      expect(json.confidenceLevel).toBe('high');
      expect(json.spoofSuspected).toBe(false);
      expect(json.livenessScore).toBe(90);
    });
  });
});
