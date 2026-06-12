"""Face verification use case."""

import asyncio
import logging
import time
from datetime import datetime
from typing import Optional

import cv2

from app.core.config import settings
from app.domain.entities.verification_result import VerificationResult
from app.domain.exceptions.face_errors import PoorImageQualityError
from app.domain.exceptions.verification_errors import EmbeddingNotFoundError
from app.domain.interfaces.embedding_extractor import IEmbeddingExtractor
from app.domain.interfaces.embedding_repository import IEmbeddingRepository
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.quality_assessor import IQualityAssessor
from app.domain.interfaces.similarity_calculator import ISimilarityCalculator

logger = logging.getLogger(__name__)


class VerifyFaceUseCase:
    """Use case for verifying a user's face (1:1 matching).

    This use case orchestrates the following steps:
    1. Detect face in image
    2. Extract face region
    3. Extract embedding
    4. Retrieve stored embedding from repository
    5. Calculate similarity
    6. Verify against threshold

    Following Single Responsibility Principle: Only handles verification orchestration.
    Dependencies are injected for testability (Dependency Inversion Principle).
    """

    # Verification quality threshold (more lenient than enrollment's 70)
    VERIFICATION_QUALITY_THRESHOLD = 50.0

    def __init__(
        self,
        detector: IFaceDetector,
        extractor: IEmbeddingExtractor,
        similarity_calculator: ISimilarityCalculator,
        repository: IEmbeddingRepository,
        quality_assessor: IQualityAssessor | None = None,
    ) -> None:
        """Initialize verification use case.

        Args:
            detector: Face detector implementation
            extractor: Embedding extractor implementation
            similarity_calculator: Similarity calculator implementation
            repository: Embedding repository implementation
            quality_assessor: Optional quality assessor for pre-verification gating
        """
        self._detector = detector
        self._extractor = extractor
        self._similarity_calculator = similarity_calculator
        self._repository = repository
        self._quality_assessor = quality_assessor

        logger.info("VerifyFaceUseCase initialized")

    async def execute(
        self,
        user_id: str,
        image_path: str,
        tenant_id: Optional[str] = None,
    ) -> VerificationResult:
        """Execute face verification.

        Args:
            user_id: User identifier to verify against
            image_path: Path to image file
            tenant_id: Optional tenant identifier for multi-tenancy

        Returns:
            VerificationResult with verification outcome

        Raises:
            FaceNotDetectedError: When no face is found
            MultipleFacesError: When multiple faces are found
            EmbeddingNotFoundError: When no stored embedding exists for user
            EmbeddingExtractionError: When embedding extraction fails
            RepositoryError: When repository access fails
        """
        logger.info(f"Starting face verification for user_id={user_id}, tenant_id={tenant_id}")

        # USER-BUG-7 (2026-05-01): per-stage timing so future cold-start
        # regressions are diagnosable from the logs without extra tooling.
        # All durations are wall-clock milliseconds; the final `total` line
        # is what surfaces in slow-verify reports.
        stage_ms: dict[str, float] = {}
        t_start = time.perf_counter()

        # Step 1: Load image (P2.11: offload blocking decode + disk I/O off the event loop)
        t0 = time.perf_counter()
        image = await asyncio.to_thread(cv2.imread, image_path)
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")
        stage_ms["decode"] = (time.perf_counter() - t0) * 1000

        # Step 2: Detect face
        # Client pre-crops to 224×224 — detection only as fallback.
        # When the input image is already ~224×224 (client-cropped), this step
        # is fast (<10ms) because there is only one face region covering most of
        # the frame. Full-frame detection (640×480+) previously cost 200-730ms.
        logger.debug("Step 1/5: Detecting face...")
        t0 = time.perf_counter()
        detection = await self._detector.detect(image)
        stage_ms["detect"] = (time.perf_counter() - t0) * 1000

        # Step 3: Extract face region
        logger.debug("Step 2/6: Extracting face region...")
        face_region = detection.get_face_region(image)

        # Step 4: Quality gate (reject poor images before expensive comparison)
        if self._quality_assessor is not None:
            logger.debug("Step 3/6: Assessing image quality...")
            t0 = time.perf_counter()
            quality = await self._quality_assessor.assess(face_region)
            stage_ms["quality"] = (time.perf_counter() - t0) * 1000

            if quality.score < self.VERIFICATION_QUALITY_THRESHOLD:
                issues = quality.get_issues(
                    blur_threshold=self._quality_assessor._blur_threshold,
                    min_face_size=self._quality_assessor._min_face_size,
                )
                logger.warning(
                    f"Verification quality gate failed: score={quality.score:.1f}, "
                    f"threshold={self.VERIFICATION_QUALITY_THRESHOLD}, issues={issues}"
                )
                raise PoorImageQualityError(
                    quality_score=quality.score,
                    min_threshold=self.VERIFICATION_QUALITY_THRESHOLD,
                    issues=issues,
                )
            logger.info(f"Verification quality check passed: score={quality.score:.1f}")

        # Step 5: Extract embedding from new image
        logger.debug("Step 4/6: Extracting embedding...")
        t0 = time.perf_counter()
        new_embedding = await self._extractor.extract(face_region)
        stage_ms["embed"] = (time.perf_counter() - t0) * 1000

        # Steps 6-7: retrieve stored template, compute distance, resolve the
        # (possibly adaptive aged) threshold, and decide. Shared with the
        # client-side embedding route (/verify-embedding) via match_embedding.
        # Pass `stage_ms` so the template-fetch duration is recorded back into the
        # same dict and the verify log line regains its `fetch=Xms` segment (the
        # extraction into match_embedding had dropped it).
        result = await self.match_embedding(
            user_id=user_id,
            embedding=new_embedding,
            tenant_id=tenant_id,
            stage_ms=stage_ms,
        )

        total_ms = (time.perf_counter() - t_start) * 1000
        timing_summary = " ".join(f"{k}={v:.0f}ms" for k, v in stage_ms.items())
        logger.info(
            f"face/verify: {timing_summary} total={total_ms:.0f}ms "
            f"user_id={user_id} verified={result.verified} "
            f"distance={result.distance:.4f} confidence={result.confidence:.4f} "
            f"threshold={result.threshold}"
        )

        return result

    async def match_embedding(
        self,
        user_id: str,
        embedding,
        tenant_id: Optional[str] = None,
        stage_ms: Optional[dict[str, float]] = None,
    ) -> VerificationResult:
        """Match an ALREADY-EXTRACTED embedding against the user's template.

        This is the pgvector match + threshold/decision logic that
        :meth:`execute` runs after it computes the embedding from an image,
        factored out so the precomputed-embedding route (``/verify-embedding``)
        can reuse the EXACT same matching, adaptive-aged-threshold and
        confidence logic without re-detecting / re-embedding. ``execute`` calls
        this with the freshly-extracted embedding, so its behaviour is
        unchanged.

        The ``embedding`` is compared via the injected similarity calculator,
        which L2-normalizes both operands internally — a client-supplied
        already-normalized vector and the stored template are therefore compared
        consistently whether or not either is pre-normalized.

        Args:
            user_id: User identifier to verify against.
            embedding: Probe embedding (numpy array or sequence of floats).
            tenant_id: Optional tenant identifier for multi-tenancy.
            stage_ms: Optional per-stage timing dict. When supplied (by
                :meth:`execute`), the template-fetch duration is recorded under
                the ``"fetch"`` key so the verify log line keeps its
                ``fetch=Xms`` segment. Observability only — no behaviour change;
                the ``/verify-embedding`` route omits it (it has no log line).

        Returns:
            VerificationResult with the verdict, distance, threshold and the
            threshold-anchored confidence.

        Raises:
            EmbeddingNotFoundError: When no stored embedding exists for the user.
        """
        # Retrieve stored embedding (timed back into stage_ms when provided, so
        # the verify log line regains its `fetch=Xms` per-stage segment).
        _t_fetch = time.perf_counter()
        stored_embedding = await self._repository.find_by_user_id(user_id, tenant_id)
        if stage_ms is not None:
            stage_ms["fetch"] = (time.perf_counter() - _t_fetch) * 1000

        if stored_embedding is None:
            logger.warning(f"No embedding found for user_id={user_id}")
            raise EmbeddingNotFoundError(user_id)

        # Calculate similarity
        distance = self._similarity_calculator.calculate(embedding, stored_embedding)

        # Determine threshold — use adaptive (lenient) threshold for aged embeddings
        threshold = self._similarity_calculator.get_threshold()
        try:
            if hasattr(self._repository, "find_created_at"):
                created_at = await self._repository.find_created_at(user_id, tenant_id)
                if created_at is not None:
                    days = (datetime.utcnow() - created_at).days
                    aged_threshold_days = int(settings.VERIFICATION_THRESHOLD_AGED_YEARS * 365)
                    if days > aged_threshold_days:
                        threshold = settings.VERIFICATION_THRESHOLD_AGED
                        logger.info(
                            f"Adaptive threshold applied: embedding_age={days}d "
                            f"(>{aged_threshold_days}d), threshold={threshold} "
                            f"(was {self._similarity_calculator.get_threshold()})"
                        )
        except Exception as _threshold_err:
            logger.warning(f"Adaptive threshold lookup failed, using default: {_threshold_err}")

        verified = distance < threshold
        # FIX #12 (2026-06-02): anchor the reported confidence on the SAME
        # (possibly adaptive aged) threshold used for the verdict, so the accept
        # boundary reads ~50% and an identical match ~100% instead of the
        # misleading naive ``1 - distance``. Decision logic is unchanged.
        confidence = self._similarity_calculator.get_confidence(distance, threshold)

        return VerificationResult(
            verified=verified,
            confidence=confidence,
            distance=distance,
            threshold=threshold,
        )
