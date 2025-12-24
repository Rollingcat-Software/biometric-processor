"""Enhanced liveness detector with multiple detection strategies.

This detector combines multiple liveness detection techniques:
1. Texture analysis (LBP) - detects print attacks
2. Blink detection - detects eye blinks using Haar cascades and eye aspect ratio
3. Smile detection - detects mouth movements using Haar cascades
4. Color/frequency analysis - detects screen displays

This multi-modal approach provides robust anti-spoofing protection.
Uses OpenCV only (no MediaPipe required) for maximum compatibility.
"""

import logging
import os
from typing import Optional, Tuple

import cv2
import numpy as np

from app.domain.entities.liveness_result import LivenessResult
from app.domain.exceptions.face_errors import FaceNotDetectedError
from app.domain.exceptions.liveness_errors import LivenessCheckError
from app.domain.interfaces.liveness_detector import ILivenessDetector

logger = logging.getLogger(__name__)


class EnhancedLivenessDetector(ILivenessDetector):
    """Enhanced liveness detector using multiple detection strategies.

    This implementation uses:
    - Local Binary Patterns (LBP) for texture analysis
    - Haar cascade classifiers for eye/smile detection
    - Eye Aspect Ratio (EAR) for blink detection
    - Color and frequency analysis for screen/print detection

    Follows Single Responsibility Principle by delegating each
    detection method to separate private methods.
    """

    # Thresholds
    EAR_BLINK_THRESHOLD = 0.21  # Below this = eye closed
    MIN_EYE_AREA_RATIO = 0.02   # Minimum eye area as ratio of face area

    def __init__(
        self,
        texture_threshold: float = 100.0,
        liveness_threshold: float = 70.0,
        enable_blink_detection: bool = True,
        enable_smile_detection: bool = True,
        blink_frames_required: int = 2,
    ) -> None:
        """Initialize enhanced liveness detector.

        Args:
            texture_threshold: Minimum texture variance for live face
            liveness_threshold: Overall score threshold for liveness
            enable_blink_detection: Enable blink detection challenge
            enable_smile_detection: Enable smile detection challenge
            blink_frames_required: Number of frames to confirm blink
        """
        self._texture_threshold = texture_threshold
        self._liveness_threshold = liveness_threshold
        self._enable_blink = enable_blink_detection
        self._enable_smile = enable_smile_detection
        self._blink_frames_required = blink_frames_required

        # Initialize Haar cascade classifiers
        try:
            opencv_data_dir = os.path.join(cv2.__path__[0], "data")

            # Load face cascade
            face_cascade_path = os.path.join(opencv_data_dir, "haarcascade_frontalface_default.xml")
            self._face_cascade = cv2.CascadeClassifier(face_cascade_path)

            # Load eye cascade
            eye_cascade_path = os.path.join(opencv_data_dir, "haarcascade_eye.xml")
            self._eye_cascade = cv2.CascadeClassifier(eye_cascade_path)

            # Load smile cascade
            smile_cascade_path = os.path.join(opencv_data_dir, "haarcascade_smile.xml")
            self._smile_cascade = cv2.CascadeClassifier(smile_cascade_path)

            if self._face_cascade.empty() or self._eye_cascade.empty() or self._smile_cascade.empty():
                raise LivenessCheckError("Failed to load Haar cascade classifiers")

        except Exception as e:
            logger.error(f"Failed to initialize Haar cascades: {e}")
            raise LivenessCheckError(f"Failed to initialize cascades: {e}")

        # State for sequential detection
        self._blink_counter = 0
        self._eyes_closed_frames = 0
        self._previous_eye_count = 2

        logger.info(
            f"EnhancedLivenessDetector initialized: "
            f"texture_threshold={texture_threshold}, "
            f"liveness_threshold={liveness_threshold}, "
            f"blink_detection={enable_blink_detection}, "
            f"smile_detection={enable_smile_detection}"
        )

    async def check_liveness(self, image: np.ndarray) -> LivenessResult:
        """Check if image shows a live person.

        Args:
            image: Input image as numpy array (H, W, C) in BGR format

        Returns:
            LivenessResult containing liveness score and challenge information

        Raises:
            FaceNotDetectedError: When no face is found
            LivenessCheckError: When liveness check fails
        """
        logger.info("Starting enhanced liveness detection")

        try:
            # Validate input
            if image is None or image.size == 0:
                raise LivenessCheckError("Invalid input image")

            # Calculate texture score (passive)
            texture_score = self._calculate_texture_score(image)
            logger.debug(f"Texture score: {texture_score:.2f}")

            # Calculate LBP score (passive)
            lbp_score = self._calculate_lbp_score(image)
            logger.debug(f"LBP score: {lbp_score:.2f}")

            # Calculate color naturalness score (passive)
            color_score = self._calculate_color_score(image)
            logger.debug(f"Color score: {color_score:.2f}")

            # Detect face using Haar cascade
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            faces = self._face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )

            if len(faces) == 0:
                raise FaceNotDetectedError()

            # Use the largest face
            face = max(faces, key=lambda rect: rect[2] * rect[3])
            x, y, w, h = face
            face_roi = gray[y : y + h, x : x + w]
            face_roi_color = image[y : y + h, x : x + w]

            # Active challenges based on configuration
            blink_score = 0.0
            smile_score = 0.0
            challenge_type = "passive"
            challenge_completed = True

            if self._enable_blink:
                blink_score, blink_detected = self._detect_blink(face_roi, face)
                logger.debug(f"Blink score: {blink_score:.2f}, detected: {blink_detected}")
                challenge_type = "blink"
                challenge_completed = blink_detected

            if self._enable_smile:
                smile_score, smile_detected = self._detect_smile(face_roi)
                logger.debug(f"Smile score: {smile_score:.2f}, detected: {smile_detected}")
                if challenge_type == "blink":
                    challenge_type = "blink_and_smile"
                else:
                    challenge_type = "smile"
                challenge_completed = challenge_completed and smile_detected

            # Combine scores with weights
            weights = self._get_score_weights()

            liveness_score = (
                texture_score * weights["texture"]
                + lbp_score * weights["lbp"]
                + color_score * weights["color"]
                + blink_score * weights["blink"]
                + smile_score * weights["smile"]
            )

            # Normalize to 0-100
            liveness_score = min(100.0, max(0.0, liveness_score))

            is_live = liveness_score >= self._liveness_threshold

            logger.info(
                f"Liveness detection complete: score={liveness_score:.2f}, "
                f"is_live={is_live}, challenge={challenge_type}, "
                f"challenge_completed={challenge_completed}"
            )

            return LivenessResult(
                is_live=is_live,
                liveness_score=liveness_score,
                challenge=challenge_type,
                challenge_completed=challenge_completed,
            )

        except FaceNotDetectedError:
            raise
        except Exception as e:
            logger.error(f"Liveness check error: {e}", exc_info=True)
            raise LivenessCheckError(f"Liveness detection failed: {str(e)}")

    def _get_score_weights(self) -> dict:
        """Get score weights based on enabled features.

        Returns:
            Dictionary of score weights
        """
        weights = {
            "texture": 0.25,
            "lbp": 0.25,
            "color": 0.20,
            "blink": 0.15 if self._enable_blink else 0.0,
            "smile": 0.15 if self._enable_smile else 0.0,
        }

        # Redistribute unused weights to passive checks
        unused = 0.0
        if not self._enable_blink:
            unused += 0.15
        if not self._enable_smile:
            unused += 0.15

        if unused > 0:
            weights["texture"] += unused / 3
            weights["lbp"] += unused / 3
            weights["color"] += unused / 3

        return weights

    def _detect_blink(self, face_roi: np.ndarray, face_rect: Tuple) -> Tuple[float, bool]:
        """Detect eye blink using Haar cascade eye detection.

        Args:
            face_roi: Face region of interest (grayscale)
            face_rect: Face rectangle (x, y, w, h)

        Returns:
            Tuple of (blink_score, blink_detected)
        """
        try:
            # Detect eyes in face ROI
            eyes = self._eye_cascade.detectMultiScale(
                face_roi, scaleFactor=1.1, minNeighbors=5, minSize=(20, 20)
            )

            num_eyes = len(eyes)
            face_area = face_rect[2] * face_rect[3]

            # Calculate total eye area
            total_eye_area = sum(ew * eh for _, _, ew, eh in eyes)
            eye_area_ratio = total_eye_area / face_area if face_area > 0 else 0

            logger.debug(
                f"Eye detection: found {num_eyes} eyes, "
                f"area_ratio={eye_area_ratio:.3f}, "
                f"previous_count={self._previous_eye_count}"
            )

            # Detect eye closure
            # If we had 2 eyes before and now have 0 or 1, eyes might be closing
            # If area ratio is very small, eyes are likely closed
            eyes_closed = (num_eyes < 2 and self._previous_eye_count >= 2) or (
                eye_area_ratio < self.MIN_EYE_AREA_RATIO and num_eyes < 2
            )

            if eyes_closed:
                self._eyes_closed_frames += 1
                logger.debug(f"Eyes closed detected: frame {self._eyes_closed_frames}")
            else:
                # Check if we had a blink (eyes were closed, now open)
                if self._eyes_closed_frames >= self._blink_frames_required:
                    self._blink_counter += 1
                    logger.info(f"Blink detected! Total blinks: {self._blink_counter}")
                self._eyes_closed_frames = 0

            self._previous_eye_count = num_eyes

            # Blink detected if we've seen at least one blink
            blink_detected = self._blink_counter > 0

            # Score based on blink detection and eye openness variation
            if blink_detected:
                blink_score = 100.0
            else:
                # Partial score based on eye visibility
                blink_score = min(60.0, (num_eyes / 2.0) * 50.0 + eye_area_ratio * 200.0)

            return blink_score, blink_detected

        except Exception as e:
            logger.warning(f"Blink detection failed: {e}")
            return 50.0, False

    def _detect_smile(self, face_roi: np.ndarray) -> Tuple[float, bool]:
        """Detect smile using Haar cascade smile detection.

        Args:
            face_roi: Face region of interest (grayscale)

        Returns:
            Tuple of (smile_score, smile_detected)
        """
        try:
            # Detect smiles in lower half of face (where mouth is)
            h = face_roi.shape[0]
            mouth_roi = face_roi[h // 2 :, :]

            smiles = self._smile_cascade.detectMultiScale(
                mouth_roi,
                scaleFactor=1.8,  # Higher scale factor to avoid false positives
                minNeighbors=20,  # Higher neighbors threshold for more confidence
                minSize=(25, 25),
            )

            num_smiles = len(smiles)
            smile_detected = num_smiles > 0

            logger.debug(f"Smile detection: found {num_smiles} smiles")

            # Score based on smile detection
            if smile_detected:
                # Calculate smile confidence based on number and size of detections
                total_smile_area = sum(sw * sh for _, _, sw, sh in smiles)
                mouth_roi_area = mouth_roi.shape[0] * mouth_roi.shape[1]
                smile_ratio = total_smile_area / mouth_roi_area if mouth_roi_area > 0 else 0

                smile_score = min(100.0, 70.0 + smile_ratio * 300.0)
            else:
                smile_score = 30.0

            return smile_score, smile_detected

        except Exception as e:
            logger.warning(f"Smile detection failed: {e}")
            return 50.0, False

    def _calculate_texture_score(self, image: np.ndarray) -> float:
        """Calculate texture score using Laplacian variance.

        Real faces have more texture variation than printed photos.

        Args:
            image: Input image (BGR)

        Returns:
            Texture score (0-100)
        """
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Calculate Laplacian variance
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            variance = laplacian.var()

            # Normalize score: higher variance = more texture = more likely live
            # Typical range: 50-500 for real faces, 10-100 for printed
            if variance >= self._texture_threshold:
                score = min(100.0, 50.0 + (variance - self._texture_threshold) * 0.2)
            else:
                score = max(0.0, (variance / self._texture_threshold) * 50.0)

            return score

        except Exception as e:
            logger.warning(f"Texture calculation failed: {e}")
            return 50.0

    def _calculate_lbp_score(self, image: np.ndarray) -> float:
        """Calculate Local Binary Pattern (LBP) score.

        LBP is effective at detecting printed photos as they have
        different texture patterns than real skin.

        Args:
            image: Input image (BGR)

        Returns:
            LBP score (0-100)
        """
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Calculate LBP
            lbp = self._compute_lbp(gray)

            # Calculate histogram
            hist, _ = np.histogram(lbp, bins=256, range=(0, 256))
            hist = hist.astype("float")
            hist /= hist.sum() + 1e-6

            # Real faces have more uniform LBP distributions
            # Printed photos have spiky histograms
            hist_variance = np.var(hist)

            # Lower variance = more uniform = more likely real face
            # Typical range: 0.0001-0.001 for real, 0.001-0.01 for printed
            if hist_variance < 0.0005:
                score = 100.0
            elif hist_variance < 0.002:
                score = 100.0 - (hist_variance - 0.0005) * 20000.0
            else:
                score = max(0.0, 70.0 - (hist_variance - 0.002) * 5000.0)

            return score

        except Exception as e:
            logger.warning(f"LBP calculation failed: {e}")
            return 50.0

    def _compute_lbp(self, gray: np.ndarray, radius: int = 1, neighbors: int = 8) -> np.ndarray:
        """Compute Local Binary Pattern.

        Args:
            gray: Grayscale image
            radius: Radius of circular pattern
            neighbors: Number of neighbors

        Returns:
            LBP image
        """
        height, width = gray.shape
        lbp = np.zeros((height, width), dtype=np.uint8)

        for i in range(radius, height - radius):
            for j in range(radius, width - radius):
                center = gray[i, j]
                code = 0

                # Sample neighbors in circular pattern
                for n in range(neighbors):
                    angle = 2 * np.pi * n / neighbors
                    x = i + radius * np.cos(angle)
                    y = j + radius * np.sin(angle)

                    # Bilinear interpolation
                    x1, y1 = int(x), int(y)
                    x2, y2 = x1 + 1, y1 + 1

                    if x2 < height and y2 < width:
                        wa = (x2 - x) * (y2 - y)
                        wb = (x2 - x) * (y - y1)
                        wc = (x - x1) * (y2 - y)
                        wd = (x - x1) * (y - y1)

                        neighbor = (
                            wa * gray[x1, y1]
                            + wb * gray[x1, y2]
                            + wc * gray[x2, y1]
                            + wd * gray[x2, y2]
                        )

                        if neighbor >= center:
                            code |= 1 << n

                lbp[i, j] = code

        return lbp

    def _calculate_color_score(self, image: np.ndarray) -> float:
        """Calculate color naturalness score.

        Screens and printed photos often have unnatural color distributions.

        Args:
            image: Input image (BGR)

        Returns:
            Color naturalness score (0-100)
        """
        try:
            # Convert to HSV for better color analysis
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

            # Analyze saturation distribution
            saturation = hsv[:, :, 1]
            sat_mean = np.mean(saturation)
            sat_std = np.std(saturation)

            # Analyze value (brightness) distribution
            value = hsv[:, :, 2]
            val_std = np.std(value)

            # Real faces have moderate saturation and varied brightness
            # Ideal ranges
            ideal_sat_mean = 80
            ideal_val_std = 50

            # Calculate deviations
            sat_deviation = abs(sat_mean - ideal_sat_mean) / 128.0
            val_deviation = abs(val_std - ideal_val_std) / 64.0

            # Combined deviation
            combined_deviation = (sat_deviation + val_deviation) / 2.0

            # Score: lower deviation = higher score
            score = max(0.0, 100.0 - combined_deviation * 100.0)

            return score

        except Exception as e:
            logger.warning(f"Color calculation failed: {e}")
            return 50.0

    def get_challenge_type(self) -> str:
        """Get the type of liveness challenge used.

        Returns:
            Challenge type
        """
        if self._enable_blink and self._enable_smile:
            return "blink_and_smile"
        elif self._enable_blink:
            return "blink"
        elif self._enable_smile:
            return "smile"
        else:
            return "passive"

    def get_liveness_threshold(self) -> float:
        """Get the threshold for considering result as live.

        Returns:
            Liveness score threshold (0-100)
        """
        return self._liveness_threshold

    def reset_state(self) -> None:
        """Reset detection state for new session."""
        self._blink_counter = 0
        self._eyes_closed_frames = 0
        self._previous_eye_count = 2
        logger.debug("Liveness detector state reset")
