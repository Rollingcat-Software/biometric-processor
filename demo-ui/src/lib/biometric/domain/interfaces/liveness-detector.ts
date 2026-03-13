/**
 * Port for passive liveness detection.
 *
 * Mirrors: app/domain/interfaces/liveness_detector.py → ILivenessDetector
 */

import type { LivenessResult } from '../entities/liveness-result';
import type { DetectorInput } from '../types';

export interface ILivenessDetector {
  /**
   * Check if image shows a live person (passive check).
   *
   * @param image - Input image
   * @returns Liveness result with score and challenge info
   */
  checkLiveness(image: DetectorInput): Promise<LivenessResult>;

  /** Get the type of liveness challenge used. */
  getChallengeType(): string;

  /** Get the threshold for considering result as live (0-100). */
  getLivenessThreshold(): number;
}
