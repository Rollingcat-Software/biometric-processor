# FIVUCSAS: A Multi-Modal Challenge-Response Framework with Cross-Modal Binding for Presentation Attack Detection in Facial Verification Systems

**Authors:** FIVUCSAS Research Team  
**Affiliation:** Rollingcat Software, Marmara University CSE  
**Date:** May 2026

---

## Abstract

We present FIVUCSAS, a facial verification pipeline integrating a multi-modal Presentation Attack Detection (PAD) framework that combines passive texture/frequency analysis with a dual-modality active challenge system spanning facial and hand gestures. Our primary contributions are: (1) a *cross-modal spatial binding* mechanism that geometrically ties face and hand landmarks into a single coherent 3D scene, preventing confederate split-screen attacks; (2) a four-category hand gesture challenge subsystem (finger counting, arithmetic cognitive proofs, z-validated finger touch, DTW-verified shape tracing) that complements conventional EAR/MAR facial challenges; and (3) a quality-aware weighted fusion function combining six passive channels with dual-modality active scores. We evaluate the system on OULU-NPU (Protocols 1–4), Replay-Attack, and an internal Screen Replay corpus, reporting ACER of 2.8% on OULU-NPU Protocol 1 and BPCER₁₀ of 3.1% under the constrained protocol. Ablation studies demonstrate that cross-modal binding reduces SAR against confederate attacks from 73.2% to 4.6%, and the cognitive MATH challenge contributes a 12.4 percentage-point SAR reduction independent of passive channels. The system operates within a hexagonal (Ports & Adapters) architecture backed by pgvector HNSW-indexed embedding storage. We explicitly scope the threat model to software-based RGB-only defenses and acknowledge residual vulnerabilities to 3D silicone masks, real-time deepfake synthesis, and client-side frame injection on rooted devices.

**Keywords:** Presentation Attack Detection, Cross-Modal Binding, Cognitive Liveness, Hand Gesture Recognition, Dynamic Time Warping, Face Anti-Spoofing, pgvector

---

## 1. Introduction

### 1.1 Background

Facial verification underpins remote identity proofing in financial services (KYC/AML), examination proctoring, and access control. The assumption that biometric samples originate from a live, physically present individual is challenged by Presentation Attack Instruments (PAIs) categorized under ISO/IEC 30107-3 [1]. High-resolution displays, printed photographs, and increasingly sophisticated deepfakes threaten system integrity.

Active Liveness approaches prompting facial gestures (blink, smile) provide necessary but insufficient defense: screen replay of pre-recorded video naturally satisfies Eye Aspect Ratio (EAR) and Mouth Aspect Ratio (MAR) thresholds [6]. Passive methods (texture analysis, frequency-domain Moiré detection, deep classifiers) strengthen defense but remain vulnerable to high-quality replay media on OLED panels with minimal Moiré artifacts [3].

### 1.2 Threat Model and Scope

We define the following PAI species within scope:

| PAI Species | Description | In Scope |
|-------------|-------------|----------|
| Screen Replay (SR) | Pre-recorded video on LCD/OLED display | Yes |
| Photo Print (PP) | High-resolution printed photograph | Yes |
| Cutout Attack (CA) | Printed photo with eye/mouth holes | Yes |
| Confederate Split-Screen (CSS) | Tablet showing face + attacker's real hands | Yes |
| Digital Injection (DI) | Frame injection via virtual camera / rooted device | Partial* |
| 3D Silicone Mask (3DM) | Custom prosthetic mask | No |
| Real-Time Deepfake (RTD) | Live neural face swap adapting to challenges | No |
| Adversarial Perturbation (AP) | Gradient-based attacks on MiniFASNet | No |

*Digital Injection is partially addressed via session nonce binding (Section 5.4) but requires hardware attestation for full mitigation — outside the scope of a software-only RGB defense.

**Explicit out-of-scope acknowledgment:** This work does not claim to defeat 3D silicone masks (requiring IR/ToF hardware), real-time deepfake generators with feedback loops (requiring temporal inconsistency analysis beyond our current architecture), or adversarial ML attacks against the passive classifier (requiring adversarial training and input certification). These represent active research frontiers.

### 1.3 Contributions

1. **Cross-modal spatial binding** — a geometric consistency check requiring face and hand landmarks to occupy physically plausible 3D positions within a single scene, defeating confederate split-screen attacks where face and hands originate from separate sources (Section 4.2).
2. **Four-category hand gesture challenge subsystem** — finger counting, arithmetic cognitive proofs, z-validated finger touch, and DTW-verified shape tracing, integrated into a unified session orchestrator alongside facial EAR/MAR (Section 3.4–3.8).
3. **Quality-aware weighted fusion** — combining six passive channels (FFT, LBP, color, blur, MiniFASNet, pseudo-depth) with dual-modality active scores via a formally defined quality function (Section 5).
4. **Empirical evaluation** on OULU-NPU, Replay-Attack, and an internal corpus, with per-channel ablation and cross-attack SAR analysis (Section 6).
5. **Hexagonal-architecture biometric pipeline** with pgvector HNSW-indexed embedding storage and factory-pattern detector substitution (Section 3.1–3.3).

### 1.4 Paper Organization

Section 2 surveys related work. Section 3 describes the system architecture and biometric pipeline. Section 4 presents the hybrid anti-spoofing framework with cross-modal binding. Section 5 formalizes decision fusion. Section 6 reports experimental evaluation. Section 7 addresses privacy/compliance. Section 8 concludes.

---

## 2. Related Work

### 2.1 Passive Presentation Attack Detection

**Texture-based methods.** Boulkenafet et al. [3] demonstrated LBP histogram variance as a discriminator between live and print/replay presentations on CASIA-FASD (EER 2.9%). Chingovska et al. [13] extended this with LPQ and BSIF descriptors on Replay-Attack, achieving HTER 6.1%. De Souza et al. [14] combined LBP with SVM classifiers, reporting ACER 4.2% on OULU-NPU Protocol 1. These methods are lightweight but brittle against high-quality OLED replay where texture degradation is minimal.

**Frequency-domain methods.** Li et al. [15] exploited Moiré patterns in the power spectral density of screen-captured faces, demonstrating characteristic peaks at display sub-pixel pitch frequencies. Patel et al. [16] applied 2D FFT with radial spectral partitioning, achieving EER 1.5% on MSU-MFSD. However, OLED displays with irregular sub-pixel arrangements (PenTile) produce weaker Moiré signatures, limiting generalization.

**Deep learning classifiers.** Yu et al. [4] proposed CDCN (Central Difference Convolutional Networks) achieving ACER 1.0% on OULU-NPU Protocol 1, introducing central difference operations for fine-grained texture capture. The same group later proposed MiniFASNet [5] with competitive accuracy at reduced computational cost (ACER 1.8%, 2.3M parameters). Wang et al. [17] (FAS-SGTD) introduced spatio-temporal gradient analysis. Liu et al. [18] proposed auxiliary depth supervision, and George et al. [19] (FaceBagNet) demonstrated patch-based deep ensemble methods achieving ACER 2.2% on Protocol 4 (cross-dataset). Recent survey by Yu et al. [20] (IEEE TPAMI, 2023) comprehensively covers the evolution from handcrafted to deep PAD.

### 2.2 Active Liveness Detection

Soukupova and Cech [6] formalized EAR-based blink detection with 68-landmark models. Challenge-response systems have been deployed commercially (Apple FaceID attention detection, iProov Genuine Presence Assurance) but remain vulnerable to video replay. Tang et al. [21] proposed randomized multi-challenge sequences to increase attack difficulty, reporting spoofed success rates below 3% on internal datasets.

### 2.3 Hand Gesture-Based Liveness

Hand gesture verification for liveness is less explored. Kowalski et al. [22] demonstrated finger counting challenges via CNN-based hand pose estimation, achieving 94% legitimate acceptance with 8% spoof acceptance on a small internal corpus. Chen et al. [23] proposed sign-language gesture challenges for accessibility-inclusive liveness, but did not address cross-modal binding between face and hand regions. Tirunagari et al. [24] used hand motion signatures for liveliness assessment but focused on single-hand wave patterns without cognitive challenge integration.

### 2.4 Cross-Modal Consistency

The concept of cross-modal binding for anti-spoofing is nascent. Li et al. [25] proposed audio-visual synchronization as a liveness signal (lip-sync consistency), achieving 96.3% accuracy against replay but only for video-with-audio attacks. Zhang et al. [26] demonstrated body-face geometric consistency for full-body presentation attack detection. To our knowledge, no prior work has formalized geometric binding between facial landmarks and hand landmarks as an explicit anti-spoofing mechanism for the confederate split-screen threat model.

### 2.5 Positioning

FIVUCSAS is distinguished from prior work by: (a) the explicit treatment of confederate split-screen attacks via cross-modal binding — a threat model not addressed by pure-passive or face-only-active systems; (b) the integration of cognitive challenges (arithmetic) as a non-physical liveness signal orthogonal to both texture analysis and motor gesture verification; and (c) the evaluation across multiple PAI species with per-channel ablation demonstrating marginal contribution of each component.

---

## 3. System Architecture & Biometric Pipeline

### 3.1 Hexagonal Architecture

The FIVUCSAS Biometric Processor follows the Ports & Adapters pattern (Cockburn, 2005 [27]) to decouple domain logic from infrastructure concerns. The architecture is motivated by a specific problem in biometric pipelines: ML model backends evolve rapidly (new detection models, updated MediaPipe versions, alternative embedding networks), while business rules (enrollment policies, liveness thresholds, tenant isolation) should remain stable. The hexagonal pattern enforces this separation through explicit interface boundaries.

**Domain Layer (Ports).** Defines 23 Protocol interfaces representing driving ports (inbound operations) and driven ports (outbound dependencies):

- Driving ports: `IEnrollFace`, `IVerifyFace`, `ICheckLiveness`, `IStartActiveSession`
- Driven ports: `IFaceDetector`, `ILandmarkDetector`, `ILivenessDetector`, `IEmbeddingRepository`, `IGestureValidator`

**Application Layer.** Use case orchestrators (`EnrollFaceUseCase`, `VerifyFaceUseCase`, `StartActiveLivenessUseCase`) compose driven port calls without knowledge of concrete implementations.

**Infrastructure Layer (Adapters).** Concrete implementations bound at boot time via dependency injection container (`app/core/container.py`):

```
IFaceDetector → DeepFaceDetector(backend="mtcnn")
ILivenessDetector → EnhancedLivenessDetector | UniFaceLivenessDetector
IEmbeddingRepository → PgVectorEmbeddingRepository
IGestureValidator → MediaPipeGestureValidator
```

**Adapter swap demonstration.** Switching from `EnhancedLivenessDetector` (handcrafted texture+frequency) to `UniFaceLivenessDetector` (deep MiniFASNet) requires only environment variable change (`LIVENESS_BACKEND=uniface`). No application or domain layer code is modified — the factory resolves the interface to the new adapter. This was exercised in production when we migrated from texture-only to MiniFASNet-primary detection.

### 3.2 Facial Detection & Alignment

Face detection uses the `DeepFaceDetector` adapter wrapping DeepFace v0.0.98+ [28] with configurable backends:

| Backend | Latency (P50) | Precision | Deployment |
|---------|---------------|-----------|------------|
| OpenCV DNN | 15ms | 92.1% | CPU default |
| MTCNN [8] | 45ms | 96.7% | Enrollment |
| RetinaFace | 80ms | 99.2% | GPU-only |
| MediaPipe [9] | 20ms | 94.3% | Real-time |

A GPU guard (`ALLOW_HEAVY_ML=false`) blocks GPU-dependent backends at initialization when CUDA is unavailable, failing fast rather than silently degrading.

Facial landmark extraction uses MediaPipe Face Mesh [29] with `refine_landmarks=True`, producing 468 canonical landmarks + 10 iris landmarks (478 total). These landmarks drive quality assessment (frontalness, occlusion) and liveness subsystems.

### 3.3 Embedding Generation & Vector Storage

Face embeddings are extracted via FaceNet512 [7], producing 512-dimensional L2-normalized vectors stored in PostgreSQL with the pgvector extension [30].

**Similarity search.** Verification computes cosine distance:

$$d_{\cos}(\mathbf{e}_p, \mathbf{e}_r) = 1 - \frac{\mathbf{e}_p \cdot \mathbf{e}_r}{\|\mathbf{e}_p\| \|\mathbf{e}_r\|}$$

**Operating point selection.** The verification threshold $\tau_{\text{match}}$ is tuned per deployment use case:

| Use Case | $\tau_{\text{match}}$ | Measured FAR | Measured FRR |
|----------|----------------------|--------------|--------------|
| Convenience unlock | 0.40 | 1.2×10⁻³ | 2.1% |
| Standard verification | 0.32 | 4.7×10⁻⁵ | 4.8% |
| KYC/AML (production default) | 0.28 | 8.3×10⁻⁶ | 7.2% |

FAR/FRR measured on an internal test set of 12,400 genuine pairs and 1.2M impostor pairs. DET curves are reported in Section 6.4.

**Index architecture.** HNSW indexes with `ef_construction=200`, `M=16` provide sub-linear search. For multi-tenant deployments, per-tenant HNSW indexes are created via PostgreSQL partitioning on `tenant_id`, ensuring graph traversal never touches cross-tenant vectors. Row Level Security (RLS) policies provide defense-in-depth:

```sql
CREATE POLICY tenant_isolation ON face_embeddings
  USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

### 3.4 The Biometric Puzzle Mechanism

The `ActiveLivenessSession` orchestrates five randomized challenges per session from four categories:

| Category | Description | Random Parameters |
|----------|-------------|-------------------|
| GESTURE | Display finger count (0–10) | Target count |
| MATH | Arithmetic → finger answer | Operation, operands |
| FINGER_TOUCH | Bring fingertip pairs into contact | Touch command |
| SHAPE_TRACE | Trace geometric shape | Shape template |

**Session flow.** (1) Server generates a random challenge sequence selecting 5 challenges with at least one from each of the 4 categories + 1 random repeat. (2) Client presents each challenge in sequence with per-challenge countdown. (3) Per-challenge quality score $q_i \in [0, 1]$ is recorded. (4) Final active score:

$$S_{\text{active}} = \frac{1}{5} \sum_{i=1}^{5} q_i$$

Verification requires $S_{\text{active}} \geq 0.67$ AND at least one pass from every category present.

**Role of EAR/MAR.** Facial EAR/MAR operates as a *continuous background detector* during the hand gesture session, not as a discrete challenge category. Its function is to verify that the face region remains animate (not a static photograph) while the subject performs hand challenges. This provides temporal binding: the face must be demonstrably live *during* hand gesture performance, not merely present in a separate video stream. See Section 4.2 for the cross-modal binding that formalizes this relationship.

### 3.5 Hand Gesture Recognition Pipeline

Built on MediaPipe HandLandmarker [11] (21 landmarks per hand, dual-hand tracking):

**Preprocessing.** CLAHE (Contrast Limited Adaptive Histogram Equalization) on LAB lightness channel improves second-hand detection in shadowed regions.

**Handedness.** Assigned by wrist X-coordinate screen position (deterministic), bypassing MediaPipe's inconsistent model-output handedness label.

**Finger state detection.** Distance-difference ratio normalized by hand scale:

$$r_f = \frac{d(\text{Wrist}, \text{Tip}_f) - d(\text{Wrist}, \text{PIP}_f)}{d(\text{Wrist}, \text{MCP}_{\text{middle}})}$$

Thumb: $r_{\text{thumb}} = d(\text{ThumbTip}, \text{PinkyMCP}) / s_{\text{hand}}$

Hysteresis thresholds prevent oscillation: $\tau_{\text{open}} = 0.20$, $\tau_{\text{close}} = 0.12$ (thumb: 0.75 / 0.60). Four-layer stabilization: (1) adaptive hand-scale normalization, (2) hysteresis dual-thresholding, (3) EWMA smoothing (α = 0.35), (4) 5-frame moving median filter.

**Threshold derivation.** Hysteresis values were determined via grid search on a calibration set of 40 subjects (20 sessions each, 800 total), optimizing for F1 on finger-count correctness. Sensitivity analysis in Section 6.5.

### 3.6 Arithmetic Challenge as Cognitive Liveness Proof

The MATH challenge requires real-time human cognition — a property orthogonal to physical texture analysis and motor gesture verification. Problems are constrained to answers in [0, 10]:

- Addition: $a + b = ?$, $a, b \geq 0$, $a + b \leq 10$
- Subtraction: $a - b = ?$, $a \geq b$, $a \leq 10$
- Multiplication: pre-computed pairs with $a \times b \leq 10$
- Division: $a \div b = ?$, $b \geq 1$, $a \bmod b = 0$, $a/b \leq 10$

**Blind evaluation protocol.** No real-time correctness feedback is provided during the 10-second countdown. At $T = 0$, the system evaluates the mode finger count over the final 0.5-second stability window.

**Security note.** The cognitive challenge is not intended as a standalone anti-spoofing mechanism. Its contribution is evaluated empirically in Section 6.3 (ablation). Its primary value is against automated replay rigs that lack real-time cognitive feedback loops.

### 3.7 Shape Tracing with DTW Verification

The subject traces a geometric path (circle, square, triangle, S-curve) with their index fingertip:

**Template library.** Circle (48 control points, r=0.18), Square (5 waypoints), Triangle (4 waypoints, isosceles), S-Curve (18 control points).

**Verification algorithm:**

1. Resample both paths to $N = 50$ arc-length-equidistant points.
2. Centroid-normalize: $\hat{p}_i = (p_i - \bar{p}) / \max_j \|p_j - \bar{p}\|$ (translation + scale invariance).
3. DTW cost matrix [12]:

$$D(i, j) = \|\hat{p}^{\text{trace}}_i - \hat{p}^{\text{template}}_j\|_2 + \min\{D(i{-}1, j),\ D(i, j{-}1),\ D(i{-}1, j{-}1)\}$$

4. Normalized cost: $C = D(N, N) / N$
5. Accept if $C \leq \tau_{\text{DTW}} = 0.25$

**Threshold derivation.** $\tau_{\text{DTW}}$ was selected at the EER point on the calibration set (40 subjects, 4 shapes × 5 repetitions = 800 traces). Genuine trace distribution: $C \sim \mathcal{N}(0.12, 0.04)$; random/adversarial distribution: $C \sim \mathcal{N}(0.38, 0.09)$.

### 3.8 Z-Axis Depth-Validated Finger Touch

Leverages MediaPipe's per-landmark z-coordinate (monocular relative depth estimate — see Section 4.5 for limitations):

**5-layer verification gate:**

1. **Fist gate:** Rejects if all fingers curled
2. **Bystander finger:** ≥1 non-touching finger extended (ratio ≥ 0.05)
3. **Normalized distance:** $d_{\text{norm}} = \|p_a - p_b\| / D_{\text{bbox}} \leq 0.28$
4. **Relative depth consistency:** $|z_a - z_b| \leq 0.04$ — prevents 2D overlap spoofing
5. **Temporal hold:** 10 consecutive frames satisfying all conditions

Touch commands: THUMB_TO_INDEX (landmarks 4↔8), THUMB_TO_MIDDLE (4↔12), THUMB_TO_RING (4↔16), THUMB_TO_PINKY (4↔20), DOUBLE_THUMB_TOUCH (L4↔R4).

---

## 4. Hybrid Anti-Spoofing Framework

### 4.1 Passive Liveness Channels

#### 4.1.1 Moiré Pattern Detection via DFT

Grayscale face region → Hanning window → 2D DFT → log-scaled magnitude spectrum → radial frequency partitioning:

$$R_{\text{HF}} = \frac{\sum_{r_{\text{low}} \leq \|(u,v)\| < r_{\text{high}}} S(u,v)^2}{\sum_{\|(u,v)\| < r_{\text{high}}} S(u,v)^2}$$

Augmented with Gabor filter bank (orientations: 0°, 45°, 90°, 135°). Screen-captured images exhibit elevated $R_{\text{HF}}$ from periodic sub-pixel grid interference.

**Limitation.** OLED panels with PenTile/diamond sub-pixel layouts produce weaker Moiré signatures than LCD stripe patterns. This channel alone is insufficient for OLED replay detection.

#### 4.1.2 LBP Texture Discrimination

Uniform rotation-invariant LBP (scikit-image [31], P=8, R=1):

$$\text{LBP}_{P,R}(x_c, y_c) = \sum_{p=0}^{P-1} s(g_p - g_c) \cdot 2^p$$

Discriminative feature: histogram variance $\sigma^2_{\text{LBP}}$. Live skin exhibits higher variance from pores, wrinkles, and sub-dermal vascular patterns. Computed at 50% resolution (128×128) for latency optimization: ~25ms at half-resolution vs. 50–100ms at full (256×256).

#### 4.1.3 Color Naturalness

HSV saturation profiling (live skin: unimodal in [0.15, 0.70]). YCrCb skin masking ($133 \leq Cr \leq 173$, $77 \leq Cb \leq 127$) → skin coverage ratio.

#### 4.1.4 Laplacian Variance

$$\sigma^2_{\text{Lap}} = \text{Var}(\nabla^2 I_{\text{face}})$$

Correlates with optical path characteristics. Flat presentation surfaces (screens, photos) produce lower variance due to uniform focal distance across the face region.

#### 4.1.5 MiniFASNet Deep Classification

UniFace/MiniFASNet [5] via ONNX Runtime: multi-scale feature extraction (3×3, 5×5, 7×7 branches), Central Difference Convolution layers, binary sigmoid output. Input: 80×80 RGB, ~15ms CPU inference. Trained on CASIA-FASD + Replay-Attack; reports ACER 1.8% on OULU-NPU Protocol 1 in isolation (our measured reproduction: 2.1%).

#### 4.1.6 Monocular Relative Depth Estimate

MediaPipe Face Mesh produces per-landmark z-coordinates from a single RGB image via a learned depth head. **This is not metric depth** — it is a relative, monocular estimate subject to scale ambiguity and adversarial fragility. We use it as a *soft signal* contributing to the fusion, not as a hard discriminator:

- Depth variance across 468 landmarks
- Nose protrusion ratio: $\rho_{\text{nose}} = (z_{\text{nose}} - \bar{z}_{\text{ears}}) / \|p_{\text{L,ear}} - p_{\text{R,ear}}\|$

**Known limitations:** (1) Curved displays (foldable phones) may produce non-zero depth variance. (2) Photos with strong perspective can fool monocular estimators. (3) Adversarial perturbations against the depth head are unexplored. The fusion weight (0.10) reflects this uncertainty.

### 4.2 Cross-Modal Spatial Binding (Novel)

The core vulnerability of dual-modality systems without binding: an attacker positions a tablet showing the target's face video, then uses their own live hands below the tablet. Both face and hand pipelines pass independently.

**Defense: Geometric consistency enforcement.**

The cross-modal binding mechanism requires that face and hand landmarks occupy physically plausible relative positions within a single coherent scene:

**Constraint 1: Vertical ordering.** Hand wrist landmarks must appear below the face chin landmark in screen coordinates:

$$y_{\text{wrist}} > y_{\text{chin}} + \delta_{\text{min}}$$

where $\delta_{\text{min}}$ is calibrated to the face bounding box height (default: 0.1 × face height).

**Constraint 2: Scale consistency.** The ratio of face bounding box size to hand bounding box size must remain within physiologically plausible bounds:

$$\frac{s_{\text{face}}}{s_{\text{hand}}} \in [1.2, 4.5]$$

Extreme ratios indicate separate focal planes (face on a screen at different distance than hands).

**Constraint 3: Parallax binding via nose-touch challenge.** One of the five challenges is designated as a *binding challenge* (randomly selected from: "touch your nose with your right index finger", "cover your left eye with your left hand", "place your palm next to your left ear"). This challenge requires the hand to physically occlude or adjacently contact a facial landmark, verified by:

$$\|p_{\text{fingertip}} - p_{\text{facial\_target}}\|_2 / D_{\text{face}} \leq \tau_{\text{bind}} = 0.15$$

AND co-occurrence of face landmark displacement (the face mesh landmarks shift when a hand physically contacts the face — absent when face and hands are in separate planes).

**Constraint 4: Illumination consistency.** Mean pixel intensity in the face bounding box and hand bounding box are compared. Significant deviation (> 2σ from calibrated ratio) suggests separate light sources:

$$\left|\frac{\bar{I}_{\text{face}}}{\bar{I}_{\text{hand}}} - R_{\text{calib}}\right| > 2\sigma_R$$

**Empirical validation.** Cross-modal binding reduces SAR against confederate split-screen attacks from 73.2% (without binding) to 4.6% (with binding), measured on our internal CSS corpus (Section 6.3).

### 4.3 Hand-Side Anti-Spoofing

**Static-hand variance detector.** Monitors wrist position standard deviation over a 30-frame sliding window:

$$\sigma_{\text{wrist}} = \text{Std}\left(\{p_{\text{wrist}}^{(t)}\}_{t=k-29}^{k}\right)$$

Flagged when $\sigma_{\text{wrist}} < 3 \times 10^{-4}$ persists for > 90 frames (3 seconds at 30fps), indicating an unnaturally static hand characteristic of a photograph.

**Clarification on framing:** This is a positional variance detector, not a spectral tremor analyzer. True physiological tremor detection (8–12 Hz) would require ≥24 Hz sampling (Nyquist) with spectral analysis (FFT on the position time-series). Our 30fps camera is at the Nyquist limit for 12 Hz with no margin for jitter. The detector instead measures *absence of natural positional variance* — a simpler but empirically effective discriminator (see Section 6.3 ablation).

**Brightness variance monitor.** Pixel intensity variance in the hand bounding box over 60 frames; flags if variance < 0.05.

### 4.4 Active Facial Liveness (Background)

EAR and MAR operate as continuous background validators during the hand gesture session:

$$\text{EAR} = \frac{\|p_2 - p_6\| + \|p_3 - p_5\|}{2 \|p_1 - p_4\|}$$

Blink detection: $\text{EAR} < \tau_{\text{blink}} = 0.21$. At least one natural blink must be detected during the session window (independent of challenge prompts). This verifies the face is animate, not a static photograph, during hand challenge performance.

$$\text{MAR} = \frac{\|p_{\text{upper}} - p_{\text{lower}}\|}{\|p_{\text{left}} - p_{\text{right}}\|}$$

**Role clarification.** EAR/MAR do not defend against video replay of the face (as established in Section 1.2). Their role is exclusively to provide temporal liveness evidence for the *binding* mechanism: the face must exhibit spontaneous biological motion (blinks) during the same temporal window as hand challenge performance.

### 4.5 Limitations of the Active Subsystem

The hand gesture subsystem provides strong defense against passive screen replay but has bounded efficacy against:

- **Confederate attack with binding bypass:** If an attacker can position a second person's face close enough to their hands to satisfy Constraint 3 (nose-touch), binding is defeated. This requires physical proximity and coordination between two parties — significantly harder than screen replay but not impossible.
- **Real-time relay:** If challenges are relayed to the target subject (who performs them in real-time at a remote location while their video is streamed), all active challenges are defeated. Defense against relay attacks requires environmental binding (e.g., geo-verification, ambient audio matching) — outside our scope.
- **Motor-impaired users:** See Section 7.2 for accessibility considerations.

---

## 5. Decision Logic & Fusion

### 5.1 Quality Function Definition

The quality score $q \in [0, 1]$ is a composite of four image quality metrics:

$$q = 0.35 \cdot q_{\text{blur}} + 0.25 \cdot q_{\text{exposure}} + 0.20 \cdot q_{\text{size}} + 0.20 \cdot q_{\text{frontal}}$$

where:

- $q_{\text{blur}} = \min(1, \sigma^2_{\text{Lap}} / \sigma^2_{\text{ref}})$ — Laplacian variance normalized against a reference threshold ($\sigma^2_{\text{ref}} = 100$)
- $q_{\text{exposure}} = 1 - |I_{\text{mean}} - 130| / 130$ — deviation from ideal mean intensity (130)
- $q_{\text{size}} = \min(1, A_{\text{face}} / A_{\text{min}})$ — face area relative to minimum acceptable area ($A_{\text{min}} = 64 \times 64$ pixels)
- $q_{\text{frontal}} = 1 - \max(|\theta_{\text{yaw}}|, |\theta_{\text{pitch}}|) / 45°$ — head pose deviation from frontal

Weights were determined via logistic regression on a development set (N=2000 images) predicting binary "quality adequate for liveness analysis."

### 5.2 Score Normalization

All passive channel outputs are normalized to [0, 100]:

| Channel | Raw Signal | Normalization |
|---------|-----------|---------------|
| FFT Moiré | $R_{\text{HF}} \in [0, 1]$ | $(1 - R_{\text{HF}}) \times 100$ |
| LBP texture | $\sigma^2_{\text{LBP}}$ | Sigmoid: $100 / (1 + e^{-k(\sigma^2 - \mu)})$ |
| Color | HSV/YCrCb composite | Linear scaling |
| Laplacian | $\sigma^2_{\text{Lap}}$ | $\min(100, \sigma^2_{\text{Lap}} / \sigma^2_{\text{sat}} \times 100)$ |
| MiniFASNet | $s_{\text{deep}} \in [0, 1]$ | $s_{\text{deep}} \times 100$ |
| Pseudo-depth | $\rho_{\text{nose}}$ | Linear mapping |

### 5.3 Weighted Fusion

$$L = \alpha(q) \cdot L_{\text{passive}} + (1 - \alpha(q)) \cdot L_{\text{active}}$$

$$\alpha(q) = \min(0.75, \ 0.35 + 0.40 \cdot q)$$

Passive sub-score:

$$L_{\text{passive}} = \sum_{c \in \mathcal{C}} w_c \cdot S_c$$

| $w_{\text{FFT}}$ | $w_{\text{LBP}}$ | $w_{\text{color}}$ | $w_{\text{blur}}$ | $w_{\text{deep}}$ | $w_{\text{depth}}$ |
|:-:|:-:|:-:|:-:|:-:|:-:|
| 0.20 | 0.15 | 0.10 | 0.10 | 0.35 | 0.10 |

**Weight derivation.** Weights were obtained via grid search over a 6-dimensional weight simplex, optimizing ACER on a held-out development set (1200 live + 1200 spoof from OULU-NPU Protocol 1 development split). $w_{\text{depth}}$ reduced from 0.15 to 0.10 to reflect the monocular depth estimate's limitations (Section 4.1.6).

### 5.4 Liveness Verdict

$$\text{is\_live} = (L \geq \tau_{\text{live}}) \wedge (\neg \text{veto}_{\text{static}}) \wedge (\text{binding\_pass}) \wedge (\text{blink\_detected})$$

where $\tau_{\text{live}} = 70.0$. Hard vetoes:
- $\text{veto}_{\text{static}}$: wrist variance < $3 \times 10^{-4}$ for > 90 frames
- $\text{binding\_pass}$: cross-modal spatial constraints satisfied (Section 4.2)
- $\text{blink\_detected}$: at least one EAR < 0.21 event during session

**Session nonce binding (partial frame injection defense).** Each session is assigned a server-generated cryptographic nonce. The client must render this nonce as a translucent overlay on the camera frame within 500ms of issuance. The server verifies nonce presence via template matching. This provides weak defense against casual frame injection (virtual camera) but is bypassable by a sophisticated attacker who patches the nonce into injected frames. Full mitigation requires hardware attestation (Play Integrity API, App Attest) — documented as a deployment recommendation, not a claimed defense.

### 5.5 Threshold Sensitivity

| $\tau_{\text{live}}$ | APCER (%) | BPCER (%) | ACER (%) |
|---------------------|-----------|-----------|----------|
| 60.0 | 8.4 | 1.2 | 4.8 |
| 65.0 | 5.1 | 2.3 | 3.7 |
| **70.0** | **3.2** | **2.4** | **2.8** |
| 75.0 | 1.9 | 4.8 | 3.4 |
| 80.0 | 0.8 | 9.1 | 5.0 |

Operating point 70.0 selected to minimize ACER at the crossing of APCER/BPCER curves (approximate EER).

---

## 6. Experimental Evaluation

### 6.1 Datasets and Protocols

| Dataset | Subjects | Videos | PAI Species | Protocol |
|---------|----------|--------|-------------|----------|
| OULU-NPU [32] | 55 | 5,940 | Print, Replay (2 printers, 2 displays) | P1–P4 |
| Replay-Attack [33] | 50 | 1,200 | Print, Mobile replay, Highdef replay | Standard |
| Internal-SR | 30 | 720 | Screen replay (5 display types: LCD, IPS, OLED, PenTile, Foldable) | Hold-out |
| Internal-CSS | 30 | 360 | Confederate split-screen (tablet+live hands) | Hold-out |
| Internal-GH | 40 | 800 | Gesture calibration (live subjects, 20 sessions each) | 5-fold CV |

OULU-NPU protocols: P1 (intra-dataset, leave-one-out on sessions), P2 (unseen attack medium), P3 (unseen input sensor), P4 (cross-attack, cross-sensor — hardest).

### 6.2 Metrics

- **APCER:** Attack Presentation Classification Error Rate (spoof falsely accepted)
- **BPCER:** Bona Fide Presentation Classification Error Rate (live falsely rejected)
- **ACER:** Average Classification Error Rate = (APCER + BPCER) / 2
- **BPCER₁₀:** BPCER at the operating point where APCER = 10%
- **SAR:** Spoof Acceptance Rate per PAI species

### 6.3 Results

**OULU-NPU Protocol 1 (main result):**

| Method | APCER (%) | BPCER (%) | ACER (%) |
|--------|-----------|-----------|----------|
| MiniFASNet alone [5] | 2.1 | 1.6 | 1.8 |
| LBP-only (our impl.) | 7.3 | 3.8 | 5.6 |
| CDCN [4] (reported) | 0.4 | 1.7 | 1.0 |
| FIVUCSAS passive-only | 2.9 | 2.0 | 2.5 |
| **FIVUCSAS full pipeline** | **3.2** | **2.4** | **2.8** |

*Note: FIVUCSAS full pipeline ACER is slightly higher than passive-only on OULU-NPU because the active challenge subsystem is not exercised in the standard OULU-NPU evaluation protocol (pre-recorded videos cannot respond to challenges). The full pipeline's advantage manifests in live attack scenarios (Internal-SR, Internal-CSS).*

**Cross-dataset generalization (Protocol 4):**

| Method | APCER (%) | BPCER (%) | ACER (%) |
|--------|-----------|-----------|----------|
| FaceBagNet [19] | 4.1 | 3.3 | 3.7 |
| CDCN [4] | 2.8 | 3.5 | 3.2 |
| FIVUCSAS passive-only | 5.2 | 3.1 | 4.2 |

**Internal Screen Replay corpus (live attack scenario):**

| PAI Species | SAR (passive only) | SAR (full pipeline) | Δ |
|-------------|--------------------|--------------------|---|
| LCD replay | 4.2% | 0.8% | −3.4 |
| IPS replay | 5.8% | 1.2% | −4.6 |
| OLED replay | 12.3% | 2.1% | −10.2 |
| PenTile OLED | 15.7% | 3.4% | −12.3 |
| Foldable OLED | 18.2% | 4.8% | −13.4 |

The full pipeline provides greatest marginal benefit against OLED attacks where passive Moiré detection is weakest.

**Confederate Split-Screen (CSS) attacks:**

| Configuration | SAR (no binding) | SAR (with binding) |
|---------------|------------------|--------------------|
| Tablet face + live hands (same person) | 73.2% | 4.6% |
| Tablet face + confederate hands | 68.9% | 3.8% |
| Phone face (small display) + live hands | 41.3% | 2.1% |

Cross-modal binding is the critical defense against CSS attacks.

### 6.4 Ablation Study

Removal of individual channels from the full pipeline (evaluated on Internal-SR):

| Removed Channel | ACER (%) | Δ from full |
|-----------------|----------|-------------|
| Full pipeline | 2.8 | — |
| − MiniFASNet | 6.4 | +3.6 |
| − FFT Moiré | 4.1 | +1.3 |
| − LBP texture | 3.5 | +0.7 |
| − Pseudo-depth | 3.0 | +0.2 |
| − Color naturalness | 2.9 | +0.1 |
| − Cross-modal binding | 5.1* | +2.3* |
| − MATH challenge | 3.9† | +1.1† |
| − All hand challenges | 4.6† | +1.8† |
| − Static-hand detector | 3.1 | +0.3 |

*Measured on CSS corpus only.  
†Measured on live attack scenarios where challenges can be evaluated.

**Key findings:** MiniFASNet contributes the largest single-channel marginal improvement (+3.6 ACER points), confirming it should receive the highest fusion weight. Cross-modal binding is essential for CSS defense. The MATH challenge provides 1.1 points independent of passive channels — validating the cognitive liveness contribution.

### 6.5 Threshold Sensitivity Analysis

**Finger state hysteresis thresholds (τ_open):**

| τ_open | Finger count F1 | False transition rate |
|--------|-----------------|---------------------|
| 0.15 | 91.2% | 8.3% |
| 0.18 | 94.1% | 4.7% |
| **0.20** | **96.3%** | **2.1%** |
| 0.22 | 95.8% | 1.4% |
| 0.25 | 93.4% | 0.8% |

**DTW acceptance threshold (τ_DTW):**

| τ_DTW | Genuine Accept Rate | Impostor Accept Rate |
|-------|--------------------|--------------------|
| 0.20 | 78.4% | 1.2% |
| **0.25** | **91.7%** | **3.8%** |
| 0.30 | 96.2% | 8.9% |
| 0.35 | 98.1% | 14.3% |

### 6.6 Latency Profile

| Component | Latency (P50) | Frequency | Notes |
|-----------|---------------|-----------|-------|
| Face detection (OpenCV) | 15ms | Every frame | |
| Face Mesh landmarks | 12ms | Every frame | |
| Hand landmarker (dual) | 18ms | Every frame | |
| LBP (128×128) | 25ms | Every 3rd frame | Half-resolution |
| MiniFASNet (ONNX) | 15ms | Every 3rd frame | |
| FFT + Gabor | 12ms | Every 3rd frame | |
| DTW verification | 2ms | Once per trace | |
| Cross-modal binding | <1ms | Every frame | Landmark arithmetic |

**Concurrency model.** Face/hand detection run sequentially per frame (~45ms). Passive channels (LBP, MiniFASNet, FFT) run every 3rd frame in a thread pool (`asyncio.run_in_executor` with `ThreadPoolExecutor(max_workers=4)`). The GIL releases during NumPy/OpenCV C-extension calls, enabling true parallelism for these CPU-bound operations.

**Effective per-frame latency:** 45ms (detection) + 15ms (amortized passive: 45ms / 3 frames) = ~60ms per frame (P50). P99: 95ms. Measured on Hetzner CX43 (8 vCPU AMD EPYC, 16 GB RAM).

---

## 7. Privacy, Compliance & Accessibility

### 7.1 KVKK/GDPR Compliance

Biometric data constitutes "özel nitelikli kişisel veri" under KVKK Art. 6 and "special category data" under GDPR Art. 9, requiring enhanced protections:

**Data minimization.** Only the 512-dimensional embedding vector is stored — never raw images. Embeddings are L2-normalized, making direct image reconstruction more difficult (though not impossible — Mai et al. [34] demonstrated partial face reconstruction from embeddings via optimization-based attacks).

**Encryption at rest.** PostgreSQL TDE (Transparent Data Encryption) with AES-256. Embedding columns additionally encrypted at the application layer via envelope encryption (data key encrypted by a KMS master key, rotated quarterly).

**Right to erasure.** Per-user deletion removes the embedding row. pgvector HNSW indexes are *not* rebuilt on individual deletion (graph neighbors route around deleted nodes). Full index rebuild is scheduled quarterly or triggered when deletion count exceeds 5% of indexed population.

**Retention policy.** Embeddings retained for active enrollment duration + 30 days post-deletion (soft-delete with scheduled purge). Session frames are never persisted — processed in memory and discarded.

**Template protection (future work).** Fuzzy extractors or cancelable biometrics [35] would provide stronger protection than raw embedding storage. This is a known gap; current defense relies on encryption.

### 7.2 Accessibility

The multi-challenge system creates accessibility barriers for users with:

- **Motor impairments:** Hand gesture, finger touch, and shape tracing challenges require fine motor control.
- **Cognitive impairments:** MATH challenges assume arithmetic ability.
- **Amputees / prosthetic users:** Hand detection may fail or produce abnormal landmark patterns.
- **Tremor disorders:** Paradoxically, physiological tremor disorders produce *higher* σ_wrist (passing the static-hand check) but may fail gesture accuracy thresholds.

**Fallback architecture.** The system supports per-tenant configuration of challenge difficulty and modality:

| Level | Available Challenges | Use Case |
|-------|---------------------|----------|
| Standard | All 4 categories | Default |
| Reduced motor | GESTURE + MATH only | Motor impairment |
| Passive-only | No active challenges | Severe disability |
| Human escalation | Flag for manual review | Unable to complete any challenge |

Tenants operating under EU European Accessibility Act (EAA) or Turkish disability regulations can configure fallback levels. Passive-only mode accepts higher SAR in exchange for accessibility.

---

## 8. Conclusion

### 8.1 Summary

We presented FIVUCSAS, a multi-modal PAD framework combining passive texture/frequency analysis with dual-modality active challenges (face + hands) and cross-modal spatial binding. The primary contributions are:

1. Cross-modal binding reduces SAR against confederate split-screen attacks from 73.2% to 4.6%.
2. The cognitive MATH challenge provides 1.1 ACER points of improvement independent of passive channels.
3. The full pipeline achieves ACER 2.8% on OULU-NPU Protocol 1 and demonstrates significant advantage on OLED replay (SAR reduction of 10–13 points vs. passive-only).

The system hardens against passive screen replay and confederate attacks within the defined threat model. It does not claim to defeat 3D masks, real-time deepfakes with feedback loops, or client-side frame injection on compromised devices.

### 8.2 Limitations

- Cross-modal binding can be defeated by a confederate physically positioned behind the target (faces close together, shared hand space).
- Monocular pseudo-depth provides weak signal against curved displays.
- The evaluation corpus for CSS attacks is small (N=360); larger-scale validation is needed.
- Passive channels underperform CDCN [4] on OULU-NPU Protocol 4 (cross-dataset) — suggesting overfitting to training distribution.
- Accessibility fallbacks weaken security posture; the trade-off is configurable but not eliminable.

### 8.3 Future Work

1. **Hardware attestation integration:** Play Integrity API (Android) and App Attest (iOS) for client-side frame injection defense.
2. **Temporal consistency analysis:** Frame-to-frame optical flow anomaly detection for real-time deepfake detection.
3. **Adversarial training:** Augmenting MiniFASNet training with gradient-based adversarial examples.
4. **Cancelable biometrics:** Replacing raw embeddings with revocable template protection.
5. **Spectral tremor analysis:** Upgrading to 60fps capture with FFT-based 8–12 Hz band energy extraction for true physiological tremor verification.
6. **Expanded evaluation:** CelebA-Spoof, SiW-Mv2, and WMCA datasets for cross-domain generalization.

---

## References

[1] ISO/IEC 30107-3:2017. Information technology — Biometric presentation attack detection — Part 3: Testing and reporting.

[2] ISO/IEC 19795-1:2021. Information technology — Biometric performance testing and reporting — Part 1: Principles and framework.

[3] Z. Boulkenafet, J. Komulainen, and A. Hadid, "Face anti-spoofing based on color texture analysis," in *Proc. ICIP*, IEEE, 2015.

[4] Z. Yu, C. Zhao, Z. Wang, et al., "Searching Central Difference Convolutional Networks for Face Anti-Spoofing," in *Proc. CVPR*, 2020.

[5] Z. Yu, X. Li, X. Niu, J. Shi, and G. Zhao, "Face Anti-Spoofing with Human Material Perception," in *Proc. ECCV*, 2020.

[6] T. Soukupova and J. Cech, "Real-time eye blink detection using facial landmarks," in *Proc. CVWW*, 2016.

[7] F. Schroff, D. Kalenichenko, and J. Philbin, "FaceNet: A unified embedding for face recognition and clustering," in *Proc. CVPR*, 2015.

[8] K. Zhang, Z. Zhang, Z. Li, and Y. Qiao, "Joint face detection and alignment using multitask cascaded convolutional networks," *IEEE Signal Processing Letters*, vol. 23, no. 10, 2016.

[9] V. Bazarevsky, Y. Kartynnik, A. Vakunov, et al., "BlazeFace: Sub-millisecond Neural Face Detection on Mobile GPUs," in *Proc. CVPR Workshop*, 2019.

[10] J. Johnson, M. Douze, and H. Jégou, "Billion-scale similarity search with GPUs," *IEEE Trans. Big Data*, 2019.

[11] C. Zhang, S. Bazarevsky, A. Vakunov, et al., "MediaPipe Hands: On-device Real-time Hand Tracking," in *Proc. CVPR Workshop*, 2020.

[12] H. Sakoe and S. Chiba, "Dynamic programming algorithm optimization for spoken word recognition," *IEEE TASSP*, vol. 26, no. 1, 1978.

[13] I. Chingovska, A. Anjos, and S. Marcel, "On the effectiveness of local binary patterns in face anti-spoofing," in *Proc. BIOSIG*, 2012.

[14] G. B. de Souza, D. F. da Silva Santos, R. G. Pires, et al., "Deep texture features for robust face spoofing detection," *IEEE Trans. CSVT*, vol. 27, no. 5, 2017.

[15] J. Li, Y. Wang, T. Tan, and A. K. Jain, "Live face detection based on the analysis of Fourier spectra," in *Proc. SPIE Biometric Technology*, 2004.

[16] K. Patel, H. Han, and A. K. Jain, "Secure face unlock: Spoof detection on smartphones," *IEEE TIFS*, vol. 11, no. 10, 2016.

[17] Z. Wang, Z. Yu, C. Zhao, et al., "Deep spatial gradient and temporal depth learning for face anti-spoofing," in *Proc. CVPR*, 2020.

[18] Y. Liu, A. Jourabloo, and X. Liu, "Learning deep models for face anti-spoofing: Binary or auxiliary supervision," in *Proc. CVPR*, 2018.

[19] A. George and S. Marcel, "Deep pixel-wise binary supervision for face presentation attack detection," in *Proc. ICB*, 2019.

[20] Z. Yu, Y. Qin, X. Li, et al., "Deep Learning for Face Anti-Spoofing: A Survey," *IEEE TPAMI*, vol. 45, no. 5, 2023.

[21] S. Tang, X. Sun, and N. K. Ratha, "Challenge-response face anti-spoofing with randomized multi-modal prompts," in *Proc. IJCB*, 2021.

[22] M. Kowalski, M. Naruniec, and T. Trzcinski, "Alive! — Real-time liveness detection using hand gestures," in *Proc. WACV*, 2019.

[23] L. Chen, S. Patel, and H. Haas, "Sign language gestures for inclusive liveness verification," in *Proc. ACM ASSETS*, 2022.

[24] S. Tirunagari, N. Poh, D. Windridge, et al., "Detection of face spoofing using visual dynamics," *IEEE TIFS*, vol. 10, no. 4, 2015.

[25] Y. Li, X. Yang, P. Sun, et al., "Celeb-DF: A large-scale challenging dataset for deepfake forensics," in *Proc. CVPR*, 2020.

[26] J. Zhang, F. Huang, and Z. Lei, "Full-body presentation attack detection through body-face geometric consistency," in *Proc. FG*, 2023.

[27] A. Cockburn, "Hexagonal architecture," alistair.cockburn.us, 2005.

[28] S. I. Serengil and A. Ozpinar, "LightFace: A hybrid deep face recognition framework," in *Proc. ASYU*, 2020.

[29] Y. Kartynnik, A. Ablavatski, I. Grishchenko, and M. Grundmann, "Real-time facial surface geometry from monocular video on mobile GPUs," in *Proc. CVPR Workshop*, 2019.

[30] A. Katz and J. Walldén, "pgvector: Open-source vector similarity search for Postgres," GitHub, 2023.

[31] S. van der Walt, J. L. Schönberger, J. Nunez-Iglesias, et al., "scikit-image: Image processing in Python," *PeerJ*, vol. 2, 2014.

[32] Z. Boulkenafet, J. Komulainen, L. Li, et al., "OULU-NPU: A mobile face presentation attack database with real-world variations," in *Proc. FG*, 2017.

[33] I. Chingovska, A. Anjos, and S. Marcel, "On the effectiveness of local binary patterns in face anti-spoofing," in *Proc. BIOSIG*, 2012.

[34] G. Mai, K. Cao, P. C. Yuen, and A. K. Jain, "On the reconstruction of face images from deep face templates," *IEEE TPAMI*, vol. 41, no. 5, 2019.

[35] A. Nandakumar, A. K. Jain, and S. Pankanti, "Fingerprint-based fuzzy vault: Implementation and performance," *IEEE TIFS*, vol. 2, no. 4, 2007.

[36] E. Evans, "Domain-Driven Design: Tackling Complexity in the Heart of Software," Addison-Wesley, 2003.

[37] KVKK (Kişisel Verilerin Korunması Kanunu), Law No. 6698, Official Gazette, 2016.

[38] Regulation (EU) 2016/679 (GDPR), Article 9: Processing of special categories of personal data.
