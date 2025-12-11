"""Similarity matrix API routes."""

from io import BytesIO
from typing import List, Optional

import numpy as np
from fastapi import APIRouter, File, Form, Query, UploadFile
from PIL import Image

from app.core.container import get_compute_similarity_matrix_use_case
from app.domain.entities.similarity_matrix import SimilarityMatrixResponse

router = APIRouter(
    prefix="/similarity",
    tags=["Similarity"],
)


@router.post(
    "/matrix",
    response_model=SimilarityMatrixResponse,
    summary="Compute similarity matrix",
    description=(
        "Computes NxN similarity matrix for multiple face images. "
        "Returns pairwise similarities and face clusters."
    ),
)
async def compute_similarity_matrix(
    files: List[UploadFile] = File(..., description="Face images to compare"),
    labels: Optional[str] = Form(
        default=None,
        description="Comma-separated labels for faces (e.g., 'person_a,person_b,person_c')",
    ),
    threshold: Optional[float] = Query(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Threshold for considering faces as matching",
    ),
) -> SimilarityMatrixResponse:
    """Compute similarity matrix for multiple faces.

    Args:
        files: List of face images
        labels: Optional comma-separated labels
        threshold: Matching threshold

    Returns:
        SimilarityMatrixResponse with matrix and analysis
    """
    # Read all images
    images = []
    for file in files:
        content = await file.read()
        image = Image.open(BytesIO(content)).convert("RGB")
        img_np = np.array(image)
        images.append(img_np)

    # Parse labels
    label_list = None
    if labels:
        label_list = [l.strip() for l in labels.split(",")]
        # Ensure label count matches image count
        if len(label_list) != len(images):
            label_list = None

    # Get use case from container
    use_case = get_compute_similarity_matrix_use_case()

    # Execute computation
    result = await use_case.execute(images, labels=label_list, threshold=threshold)

    return SimilarityMatrixResponse.from_result(result)
