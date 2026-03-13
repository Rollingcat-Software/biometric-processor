# Browser-Side Biometric Processing Architecture

## Document Info

| Field | Value |
|-------|-------|
| **Status** | Approved Design |
| **Author** | Architecture Team |
| **Date** | 2026-03-13 |
| **Version** | 1.0.0 |
| **Relates To** | ARCHITECTURE.md, TODO.md (BC1, BH1) |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Architecture Overview](#3-architecture-overview)
4. [Layer Design](#4-layer-design)
5. [Domain Layer — Interfaces & Entities](#5-domain-layer--interfaces--entities)
6. [Infrastructure Layer — ML Adapters](#6-infrastructure-layer--ml-adapters)
7. [Application Layer — Use Cases](#7-application-layer--use-cases)
8. [Presentation Layer — React Hooks & Components](#8-presentation-layer--react-hooks--components)
9. [Hybrid Client-Server Flow](#9-hybrid-client-server-flow)
10. [WebAuthn Integration](#10-webauthn-integration)
11. [DI Container](#11-di-container)
12. [Security Architecture](#12-security-architecture)
13. [Testing Strategy](#13-testing-strategy)
14. [Directory Structure](#14-directory-structure)
15. [Migration Plan](#15-migration-plan)

---

## 1. Executive Summary

This document defines the architecture for moving biometric pre-processing
(face detection, quality assessment, passive liveness) from the Python backend
into the browser using MediaPipe WASM, ONNX Runtime Web, and OpenCV.js.

The design mirrors the existing Hexagonal Architecture (Ports & Adapters) already
established in the Python backend, translated into idiomatic TypeScript with the
same SOLID principles, dependency inversion, and clean separation of concerns.

### Goals

- **Offload ~60% of compute** from biometric-processor to the browser
- **Instant feedback** for users (no network round-trip for quality/detection)
- **Fix critical stubs** (fingerprint/voice) via WebAuthn/FIDO2 passkeys
- **Zero breaking changes** to existing API contracts
- **Isomorphic domain model** — client entities mirror server entities

### Non-Goals

- Replacing server-side enrollment/verification (security-critical, stays server-side)
- Supporting browsers without WASM (Safari 14-, IE)
- Client-side embedding storage (vectors never persist in browser)

---

## 2. Problem Statement

### Current State

```
┌──────────┐    every frame    ┌───────────────────┐
│  Browser  │ ──────────────→ │ biometric-processor │
│ (demo-ui) │    HTTP/WS      │   Python/FastAPI    │
│           │ ←────────────── │   Port 8001         │
└──────────┘    JSON result   └───────────────────┘
```

**Issues:**
1. Every quality check, face detection, and liveness pre-check requires a server round-trip (~200-500ms)
2. WebSocket live analysis (`/api/v1/live-analysis`) sends raw frames to server — bandwidth-intensive
3. Fingerprint/voice stubs always return `success: false` (TODO.md BC1)
4. No client-side validation — poor images are uploaded, rejected, re-uploaded

### Target State

```
┌──────────────────────────────────────────────┐
│                   Browser                     │
│  ┌─────────────┐  ┌──────────┐  ┌─────────┐ │
│  │ MediaPipe    │  │ OpenCV   │  │ WebAuthn│ │
│  │ Face Detect  │  │ Quality  │  │ Passkey │ │
│  └──────┬───────┘  └────┬─────┘  └────┬────┘ │
│         │               │              │      │
│    ┌────▼───────────────▼──────────────▼────┐ │
│    │       Client Use Cases (TypeScript)     │ │
│    │   Quality Gate → Hybrid Enrollment      │ │
│    └────────────────┬────────────────────────┘ │
└─────────────────────┼──────────────────────────┘
                      │ only high-quality,
                      │ pre-validated images
                      ▼
              ┌───────────────────┐
              │ biometric-processor│
              │  (enrollment,      │
              │   verification,    │
              │   embedding store) │
              └───────────────────┘
```

---

## 3. Architecture Overview

### Hexagonal Architecture — Client Side

The client-side architecture mirrors the server-side hexagonal pattern:

```
┌─────────────────────────────────────────────────────────────────┐
│                 Presentation Layer (React Hooks)                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │useClientDetection│  │useClientQuality  │  │useHybrid     │  │
│  │                  │  │                  │  │  Enrollment  │  │
│  └────────┬─────────┘  └────────┬─────────┘  └──────┬───────┘  │
└───────────┼──────────────────────┼───────────────────┼──────────┘
            │                      │                   │
            ▼                      ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│              Application Layer (Use Cases)                       │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │ClientDetectFace  │  │ClientAssess      │  │HybridEnroll  │  │
│  │   UseCase        │  │ Quality UseCase  │  │  UseCase     │  │
│  └────────┬─────────┘  └────────┬─────────┘  └──────┬───────┘  │
└───────────┼──────────────────────┼───────────────────┼──────────┘
            │                      │                   │
            ▼                      ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│          Domain Layer (Interfaces + Entities)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │IFaceDetector │  │IQualityAs-   │  │ILivenessDetector     │  │
│  │              │  │  sessor      │  │                      │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │FaceDetection │  │Quality       │  │LivenessResult        │  │
│  │  Result      │  │  Assessment  │  │                      │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
            ▲                      ▲                   ▲
            │                      │                   │
┌───────────┴──────────────────────┴───────────────────┴──────────┐
│          Infrastructure Layer (Adapters)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │MediaPipe     │  │OpenCV.js     │  │MediaPipe Passive     │  │
│  │FaceDetector  │  │QualityAs-    │  │LivenessDetector      │  │
│  │  (WASM)      │  │  sessor      │  │  (WASM)              │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐                             │
│  │ServerFace    │  │ServerQuality │  ← Fallback adapters        │
│  │Detector      │  │Assessor      │    (delegate to backend)    │
│  │  (HTTP)      │  │  (HTTP)      │                             │
│  └──────────────┘  └──────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
```

### SOLID Compliance

| Principle | How It's Applied |
|-----------|-----------------|
| **SRP** | Each class has one responsibility: `MediaPipeFaceDetector` only detects faces, `OpenCVQualityAssessor` only assesses quality |
| **OCP** | New ML backends (e.g., TFLite, WebNN) are added by creating new adapters — no existing code changes |
| **LSP** | All `IFaceDetector` implementations are interchangeable — `MediaPipeFaceDetector` and `ServerFaceDetector` both satisfy the same contract |
| **ISP** | Small, focused interfaces: `IFaceDetector`, `IQualityAssessor`, `ILivenessDetector` — no "god interface" |
| **DIP** | Use cases depend on `IFaceDetector` (abstraction), never on `MediaPipeFaceDetector` (concrete) |

---

## 4. Layer Design

### Dependency Rule

```
Presentation → Application → Domain ← Infrastructure
```

- **Domain Layer**: Zero dependencies — pure TypeScript types and interfaces
- **Application Layer**: Depends only on Domain interfaces
- **Infrastructure Layer**: Implements Domain interfaces using specific libraries
- **Presentation Layer**: Depends on Application layer (use cases)

### Cross-Cutting Concerns

| Concern | Implementation |
|---------|---------------|
| **Logging** | `ILogger` interface with `ConsoleLogger` / `SentryLogger` adapters |
| **Error Handling** | Domain-specific error hierarchy (mirrors Python `face_errors.py`) |
| **Configuration** | `BiometricConfig` value object with runtime validation |
| **Model Loading** | `IModelLoader` interface with lazy initialization and caching |

---

## 5. Domain Layer — Interfaces & Entities

### 5.1 Interfaces (Ports)

These TypeScript interfaces mirror the Python `Protocol` classes 1:1.

#### IFaceDetector

```typescript
// demo-ui/src/lib/biometric/domain/interfaces/face-detector.ts

/**
 * Port for face detection implementations.
 *
 * Mirrors: app/domain/interfaces/face_detector.py → IFaceDetector
 *
 * Implementations can use different algorithms (MediaPipe, TFLite, Server API)
 * without changing client code (Open/Closed Principle).
 */
export interface IFaceDetector {
  /**
   * Detect faces in an image.
   *
   * @param image - Image data (ImageData, HTMLCanvasElement, or HTMLVideoElement)
   * @returns Face detection result
   * @throws FaceNotDetectedError when no face is found
   */
  detect(image: DetectorInput): Promise<FaceDetectionResult>;

  /** Release resources (WASM memory, GPU textures) */
  dispose(): Promise<void>;
}
```

#### IQualityAssessor

```typescript
// demo-ui/src/lib/biometric/domain/interfaces/quality-assessor.ts

/**
 * Port for image quality assessment.
 *
 * Mirrors: app/domain/interfaces/quality_assessor.py → IQualityAssessor
 */
export interface IQualityAssessor {
  /**
   * Assess the quality of a face image.
   *
   * @param faceImage - Cropped face region as ImageData
   * @returns Quality assessment with metrics and overall score
   */
  assess(faceImage: ImageData): Promise<QualityAssessment>;

  /** Get minimum acceptable quality score (0-100) */
  getMinimumAcceptableScore(): number;
}
```

#### ILivenessDetector

```typescript
// demo-ui/src/lib/biometric/domain/interfaces/liveness-detector.ts

/**
 * Port for passive liveness detection.
 *
 * Mirrors: app/domain/interfaces/liveness_detector.py → ILivenessDetector
 */
export interface ILivenessDetector {
  /**
   * Check if image shows a live person (passive check).
   *
   * @param image - Input image
   * @returns Liveness result with score and challenge info
   */
  checkLiveness(image: DetectorInput): Promise<LivenessResult>;

  /** Get the type of liveness challenge used */
  getChallengeType(): string;

  /** Get the threshold for considering result as live (0-100) */
  getLivenessThreshold(): number;
}
```

#### IModelLoader

```typescript
// demo-ui/src/lib/biometric/domain/interfaces/model-loader.ts

/**
 * Port for ML model lifecycle management.
 *
 * Handles lazy loading, caching, and disposal of WASM/ONNX models.
 * Single Responsibility: only manages model loading, not inference.
 */
export interface IModelLoader<TModel> {
  /** Load model (lazy — only loads on first call, cached after) */
  load(): Promise<TModel>;

  /** Check if model is currently loaded */
  isLoaded(): boolean;

  /** Release model from memory */
  unload(): Promise<void>;
}
```

#### IBiometricApiClient

```typescript
// demo-ui/src/lib/biometric/domain/interfaces/biometric-api-client.ts

/**
 * Port for server-side biometric API communication.
 *
 * Abstracts the HTTP client so use cases don't depend on fetch/axios.
 * Enables testing with mock API responses.
 */
export interface IBiometricApiClient {
  /** Enroll a face with pre-validated image */
  enrollFace(params: EnrollFaceRequest): Promise<EnrollFaceResponse>;

  /** Verify a face against stored embedding */
  verifyFace(params: VerifyFaceRequest): Promise<VerifyFaceResponse>;

  /** Search for matching faces */
  searchFace(params: SearchFaceRequest): Promise<SearchFaceResponse>;

  /** Server-side liveness check (for high-security flows) */
  checkLiveness(image: Blob): Promise<ServerLivenessResponse>;

  /** Server-side quality check (fallback) */
  assessQuality(image: Blob): Promise<ServerQualityResponse>;
}
```

### 5.2 Entities (Value Objects)

Immutable, validated value objects that mirror the Python dataclasses.

#### FaceDetectionResult

```typescript
// demo-ui/src/lib/biometric/domain/entities/face-detection-result.ts

/**
 * Immutable value object for face detection output.
 *
 * Mirrors: app/domain/entities/face_detection.py → FaceDetectionResult
 *
 * Invariants enforced at construction:
 * - confidence ∈ [0, 1]
 * - boundingBox dimensions > 0 when found = true
 * - boundingBox required when found = true
 */
export class FaceDetectionResult {
  readonly found: boolean;
  readonly boundingBox: BoundingBox | null;
  readonly landmarks: LandmarkPoint[] | null;
  readonly confidence: number;

  private constructor(params: FaceDetectionParams) { /* validate + assign */ }

  static create(params: FaceDetectionParams): FaceDetectionResult { /* factory */ }

  getFaceRegion(canvas: HTMLCanvasElement): ImageData | null { /* crop */ }
  getFaceCenter(): Point | null { /* compute center */ }
}
```

#### QualityAssessment

```typescript
// demo-ui/src/lib/biometric/domain/entities/quality-assessment.ts

/**
 * Immutable value object for quality assessment output.
 *
 * Mirrors: app/domain/entities/quality_assessment.py → QualityAssessment
 *
 * Invariants:
 * - score ∈ [0, 100]
 * - blurScore ≥ 0
 * - faceSize ≥ 0
 */
export class QualityAssessment {
  readonly score: number;
  readonly blurScore: number;
  readonly lightingScore: number;
  readonly faceSize: number;
  readonly isAcceptable: boolean;

  private constructor(params: QualityParams) { /* validate + assign */ }

  static create(params: QualityParams): QualityAssessment { /* factory */ }

  getQualityLevel(): 'poor' | 'fair' | 'good' { /* thresholds */ }
  isBlurry(threshold?: number): boolean { /* blur check */ }
  isTooSmall(minSize?: number): boolean { /* size check */ }
  getIssues(): QualityIssue[] { /* collect all issues */ }
}
```

#### LivenessResult

```typescript
// demo-ui/src/lib/biometric/domain/entities/liveness-result.ts

/**
 * Immutable value object for liveness detection output.
 *
 * Mirrors: app/domain/entities/liveness_result.py → LivenessResult
 *
 * Invariants:
 * - livenessScore ∈ [0, 100]
 * - challenge is non-empty
 */
export class LivenessResult {
  readonly isLive: boolean;
  readonly livenessScore: number;
  readonly challenge: string;
  readonly challengeCompleted: boolean;

  private constructor(params: LivenessParams) { /* validate + assign */ }

  static create(params: LivenessParams): LivenessResult { /* factory */ }

  getConfidenceLevel(): 'low' | 'medium' | 'high' { /* thresholds */ }
  isSpoofSuspected(threshold?: number): boolean { /* check */ }
  requiresAdditionalVerification(threshold?: number): boolean { /* check */ }
}
```

### 5.3 Domain Errors

```typescript
// demo-ui/src/lib/biometric/domain/errors.ts

/**
 * Domain error hierarchy.
 *
 * Mirrors: app/domain/exceptions/face_errors.py
 */
export abstract class BiometricError extends Error {
  abstract readonly code: string;
}

export class FaceNotDetectedError extends BiometricError {
  readonly code = 'FACE_NOT_DETECTED';
}

export class MultipleFacesError extends BiometricError {
  readonly code = 'MULTIPLE_FACES';
  constructor(readonly count: number) { super(`Expected 1 face, found ${count}`); }
}

export class PoorImageQualityError extends BiometricError {
  readonly code = 'POOR_IMAGE_QUALITY';
  constructor(
    readonly qualityScore: number,
    readonly minThreshold: number,
    readonly issues: QualityIssue[],
  ) { super(`Quality ${qualityScore} below threshold ${minThreshold}`); }
}

export class LivenessCheckError extends BiometricError {
  readonly code = 'LIVENESS_CHECK_FAILED';
}

export class ModelNotLoadedError extends BiometricError {
  readonly code = 'MODEL_NOT_LOADED';
}

export class ModelLoadError extends BiometricError {
  readonly code = 'MODEL_LOAD_FAILED';
  constructor(readonly modelName: string, cause?: Error) {
    super(`Failed to load model: ${modelName}`);
  }
}
```

### 5.4 Shared Types

```typescript
// demo-ui/src/lib/biometric/domain/types.ts

/** Input accepted by detector implementations */
export type DetectorInput = ImageData | HTMLCanvasElement | HTMLVideoElement;

/** Bounding box in pixel coordinates */
export interface BoundingBox {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

/** 2D/3D landmark point */
export interface LandmarkPoint {
  readonly x: number;
  readonly y: number;
  readonly z?: number;
  readonly label?: string;
}

/** 2D point */
export interface Point {
  readonly x: number;
  readonly y: number;
}

/** Quality issue descriptor */
export interface QualityIssue {
  readonly type: 'blur' | 'lighting' | 'face_size' | 'occlusion' | 'pose';
  readonly description: string;
  readonly score: number;
  readonly threshold: number;
}

/** Biometric processing configuration */
export interface BiometricConfig {
  readonly qualityThreshold: number;       // 0-100, default 50
  readonly blurThreshold: number;          // Laplacian variance, default 100
  readonly minFaceSize: number;            // pixels, default 80
  readonly livenessThreshold: number;      // 0-100, default 50
  readonly detectionConfidence: number;    // 0-1, default 0.7
  readonly maxDetectionTimeMs: number;     // timeout, default 500
  readonly enableClientLiveness: boolean;  // default true
  readonly enableClientQuality: boolean;   // default true
  readonly serverFallbackEnabled: boolean; // default true
}

/** Default configuration values */
export const DEFAULT_BIOMETRIC_CONFIG: BiometricConfig = {
  qualityThreshold: 50,
  blurThreshold: 100,
  minFaceSize: 80,
  livenessThreshold: 50,
  detectionConfidence: 0.7,
  maxDetectionTimeMs: 500,
  enableClientLiveness: true,
  enableClientQuality: true,
  serverFallbackEnabled: true,
} as const;
```

---

## 6. Infrastructure Layer — ML Adapters

### 6.1 MediaPipe Face Detector (WASM)

```typescript
// demo-ui/src/lib/biometric/infrastructure/ml/mediapipe-face-detector.ts

/**
 * MediaPipe Face Detection adapter.
 *
 * Implements IFaceDetector using MediaPipe Face Detection WASM.
 * - 468 landmarks at 30+ FPS
 * - Runs entirely in browser (no server round-trip)
 * - Lazy model loading with IModelLoader
 *
 * Liskov Substitution: Can replace ServerFaceDetector transparently.
 */
export class MediaPipeFaceDetector implements IFaceDetector {
  constructor(
    private readonly modelLoader: IModelLoader<FaceDetection>,
    private readonly config: Pick<BiometricConfig, 'detectionConfidence'>,
  ) {}

  async detect(image: DetectorInput): Promise<FaceDetectionResult> { /* ... */ }
  async dispose(): Promise<void> { /* ... */ }
}
```

### 6.2 OpenCV.js Quality Assessor

```typescript
// demo-ui/src/lib/biometric/infrastructure/ml/opencv-quality-assessor.ts

/**
 * OpenCV.js quality assessment adapter.
 *
 * Implements IQualityAssessor using OpenCV.js for:
 * - Blur detection (Laplacian variance)
 * - Lighting assessment (mean brightness, histogram analysis)
 * - Face size validation
 *
 * Mirrors: app/infrastructure/ml/quality/quality_assessor.py
 */
export class OpenCVQualityAssessor implements IQualityAssessor {
  constructor(
    private readonly modelLoader: IModelLoader<typeof cv>,
    private readonly config: Pick<BiometricConfig,
      'qualityThreshold' | 'blurThreshold' | 'minFaceSize'>,
  ) {}

  async assess(faceImage: ImageData): Promise<QualityAssessment> { /* ... */ }
  getMinimumAcceptableScore(): number { return this.config.qualityThreshold; }
}
```

### 6.3 MediaPipe Passive Liveness Detector

```typescript
// demo-ui/src/lib/biometric/infrastructure/ml/mediapipe-liveness-detector.ts

/**
 * Passive liveness detection using MediaPipe Face Mesh.
 *
 * Implements ILivenessDetector for client-side passive checks:
 * - Depth estimation from 3D landmarks (z-coordinates)
 * - Texture frequency analysis (moire pattern detection)
 * - Edge sharpness analysis (print attack detection)
 *
 * Note: This is a PRE-CHECK only. High-security flows still
 * require server-side liveness verification.
 */
export class MediaPipeLivenessDetector implements ILivenessDetector {
  constructor(
    private readonly modelLoader: IModelLoader<FaceMesh>,
    private readonly config: Pick<BiometricConfig, 'livenessThreshold'>,
  ) {}

  async checkLiveness(image: DetectorInput): Promise<LivenessResult> { /* ... */ }
  getChallengeType(): string { return 'passive_depth'; }
  getLivenessThreshold(): number { return this.config.livenessThreshold; }
}
```

### 6.4 Server Fallback Adapters

```typescript
// demo-ui/src/lib/biometric/infrastructure/server/server-face-detector.ts

/**
 * Server-side face detection fallback adapter.
 *
 * Implements IFaceDetector by delegating to the backend API.
 * Used when:
 * - WASM is not supported
 * - Client-side detection fails
 * - Higher accuracy is required
 *
 * Open/Closed Principle: Added without changing existing code.
 */
export class ServerFaceDetector implements IFaceDetector {
  constructor(private readonly apiClient: IBiometricApiClient) {}

  async detect(image: DetectorInput): Promise<FaceDetectionResult> { /* ... */ }
  async dispose(): Promise<void> { /* no-op */ }
}
```

```typescript
// demo-ui/src/lib/biometric/infrastructure/server/server-quality-assessor.ts

/**
 * Server-side quality assessment fallback adapter.
 */
export class ServerQualityAssessor implements IQualityAssessor {
  constructor(private readonly apiClient: IBiometricApiClient) {}

  async assess(faceImage: ImageData): Promise<QualityAssessment> { /* ... */ }
  getMinimumAcceptableScore(): number { return 50; }
}
```

### 6.5 Model Loaders

```typescript
// demo-ui/src/lib/biometric/infrastructure/ml/loaders/mediapipe-model-loader.ts

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
export class MediaPipeModelLoader<TModel> implements IModelLoader<TModel> {
  private model: TModel | null = null;
  private loadPromise: Promise<TModel> | null = null;

  constructor(
    private readonly factory: () => Promise<TModel>,
    private readonly modelName: string,
  ) {}

  async load(): Promise<TModel> {
    if (this.model) return this.model;
    if (this.loadPromise) return this.loadPromise;

    this.loadPromise = this.factory()
      .then(model => { this.model = model; return model; })
      .catch(err => {
        this.loadPromise = null;
        throw new ModelLoadError(this.modelName, err);
      });

    return this.loadPromise;
  }

  isLoaded(): boolean { return this.model !== null; }

  async unload(): Promise<void> {
    if (this.model && typeof (this.model as any).close === 'function') {
      (this.model as any).close();
    }
    this.model = null;
    this.loadPromise = null;
  }
}
```

### 6.6 Resilient Adapter (Decorator Pattern)

```typescript
// demo-ui/src/lib/biometric/infrastructure/resilience/fallback-face-detector.ts

/**
 * Resilient face detector with automatic fallback.
 *
 * Decorator Pattern: Wraps a primary IFaceDetector and falls back
 * to a secondary implementation on failure.
 *
 * Example: MediaPipeFaceDetector (primary) → ServerFaceDetector (fallback)
 *
 * Open/Closed: Adds resilience without modifying existing detectors.
 */
export class FallbackFaceDetector implements IFaceDetector {
  constructor(
    private readonly primary: IFaceDetector,
    private readonly fallback: IFaceDetector,
    private readonly logger: ILogger,
  ) {}

  async detect(image: DetectorInput): Promise<FaceDetectionResult> {
    try {
      return await this.primary.detect(image);
    } catch (error) {
      this.logger.warn('Primary detector failed, using fallback', { error });
      return this.fallback.detect(image);
    }
  }

  async dispose(): Promise<void> {
    await Promise.all([this.primary.dispose(), this.fallback.dispose()]);
  }
}
```

---

## 7. Application Layer — Use Cases

### 7.1 ClientDetectFaceUseCase

```typescript
// demo-ui/src/lib/biometric/application/use-cases/client-detect-face.ts

/**
 * Client-side face detection use case.
 *
 * Mirrors: app/application/use_cases/detect_multi_face.py (single face variant)
 *
 * Orchestrates:
 * 1. Detect face via IFaceDetector
 * 2. Validate single face found
 * 3. Return structured result
 *
 * SRP: Only orchestrates detection, no quality or liveness logic.
 * DIP: Depends on IFaceDetector interface, not MediaPipe directly.
 */
export class ClientDetectFaceUseCase {
  constructor(private readonly detector: IFaceDetector) {}

  async execute(image: DetectorInput): Promise<FaceDetectionResult> {
    const result = await this.detector.detect(image);

    if (!result.found) {
      throw new FaceNotDetectedError();
    }

    return result;
  }
}
```

### 7.2 ClientAssessQualityUseCase

```typescript
// demo-ui/src/lib/biometric/application/use-cases/client-assess-quality.ts

/**
 * Client-side quality assessment use case.
 *
 * Mirrors: app/application/use_cases/analyze_quality.py
 *
 * Orchestrates:
 * 1. Detect face (to crop face region)
 * 2. Assess quality on cropped region
 * 3. Return quality assessment with issues
 *
 * SRP: Only orchestrates quality assessment pipeline.
 */
export class ClientAssessQualityUseCase {
  constructor(
    private readonly detector: IFaceDetector,
    private readonly qualityAssessor: IQualityAssessor,
  ) {}

  async execute(image: DetectorInput): Promise<ClientQualityResult> {
    // Step 1: Detect face
    const detection = await this.detector.detect(image);
    if (!detection.found) throw new FaceNotDetectedError();

    // Step 2: Crop face region
    const faceImage = detection.getFaceRegion(/* canvas */);
    if (!faceImage) throw new FaceNotDetectedError();

    // Step 3: Assess quality
    const quality = await this.qualityAssessor.assess(faceImage);

    return { detection, quality };
  }
}
```

### 7.3 HybridEnrollFaceUseCase

```typescript
// demo-ui/src/lib/biometric/application/use-cases/hybrid-enroll-face.ts

/**
 * Hybrid enrollment use case — client pre-processing + server enrollment.
 *
 * This is the key use case that combines client and server capabilities:
 *
 * Client side:
 * 1. Detect face (MediaPipe WASM)
 * 2. Assess quality (OpenCV.js)
 * 3. Passive liveness check (MediaPipe)
 * 4. Reject poor images BEFORE upload
 *
 * Server side:
 * 5. Extract embedding (DeepFace — requires GPU/CPU-intensive models)
 * 6. Store in pgvector database
 * 7. Return enrollment result
 *
 * This pattern ensures:
 * - Instant feedback for quality/detection issues
 * - Reduced server load (only good images reach the backend)
 * - Security-critical operations stay server-side
 *
 * SRP: Orchestrates the full hybrid enrollment pipeline.
 * DIP: All dependencies are interfaces.
 */
export class HybridEnrollFaceUseCase {
  constructor(
    private readonly detector: IFaceDetector,
    private readonly qualityAssessor: IQualityAssessor,
    private readonly livenessDetector: ILivenessDetector,
    private readonly apiClient: IBiometricApiClient,
  ) {}

  async execute(params: HybridEnrollParams): Promise<HybridEnrollResult> {
    // Phase 1 — Client-side pre-processing (instant feedback)
    const detection = await this.detector.detect(params.image);
    if (!detection.found) throw new FaceNotDetectedError();

    const faceImage = detection.getFaceRegion(/* canvas */);
    if (!faceImage) throw new FaceNotDetectedError();

    const quality = await this.qualityAssessor.assess(faceImage);
    if (!quality.isAcceptable) {
      throw new PoorImageQualityError(
        quality.score,
        this.qualityAssessor.getMinimumAcceptableScore(),
        quality.getIssues(),
      );
    }

    const liveness = await this.livenessDetector.checkLiveness(params.image);
    if (liveness.isSpoofSuspected()) {
      throw new LivenessCheckError();
    }

    // Phase 2 — Server-side enrollment (security-critical)
    const imageBlob = await canvasToBlob(params.image);

    const serverResult = await this.apiClient.enrollFace({
      personId: params.personId,
      image: imageBlob,
      clientQualityScore: quality.score,
      clientLivenessScore: liveness.livenessScore,
      metadata: params.metadata,
    });

    return {
      ...serverResult,
      clientSide: { detection, quality, liveness },
    };
  }
}
```

### 7.4 HybridVerifyFaceUseCase

```typescript
// demo-ui/src/lib/biometric/application/use-cases/hybrid-verify-face.ts

/**
 * Hybrid verification use case — client pre-check + server verification.
 *
 * Client: detect + quality gate (reject early)
 * Server: embedding extraction + similarity computation
 */
export class HybridVerifyFaceUseCase {
  constructor(
    private readonly detector: IFaceDetector,
    private readonly qualityAssessor: IQualityAssessor,
    private readonly apiClient: IBiometricApiClient,
  ) {}

  async execute(params: HybridVerifyParams): Promise<HybridVerifyResult> { /* ... */ }
}
```

### 7.5 RealTimeAnalysisUseCase

```typescript
// demo-ui/src/lib/biometric/application/use-cases/realtime-analysis.ts

/**
 * Real-time video frame analysis use case.
 *
 * Replaces WebSocket-based live analysis with client-side processing.
 * Runs detection + quality on each frame at target FPS.
 *
 * Used by: Live camera overlay, proctoring, enrollment guidance
 */
export class RealTimeAnalysisUseCase {
  constructor(
    private readonly detector: IFaceDetector,
    private readonly qualityAssessor: IQualityAssessor,
    private readonly config: Pick<BiometricConfig, 'maxDetectionTimeMs'>,
  ) {}

  /**
   * Analyze a single frame. Designed to be called from requestAnimationFrame.
   * Returns null if processing exceeds time budget.
   */
  async analyzeFrame(frame: DetectorInput): Promise<FrameAnalysis | null> { /* ... */ }
}
```

---

## 8. Presentation Layer — React Hooks & Components

### 8.1 Hooks

```typescript
// demo-ui/src/hooks/use-client-face-detection.ts

/**
 * React hook for client-side face detection.
 *
 * Wraps ClientDetectFaceUseCase with React state management.
 * Uses the DI container to resolve the correct IFaceDetector.
 */
export function useClientFaceDetection() {
  const useCase = useBiometricContainer().clientDetectFace;
  // ... React Query mutation wrapping useCase.execute()
}
```

```typescript
// demo-ui/src/hooks/use-client-quality.ts

/**
 * React hook for client-side quality assessment.
 *
 * Provides real-time quality feedback with debouncing.
 */
export function useClientQuality() { /* ... */ }
```

```typescript
// demo-ui/src/hooks/use-hybrid-enrollment.ts

/**
 * React hook for hybrid enrollment.
 *
 * Orchestrates the full client + server enrollment flow
 * with progress tracking and error handling.
 */
export function useHybridEnrollment() { /* ... */ }
```

```typescript
// demo-ui/src/hooks/use-realtime-analysis.ts

/**
 * React hook for real-time frame analysis.
 *
 * Replaces the existing use-live-camera-analysis.ts (WebSocket-based)
 * with client-side processing using requestAnimationFrame.
 */
export function useRealtimeAnalysis(
  videoRef: RefObject<HTMLVideoElement>,
  options?: { targetFps?: number; enabled?: boolean },
) { /* ... */ }
```

### 8.2 Components

```typescript
// demo-ui/src/components/biometric/quality-overlay.tsx

/**
 * Real-time quality feedback overlay.
 *
 * Renders on top of the camera feed:
 * - Face bounding box (green/yellow/red based on quality)
 * - Quality score badge
 * - Issue descriptions ("Too blurry", "Face too small", etc.)
 * - Liveness indicator
 */
export function QualityOverlay({ analysis }: { analysis: FrameAnalysis }) { /* ... */ }
```

```typescript
// demo-ui/src/components/biometric/guided-capture.tsx

/**
 * Guided face capture component.
 *
 * Combines camera feed + real-time analysis + capture trigger.
 * Only enables the "Capture" button when quality is acceptable.
 */
export function GuidedCapture({
  onCapture,
  minQuality,
}: GuidedCaptureProps) { /* ... */ }
```

---

## 9. Hybrid Client-Server Flow

### 9.1 Enrollment Sequence

```
┌────────┐      ┌──────────┐      ┌────────────┐     ┌─────────────┐
│  User  │      │  React   │      │  Use Case  │     │   Backend   │
│        │      │  Hook    │      │  (Client)  │     │   API       │
└───┬────┘      └────┬─────┘      └─────┬──────┘     └──────┬──────┘
    │                │                   │                    │
    │ Click Capture  │                   │                    │
    │───────────────→│                   │                    │
    │                │ execute(image)    │                    │
    │                │──────────────────→│                    │
    │                │                   │                    │
    │                │    ┌──────────────┴─────────────┐     │
    │                │    │ 1. detect(image)           │     │
    │                │    │    → MediaPipe WASM        │     │
    │                │    │ 2. assess(faceRegion)      │     │
    │                │    │    → OpenCV.js             │     │
    │                │    │ 3. checkLiveness(image)    │     │
    │                │    │    → MediaPipe passive     │     │
    │                │    └──────────────┬─────────────┘     │
    │                │                   │                    │
    │                │                   │ [quality OK]       │
    │                │                   │ enrollFace(blob)   │
    │                │                   │───────────────────→│
    │                │                   │                    │
    │                │                   │    ┌───────────────┴────┐
    │                │                   │    │ 4. detect(image)   │
    │                │                   │    │ 5. extract(face)   │
    │                │                   │    │ 6. save(embedding) │
    │                │                   │    └───────────────┬────┘
    │                │                   │                    │
    │                │                   │   EnrollResult     │
    │                │                   │←───────────────────│
    │                │  HybridResult     │                    │
    │                │←──────────────────│                    │
    │  success + ID  │                   │                    │
    │←───────────────│                   │                    │
```

### 9.2 Real-Time Analysis (Replaces WebSocket)

```
┌───────────────────────────────────────────────────────────┐
│ Browser — requestAnimationFrame loop                      │
│                                                           │
│  Video Frame → MediaPipe Detect → OpenCV Quality          │
│       ↓              ↓                  ↓                 │
│   30 FPS        < 15ms/frame       < 5ms/frame            │
│                      ↓                  ↓                 │
│              FrameAnalysis { detection, quality }          │
│                      ↓                                    │
│              QualityOverlay (React render)                 │
│                                                           │
│  NO NETWORK TRAFFIC for real-time analysis                │
└───────────────────────────────────────────────────────────┘
```

### 9.3 Fallback Strategy

```
                ┌─────────────────┐
                │ Feature Detect  │
                │ (WASM Support?) │
                └────────┬────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
         ┌────▼────┐          ┌─────▼─────┐
         │  YES    │          │   NO      │
         │ Client  │          │  Server   │
         │ Pipeline│          │  Fallback │
         └────┬────┘          └─────┬─────┘
              │                     │
    ┌─────────▼──────────┐   ┌─────▼──────────┐
    │ MediaPipe Detect   │   │ POST /detect   │
    │ OpenCV Quality     │   │ POST /quality  │
    │ MediaPipe Liveness │   │ POST /liveness │
    └─────────┬──────────┘   └─────┬──────────┘
              │                     │
              └──────────┬──────────┘
                         │
                ┌────────▼────────┐
                │ Unified Result  │
                │ (same types)    │
                └─────────────────┘
```

---

## 10. WebAuthn Integration

### 10.1 Architecture

WebAuthn replaces the always-failing fingerprint and voice stubs with
real device-native biometric authentication (Touch ID, Face ID, Windows Hello).

```
┌────────────────────────────────────────────────────────┐
│ Browser                                                 │
│                                                         │
│  ┌─────────────┐    ┌───────────────────────────────┐  │
│  │  WebAuthn   │    │  Platform Authenticator       │  │
│  │  Client     │───→│  (Touch ID / Face ID /        │  │
│  │  (JS API)   │    │   Windows Hello / PIN)        │  │
│  └──────┬──────┘    └───────────────────────────────┘  │
│         │                                               │
└─────────┼───────────────────────────────────────────────┘
          │  credential (public key + attestation)
          ▼
┌──────────────────────────────────────────────────────────┐
│ Backend (biometric-processor)                            │
│                                                          │
│  ┌────────────────────┐    ┌────────────────────────┐   │
│  │  /api/v1/webauthn/ │    │  WebAuthn Credential   │   │
│  │    register        │───→│    Repository          │   │
│  │    authenticate    │    │    (PostgreSQL)         │   │
│  │    delete          │    └────────────────────────┘   │
│  └────────────────────┘                                  │
│                                                          │
│  Replaces: fingerprint.py (stub) + voice.py (stub)      │
└──────────────────────────────────────────────────────────┘
```

### 10.2 Domain Interface

```typescript
// demo-ui/src/lib/biometric/domain/interfaces/device-authenticator.ts

/**
 * Port for device-native biometric authentication.
 *
 * Replaces fingerprint/voice stubs with WebAuthn/FIDO2.
 * Abstracts the WebAuthn API so use cases don't depend on browser APIs.
 */
export interface IDeviceAuthenticator {
  /** Check if device supports biometric authentication */
  isAvailable(): Promise<boolean>;

  /** Register a new credential (enrollment equivalent) */
  register(params: DeviceRegisterParams): Promise<DeviceCredential>;

  /** Authenticate with existing credential (verification equivalent) */
  authenticate(params: DeviceAuthParams): Promise<DeviceAuthResult>;

  /** Remove a stored credential */
  removeCredential(credentialId: string): Promise<void>;
}
```

### 10.3 Backend Route

```python
# app/api/routes/webauthn.py

"""
WebAuthn/FIDO2 endpoints.

Replaces fingerprint and voice stubs with real device-native
biometric authentication. Maps to the same enrollment/verify/delete
contract that identity-core-api expects.

Endpoints:
  POST /api/v1/webauthn/register/begin     → Generate challenge
  POST /api/v1/webauthn/register/complete   → Store credential
  POST /api/v1/webauthn/authenticate/begin  → Generate assertion
  POST /api/v1/webauthn/authenticate/complete → Verify assertion
  DELETE /api/v1/webauthn/{credential_id}   → Remove credential
"""
```

---

## 11. DI Container

### 11.1 Client-Side Container

```typescript
// demo-ui/src/lib/biometric/container.ts

/**
 * Dependency injection container for browser biometric processing.
 *
 * Mirrors: app/core/container.py
 *
 * Wires together all interfaces and implementations:
 * - Detects WASM capability and selects client vs. server adapters
 * - Applies decorator pattern for fallback resilience
 * - Provides singleton model loaders for memory efficiency
 * - Exposes fully-configured use cases
 *
 * Usage:
 *   const container = createBiometricContainer(config);
 *   const result = await container.hybridEnroll.execute(params);
 */

export interface BiometricContainer {
  // Use cases (application layer)
  readonly clientDetectFace: ClientDetectFaceUseCase;
  readonly clientAssessQuality: ClientAssessQualityUseCase;
  readonly hybridEnroll: HybridEnrollFaceUseCase;
  readonly hybridVerify: HybridVerifyFaceUseCase;
  readonly realtimeAnalysis: RealTimeAnalysisUseCase;

  // Lifecycle
  dispose(): Promise<void>;
}

export function createBiometricContainer(
  config: Partial<BiometricConfig> = {},
  apiClient: IBiometricApiClient = createDefaultApiClient(),
): BiometricContainer {
  const cfg = { ...DEFAULT_BIOMETRIC_CONFIG, ...config };

  // Model loaders (singleton, lazy)
  const mediapipeLoader = new MediaPipeModelLoader(/* ... */);
  const opencvLoader = new OpenCVModelLoader(/* ... */);

  // Infrastructure — ML adapters
  const clientDetector = new MediaPipeFaceDetector(mediapipeLoader, cfg);
  const serverDetector = new ServerFaceDetector(apiClient);
  const detector = new FallbackFaceDetector(clientDetector, serverDetector, logger);

  const clientQuality = new OpenCVQualityAssessor(opencvLoader, cfg);
  const serverQuality = new ServerQualityAssessor(apiClient);
  const quality = cfg.serverFallbackEnabled
    ? new FallbackQualityAssessor(clientQuality, serverQuality, logger)
    : clientQuality;

  const liveness = new MediaPipeLivenessDetector(mediapipeLoader, cfg);

  // Application — Use cases
  return {
    clientDetectFace: new ClientDetectFaceUseCase(detector),
    clientAssessQuality: new ClientAssessQualityUseCase(detector, quality),
    hybridEnroll: new HybridEnrollFaceUseCase(detector, quality, liveness, apiClient),
    hybridVerify: new HybridVerifyFaceUseCase(detector, quality, apiClient),
    realtimeAnalysis: new RealTimeAnalysisUseCase(detector, quality, cfg),
    dispose: () => Promise.all([mediapipeLoader.unload(), opencvLoader.unload()]),
  };
}
```

### 11.2 React Context Provider

```typescript
// demo-ui/src/lib/biometric/provider.tsx

/**
 * React context provider for the biometric DI container.
 *
 * Initializes the container once and provides it to all child components.
 * Handles cleanup on unmount (model disposal).
 */
export function BiometricProvider({
  config,
  children,
}: BiometricProviderProps) {
  const container = useMemo(() => createBiometricContainer(config), [config]);

  useEffect(() => {
    return () => { container.dispose(); };
  }, [container]);

  return (
    <BiometricContext.Provider value={container}>
      {children}
    </BiometricContext.Provider>
  );
}

export function useBiometricContainer(): BiometricContainer {
  const ctx = useContext(BiometricContext);
  if (!ctx) throw new Error('useBiometricContainer must be used within BiometricProvider');
  return ctx;
}
```

---

## 12. Security Architecture

### 12.1 Principles

1. **Embeddings never leave the server** — client computes quality/detection only
2. **Server-side verification is authoritative** — client checks are UX optimization
3. **Client scores are advisory** — server re-validates quality before enrollment
4. **No client-side embedding extraction** — prevents template theft
5. **WebAuthn credentials are origin-bound** — cannot be phished

### 12.2 Threat Model

| Threat | Mitigation |
|--------|-----------|
| Spoofed client quality scores | Server re-validates all images independently |
| Injected pre-computed embeddings | Server extracts embeddings itself, never accepts client embeddings |
| WASM model tampering | Models loaded from same-origin CDN with SRI hashes |
| Camera feed interception | All processing in-memory, no disk writes |
| WebAuthn credential theft | Hardware-bound keys, non-exportable by spec |

### 12.3 API Contract Extension

The existing enrollment API gains optional client-side metadata:

```python
# Server accepts but DOES NOT TRUST these values — they're for logging/analytics
class EnrollmentRequestExtended(BaseModel):
    user_id: str
    file: UploadFile
    tenant_id: Optional[str] = None
    # New — advisory fields from client
    client_quality_score: Optional[float] = None    # Client's quality assessment
    client_liveness_score: Optional[float] = None   # Client's liveness pre-check
    client_detection_time_ms: Optional[int] = None  # Client processing time
```

---

## 13. Testing Strategy

### 13.1 Test Pyramid

```
                    ┌────────────┐
                    │    E2E     │  Playwright (3-5 tests)
                    │  Browser   │  Full camera → enrollment flow
                   ┌┴────────────┴┐
                   │  Integration  │  Vitest (10-15 tests)
                   │  Hook + API   │  Hooks with mock container
                  ┌┴──────────────┴┐
                  │   Use Case     │  Vitest (15-20 tests)
                  │   Unit Tests   │  Use cases with mock interfaces
                 ┌┴────────────────┴┐
                 │  Domain Entity   │  Vitest (20-30 tests)
                 │  + Adapter Unit  │  Entities, adapters, value objects
                 └──────────────────┘
```

### 13.2 Test Locations

| Layer | Directory | Framework | What's Tested |
|-------|-----------|-----------|---------------|
| Domain entities | `demo-ui/src/lib/biometric/domain/__tests__/` | Vitest | Value object creation, validation, invariants |
| Domain interfaces | — | — | Not tested directly (Protocols) |
| Infrastructure adapters | `demo-ui/src/lib/biometric/infrastructure/__tests__/` | Vitest | Each adapter in isolation with mock models |
| Use cases | `demo-ui/src/lib/biometric/application/__tests__/` | Vitest | Use cases with mock interface implementations |
| Container | `demo-ui/src/lib/biometric/__tests__/container.test.ts` | Vitest | Container wiring, fallback behavior |
| React hooks | `demo-ui/src/hooks/__tests__/` | Vitest + Testing Library | Hook state transitions, error handling |
| Components | `demo-ui/src/components/biometric/__tests__/` | Vitest + Testing Library | Render output, user interaction |
| E2E | `demo-ui/e2e/` | Playwright | Full browser flow with real camera mock |
| Backend WebAuthn | `tests/unit/api/routes/test_webauthn.py` | Pytest | WebAuthn endpoint behavior |
| Backend hybrid | `tests/integration/test_client_biometric.py` | Pytest | Hybrid endpoint with client metadata |

### 13.3 Mock Strategy

```typescript
// demo-ui/src/lib/biometric/testing/mocks.ts

/**
 * Mock implementations for testing.
 *
 * Each mock implements the domain interface and returns configurable results.
 * Used in use case and hook tests.
 */
export function createMockFaceDetector(
  overrides?: Partial<IFaceDetector>,
): IFaceDetector { /* ... */ }

export function createMockQualityAssessor(
  overrides?: Partial<IQualityAssessor>,
): IQualityAssessor { /* ... */ }

export function createMockLivenessDetector(
  overrides?: Partial<ILivenessDetector>,
): ILivenessDetector { /* ... */ }

export function createMockApiClient(
  overrides?: Partial<IBiometricApiClient>,
): IBiometricApiClient { /* ... */ }

/**
 * Create a fully-configured container with all mocks.
 * Useful for integration testing hooks and components.
 */
export function createMockBiometricContainer(
  overrides?: Partial<BiometricContainer>,
): BiometricContainer { /* ... */ }
```

---

## 14. Directory Structure

```
demo-ui/src/lib/biometric/
├── domain/                          # Layer 0 — Pure types, zero deps
│   ├── interfaces/
│   │   ├── face-detector.ts         # IFaceDetector port
│   │   ├── quality-assessor.ts      # IQualityAssessor port
│   │   ├── liveness-detector.ts     # ILivenessDetector port
│   │   ├── model-loader.ts          # IModelLoader<T> port
│   │   ├── biometric-api-client.ts  # IBiometricApiClient port
│   │   ├── device-authenticator.ts  # IDeviceAuthenticator port (WebAuthn)
│   │   └── index.ts                 # Barrel export
│   ├── entities/
│   │   ├── face-detection-result.ts # FaceDetectionResult value object
│   │   ├── quality-assessment.ts    # QualityAssessment value object
│   │   ├── liveness-result.ts       # LivenessResult value object
│   │   └── index.ts
│   ├── errors.ts                    # BiometricError hierarchy
│   ├── types.ts                     # Shared types (BoundingBox, etc.)
│   └── index.ts
│
├── application/                     # Layer 1 — Use cases, depends on domain only
│   ├── use-cases/
│   │   ├── client-detect-face.ts
│   │   ├── client-assess-quality.ts
│   │   ├── hybrid-enroll-face.ts
│   │   ├── hybrid-verify-face.ts
│   │   ├── realtime-analysis.ts
│   │   └── index.ts
│   └── index.ts
│
├── infrastructure/                  # Layer 2 — Adapters, implements domain interfaces
│   ├── ml/
│   │   ├── mediapipe-face-detector.ts
│   │   ├── opencv-quality-assessor.ts
│   │   ├── mediapipe-liveness-detector.ts
│   │   └── loaders/
│   │       ├── mediapipe-model-loader.ts
│   │       └── opencv-model-loader.ts
│   ├── server/
│   │   ├── server-face-detector.ts
│   │   ├── server-quality-assessor.ts
│   │   └── biometric-api-client-impl.ts
│   ├── webauthn/
│   │   └── webauthn-device-authenticator.ts
│   ├── resilience/
│   │   ├── fallback-face-detector.ts
│   │   └── fallback-quality-assessor.ts
│   └── index.ts
│
├── testing/                         # Test utilities
│   ├── mocks.ts                     # Mock implementations
│   ├── fixtures.ts                  # Test data factories
│   └── index.ts
│
├── container.ts                     # DI container factory
├── provider.tsx                     # React context provider
└── index.ts                         # Public API barrel export

# Backend additions:
app/api/routes/
├── webauthn.py                      # WebAuthn endpoints (replaces stubs)
└── client_biometric.py              # Extended enrollment with client metadata

app/domain/interfaces/
└── credential_repository.py         # WebAuthn credential storage port

app/infrastructure/persistence/
└── webauthn_credential_repository.py # PostgreSQL WebAuthn storage
```

---

## 15. Migration Plan

### Phase 1: Foundation (Week 1-2)

- [ ] Domain layer: entities, interfaces, errors, types
- [ ] Infrastructure: MediaPipe face detector adapter
- [ ] Infrastructure: OpenCV quality assessor adapter
- [ ] Infrastructure: Model loaders with lazy initialization
- [ ] DI Container + React Provider
- [ ] Unit tests for all domain entities
- [ ] Unit tests for adapters with mock models

### Phase 2: Use Cases + Hooks (Week 3)

- [ ] ClientDetectFaceUseCase + useClientFaceDetection hook
- [ ] ClientAssessQualityUseCase + useClientQuality hook
- [ ] RealTimeAnalysisUseCase + useRealtimeAnalysis hook
- [ ] QualityOverlay component
- [ ] GuidedCapture component
- [ ] Integration tests for hooks

### Phase 3: Hybrid Flow (Week 4)

- [ ] Server fallback adapters (ServerFaceDetector, ServerQualityAssessor)
- [ ] FallbackFaceDetector decorator
- [ ] HybridEnrollFaceUseCase + useHybridEnrollment hook
- [ ] HybridVerifyFaceUseCase
- [ ] Backend: Extended enrollment endpoint with client metadata
- [ ] Integration tests for hybrid flow

### Phase 4: WebAuthn (Week 5)

- [ ] Backend: WebAuthn credential repository
- [ ] Backend: WebAuthn route endpoints
- [ ] Client: WebAuthnDeviceAuthenticator adapter
- [ ] Client: useDeviceAuth hook
- [ ] Update fingerprint/voice routes to delegate to WebAuthn
- [ ] E2E tests with Playwright

### Phase 5: Polish + E2E (Week 6)

- [ ] Performance benchmarking (target: < 15ms/frame)
- [ ] Bundle size optimization (tree-shaking WASM modules)
- [ ] Playwright E2E tests for full enrollment flow
- [ ] Documentation updates
- [ ] CLAUDE.md updates

---

## Appendix A: Technology Versions

| Technology | Version | Purpose |
|-----------|---------|---------|
| MediaPipe Face Detection | 0.4.x | Browser face detection (WASM) |
| MediaPipe Face Mesh | 0.4.x | 468 landmarks + passive liveness |
| OpenCV.js | 4.9.x | Quality assessment (Laplacian, histogram) |
| ONNX Runtime Web | 1.17.x | Future: client-side embedding (reserved) |
| @simplewebauthn/browser | 10.x | WebAuthn client-side API |
| @simplewebauthn/server | 10.x | WebAuthn server-side validation |
| py_webauthn | 2.x | Python WebAuthn (alternative to JS server) |

## Appendix B: Performance Budget

| Operation | Target | Fallback Threshold |
|-----------|--------|-------------------|
| Face detection (MediaPipe) | < 15ms | > 100ms → use server |
| Quality assessment (OpenCV) | < 5ms | > 50ms → use server |
| Passive liveness (MediaPipe) | < 20ms | > 150ms → use server |
| Full frame analysis | < 33ms (30 FPS) | > 50ms → drop frames |
| Model initial load | < 3s | > 10s → show warning |
| WASM bundle size | < 2MB gzipped | — |

## Appendix C: Browser Support

| Browser | WASM | MediaPipe | WebAuthn | Status |
|---------|------|-----------|----------|--------|
| Chrome 90+ | Yes | Yes | Yes | Full support |
| Firefox 89+ | Yes | Yes | Yes | Full support |
| Safari 15.2+ | Yes | Yes | Yes | Full support |
| Edge 90+ | Yes | Yes | Yes | Full support |
| Safari 14- | Partial | No | No | Server fallback only |
| IE 11 | No | No | No | Not supported |
