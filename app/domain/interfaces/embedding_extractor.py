"""Embedding extractor interface following Interface Segregation Principle."""

from typing import Protocol
import numpy as np


class IEmbeddingExtractor(Protocol):
    """Protocol for face embedding extraction implementations.

    Implementations can use different models (FaceNet, ArcFace, VGGFace, etc.)
    without changing client code (Open/Closed Principle).
    """

    async def extract(self, face_image: np.ndarray) -> np.ndarray:
        """Extract face embedding from aligned face image.

        Args:
            face_image: Aligned and cropped face image as numpy array (H, W, C)

        Returns:
            Face embedding as 1D numpy array (typically 128-D or 512-D)
            The embedding is L2-normalized for cosine similarity comparison

        Raises:
            EmbeddingExtractionError: When embedding extraction fails

        Note:
            Input should be a properly aligned and cropped face region.
            The output dimension depends on the model used.
        """
        ...

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this extractor.

        Returns:
            Embedding dimension (e.g., 128 for FaceNet, 512 for ArcFace)
        """
        ...
