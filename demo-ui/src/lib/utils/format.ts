/**
 * Normalizes a value to 0-100 percentage scale.
 * Handles both 0-1 scale (confidence values) and 0-100 scale (scores).
 *
 * @param value - The value to normalize
 * @returns Value in 0-100 scale
 */
function normalizeToPercent(value: number): number {
  // If value is clearly 0-1 scale (less than or equal to 1), multiply by 100
  // Values > 1 are assumed to already be 0-100 scale
  return value <= 1 ? value * 100 : value;
}

/**
 * Formats a score value to a percentage number.
 * Auto-detects if value is 0-1 or 0-100 scale.
 *
 * @param value - The score value from backend (0-1 or 0-100)
 * @param decimals - Number of decimal places (default: 1)
 * @returns Formatted percentage number (not string, no % sign)
 */
export function toPercent(value: number | undefined | null, decimals: number = 1): number {
  if (value === undefined || value === null) return 0;

  const percentValue = normalizeToPercent(value);
  const multiplier = Math.pow(10, decimals);
  return Math.round(percentValue * multiplier) / multiplier;
}

/**
 * Formats a score value to a percentage string with % sign.
 * Auto-detects if value is 0-1 or 0-100 scale.
 *
 * @param value - The score value from backend (0-1 or 0-100)
 * @param decimals - Number of decimal places (default: 1)
 * @returns Formatted percentage string with % sign
 */
export function formatPercent(value: number | undefined | null, decimals: number = 1): string {
  return toPercent(value, decimals).toFixed(decimals) + '%';
}