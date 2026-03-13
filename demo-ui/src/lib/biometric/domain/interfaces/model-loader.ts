/**
 * Port for ML model lifecycle management.
 *
 * Handles lazy loading, caching, and disposal of WASM/ONNX models.
 * Single Responsibility: only manages model loading, not inference.
 */

export interface IModelLoader<TModel> {
  /** Load model (lazy — only loads on first call, cached after). */
  load(): Promise<TModel>;

  /** Check if model is currently loaded in memory. */
  isLoaded(): boolean;

  /** Release model from memory. */
  unload(): Promise<void>;
}
