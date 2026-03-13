/**
 * Console-based logger implementation.
 *
 * Implements ILogger using browser console.
 * Only logs in development mode to avoid production noise.
 */

import type { ILogger } from '../../domain/interfaces/logger';

export class ConsoleLogger implements ILogger {
  private readonly prefix: string;

  constructor(
    private readonly module: string,
    private readonly isDev = process.env.NODE_ENV === 'development',
  ) {
    this.prefix = `[Biometric:${module}]`;
  }

  debug(message: string, context?: Record<string, unknown>): void {
    if (this.isDev) {
      console.debug(this.prefix, message, context ?? '');
    }
  }

  info(message: string, context?: Record<string, unknown>): void {
    if (this.isDev) {
      console.info(this.prefix, message, context ?? '');
    }
  }

  warn(message: string, context?: Record<string, unknown>): void {
    console.warn(this.prefix, message, context ?? '');
  }

  error(message: string, context?: Record<string, unknown>): void {
    console.error(this.prefix, message, context ?? '');
  }
}
