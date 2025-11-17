"""DeepFace-based embedding extractor implementation."""

import logging
import numpy as np
from deepface import DeepFace

from app.domain.interfaces.embedding_extractor import IEmbeddingExtractor
from app.domain.exceptions.face_errors import EmbeddingExtractionError

logger = logging.getLogger(__name__)


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
            logger.info(f"Successfully loaded {model_name} model")
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            raise EmbeddingExtractionError(f"Model load failed: {e}")

    async def extract(self, face_image: np.ndarray) -> np.ndarray:
        """Extract face embedding from image.

        Args:
            face_image: Face image as numpy array (H, W, C)

        Returns:
            Face embedding as 1D numpy array (dimension depends on model)

        Raises:
            EmbeddingExtractionError: When extraction fails
        """
        try:
            logger.debug(f"Extracting embedding using {self._model_name}")

            # Extract embedding using DeepFace
            embedding_objs = DeepFace.represent(
                img_path=face_image,
                model_name=self._model_name,
                detector_backend=self._detector_backend,
                enforce_detection=self._enforce_detection,
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

            logger.info(
                f"Successfully extracted {len(embedding_normalized)}-D embedding"
            )

            return embedding_normalized

        except ValueError as e:
            logger.error(f"Embedding extraction failed: {e}")
            raise EmbeddingExtractionError(str(e))

        except Exception as e:
            logger.error(f"Unexpected error during embedding extraction: {e}", exc_info=True)
            raise EmbeddingExtractionError(f"Unexpected error: {e}")

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
