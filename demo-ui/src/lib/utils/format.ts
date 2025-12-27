/**
 * Formats a score value to a percentage string.
 * Backend now returns all metrics normalized to 0-100 scale.
 *
 * @param value - The score value from backend (0-100)
 * @param decimals - Number of decimal places (default: 1)
 * @returns Formatted percentage number (not string, no % sign)
 */
export function toPercent(value: number | undefined | null, decimals: number = 1): number {
  if (value === undefined || value === null) return 0;

  // Backend returns normalized 0-100 values, just round
  const multiplier = Math.pow(10, decimals);
  return Math.round(value * multiplier) / multiplier;
}

/**
 * Formats a score value to a percentage string with % sign.
 *
 * @param value - The score value from backend
 * @param decimals - Number of decimal places (default: 1)
 * @returns Formatted percentage string with % sign
 */
export function formatPercent(value: number | undefined | null, decimals: number = 1): string {
  return `${toPercent(value, decimals).toFixed(decimals)}%`;
}
