/**
 * Lazy-loading model manager for MediaPipe WASM models.
 *
 * Implements IModelLoader with:
 * - Lazy initialization (load on first use)
 * - Singleton caching (load once, reuse)
 * - Graceful error handling with ModelLoadError
 * - Resource cleanup on dispose
 *
 * Single Responsibility: Only manages model lifecycle, not inference.
 */

import type { IModelLoader } from '../../../biometric/domain/interfaces/model-loader';
import { ModelLoadError } from '../../../biometric/domain/errors';

export class MediaPipeModelLoader<TModel> implements IModelLoader<TModel> {
  private model: TModel | null = null;
  private loadPromise: Promise<TModel> | null = null;

  constructor(
    private readonly factory: () => Promise<TModel>,
    private readonly modelName: string,
  ) {}

  async load(): Promise<TModel> {
    if (this.model) return this.model;

    // Prevent concurrent loads — reuse the same promise
    if (this.loadPromise) return this.loadPromise;

    this.loadPromise = this.factory()
      .then((model) => {
        this.model = model;
        return model;
      })
      .catch((err) => {
        // Reset promise so next call retries
        this.loadPromise = null;
        throw new ModelLoadError(
          this.modelName,
          err instanceof Error ? err : new Error(String(err)),
        );
      });

    return this.loadPromise;
  }

  isLoaded(): boolean {
    return this.model !== null;
  }

  async unload(): Promise<void> {
    if (this.model && typeof (this.model as Record<string, unknown>).close === 'function') {
      (this.model as unknown as { close(): void }).close();
    }
    this.model = null;
    this.loadPromise = null;
  }
}
