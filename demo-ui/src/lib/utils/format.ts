/**
 * Formats a score value to a percentage string.
 * Handles both 0-1 (decimal) and 0-100 (percentage) ranges from backend.
 *
 * @param value - The score value from backend
 * @param decimals - Number of decimal places (default: 1)
 * @returns Formatted percentage number (not string, no % sign)
 */
export function toPercent(value: number | undefined | null, decimals: number = 1): number {
  if (value === undefined || value === null) return 0;

  // If value is <= 1, assume it's in 0-1 range and convert to percentage
  // If value is > 1, assume it's already a percentage (0-100 range)
  const percent = value <= 1 ? value * 100 : value;

  // Round to specified decimals
  const multiplier = Math.pow(10, decimals);
  return Math.round(percent * multiplier) / multiplier;
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
