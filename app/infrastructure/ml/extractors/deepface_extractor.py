"""DeepFace-based embedding extractor implementation."""

import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np
from deepface import DeepFace

from app.domain.exceptions.face_errors import EmbeddingExtractionError

logger = logging.getLogger(__name__)

# Mapping from DeepFace model name -> expected weight-file basename(s) under
# ~/.deepface/weights/. Used for ML-M1 post-load integrity verification.
# NOTE: DeepFace stores weights in ``~/.deepface/weights/`` (override with
# DEEPFACE_HOME env var). File names match the library's internal download URLs.
_DEEPFACE_WEIGHT_FILENAMES = {
    "Facenet512": ("facenet512_weights.h5",),
    "Facenet": ("facenet_weights.h5",),
    "VGG-Face": ("vgg_face_weights.h5",),
    "ArcFace": ("arcface_weights.h5",),
}


def _deepface_weights_dir() -> Path:
    home = os.environ.get("DEEPFACE_HOME") or os.path.expanduser("~")
    return Path(home) / ".deepface" / "weights"


def _resolve_weight_path(model_name: str) -> Optional[Path]:
    filenames = _DEEPFACE_WEIGHT_FILENAMES.get(model_name, ())
    weights_dir = _deepface_weights_dir()
    for name in filenames:
        candidate = weights_dir / name
        if candidate.is_file():
            return candidate
    return None


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_model_integrity(model_name: str) -> None:
    """Verify the DeepFace weight file against a pinned SHA256.

    Addresses ML-M1 (Audit 2026-04-19): ``DeepFace.build_model`` pulls weights
    from the internet into ``~/.deepface/weights/`` with no integrity check.

    Behaviour:
        * Facenet512 is the model FIVUCSAS actually uses in production.
        * If a pinned hash is configured (``settings.DEEPFACE_FACENET512_SHA256``)
          and the file exists, the digest MUST match or startup is aborted.
        * If no pinned hash is configured, the check logs a WARNING and returns
          without raising — we do not want to break deploys before the hash
          has been recorded. TODO: pin the hash.
        * If the weight file cannot be located (e.g. custom DEEPFACE_HOME), we
          log a warning but do not raise.
    """
    # Import here to avoid a circular import at module load time.
    from app.core.config import settings

    # Only Facenet512 is production-critical; other models fall through.
    if model_name != "Facenet512":
        logger.debug(
            "Skipping SHA256 integrity check for non-Facenet512 model '%s'",
            model_name,
        )
        return

    expected = (settings.DEEPFACE_FACENET512_SHA256 or "").strip().lower()
    weight_path = _resolve_weight_path(model_name)

    if weight_path is None:
        logger.warning(
            "DeepFace model integrity check skipped: weight file for '%s' "
            "not found under %s (DeepFace may load from an embedded archive)",
            model_name,
            _deepface_weights_dir(),
        )
        return

    if not expected:
        # TODO: pin DEEPFACE_FACENET512_SHA256 in config.py once the known-good
        # hash has been recorded from a trusted build. See ML-M1 in
        # docs/audits/AUDIT_2026-04-19.md.
        logger.warning(
            "DeepFace model integrity check skipped (no pinned hash): %s. "
            "Set DEEPFACE_FACENET512_SHA256 once verified.",
            weight_path,
        )
        return

    actual = _sha256_file(weight_path)
    if actual.lower() != expected:
        logger.error(
            "DeepFace model integrity check FAILED for %s: expected=%s actual=%s",
            weight_path,
            expected,
            actual,
        )
        raise RuntimeError("DeepFace model integrity check failed")

    logger.info(
        "DeepFace model integrity check passed for %s (sha256=%s...)",
        weight_path.name,
        actual[:16],
    )


class DeepFaceExtractor:
    """Embedding extractor using DeepFace library.

    Implements IEmbeddingExtractor interface using DeepFace's face recognition models.
    Supports multiple models (VGG-Face, Facenet, OpenFace, DeepFace, DeepID, ArcFace, Dlib, SFace).

    Following Open/Closed Principle: Can be replaced with different extractor
    without changing client code.
    """

    # Embedding dimensions for different models
    EMBEDDING_DIMENSIONS = {
        "VGG-Face": 2622,
        "Facenet": 128,
        "Facenet512": 512,
        "OpenFace": 128,
        "DeepFace": 4096,
        "DeepID": 160,
        "ArcFace": 512,
        "Dlib": 128,
        "SFace": 128,
    }

    def __init__(
        self,
        model_name: str = "Facenet",
        detector_backend: str = "opencv",
        enforce_detection: bool = False,
    ) -> None:
        """Initialize DeepFace extractor.

        Args:
            model_name: Model to use for embedding extraction
                Options: "VGG-Face", "Facenet", "Facenet512", "OpenFace",
                        "DeepFace", "DeepID", "ArcFace", "Dlib", "SFace"
            detector_backend: Detection backend to use
            enforce_detection: Whether to enforce face detection

        Note:
            - Facenet: 128-D, good balance (recommended)
            - ArcFace: 512-D, state-of-the-art accuracy
            - VGG-Face: 2622-D, older but reliable
        """
        self._model_name = model_name
        self._detector_backend = detector_backend
        self._enforce_detection = enforce_detection

        # Warm up the model by building it
        try:
            logger.info(f"Loading {model_name} model...")
            DeepFace.build_model(model_name)
            # ML-M1 (Audit 2026-04-19): verify the just-downloaded/loaded
            # weight file against a pinned SHA256. A RuntimeError here must
            # halt startup — do not swallow it into EmbeddingExtractionError.
            _verify_model_integrity(model_name)
            logger.info(f"Successfully loaded {model_name} model")
        except RuntimeError:
            # Integrity check failure — propagate unchanged so startup aborts.
            raise
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            raise EmbeddingExtractionError(f"Model load failed: {e}")

    def extract_sync(self, face_image: np.ndarray) -> np.ndarray:
        """Synchronous embedding extraction for thread pool execution.

        This method contains the actual blocking DeepFace call.
        Called by AsyncEmbeddingExtractor via thread pool for non-blocking execution.

        CRITICAL OPTIMIZATION:
            This method sets enforce_detection=False to skip redundant face detection.
            Face detection is already done by FaceDetector, so we only need embedding extraction.
            This eliminates duplicate DeepFace.extract_faces() calls and improves performance by 20-40%.

        Args:
            face_image: Pre-detected face region as numpy array (H, W, C)

        Returns:
            Face embedding as 1D numpy array (dimension depends on model)

        Raises:
            EmbeddingExtractionError: When extraction fails
        """
        try:
            logger.debug(f"Extracting embedding using {self._model_name}")

            # CRITICAL FIX: Set enforce_detection=False to skip redundant detection
            # Face is already detected and cropped by FaceDetector
            embedding_objs = DeepFace.represent(
                img_path=face_image,
                model_name=self._model_name,
                detector_backend=self._detector_backend,
                enforce_detection=False,  # Skip detection - already done!
                align=True,
                normalization="base",  # Use base normalization (L2 norm)
            )

            if not embedding_objs or len(embedding_objs) == 0:
                raise EmbeddingExtractionError("No embedding generated")

            # Get the first face's embedding
            embedding = embedding_objs[0]["embedding"]

            # Convert to numpy array
            embedding_array = np.array(embedding, dtype=np.float32)

            # L2 normalize the embedding for cosine similarity
            embedding_normalized = self._l2_normalize(embedding_array)

            logger.info(f"Successfully extracted {len(embedding_normalized)}-D embedding")

            return embedding_normalized

        except ValueError as e:
            logger.error(f"Embedding extraction failed: {e}")
            raise EmbeddingExtractionError(str(e))

        except Exception as e:
            logger.error(f"Unexpected error during embedding extraction: {e}", exc_info=True)
            raise EmbeddingExtractionError(f"Unexpected error: {e}")

    async def extract(self, face_image: np.ndarray) -> np.ndarray:
        """Extract face embedding from image (async wrapper).

        This method delegates to extract_sync for backward compatibility.
        For truly non-blocking execution, use AsyncEmbeddingExtractor wrapper.

        Args:
            face_image: Face image as numpy array (H, W, C)

        Returns:
            Face embedding as 1D numpy array (dimension depends on model)

        Raises:
            EmbeddingExtractionError: When extraction fails
        """
        return self.extract_sync(face_image)

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this extractor.

        Returns:
            Embedding dimension
        """
        return self.EMBEDDING_DIMENSIONS.get(self._model_name, 128)

    def get_model_name(self) -> str:
        """Get the name of the model being used.

        Returns:
            Model name
        """
        return self._model_name

    @staticmethod
    def _l2_normalize(embedding: np.ndarray) -> np.ndarray:
        """L2 normalize an embedding vector.

        Args:
            embedding: Embedding vector

        Returns:
            L2-normalized embedding
        """
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return embedding
        return embedding / norm
