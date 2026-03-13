/**
 * Liveness detection result value object.
 *
 * Mirrors: app/domain/entities/liveness_result.py → LivenessResult
 *
 * Immutable — validated at construction via static factory.
 *
 * Liveness Score Guidelines:
 *   - 0-50:  Likely spoof (reject)
 *   - 51-80: Uncertain (additional verification recommended)
 *   - 81-100: Live person (accept)
 */

export interface LivenessParams {
  readonly isLive: boolean;
  readonly livenessScore: number;
  readonly challenge: string;
  readonly challengeCompleted: boolean;
}

export type ConfidenceLevel = 'low' | 'medium' | 'high';

export class LivenessResult {
  readonly isLive: boolean;
  readonly livenessScore: number;
  readonly challenge: string;
  readonly challengeCompleted: boolean;

  private constructor(params: LivenessParams) {
    this.isLive = params.isLive;
    this.livenessScore = params.livenessScore;
    this.challenge = params.challenge;
    this.challengeCompleted = params.challengeCompleted;
  }

  /**
   * Create a validated LivenessResult.
   *
   * @throws {Error} if invariants are violated:
   *   - livenessScore must be in [0, 100]
   *   - challenge must be non-empty
   */
  static create(params: LivenessParams): LivenessResult {
    if (params.livenessScore < 0 || params.livenessScore > 100) {
      throw new Error(
        `Liveness score must be between 0 and 100, got ${params.livenessScore}`,
      );
    }
    if (!params.challenge || params.challenge.trim().length === 0) {
      throw new Error('Challenge type cannot be empty');
    }
    return new LivenessResult(params);
  }

  /** Get confidence level based on score thresholds. */
  getConfidenceLevel(): ConfidenceLevel {
    if (this.livenessScore < 50) return 'low';
    if (this.livenessScore < 81) return 'medium';
    return 'high';
  }

  /** Check if a spoof attack is suspected. */
  isSpoofSuspected(threshold = 50): boolean {
    return this.livenessScore < threshold;
  }

  /** Check if additional server-side verification is recommended. */
  requiresAdditionalVerification(threshold = 80): boolean {
    return this.livenessScore >= 50 && this.livenessScore < threshold;
  }

  /** Convert to plain object for serialization. */
  toJSON(): LivenessParams & {
    confidenceLevel: ConfidenceLevel;
    spoofSuspected: boolean;
  } {
    return {
      isLive: this.isLive,
      livenessScore: this.livenessScore,
      challenge: this.challenge,
      challengeCompleted: this.challengeCompleted,
      confidenceLevel: this.getConfidenceLevel(),
      spoofSuspected: this.isSpoofSuspected(),
    };
  }
}
