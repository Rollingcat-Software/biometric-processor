"""Hash-based fingerprint embedding extractor.

Generates a deterministic 256-dimensional embedding from fingerprint image
data using SHA-256 based hashing. This is a placeholder implementation that
allows the full enroll/verify/delete pipeline to work end-to-end without
real fingerprint hardware or an SDK.

When a real fingerprint scanner/SDK is available, replace this class with
one that extracts actual minutiae-based embeddings.

The embedding is L2-normalized so cosine similarity works correctly.
"""

import hashlib
import logging

import numpy as np

logger = logging.getLogger(__name__)

FINGERPRINT_EMBEDDING_DIM = 256


class FingerprintHashEmbedder:
    """Extracts a pseudo-embedding from fingerprint image bytes via SHA-256.

    The same input always produces the same embedding (deterministic),
    and different inputs produce uncorrelated embeddings with high
    probability thanks to the avalanche property of SHA-256.

    Thread Safety:
        Stateless — safe for concurrent use.
    """

    def __init__(self) -> None:
        self._embedding_dim = FINGERPRINT_EMBEDDING_DIM
        logger.info(
            f"FingerprintHashEmbedder initialized (dim={self._embedding_dim})"
        )

    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim

    def extract_embedding(self, image_bytes: bytes) -> np.ndarray:
        """Convert raw fingerprint image bytes to a 256-dim embedding.

        Strategy: hash the image in 256 overlapping windows to produce
        256 float values, then L2-normalize.

        Args:
            image_bytes: Raw fingerprint image content (PNG/JPEG/BMP/raw).

        Returns:
            numpy array of shape (256,) — L2-normalized embedding.

        Raises:
            ValueError: If image_bytes is empty.
        """
        if not image_bytes:
            raise ValueError("Fingerprint image data is empty")

        # Build a 256-dim vector by hashing successive chunks of the input
        # with different salts (the dimension index).
        embedding = np.zeros(self._embedding_dim, dtype=np.float32)

        for i in range(self._embedding_dim):
            h = hashlib.sha256()
            h.update(i.to_bytes(4, "big"))
            h.update(image_bytes)
            # Take first 4 bytes of the digest as an unsigned int, map to [0,1)
            digest = h.digest()
            val = int.from_bytes(digest[:4], "big") / (2**32)
            embedding[i] = val

        # L2-normalize for cosine similarity
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        logger.debug(
            f"Fingerprint embedding extracted: dim={len(embedding)}, "
            f"norm={np.linalg.norm(embedding):.4f}"
        )
        return embedding

    def extract_embedding_from_base64(self, base64_data: str) -> np.ndarray:
        """Extract embedding from a base64-encoded fingerprint image.

        The base64 string may optionally include a data URI prefix
        (e.g. "data:image/png;base64,...").

        Args:
            base64_data: Base64-encoded fingerprint image.

        Returns:
            numpy array of shape (256,).
        """
        import base64

        # Strip data URI prefix if present
        if base64_data.startswith("data:"):
            _, base64_data = base64_data.split(",", 1)

        image_bytes = base64.b64decode(base64_data)

        if len(image_bytes) < 100:
            raise ValueError(
                f"Fingerprint data too small ({len(image_bytes)} bytes). "
                "Please provide a valid fingerprint image."
            )

        return self.extract_embedding(image_bytes)
