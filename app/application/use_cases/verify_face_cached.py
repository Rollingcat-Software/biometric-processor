"""Face verification use case with Redis caching.

Enhanced version of verify_face.py that includes distributed caching
for improved performance. Uses Redis to cache:
- Extracted embeddings (keyed by image hash)
- Verification results (keyed by user_id + image hash)
"""

import logging
from typing import Optional

import cv2
import numpy as np

from app.domain.entities.verification_result import VerificationResult
from app.domain.exceptions.verification_errors import EmbeddingNotFoundError
from app.domain.interfaces.embedding_extractor import IEmbeddingExtractor
from app.domain.interfaces.embedding_repository import IEmbeddingRepository
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.similarity_calculator import ISimilarityCalculator
from app.infrastructure.caching.redis_embedding_cache import (
    RedisEmbeddingCache,
    get_embedding_cache,
)

logger = logging.getLogger(__name__)


class VerifyFaceCachedUseCase:
    """Face verification use case with distributed caching.

    Extends the basic verification flow with Redis caching to:
    - Cache extracted embeddings to avoid redundant ML inference
    - Cache verification results for repeated requests
    - Cache enrolled embeddings to reduce database queries

    Cache hit scenarios:
    1. Same image verified against same user: Full cache hit
    2. Same image verified against different user: Embedding cache hit
    3. Different image, same user: Enrolled embedding cache hit
    """

    def __init__(
        self,
        detector: IFaceDetector,
        extractor: IEmbeddingExtractor,
        similarity_calculator: ISimilarityCalculator,
        repository: IEmbeddingRepository,
        cache: Optional[RedisEmbeddingCache] = None,
    ) -> None:
        """Initialize cached verification use case.

        Args:
            detector: Face detector implementation
            extractor: Embedding extractor implementation
            similarity_calculator: Similarity calculator implementation
            repository: Embedding repository implementation
            cache: Optional Redis cache (uses global instance if None)
        """
        self._detector = detector
        self._extractor = extractor
        self._similarity_calculator = similarity_calculator
        self._repository = repository
        self._cache = cache or get_embedding_cache()

        logger.info("VerifyFaceCachedUseCase initialized with Redis caching")

    async def execute(
        self,
        user_id: str,
        image_data: bytes,
        tenant_id: Optional[str] = None,
        threshold: Optional[float] = None,
        use_cache: bool = True,
    ) -> VerificationResult:
        """Execute face verification with caching.

        Args:
            user_id: User identifier to verify against
            image_data: Raw image bytes
            tenant_id: Optional tenant identifier for multi-tenancy
            threshold: Optional custom similarity threshold
            use_cache: Whether to use caching (default True)

        Returns:
            VerificationResult with verification outcome

        Raises:
            FaceNotDetectedError: When no face is found
            MultipleFacesError: When multiple faces are found
            EmbeddingNotFoundError: When no stored embedding exists for user
            EmbeddingExtractionError: When embedding extraction fails
            RepositoryError: When repository access fails
        """
        logger.info(
            f"Starting cached face verification for user_id={user_id}, tenant_id={tenant_id}"
        )

        # Hash the image for cache lookups
        image_hash = self._cache.hash_image(image_data)

        # Check for cached verification result
        if use_cache:
            cached_result = await self._cache.get_verification_result(user_id, image_hash)
            if cached_result:
                logger.info(f"Cache hit: verification result for user_id={user_id}")
                return VerificationResult(**cached_result)

        # Decode image
        image = self._decode_image(image_data)

        # Get probe embedding (with caching)
        probe_embedding = await self._get_probe_embedding(
            image, image_hash, use_cache
        )

        # Get enrolled embedding (with caching)
        enrolled_embedding = await self._get_enrolled_embedding(
            user_id, tenant_id, use_cache
        )

        if enrolled_embedding is None:
            logger.warning(f"No embedding found for user_id={user_id}")
            raise EmbeddingNotFoundError(user_id)

        # Calculate similarity
        logger.debug("Calculating similarity...")
        distance = self._similarity_calculator.calculate(
            probe_embedding, enrolled_embedding
        )

        # Determine verification result
        effective_threshold = threshold or self._similarity_calculator.get_threshold()
        verified = distance < effective_threshold
        confidence = self._similarity_calculator.get_confidence(distance)

        result = VerificationResult(
            verified=verified,
            confidence=confidence,
            distance=distance,
            threshold=effective_threshold,
        )

        # Cache the verification result
        if use_cache:
            await self._cache.set_verification_result(
                user_id,
                image_hash,
                result.model_dump() if hasattr(result, 'model_dump') else result.__dict__,
            )

        logger.info(
            f"Verification completed: user_id={user_id}, "
            f"verified={verified}, "
            f"distance={distance:.4f}, "
            f"confidence={confidence:.4f}"
        )

        return result

    async def execute_from_path(
        self,
        user_id: str,
        image_path: str,
        tenant_id: Optional[str] = None,
        threshold: Optional[float] = None,
        use_cache: bool = True,
    ) -> VerificationResult:
        """Execute verification from image file path.

        Convenience method that reads the image file and calls execute().

        Args:
            user_id: User identifier to verify against
            image_path: Path to image file
            tenant_id: Optional tenant identifier
            threshold: Optional custom threshold
            use_cache: Whether to use caching

        Returns:
            VerificationResult with verification outcome
        """
        with open(image_path, "rb") as f:
            image_data = f.read()

        return await self.execute(
            user_id=user_id,
            image_data=image_data,
            tenant_id=tenant_id,
            threshold=threshold,
            use_cache=use_cache,
        )

    async def _get_probe_embedding(
        self,
        image: np.ndarray,
        image_hash: str,
        use_cache: bool,
    ) -> np.ndarray:
        """Get embedding for probe image with caching.

        Args:
            image: Decoded image array
            image_hash: SHA-256 hash of original image bytes
            use_cache: Whether to use caching

        Returns:
            Embedding vector
        """
        # Try cache first
        if use_cache:
            cached_embedding = await self._cache.get_embedding(image_hash)
            if cached_embedding is not None:
                logger.debug(f"Cache hit: probe embedding {image_hash[:16]}...")
                return cached_embedding

        # Detect face
        logger.debug("Detecting face...")
        detection = await self._detector.detect(image)

        # Extract face region
        logger.debug("Extracting face region...")
        face_region = detection.get_face_region(image)

        # Extract embedding
        logger.debug("Extracting embedding...")
        embedding = await self._extractor.extract(face_region)

        # Get the vector from the embedding result
        embedding_vector = embedding.vector if hasattr(embedding, 'vector') else embedding

        # Cache the embedding
        if use_cache:
            await self._cache.set_embedding(image_hash, embedding_vector)

        return embedding_vector

    async def _get_enrolled_embedding(
        self,
        user_id: str,
        tenant_id: Optional[str],
        use_cache: bool,
    ) -> Optional[np.ndarray]:
        """Get enrolled embedding for user with caching.

        Args:
            user_id: User identifier
            tenant_id: Tenant identifier
            use_cache: Whether to use caching

        Returns:
            Enrolled embedding vector or None if not found
        """
        # Try cache first
        if use_cache and tenant_id:
            cached = await self._cache.get_enrolled_embedding(user_id, tenant_id)
            if cached is not None:
                logger.debug(f"Cache hit: enrolled embedding for {user_id}")
                return cached

        # Fetch from repository
        logger.debug(f"Fetching enrolled embedding from repository for {user_id}...")
        stored = await self._repository.find_by_user_id(user_id, tenant_id)

        if stored is None:
            return None

        # Extract the embedding vector
        embedding_vector = stored.vector if hasattr(stored, 'vector') else stored

        # Cache for future requests
        if use_cache and tenant_id:
            await self._cache.set_enrolled_embedding(user_id, tenant_id, embedding_vector)

        return embedding_vector

    def _decode_image(self, image_data: bytes) -> np.ndarray:
        """Decode image bytes to numpy array.

        Args:
            image_data: Raw image bytes

        Returns:
            Decoded image as BGR numpy array

        Raises:
            ValueError: If image cannot be decoded
        """
        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            raise ValueError("Failed to decode image")

        return image

    async def invalidate_cache(self, user_id: str, tenant_id: Optional[str] = None):
        """Invalidate all cached data for a user.

        Should be called when user re-enrolls or is deleted.

        Args:
            user_id: User identifier
            tenant_id: Optional tenant identifier
        """
        await self._cache.invalidate_user_cache(user_id, tenant_id)
        logger.info(f"Cache invalidated for user_id={user_id}")
