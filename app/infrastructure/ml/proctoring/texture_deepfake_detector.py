"""Texture-based deepfake detector for proctoring.

Detects synthetic/manipulated faces using multiple analysis techniques:
- Frequency domain analysis (FFT)
- Texture consistency analysis
- Color channel analysis
- Temporal coherence (for video streams)
- Facial boundary artifacts
"""

import logging
from collections import deque
from datetime import datetime
from typing import Deque, Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.domain.entities.proctor_analysis import DeepfakeAnalysisResult
from app.domain.interfaces.deepfake_detector import IDeepfakeDetector

logger = logging.getLogger(__name__)

# Thresholds for deepfake detection
DEFAULT_THRESHOLDS = {
    "frequency_anomaly": 0.4,
    "texture_consistency": 0.35,
    "color_channel": 0.3,
    "boundary_artifact": 0.5,
    "temporal_coherence": 0.4,
}


class TextureDeepfakeDetector(IDeepfakeDetector):
    """Deepfake detector using texture and frequency analysis.

    Uses multiple heuristics to detect synthetic faces:
    1. Frequency analysis - GAN artifacts in frequency domain
    2. Texture consistency - Unnatural skin texture patterns
    3. Color channel analysis - Channel correlation anomalies
    4. Boundary artifacts - Blending artifacts around face edges
    5. Temporal coherence - Inconsistency across frames
    """

    def __init__(
        self,
        deepfake_threshold: float = 0.6,
        temporal_window: int = 10,
        thresholds: Optional[Dict[str, float]] = None,
    ) -> None:
        """Initialize deepfake detector.

        Args:
            deepfake_threshold: Overall threshold for deepfake classification
            temporal_window: Number of frames to analyze for temporal coherence
            thresholds: Custom thresholds for individual detectors
        """
        self._deepfake_threshold = deepfake_threshold
        self._temporal_window = temporal_window
        self._thresholds = thresholds or DEFAULT_THRESHOLDS.copy()

        # Frame history for temporal analysis
        self._frame_history: Deque[np.ndarray] = deque(maxlen=temporal_window)
        self._feature_history: Deque[Dict] = deque(maxlen=temporal_window)

        logger.info(
            f"TextureDeepfakeDetector initialized: "
            f"threshold={deepfake_threshold}, temporal_window={temporal_window}"
        )

    async def detect(
        self,
        image: np.ndarray,
        session_id,
    ) -> DeepfakeAnalysisResult:
        """Detect deepfake in single frame.

        Args:
            image: BGR image array (should contain face)
            session_id: Session being analyzed

        Returns:
            DeepfakeAnalysisResult with detection results
        """
        timestamp = datetime.utcnow()
        artifacts_found: List[str] = []

        # Run all detection methods
        freq_score, freq_artifacts = self._analyze_frequency_domain(image)
        texture_score, texture_artifacts = self._analyze_texture_consistency(image)
        color_score, color_artifacts = self._analyze_color_channels(image)
        boundary_score, boundary_artifacts = self._analyze_boundary_artifacts(image)

        # Collect artifacts
        artifacts_found.extend(freq_artifacts)
        artifacts_found.extend(texture_artifacts)
        artifacts_found.extend(color_artifacts)
        artifacts_found.extend(boundary_artifacts)

        # Temporal analysis if we have history
        temporal_score = 0.0
        if len(self._frame_history) >= 3:
            temporal_score, temporal_artifacts = self._analyze_temporal_coherence(image)
            artifacts_found.extend(temporal_artifacts)

        # Update history
        self._frame_history.append(image.copy())
        self._feature_history.append({
            "freq": freq_score,
            "texture": texture_score,
            "color": color_score,
            "boundary": boundary_score,
        })

        # Calculate ensemble score
        weights = {
            "frequency": 0.25,
            "texture": 0.25,
            "color": 0.20,
            "boundary": 0.15,
            "temporal": 0.15,
        }

        # Anomaly scores (higher = more likely deepfake)
        ensemble_score = (
            freq_score * weights["frequency"]
            + texture_score * weights["texture"]
            + color_score * weights["color"]
            + boundary_score * weights["boundary"]
            + temporal_score * weights["temporal"]
        )

        is_deepfake = ensemble_score >= self._deepfake_threshold
        confidence = abs(ensemble_score - 0.5) * 2  # Scale to 0-1

        detection_method = "ensemble"
        if is_deepfake:
            # Determine primary detection method
            scores = {
                "frequency": freq_score,
                "texture": texture_score,
                "color": color_score,
                "boundary": boundary_score,
                "temporal": temporal_score,
            }
            detection_method = max(scores, key=scores.get)

        logger.debug(
            f"Deepfake detection: is_deepfake={is_deepfake}, "
            f"score={ensemble_score:.3f}, confidence={confidence:.3f}, "
            f"method={detection_method}"
        )

        return DeepfakeAnalysisResult(
            session_id=session_id,
            timestamp=timestamp,
            is_deepfake=is_deepfake,
            confidence=round(confidence, 3),
            detection_method=detection_method,
            artifacts_found=artifacts_found[:5],  # Limit artifacts
        )

    async def detect_video(
        self,
        frames: List[np.ndarray],
        session_id,
    ) -> DeepfakeAnalysisResult:
        """Detect deepfake in video sequence.

        Args:
            frames: List of BGR image arrays
            session_id: Session being analyzed

        Returns:
            Aggregated DeepfakeAnalysisResult
        """
        if not frames:
            return DeepfakeAnalysisResult(
                session_id=session_id,
                timestamp=datetime.utcnow(),
                is_deepfake=False,
                confidence=0.0,
                detection_method="none",
                artifacts_found=[],
            )

        # Analyze each frame
        results = []
        for frame in frames:
            result = await self.detect(frame, session_id)
            results.append(result)

        # Aggregate results
        avg_confidence = np.mean([r.confidence for r in results])
        deepfake_ratio = sum(1 for r in results if r.is_deepfake) / len(results)

        is_deepfake = deepfake_ratio >= 0.5
        all_artifacts = []
        for r in results:
            all_artifacts.extend(r.artifacts_found)

        # Get unique artifacts
        unique_artifacts = list(set(all_artifacts))[:5]

        return DeepfakeAnalysisResult(
            session_id=session_id,
            timestamp=datetime.utcnow(),
            is_deepfake=is_deepfake,
            confidence=round(float(avg_confidence), 3),
            detection_method="temporal" if len(frames) > 1 else "ensemble",
            artifacts_found=unique_artifacts,
        )

    def get_detection_methods(self) -> List[str]:
        """Get available detection methods.

        Returns:
            List of detection method names
        """
        return [
            "frequency",
            "texture",
            "color",
            "boundary",
            "temporal",
            "ensemble",
        ]

    def is_available(self) -> bool:
        """Check if deepfake detector is available."""
        return True  # Uses OpenCV which is always available

    def _analyze_frequency_domain(
        self,
        image: np.ndarray,
    ) -> Tuple[float, List[str]]:
        """Analyze frequency domain for GAN artifacts.

        GANs often produce specific frequency patterns that differ
        from natural images.
        """
        artifacts = []
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # FFT analysis
        f_transform = np.fft.fft2(gray)
        f_shift = np.fft.fftshift(f_transform)
        magnitude = np.abs(f_shift)

        # Log magnitude spectrum
        log_magnitude = np.log1p(magnitude)

        # Analyze radial frequency distribution
        rows, cols = gray.shape
        center = (rows // 2, cols // 2)

        # Create radial bins
        y, x = np.ogrid[:rows, :cols]
        r = np.sqrt((x - center[1]) ** 2 + (y - center[0]) ** 2)

        # Analyze high-frequency content
        high_freq_mask = (r > min(rows, cols) // 4)
        high_freq_energy = np.mean(log_magnitude[high_freq_mask])

        # Analyze mid-frequency content
        mid_freq_mask = (r > min(rows, cols) // 8) & (r <= min(rows, cols) // 4)
        mid_freq_energy = np.mean(log_magnitude[mid_freq_mask])

        # GAN artifacts often show unusual high-frequency patterns
        freq_ratio = high_freq_energy / (mid_freq_energy + 1e-6)

        # Check for periodic artifacts (grid patterns)
        periodic_score = self._detect_periodic_artifacts(magnitude, center)

        # Combined anomaly score
        anomaly_score = 0.0

        if freq_ratio > 0.8:  # Unusually high HF content
            anomaly_score += 0.3
            artifacts.append("high_frequency_anomaly")

        if periodic_score > self._thresholds["frequency_anomaly"]:
            anomaly_score += 0.4
            artifacts.append("periodic_pattern")

        # Check for spectral gaps (common in GANs)
        if self._has_spectral_gaps(log_magnitude):
            anomaly_score += 0.3
            artifacts.append("spectral_gaps")

        return min(1.0, anomaly_score), artifacts

    def _detect_periodic_artifacts(
        self,
        magnitude: np.ndarray,
        center: Tuple[int, int],
    ) -> float:
        """Detect periodic patterns in frequency domain."""
        rows, cols = magnitude.shape

        # Look for peaks away from center
        # Exclude central region
        mask = np.ones_like(magnitude, dtype=bool)
        cy, cx = center
        mask[cy - rows // 8:cy + rows // 8, cx - cols // 8:cx + cols // 8] = False

        masked_mag = magnitude * mask

        # Find peaks
        threshold = np.percentile(masked_mag[mask], 99)
        peaks = masked_mag > threshold

        # Count significant peaks (periodic artifacts show multiple peaks)
        num_peaks = np.sum(peaks)

        # Normalize by image size
        peak_density = num_peaks / (rows * cols)

        # Higher density = more likely periodic artifact
        return min(1.0, peak_density * 1000)

    def _has_spectral_gaps(self, log_magnitude: np.ndarray) -> bool:
        """Check for unusual gaps in frequency spectrum."""
        # Compute radial average
        rows, cols = log_magnitude.shape
        center = (rows // 2, cols // 2)

        y, x = np.ogrid[:rows, :cols]
        r = np.sqrt((x - center[1]) ** 2 + (y - center[0]) ** 2).astype(int)

        max_r = min(center)
        radial_avg = np.zeros(max_r)

        for i in range(max_r):
            mask = r == i
            if np.any(mask):
                radial_avg[i] = np.mean(log_magnitude[mask])

        # Look for sudden drops (gaps)
        diff = np.diff(radial_avg)
        gaps = np.sum(diff < -np.std(diff) * 2)

        return gaps > 3

    def _analyze_texture_consistency(
        self,
        image: np.ndarray,
    ) -> Tuple[float, List[str]]:
        """Analyze texture consistency across face regions."""
        artifacts = []
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Divide image into patches
        h, w = gray.shape
        patch_size = min(h, w) // 4

        patches = []
        for i in range(0, h - patch_size, patch_size):
            for j in range(0, w - patch_size, patch_size):
                patch = gray[i:i + patch_size, j:j + patch_size]
                patches.append(patch)

        if len(patches) < 4:
            return 0.0, []

        # Calculate texture features for each patch
        texture_features = []
        for patch in patches:
            # Laplacian variance (texture measure)
            lap_var = cv2.Laplacian(patch, cv2.CV_64F).var()
            # Local Binary Pattern approximation
            lbp_approx = np.std(patch)
            texture_features.append((lap_var, lbp_approx))

        # Check for inconsistent textures
        lap_vars = [f[0] for f in texture_features]
        lbp_stds = [f[1] for f in texture_features]

        lap_cv = np.std(lap_vars) / (np.mean(lap_vars) + 1e-6)
        lbp_cv = np.std(lbp_stds) / (np.mean(lbp_stds) + 1e-6)

        anomaly_score = 0.0

        # High variance in texture = inconsistent = possible deepfake
        if lap_cv > 0.5:
            anomaly_score += 0.4
            artifacts.append("texture_inconsistency")

        if lbp_cv > 0.4:
            anomaly_score += 0.3
            artifacts.append("local_pattern_anomaly")

        # Check for overly smooth regions (common in GAN faces)
        smooth_patches = sum(1 for lv in lap_vars if lv < 50)
        if smooth_patches > len(patches) // 2:
            anomaly_score += 0.3
            artifacts.append("unnatural_smoothness")

        return min(1.0, anomaly_score), artifacts

    def _analyze_color_channels(
        self,
        image: np.ndarray,
    ) -> Tuple[float, List[str]]:
        """Analyze color channel correlations."""
        artifacts = []

        # Split channels
        b, g, r = cv2.split(image)

        # Calculate channel correlations
        rg_corr = np.corrcoef(r.flatten(), g.flatten())[0, 1]
        rb_corr = np.corrcoef(r.flatten(), b.flatten())[0, 1]
        gb_corr = np.corrcoef(g.flatten(), b.flatten())[0, 1]

        # Natural faces have high channel correlation
        min_corr = min(rg_corr, rb_corr, gb_corr)

        anomaly_score = 0.0

        if min_corr < 0.7:  # Low correlation is suspicious
            anomaly_score += 0.4
            artifacts.append("channel_decorrelation")

        # Check for color banding (quantization artifacts)
        for channel, name in [(r, "red"), (g, "green"), (b, "blue")]:
            hist = cv2.calcHist([channel], [0], None, [256], [0, 256])
            # Look for unusual spikes (banding)
            peaks = np.sum(hist > np.mean(hist) * 3)
            if peaks < 10:  # Too few distinct levels
                anomaly_score += 0.2
                artifacts.append(f"{name}_banding")
                break

        # Check for unnatural saturation
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        saturation = hsv[:, :, 1]
        sat_std = np.std(saturation)

        if sat_std < 20:  # Unnaturally uniform saturation
            anomaly_score += 0.2
            artifacts.append("uniform_saturation")

        return min(1.0, anomaly_score), artifacts

    def _analyze_boundary_artifacts(
        self,
        image: np.ndarray,
    ) -> Tuple[float, List[str]]:
        """Analyze face boundary for blending artifacts."""
        artifacts = []
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Edge detection
        edges = cv2.Canny(gray, 50, 150)

        # Look for strong edges at face boundary
        h, w = gray.shape
        border_width = min(h, w) // 10

        # Create border mask
        border_mask = np.zeros_like(gray, dtype=bool)
        border_mask[:border_width, :] = True
        border_mask[-border_width:, :] = True
        border_mask[:, :border_width] = True
        border_mask[:, -border_width:] = True

        # Edge density at border vs center
        border_edge_density = np.sum(edges[border_mask]) / np.sum(border_mask)
        center_mask = ~border_mask
        center_edge_density = np.sum(edges[center_mask]) / np.sum(center_mask)

        anomaly_score = 0.0

        # Deepfakes often have visible seams at boundaries
        edge_ratio = border_edge_density / (center_edge_density + 1e-6)
        if edge_ratio > 2.0:
            anomaly_score += 0.5
            artifacts.append("boundary_edges")

        # Check for blur inconsistency at boundaries
        border_blur = cv2.Laplacian(gray, cv2.CV_64F)
        border_sharpness = np.mean(np.abs(border_blur[border_mask]))
        center_sharpness = np.mean(np.abs(border_blur[center_mask]))

        blur_ratio = border_sharpness / (center_sharpness + 1e-6)
        if blur_ratio < 0.5 or blur_ratio > 2.0:
            anomaly_score += 0.3
            artifacts.append("boundary_blur_mismatch")

        return min(1.0, anomaly_score), artifacts

    def _analyze_temporal_coherence(
        self,
        current_frame: np.ndarray,
    ) -> Tuple[float, List[str]]:
        """Analyze temporal coherence across frames."""
        artifacts = []

        if len(self._frame_history) < 3:
            return 0.0, []

        anomaly_score = 0.0

        # Compare with recent frames
        prev_frame = self._frame_history[-1]

        # Optical flow consistency
        gray_curr = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
        gray_prev = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

        flow = cv2.calcOpticalFlowFarneback(
            gray_prev, gray_curr, None,
            0.5, 3, 15, 3, 5, 1.2, 0
        )

        # Check for unnatural motion patterns
        flow_mag = np.sqrt(flow[:, :, 0] ** 2 + flow[:, :, 1] ** 2)
        flow_std = np.std(flow_mag)

        # Deepfakes can have jerky or inconsistent motion
        if flow_std > 5.0:  # High variance in motion
            anomaly_score += 0.3
            artifacts.append("motion_inconsistency")

        # Check feature consistency across frames
        if len(self._feature_history) >= 3:
            recent_features = list(self._feature_history)[-3:]

            # Check for sudden changes in detection scores
            for key in ["freq", "texture", "color"]:
                values = [f[key] for f in recent_features]
                if max(values) - min(values) > 0.4:
                    anomaly_score += 0.2
                    artifacts.append(f"temporal_{key}_jump")
                    break

        return min(1.0, anomaly_score), artifacts

    def reset_temporal_state(self) -> None:
        """Reset temporal analysis state."""
        self._frame_history.clear()
        self._feature_history.clear()
        logger.debug("Temporal state reset")
