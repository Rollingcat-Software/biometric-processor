"""Factory for creating embedding extractors."""

import logging

from app.domain.interfaces.embedding_extractor import IEmbeddingExtractor
from app.infrastructure.ml.extractors.deepface_extractor import DeepFaceExtractor

logger = logging.getLogger(__name__)


class EmbeddingExtractorFactory:
    """Factory for creating embedding extractor instances.

    Implements Factory Pattern for creating different embedding extractor implementations.
    This allows adding new extractors without modifying client code (Open/Closed Principle).

    Supported Models:
    - VGG-Face: 2622-D, older but reliable
    - Facenet: 128-D, good balance (recommended)
    - Facenet512: 512-D, higher accuracy
    - OpenFace: 128-D, fast
    - DeepFace: 4096-D, Facebook's model
    - DeepID: 160-D
    - ArcFace: 512-D, state-of-the-art
    - Dlib: 128-D
    - SFace: 128-D
    """

    @staticmethod
    def create(model_name: str = "Facenet", **kwargs) -> IEmbeddingExtractor:
        """Create an embedding extractor instance.

        Args:
            model_name: Model name to use for extraction
                Options: "VGG-Face", "Facenet", "Facenet512", "OpenFace",
                        "DeepFace", "DeepID", "ArcFace", "Dlib", "SFace"
            **kwargs: Additional arguments passed to extractor constructor

        Returns:
            Embedding extractor instance implementing IEmbeddingExtractor

        Raises:
            ValueError: If model_name is not supported

        Example:
            ```python
            extractor = EmbeddingExtractorFactory.create("Facenet")
            ```
        """
        logger.info(f"Creating embedding extractor: {model_name}")

        supported_models = [
            "VGG-Face",
            "Facenet",
            "Facenet512",
            "OpenFace",
            "DeepFace",
            "DeepID",
            "ArcFace",
            "Dlib",
            "SFace",
        ]

        if model_name in supported_models:
            return DeepFaceExtractor(model_name=model_name, **kwargs)
        else:
            raise ValueError(
                f"Unsupported model: {model_name}. "
                f"Supported models: {', '.join(supported_models)}"
            )

    @staticmethod
    def get_available_models() -> list[str]:
        """Get list of available model names.

        Returns:
            List of supported model names
        """
        return [
            "VGG-Face",
            "Facenet",
            "Facenet512",
            "OpenFace",
            "DeepFace",
            "DeepID",
            "ArcFace",
            "Dlib",
            "SFace",
        ]

    @staticmethod
    def get_recommended_model() -> str:
        """Get recommended model for production use.

        Returns:
            Recommended model name
        """
        return "Facenet"  # Good balance of accuracy and performance

    @staticmethod
    def get_model_dimension(model_name: str) -> int:
        """Get embedding dimension for a model.

        Args:
            model_name: Model name

        Returns:
            Embedding dimension

        Raises:
            ValueError: If model_name is not supported
        """
        dimensions = {
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

        if model_name not in dimensions:
            raise ValueError(f"Unknown model: {model_name}")

        return dimensions[model_name]
