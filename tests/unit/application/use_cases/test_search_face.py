"""Unit tests for SearchFaceUseCase.

USER-BUG-4 (2026-05-04): /face/search disagreed with /face/verify on the same
input. Root cause was that the search use case extracted an embedding from the
full input frame, while enroll_face.py and verify_face.py both pre-crop with
``detection.get_face_region(image)`` and pass the crop to the extractor.

These tests pin the parity contract: the extractor MUST be invoked with the
cropped face region, not the original frame.
"""

from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pytest

from app.application.use_cases.search_face import SearchFaceUseCase, SearchResult
from app.domain.entities.face_detection import FaceDetectionResult
from app.domain.exceptions.face_errors import FaceNotDetectedError


class TestSearchFaceUseCase:
    """Test SearchFaceUseCase parity with verify/enroll preprocessing."""

    @pytest.mark.asyncio
    async def test_extractor_receives_cropped_face_region_not_full_image(
        self,
        mock_embedding_extractor,
        mock_similarity_calculator,
        mock_embedding_repository,
        temp_image_file,
        sample_embedding,
    ):
        """USER-BUG-4 regression: search must crop face before extracting.

        Asserts that the embedding extractor is called with the bounding-box
        slice of the input image, NOT the full frame. With
        DeepFace ``enforce_detection=False`` set in
        ``DeepFaceExtractor.extract_sync``, passing the full frame produces a
        very different embedding from the one stored at enrollment time
        (which was extracted from a cropped face), so search would never match.
        """
        # Build a 200x200 frame and a detection that picks out the inner
        # 100x100 region at offset (50, 50). face_region must be image[50:150, 50:150].
        full_image = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
        bbox = (50, 50, 100, 100)  # x, y, w, h
        expected_face_region = full_image[50:150, 50:150]

        detection = FaceDetectionResult(
            found=True,
            bounding_box=bbox,
            landmarks=None,
            confidence=0.95,
        )
        detector = Mock()
        detector.detect = AsyncMock(return_value=detection)

        mock_embedding_repository.find_similar = AsyncMock(return_value=[])
        mock_embedding_repository.count = AsyncMock(return_value=0)

        use_case = SearchFaceUseCase(
            detector=detector,
            extractor=mock_embedding_extractor,
            repository=mock_embedding_repository,
            similarity_calculator=mock_similarity_calculator,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = full_image
            await use_case.execute(
                image_path=temp_image_file,
                tenant_id="tenant_xyz",
            )

        # Extractor must have been called exactly once
        mock_embedding_extractor.extract.assert_called_once()
        passed_arg = mock_embedding_extractor.extract.call_args[0][0]

        # The argument must be the cropped face region, not the full frame.
        # Shape check guards against silent fall-through to the full image.
        assert passed_arg.shape == expected_face_region.shape, (
            f"Expected face_region shape {expected_face_region.shape}, "
            f"got {passed_arg.shape}. Search likely passed full image to extractor "
            f"(USER-BUG-4 regression)."
        )
        assert np.array_equal(passed_arg, expected_face_region), (
            "Extractor received different pixels than the bounding-box crop "
            "(USER-BUG-4 regression)."
        )

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_no_face_detected(
        self,
        mock_embedding_extractor,
        mock_similarity_calculator,
        mock_embedding_repository,
        temp_image_file,
    ):
        """Search must raise FaceNotDetectedError when detector returns found=False."""
        detection = FaceDetectionResult(
            found=False,
            bounding_box=None,
            landmarks=None,
            confidence=0.0,
        )
        detector = Mock()
        detector.detect = AsyncMock(return_value=detection)

        use_case = SearchFaceUseCase(
            detector=detector,
            extractor=mock_embedding_extractor,
            repository=mock_embedding_repository,
            similarity_calculator=mock_similarity_calculator,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)

            with pytest.raises(FaceNotDetectedError):
                await use_case.execute(
                    image_path=temp_image_file,
                    tenant_id="tenant_xyz",
                )

        # Extractor must NOT be called when no face is detected
        mock_embedding_extractor.extract.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_forwards_tenant_id_to_repository(
        self,
        mock_embedding_extractor,
        mock_similarity_calculator,
        mock_embedding_repository,
        temp_image_file,
        sample_embedding,
    ):
        """tenant_id must be forwarded to find_similar (defense-in-depth)."""
        full_image = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
        bbox = (10, 10, 80, 80)
        detection = FaceDetectionResult(
            found=True,
            bounding_box=bbox,
            landmarks=None,
            confidence=0.95,
        )
        detector = Mock()
        detector.detect = AsyncMock(return_value=detection)

        mock_embedding_repository.find_similar = AsyncMock(return_value=[])
        mock_embedding_repository.count = AsyncMock(return_value=42)

        use_case = SearchFaceUseCase(
            detector=detector,
            extractor=mock_embedding_extractor,
            repository=mock_embedding_repository,
            similarity_calculator=mock_similarity_calculator,
        )

        with patch("cv2.imread") as mock_imread:
            mock_imread.return_value = full_image
            result = await use_case.execute(
                image_path=temp_image_file,
                tenant_id="tenant_abc",
                max_results=3,
            )

        # find_similar called with tenant_id keyword
        call = mock_embedding_repository.find_similar.call_args
        assert call.kwargs.get("tenant_id") == "tenant_abc", (
            f"Expected tenant_id='tenant_abc' forwarded to find_similar, "
            f"got {call.kwargs.get('tenant_id')}"
        )
        # count is also tenant-scoped
        mock_embedding_repository.count.assert_called_with(tenant_id="tenant_abc")

        assert isinstance(result, SearchResult)
        assert result.total_searched == 42
        assert result.found is False  # empty repository result
