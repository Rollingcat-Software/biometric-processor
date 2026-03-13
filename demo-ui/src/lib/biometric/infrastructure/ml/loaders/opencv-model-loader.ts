/**
 * Lazy-loading manager for OpenCV.js WASM module.
 *
 * OpenCV.js loads differently from MediaPipe — it attaches to a global `cv`
 * object and fires an `onRuntimeInitialized` callback. This loader wraps
 * that pattern into the standard IModelLoader interface.
 */

import type { IModelLoader } from '../../../biometric/domain/interfaces/model-loader';
import { ModelLoadError } from '../../../biometric/domain/errors';

/* eslint-disable @typescript-eslint/no-explicit-any */
type OpenCVModule = any;
/* eslint-enable @typescript-eslint/no-explicit-any */

export class OpenCVModelLoader implements IModelLoader<OpenCVModule> {
  private cv: OpenCVModule | null = null;
  private loadPromise: Promise<OpenCVModule> | null = null;

  constructor(private readonly scriptUrl?: string) {}

  async load(): Promise<OpenCVModule> {
    if (this.cv) return this.cv;
    if (this.loadPromise) return this.loadPromise;

    this.loadPromise = this.loadOpenCV()
      .then((cv) => {
        this.cv = cv;
        return cv;
      })
      .catch((err) => {
        this.loadPromise = null;
        throw new ModelLoadError(
          'opencv.js',
          err instanceof Error ? err : new Error(String(err)),
        );
      });

    return this.loadPromise;
  }

  isLoaded(): boolean {
    return this.cv !== null;
  }

  async unload(): Promise<void> {
    this.cv = null;
    this.loadPromise = null;
  }

  private async loadOpenCV(): Promise<OpenCVModule> {
    // Check if OpenCV is already loaded globally
    if (typeof window !== 'undefined' && (window as Record<string, unknown>).cv) {
      const globalCv = (window as Record<string, unknown>).cv as OpenCVModule;
      if (typeof globalCv.Mat === 'function') {
        return globalCv;
      }
    }

    return new Promise<OpenCVModule>((resolve, reject) => {
      if (typeof document === 'undefined') {
        reject(new Error('OpenCV.js requires a browser environment'));
        return;
      }

      const script = document.createElement('script');
      script.src = this.scriptUrl ?? '/opencv/opencv.js';
      script.async = true;

      script.onload = () => {
        const checkCv = () => {
          const cv = (window as Record<string, unknown>).cv as OpenCVModule;
          if (cv && typeof cv.Mat === 'function') {
            resolve(cv);
          } else if (cv && cv.onRuntimeInitialized !== undefined) {
            cv.onRuntimeInitialized = () => resolve(cv);
          } else {
            setTimeout(checkCv, 50);
          }
        };
        checkCv();
      };

      script.onerror = () => {
        reject(new Error(`Failed to load OpenCV.js from ${script.src}`));
      };

      document.head.appendChild(script);
    });
  }
}
