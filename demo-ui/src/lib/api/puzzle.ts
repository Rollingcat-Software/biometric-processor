/**
 * Puzzle Liveness API Client
 *
 * Provides functions for interacting with the puzzle liveness endpoints:
 * - generatePuzzle: Get a new liveness puzzle
 * - verifyPuzzle: Verify puzzle completion
 */

import { API_CONFIG } from '@/config/api.config';
import { ApiClientError } from './client';
import type {
  GeneratePuzzleRequest,
  GeneratePuzzleResponse,
  VerifyPuzzleRequest,
  VerifyPuzzleResponse,
} from '@/types/api';

const API_URL = API_CONFIG.BASE_URL;
const REQUEST_TIMEOUT = API_CONFIG.TIMEOUT.DEFAULT;

/**
 * Generate a new liveness puzzle
 *
 * @param request - Puzzle generation parameters
 * @returns Generated puzzle with steps and thresholds
 */
export async function generatePuzzle(
  request: GeneratePuzzleRequest = {}
): Promise<GeneratePuzzleResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

  try {
    const response = await fetch(`${API_URL}/api/v1/liveness/generate-puzzle`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        difficulty: request.difficulty || 'standard',
        min_steps: request.min_steps || 3,
        max_steps: request.max_steps || 4,
        timeout_seconds: request.timeout_seconds || 60,
        tenant_id: request.tenant_id,
        user_id: request.user_id,
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        message: 'Failed to generate puzzle',
      }));
      throw new ApiClientError(response.status, error.message || error.detail, {
        code: error.error_code,
        details: error,
      });
    }

    const data: GeneratePuzzleResponse = await response.json();
    return data;
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiClientError(408, 'Request timeout - puzzle generation took too long');
    }
    throw new ApiClientError(
      0,
      error instanceof Error ? error.message : 'Unknown error generating puzzle'
    );
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Verify puzzle completion
 *
 * @param request - Verification request with step evidence
 * @returns Verification result with liveness status
 */
export async function verifyPuzzle(
  request: VerifyPuzzleRequest
): Promise<VerifyPuzzleResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

  try {
    const response = await fetch(`${API_URL}/api/v1/liveness/verify`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
      signal: controller.signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        message: 'Failed to verify puzzle',
      }));
      throw new ApiClientError(response.status, error.message || error.detail, {
        code: error.error_code,
        details: error,
      });
    }

    const data: VerifyPuzzleResponse = await response.json();
    return data;
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiClientError(408, 'Request timeout - puzzle verification took too long');
    }
    throw new ApiClientError(
      0,
      error instanceof Error ? error.message : 'Unknown error verifying puzzle'
    );
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Challenge instruction text mapping
 */
export const CHALLENGE_INSTRUCTIONS: Record<string, string> = {
  blink: 'Please blink your eyes',
  smile: 'Please smile',
  turn_left: 'Please turn your head to the left',
  turn_right: 'Please turn your head to the right',
  nod: 'Please nod your head',
  open_mouth: 'Please open your mouth wide',
  raise_eyebrows: 'Please raise your eyebrows',
};

/**
 * Get instruction text for a challenge type
 */
export function getChallengeInstruction(challengeType: string): string {
  return CHALLENGE_INSTRUCTIONS[challengeType] || `Please perform: ${challengeType}`;
}
