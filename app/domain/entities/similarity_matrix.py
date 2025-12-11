"""Similarity matrix domain entities."""

from dataclasses import dataclass, field
from typing import List

from pydantic import BaseModel


@dataclass
class SimilarityPair:
    """Similarity between two faces.

    Attributes:
        a: First face label
        b: Second face label
        similarity: Similarity score (0.0-1.0)
        match: Whether faces match
    """

    a: str
    b: str
    similarity: float
    match: bool


@dataclass
class Cluster:
    """Cluster of similar faces.

    Attributes:
        cluster_id: Cluster identifier
        members: List of face labels in cluster
    """

    cluster_id: int
    members: List[str]


@dataclass
class SimilarityMatrixResult:
    """Similarity matrix computation result.

    Attributes:
        size: Matrix size (N x N)
        labels: Face labels
        matrix: Similarity matrix values
        clusters: Detected face clusters
        pairs: All pairwise comparisons
        threshold: Threshold used for matching
        computation_time_ms: Time taken to compute
    """

    size: int
    labels: List[str] = field(default_factory=list)
    matrix: List[List[float]] = field(default_factory=list)
    clusters: List[Cluster] = field(default_factory=list)
    pairs: List[SimilarityPair] = field(default_factory=list)
    threshold: float = 0.6
    computation_time_ms: int = 0


# Pydantic models for API responses


class SimilarityPairResponse(BaseModel):
    """API response model for similarity pair."""

    a: str
    b: str
    similarity: float
    match: bool


class ClusterResponse(BaseModel):
    """API response model for cluster."""

    cluster_id: int
    members: List[str]


class SimilarityMatrixResponse(BaseModel):
    """API response model for similarity matrix."""

    size: int
    labels: List[str]
    matrix: List[List[float]]
    clusters: List[ClusterResponse]
    pairs: List[SimilarityPairResponse]
    threshold: float
    computation_time_ms: int

    @classmethod
    def from_result(cls, result: SimilarityMatrixResult) -> "SimilarityMatrixResponse":
        """Create response from domain result."""
        return cls(
            size=result.size,
            labels=result.labels,
            matrix=result.matrix,
            clusters=[
                ClusterResponse(cluster_id=c.cluster_id, members=c.members)
                for c in result.clusters
            ],
            pairs=[
                SimilarityPairResponse(
                    a=p.a, b=p.b, similarity=p.similarity, match=p.match
                )
                for p in result.pairs
            ],
            threshold=result.threshold,
            computation_time_ms=result.computation_time_ms,
        )
