/**
 * Port for logging across biometric modules.
 *
 * Cross-cutting concern abstracted as an interface so implementations
 * can switch between console, Sentry, or no-op loggers.
 */

export interface ILogger {
  debug(message: string, context?: Record<string, unknown>): void;
  info(message: string, context?: Record<string, unknown>): void;
  warn(message: string, context?: Record<string, unknown>): void;
  error(message: string, context?: Record<string, unknown>): void;
}
