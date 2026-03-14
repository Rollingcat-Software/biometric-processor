# Browser-Based Biometric Processing: Comprehensive Research Report

**Date**: March 13, 2026
**Scope**: Analysis of which biometric-processor operations can be handled client-side in browsers
**Covers**: Browser APIs, CPU/GPU utilization, frontend languages, WASM (KMP/CMP), all relevant tools & AI frameworks

---

## Table of Contents

1. [Server-Side Operations & Browser Feasibility Matrix](#1-current-server-side-operations--browser-feasibility-matrix)
2. [Browser APIs & Platform Capabilities](#2-browser-apis--platform-capabilities-2025-2026)
3. [Frontend ML Frameworks & Libraries](#3-frontend-ml-frameworks--libraries)
4. [KMP & CMP WASM Power for Biometrics](#4-kmp--cmp-wasm-power-for-biometrics)
5. [CPU & GPU Utilization in Browsers](#5-cpu--gpu-utilization-in-browsers)
6. [Commercial & Open-Source Browser Biometric Solutions](#6-commercial--open-source-browser-biometric-solutions)
7. [Rust-to-WASM Biometric Pipeline](#7-rust-to-wasm-biometric-pipeline)
8. [Privacy & Security Considerations](#8-privacy--security-considerations)
9. [Recommended Hybrid Architecture](#9-recommended-architecture-hybrid-client-server-split)
10. [Implementation Technology Recommendations](#10-implementation-technology-recommendations)
11. [Emerging Standards to Watch](#11-emerging-standards-to-watch)
12. [Summary of Key Findings](#12-summary-of-key-findings)

---

## 1. Current Server-Side Operations & Browser Feasibility Matrix

Based on analysis of all 25+ endpoint groups in the biometric-processor:

| Operation | Server Time | ML Models | Browser Feasible? | Notes |
|---|---|---|---|---|
| **Quality Assessment** | 50-100ms | OpenCV (no NN) | **YES** | Pure CV: blur (Laplacian), lighting, face size |
| **Face Detection** | 100-300ms | DeepFace CNN | **YES** | MediaPipe/face-api.js can replace |
| **Facial Landmarks (468pt)** | 100-200ms | MediaPipe Face Mesh | **YES** | MediaPipe has native JS/WASM support |
| **Liveness (Passive)** | 200-400ms | Haar + LBP + Color | **PARTIAL** | Texture analysis possible; certification gap |
| **Liveness (Active: blink/smile)** | 200-400ms | Haar cascades | **YES** | OpenCV.js Haar cascades available |
| **Gaze Tracking** | 150-250ms | MediaPipe + solvePnP | **YES** | MediaPipe Face Mesh runs in browser |
| **Head Pose Estimation** | included above | solvePnP | **YES** | Pure math on landmark points |
| **Demographics (age/gender)** | 500-800ms | DeepFace CNNs | **PARTIAL** | Possible with ONNX Runtime Web + WebGPU; heavy |
| **Card Type Detection** | 100-300ms | YOLOv8/v11/v12 | **PARTIAL** | YOLO Nano via ONNX Runtime Web feasible |
| **Deepfake Detection (texture)** | ~50ms | Texture heuristics | **YES** | Laplacian + LBP computable in browser |
| **Embedding Extraction** | 200-400ms | Facenet/ArcFace CNN | **NO** (keep server) | Security-critical; embeddings must stay server-side |
| **1:1 Verification** | 300-500ms | Detection + Extraction | **NO** (keep server) | Requires stored embeddings comparison |
| **1:N Search** | 500ms-2s | Extraction + DB scan | **NO** (keep server) | Requires database access |
| **Enrollment** | 300-500ms | Full pipeline | **NO** (keep server) | Security-critical storage operation |
| **Multi-Image Enrollment** | 1-2.5s | 5x pipeline + fusion | **NO** (keep server) | Too heavy; security-critical |
| **Batch Operations** | scales | All above | **NO** (keep server) | Server-only by nature |
| **Proctoring Frame** | 500ms-2s | Combined pipeline | **HYBRID** | Detection client-side, verification server-side |
| **Object Detection (proctor)** | 100-300ms | YOLOv8n | **PARTIAL** | YOLOv8 Nano runs in ONNX Runtime Web |
| **Similarity Calculation** | <1ms | Cosine distance | **YES** (but shouldn't) | Trivial math, but embeddings are secret |

---

## 2. Browser APIs & Platform Capabilities (2025-2026)

### 2.1 WebAuthn / FIDO2
- **Status**: Fully supported across Chrome, Firefox, Safari, Edge
- **Capability**: Platform biometric authenticators (Windows Hello, Touch ID, Face ID, Android)
- **Use case**: Authentication credential management, not raw biometric processing
- **Relevance**: Can replace fingerprint/voice stubs with passkey-based auth

### 2.2 WebGPU API (PRODUCTION - Nov 2025)
- **Milestone**: All major browsers support WebGPU as of Nov 25, 2025
- **Performance**: ~10x faster than WebGL for rendering; GPU-accelerated ML inference
- **ML support**: ONNX Runtime Web, Transformers.js v3, TensorFlow.js all have WebGPU backends
- **Limitation**: Browser GPU memory caps (4-6GB before degradation); ~5x slower than native GPU
- **Backend mapping**: Chrome/Edge -> Direct3D 12 (Windows), Metal (macOS); Firefox -> Vulkan/Metal; Safari -> Metal

### 2.3 WebNN API (EXPERIMENTAL - Jan 2026)
- **Status**: W3C Updated Candidate Recommendation (Jan 22, 2026); comment period until March 22, 2026
- **Browser support**: Edge and Chrome only (behind flags in Chromium)
- **Capability**: Hardware-accelerated neural network inference on CPU, GPU, and NPU
- **95 operators** now covered across Core ML, DirectML, ONNX Runtime Web, TFLite/XNNPACK
- **NOT production-ready** yet — but will be the future standard for browser ML

### 2.4 WebCodecs API (PRODUCTION - 2025)
- **Status**: W3C standard; supported in all browsers (Safari: VideoDecoder only)
- **Capability**: Low-level access to video frames (VideoFrame), bypassing media element overhead
- **Relevance**: Efficient frame capture for liveness detection, quality check, real-time tracking

### 2.5 Media Capture APIs
- **getUserMedia()**: Widely supported; camera/microphone access
- **ImageCapture API**: High-resolution still photos from camera (limited browser support)
- **MediaStream**: Real-time video stream processing

### 2.6 Web Speech API
- **SpeechRecognition**: Chrome/Chromium only; server-based by default
- **Limitation**: Cannot work offline; not suitable for speaker verification (only speech-to-text)

### 2.7 W3C Digital Credentials API (DRAFT - 2025)
- **Status**: First draft May 2025; Chrome 141 & Safari 26 ship stable support (Sept 2025)
- **Capability**: Browser-level digital credential management (mDocs, digital passports)
- **Future**: Will integrate with biometric verification for decentralized identity

---

## 3. Frontend ML Frameworks & Libraries

### 3.1 MediaPipe Web (RECOMMENDED for face operations)
- **Runtime**: WASM + GPU acceleration via FilesetResolver
- **Face Landmarker**: 468 landmarks, 3D coordinates, blendshape scores, real-time
- **Face Detector**: Bounding boxes, facial features detection
- **Capabilities**: Blink detection, smile detection, head pose, gaze direction
- **Performance**: Real-time (30+ FPS) on modern hardware
- **Directly replaces**: Server-side MediaPipe landmarks, gaze tracking, active liveness checks

### 3.2 TensorFlow.js
- **Backends**: WebGL, WebGPU, WASM, CPU
- **Models**: MobileNet, PoseNet, BlazeFace, FaceMesh (via MediaPipe)
- **Use case**: General-purpose browser ML inference
- **face-api.js**: Built on TensorFlow.js; face detection, landmarks, recognition, age/gender

### 3.3 ONNX Runtime Web (RECOMMENDED for model inference)
- **Backends**: WebGPU, WebGL, WebNN, WASM
- **Capability**: Run any ONNX model in browser (including converted PyTorch/TF models)
- **Key advantage**: Can run the same models used server-side (Facenet, ArcFace, YOLO) in browser
- **Performance**: WebGPU backend enables GPU-accelerated inference

### 3.4 OpenCV.js / OpenCV WASM
- **Capability**: Full OpenCV compiled to WASM
- **Use case**: Image quality assessment (Laplacian blur, brightness), Haar cascades, LBP
- **Directly replaces**: Server-side quality assessor, passive liveness texture checks
- **Limitation**: Large WASM binary (~8MB); initialization overhead

### 3.5 Transformers.js v3
- **WebGPU support**: Run Hugging Face models in browser
- **Capability**: Image classification, object detection, feature extraction
- **Use case**: Could run face embedding models if security model permits

### 3.6 face-api.js / Modern Face API
- **Status**: Maintained fork with WASM optimizations (2025)
- **Capability**: Face detection, landmarks (68-point), recognition, age/gender/expression
- **Privacy**: Fully local processing
- **Limitation**: Less accurate than server-side DeepFace; 68 landmarks vs 468

### 3.7 Beyond Reality Face SDK (BRFv5)
- **Status**: Stable; includes WASM export
- **Capability**: Multi-face detection, blink/smile/yawn detection, AR overlays
- **Use case**: Active liveness detection UI, face tracking for enrollment guidance

### 3.8 jeelizFaceFilter
- **Capability**: Real-time face detection, rotation, blink detection, multi-face
- **Use case**: Lightweight liveness indicators, AR overlays

---

## 4. KMP & CMP WASM Power for Biometrics

### 4.1 Kotlin/WASM (Beta - 2025)
- **Status**: Promoted to Beta; no longer experimental
- **Performance**: Nearly 3x faster than JavaScript in UI rendering scenarios
- **Browser support**: All major browsers (WasmGC supported since Dec 2024)
- **Multi-module compilation**: Being added for dynamic loading and plugin systems
- **Biometric use**: KMP documentation lists biometric authentication as use case
- **Gap**: No pre-built biometric algorithm libraries for Kotlin/WASM; would need wrapping

### 4.2 Compose Multiplatform for Web (Beta - Sept 2025)
- **Status**: Production-ready for early adopters (v1.9.0)
- **Capability**: Full Compose UI compiled to WASM; runs in browser
- **Real deployments**: Kotlin Playground, KotlinConf app, Rijksmuseum
- **Strengths for biometrics**:
  - Responsive camera overlay UI for enrollment/liveness
  - Cross-platform shared code (Android, iOS, Desktop, Web)
  - Smooth animations for liveness prompts
  - Shared domain logic with Android/iOS apps
- **Integration path**: Compose UI + JavaScript interop for MediaPipe/ONNX Runtime Web calls

### 4.3 KMP + CMP Architecture for Biometric Client

```
+---------------------------------------------+
|  Compose Multiplatform UI (WASM)            |
|  +--------------+  +----------------------+ |
|  | Camera View  |  | Liveness Prompts     | |
|  | Face Overlay |  | Quality Feedback     | |
|  | AR Guides    |  | Enrollment Progress  | |
|  +--------------+  +----------------------+ |
+---------------------------------------------+
|  KMP Shared Logic (WASM)                    |
|  - State management, validation             |
|  - API client for server calls              |
|  - Quality threshold logic                  |
+---------------------------------------------+
|  JS Interop Layer                           |
|  +----------+ +----------+ +------------+   |
|  |MediaPipe | |ONNX RT   | |OpenCV.js   |   |
|  |Face Mesh | |Web+WebGPU| |WASM        |   |
|  +----------+ +----------+ +------------+   |
+---------------------------------------------+
|  Browser APIs                               |
|  getUserMedia | WebGPU | WebCodecs | WebAuthn|
+---------------------------------------------+
```

### 4.4 Flutter Web (Alternative)
- **WASM compilation**: Available since Flutter 3.22
- **Biometric plugins**: local_auth, flutter_biometric_login
- **Status**: Production-ready for web; but WASM performance still catching up to native

---

## 5. CPU & GPU Utilization in Browsers

### 5.1 CPU Constraints
- JavaScript: Single-threaded by default (one core)
- **Web Workers**: Multi-threading; offload ML inference to worker threads
- **SharedArrayBuffer**: Enables shared memory between workers (requires COOP/COEP headers)
- **WASM threads**: WASM can use multiple threads via Web Workers + SharedArrayBuffer
- **Practical limit**: 4-8 worker threads reasonable; diminishing returns beyond that

### 5.2 GPU Constraints
- **WebGPU memory**: 4-6GB practical limit before degradation/crashes
- **Safari Metal**: 256MB-993MB buffer limits depending on device
- **Performance gap**: Browser GPU inference ~5x slower than native GPU
- **Model size limit**: Small-to-medium models (up to ~1B parameters quantized) feasible
- **Face models**: Facenet (128-D, ~24MB), ArcFace (512-D, ~120MB) — well within GPU limits

### 5.3 Performance Benchmarks
- Browser ML inference: ~5x slower than native GPU, ~15-17x slower than native CPU
- MediaPipe Face Mesh in browser: 30+ FPS on modern devices
- OpenCV.js face detection: 50-60 FPS for lightweight operations
- Kotlin/WASM UI rendering: 3x faster than JavaScript
- LLM in browser (Llama-3.2-1B): ~10 tokens/sec via WebGPU (Sept 2025)

---

## 6. Commercial & Open-Source Browser Biometric Solutions

### 6.1 Commercial SDKs
| Vendor | Client-Side Support | Technology | Notes |
|---|---|---|---|
| **iProov** | Partial | Flashmark + server AI | Liveness verification primarily server-side |
| **Jumio** | Partial | iProov integration | Cloud-first; deepfake detection server-side |
| **Onfido** | Partial | SDK for capture | Processing server-side |
| **FaceTec** | Partial | 3D FaceScan | Liveness detection; IP disputes ongoing |
| **BioID** | Yes | Browser face recognition | Offers web-based face recognition |
| **Aware** | Yes | Face+Document Capture SDK | Web capture SDK available |
| **OCR Studio** | Yes | WASM liveness | Browser-based liveness with WASM |
| **Amazon Rekognition** | React SDK | Face liveness component | Client capture, server verify |
| **Azure Face** | SDK | Passive liveness | Client capture, server verify |
| **Identy.io** | Mobile focus | Touchless biometrics | On-device; limited browser |

### 6.2 Open-Source Libraries
| Library | Type | Stars | Status | Best For |
|---|---|---|---|---|
| **MediaPipe** (Google) | Face/Hand/Pose | 29k+ | Active | Face detection, landmarks, liveness |
| **face-api.js** | Face recognition | 16k+ | Maintained fork | Detection, recognition, age/gender |
| **OpenCV.js** | Computer vision | - | Stable | Quality assessment, image processing |
| **BRFv5** | Face tracking | - | Stable | AR overlays, blink/smile detection |
| **pico.js** | Face detection | - | Stable | Ultra-lightweight detection (~200 lines) |
| **jeelizFaceFilter** | Face tracking | - | Stable | Real-time face filters, AR |
| **clmtrackr** | Face tracking | - | Legacy | Face swapping/masking |
| **SourceAFIS-Rust** | Fingerprint | - | Available | 1:N fingerprint (compilable to WASM) |
| **rustface** | Face detection | - | Available | Rust face detection (compilable to WASM) |

---

## 7. Rust-to-WASM Biometric Pipeline

Rust biometric libraries can compile to WASM via `wasm32-unknown-unknown`:

| Library | Capability | WASM Ready |
|---|---|---|
| **SourceAFIS-Rust** | Fingerprint recognition, 1:N search | Compilable |
| **rustface** | Face detection | Compilable |
| **image (Rust crate)** | Image processing | Yes |
| **ndarray** | Numerical computation | Yes |
| **robius-authentication** | Platform biometric abstraction | Partial |

**Performance**: Rust-compiled WASM achieves near-native speeds; suitable for image preprocessing, feature extraction, and matching algorithms.

---

## 8. Privacy & Security Considerations

### 8.1 Client-Side Advantages
- Biometric data never leaves user's device
- GDPR/privacy compliance simplified
- No biometric template storage on server (for detection/quality operations)
- Reduced attack surface for biometric data theft

### 8.2 Client-Side Risks
- JavaScript/WASM code is inspectable -> model theft, bypass attacks
- No tamper-proof execution environment in browser
- Liveness detection bypass possible without server verification
- Embedding extraction on client exposes biometric templates

### 8.3 Recommended Security Model
- **Client**: Detection, quality, UI guidance, preliminary liveness — non-secret operations
- **Server**: Embedding extraction, comparison, enrollment, verification — security-critical
- **Hybrid liveness**: Client captures challenge-response video -> server verifies
- **WebAuthn**: For fingerprint/voice authentication via platform authenticators

### 8.4 Regulatory Trends (2026)
- Gartner 2025: Decentralized (on-device) biometrics are best practice
- EU Digital Identity Wallet: W3C Digital Credentials API integration
- Privacy-preserving computation: Homomorphic encryption for biometric matching emerging

---

## 9. Recommended Architecture: Hybrid Client-Server Split

### Operations to Move to Browser (Client-Side)

| Operation | Technology Stack | Benefit |
|---|---|---|
| **Face Detection** | MediaPipe Face Detector (WASM) | Eliminates server round-trip; instant feedback |
| **468-Point Landmarks** | MediaPipe Face Landmarker (WASM) | Real-time face mesh; guides enrollment |
| **Image Quality Check** | OpenCV.js (WASM) | Instant quality feedback before upload |
| **Active Liveness (blink/smile)** | MediaPipe + BRFv5 | Interactive liveness prompts client-side |
| **Head Pose Estimation** | MediaPipe landmarks + math | Real-time pose feedback |
| **Gaze Tracking** | MediaPipe Face Mesh + solvePnP | Real-time gaze for proctoring UI |
| **Texture Deepfake Check** | OpenCV.js Laplacian + LBP | Preliminary spoof detection |
| **Frame Quality Filter** | OpenCV.js blur + brightness | Only send good frames to server |
| **Camera Guidance UI** | Compose Multiplatform / React | Face centering, distance, lighting guides |
| **Fingerprint Auth** | WebAuthn / FIDO2 Passkeys | Replace stub with platform biometrics |
| **Object Detection (proctor)** | ONNX Runtime Web + YOLOv8n | Phone/book detection client-side |

### Operations to Keep Server-Side

| Operation | Reason |
|---|---|
| **Embedding Extraction** | Security-critical; model IP protection |
| **1:1 Verification** | Requires stored embeddings |
| **1:N Search** | Requires database access |
| **Enrollment Storage** | Database write; audit trail |
| **Demographics (production)** | Accuracy requirements; model size |
| **Card Type Detection** | Custom YOLO model protection |
| **Liveness Verification** | Server must validate client claims |
| **Batch Operations** | Server-only by nature |
| **Proctoring Decisions** | Tamper-proof incident recording |

### Bandwidth & Latency Savings

Moving detection + quality + liveness to client:
- **Eliminates**: 3-5 server round-trips per enrollment attempt
- **Reduces upload**: Only quality-verified images sent to server
- **User experience**: Instant feedback (<100ms vs 300-800ms server round-trip)
- **Server load**: ~60% reduction in compute for face operations

---

## 10. Implementation Technology Recommendations

### Option A: React + MediaPipe + ONNX Runtime Web (Fastest to implement)
- Aligns with existing web-app (React on port 3000)
- MediaPipe WASM for face operations
- ONNX Runtime Web + WebGPU for model inference
- OpenCV.js for quality assessment
- **Pros**: Large ecosystem, existing integration path, battle-tested
- **Cons**: No cross-platform code sharing with mobile

### Option B: Compose Multiplatform (KMP/CMP) + JS Interop (Cross-platform)
- Compose UI compiled to WASM for biometric capture screens
- JS interop layer for MediaPipe/ONNX Runtime Web
- Shared Kotlin logic across Android, iOS, Desktop, Web
- **Pros**: Single codebase; 3x faster UI than JS; type-safe
- **Cons**: Beta maturity; JS interop overhead; smaller ecosystem

### Option C: Hybrid — React shell + KMP WASM modules (Pragmatic)
- Keep React app shell
- Add KMP WASM modules for shared biometric logic (validation, state, API client)
- Use MediaPipe/ONNX directly from React components
- **Pros**: Incremental adoption; best of both worlds
- **Cons**: Dual build system complexity

### Recommendation: **Option A** for near-term, with **Option C** migration path as CMP matures.

---

## 11. Emerging Standards to Watch

| Standard | Status | Impact | Timeline |
|---|---|---|---|
| **WebNN API** | Candidate Rec. | Hardware-accelerated ML in browser | Production 2027+ |
| **W3C Digital Credentials API** | Draft + shipping | Decentralized identity credentials | Standards 2026-2027 |
| **Verifiable Credentials 2.0** | W3C Rec. (May 2025) | Cryptographic credential proofs | Available now |
| **WebGPU Compute** | Production | GPU compute shaders for ML | Available now |
| **WASM Component Model** | Proposal | Cross-language WASM modules | 2026-2027 |
| **WASM GC** | Production | Managed language support (Kotlin, Dart) | Available now |
| **WebCodecs** | Production | Efficient video frame processing | Available now |

---

## 12. Summary of Key Findings

1. **60-70% of biometric UI operations can move to browser** — face detection, landmarks, quality, active liveness, gaze tracking, head pose

2. **Security-critical operations must stay server-side** — embedding extraction, verification, enrollment, 1:N search

3. **WebGPU is the game-changer** — all major browsers support GPU-accelerated ML inference as of Nov 2025

4. **MediaPipe Web is the recommended face processing stack** — production-ready, Google-maintained, WASM-based, 468 landmarks

5. **KMP/CMP WASM is promising but early** — excellent for cross-platform UI, but biometric algorithm bindings need manual wrapping

6. **WebAuthn can replace fingerprint/voice stubs** — platform authenticators provide real biometric auth without custom implementations

7. **Privacy trend favors client-side processing** — Gartner 2025 recommends decentralized biometrics; regulators pushing on-device processing

8. **Hybrid architecture is optimal** — client-side detection + quality + liveness UI; server-side matching + storage + verification

---

## Sources

- [WebGPU now supported by all major browsers (Nov 2025)](https://videocardz.com/newz/webgpu-is-now-supported-by-all-major-browsers)
- [Compose Multiplatform 1.9.0 - Web Goes Beta (Sept 2025)](https://blog.jetbrains.com/kotlin/2025/09/compose-multiplatform-1-9-0-compose-for-web-beta/)
- [KMP Roadmap Aug 2025](https://blog.jetbrains.com/kotlin/2025/08/kmp-roadmap-aug-2025/)
- [W3C Digital Credentials API Draft (May 2025)](https://idtechwire.com/w3c-releases-digital-credentials-api-draft/)
- [W3C Web Neural Network API](https://www.w3.org/TR/webnn/)
- [WebCodecs API - MDN](https://developer.mozilla.org/en-US/docs/Web/API/WebCodecs_API)
- [MediaPipe Face Detector for Web](https://developers.google.com/mediapipe/solutions/vision/face_detector/web_js)
- [ONNX Runtime Web](https://onnxruntime.ai/)
- [face-api.js](https://github.com/justadudewhohacks/face-api.js/)
- [Beyond Reality Face SDK (BRFv5)](https://github.com/Tastenkunst/brfv5-browser)
- [SourceAFIS-Rust](https://github.com/robertvazan/sourceafis-rust)
- [Verifiable Credentials 2.0 W3C Standard (May 2025)](https://www.biometricupdate.com/202505/verifiable-credentials-2-0-now-a-w3c-standard)
- [Gartner: Biometrics in 2026](https://www.biometricupdate.com/202601/biometrics-tapped-to-tame-the-internet-in-2026)
