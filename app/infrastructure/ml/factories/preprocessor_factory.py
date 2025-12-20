"""Image preprocessor factory."""

from app.domain.interfaces.image_preprocessor import IImagePreprocessor


class ImagePreprocessorFactory:
    """Factory for creating image preprocessor instances.

    Follows Open/Closed Principle: Add new preprocessors without modifying existing code.
    """

    @staticmethod
    def create(
        auto_rotate: bool = True,
        max_size: int = 1920,
        normalize: bool = True,
    ) -> IImagePreprocessor:
        """Create image preprocessor instance.

        Args:
            auto_rotate: Whether to auto-rotate based on EXIF
            max_size: Maximum image dimension
            normalize: Whether to apply normalization

        Returns:
            IImagePreprocessor implementation
        """
        from app.infrastructure.ml.preprocessing.image_preprocessor import (
            OpenCVImagePreprocessor,
        )

        return OpenCVImagePreprocessor(
            auto_rotate=auto_rotate,
            max_size=max_size,
            normalize=normalize,
        )
