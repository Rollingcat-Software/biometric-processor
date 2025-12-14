"""Compute similarity matrix use case."""

import logging
import time
from typing import List, Optional

import numpy as np

from app.domain.entities.similarity_matrix import (
    Cluster,
    SimilarityMatrixResult,
    SimilarityPair,
)
from app.domain.exceptions.face_errors import FaceNotFoundError
from app.domain.interfaces.embedding_extractor import IEmbeddingExtractor
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.similarity_calculator import ISimilarityCalculator

logger = logging.getLogger(__name__)


class ComputeSimilarityMatrixUseCase:
    """Use case for computing NxN similarity matrix.

    Compares multiple faces and returns pairwise similarities
    with optional clustering.
    """

    def __init__(
        self,
        detector: IFaceDetector,
        extractor: IEmbeddingExtractor,
        similarity_calculator: ISimilarityCalculator,
    ) -> None:
        """Initialize similarity matrix use case.

        Args:
            detector: Face detector implementation
            extractor: Embedding extractor implementation
            similarity_calculator: Similarity calculator implementation
        """
        self._detector = detector
        self._extractor = extractor
        self._similarity_calculator = similarity_calculator
        logger.info("ComputeSimilarityMatrixUseCase initialized")

    async def execute(
        self,
        images: List[np.ndarray],
        labels: Optional[List[str]] = None,
        threshold: float = 0.6,
    ) -> SimilarityMatrixResult:
        """Execute similarity matrix computation.

        Args:
            images: List of face images
            labels: Optional labels for each image
            threshold: Threshold for considering faces as matching

        Returns:
            SimilarityMatrixResult with matrix and analysis
        """
        start_time = time.time()
        logger.info(f"Starting similarity matrix computation for {len(images)} images")

        n = len(images)
        if n == 0:
            return SimilarityMatrixResult(size=0, threshold=threshold)

        # Generate default labels if not provided
        if labels is None:
            labels = [f"face_{i}" for i in range(n)]

        # Extract embeddings for all images
        embeddings = []
        for i, image in enumerate(images):
            detection = await self._detector.detect(image)
            if not detection.found:
                raise FaceNotFoundError(f"No face detected in image {labels[i]}")

            # Extract face region and get embedding
            face_region = detection.get_face_region(image)
            embedding = await self._extractor.extract(face_region)
            embeddings.append(embedding)

        # Compute similarity matrix
        matrix = self._compute_matrix(embeddings)

        # Generate pairs
        pairs = self._generate_pairs(labels, matrix, threshold)

        # Cluster similar faces
        clusters = self._cluster_faces(labels, matrix, threshold)

        computation_time = int((time.time() - start_time) * 1000)

        result = SimilarityMatrixResult(
            size=n,
            labels=labels,
            matrix=matrix,
            clusters=clusters,
            pairs=pairs,
            threshold=threshold,
            computation_time_ms=computation_time,
        )

        logger.info(
            f"Similarity matrix computed: {n}x{n}, "
            f"{len(clusters)} clusters, {computation_time}ms"
        )

        return result

    def _compute_matrix(self, embeddings: List[np.ndarray]) -> List[List[float]]:
        """Compute NxN similarity matrix."""
        n = len(embeddings)
        matrix = [[0.0] * n for _ in range(n)]

        for i in range(n):
            for j in range(n):
                if i == j:
                    matrix[i][j] = 1.0
                elif i < j:
                    # calculate() returns distance (lower = more similar)
                    distance = self._similarity_calculator.calculate(
                        embeddings[i], embeddings[j]
                    )
                    # Convert distance to similarity (higher = more similar)
                    similarity = round(max(0.0, 1.0 - distance), 4)
                    matrix[i][j] = similarity
                    matrix[j][i] = similarity

        return matrix

    def _generate_pairs(
        self, labels: List[str], matrix: List[List[float]], threshold: float
    ) -> List[SimilarityPair]:
        """Generate all unique pairs with similarity scores."""
        pairs = []
        n = len(labels)

        for i in range(n):
            for j in range(i + 1, n):
                similarity = matrix[i][j]
                pairs.append(
                    SimilarityPair(
                        a=labels[i],
                        b=labels[j],
                        similarity=similarity,
                        match=similarity >= threshold,
                    )
                )

        # Sort by similarity descending
        pairs.sort(key=lambda p: p.similarity, reverse=True)
        return pairs

    def _cluster_faces(
        self, labels: List[str], matrix: List[List[float]], threshold: float
    ) -> List[Cluster]:
        """Cluster similar faces using union-find."""
        n = len(labels)
        parent = list(range(n))

        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        # Union faces that match
        for i in range(n):
            for j in range(i + 1, n):
                if matrix[i][j] >= threshold:
                    union(i, j)

        # Group by cluster
        cluster_map = {}
        for i in range(n):
            root = find(i)
            if root not in cluster_map:
                cluster_map[root] = []
            cluster_map[root].append(labels[i])

        # Create cluster objects
        clusters = [
            Cluster(cluster_id=idx, members=members)
            for idx, members in enumerate(cluster_map.values())
        ]

        return clusters
