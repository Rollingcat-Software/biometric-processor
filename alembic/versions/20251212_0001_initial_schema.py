"""Initial schema - face embeddings and proctoring tables.

Revision ID: 0001_initial
Revises: None
Create Date: 2025-12-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database schema."""

    # Create pgvector extension if available
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Create session_status enum
    op.execute("""
        CREATE TYPE session_status AS ENUM (
            'created', 'started', 'paused', 'completed', 'terminated', 'flagged'
        )
    """)

    # Create incident_type enum
    op.execute("""
        CREATE TYPE incident_type AS ENUM (
            'face_not_detected', 'multiple_faces', 'gaze_away_prolonged',
            'object_detected', 'audio_anomaly', 'tab_switch',
            'screen_share_stopped', 'verification_failed', 'suspicious_behavior',
            'deepfake_detected', 'environment_change', 'network_issue'
        )
    """)

    # Create incident_severity enum
    op.execute("""
        CREATE TYPE incident_severity AS ENUM (
            'low', 'medium', 'high', 'critical'
        )
    """)

    # Create review_action enum
    op.execute("""
        CREATE TYPE review_action AS ENUM (
            'pending', 'dismissed', 'confirmed', 'escalated'
        )
    """)

    # Create face_embeddings table
    op.create_table(
        "face_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("embedding", postgresql.ARRAY(sa.Float), nullable=False),
        sa.Column("embedding_dimension", sa.Integer, nullable=False, default=512),
        sa.Column("model_name", sa.String(100), nullable=False, default="facenet"),
        sa.Column("model_version", sa.String(50), nullable=True),
        sa.Column("quality_score", sa.Float, nullable=False, default=0.0),
        sa.Column("source_image_hash", sa.String(64), nullable=True),
        sa.Column("metadata", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # Create indexes for face_embeddings
    op.create_index("ix_face_embeddings_tenant_id", "face_embeddings", ["tenant_id"])
    op.create_index("ix_face_embeddings_user_id", "face_embeddings", ["user_id"])
    op.create_index(
        "ix_face_embeddings_tenant_user", "face_embeddings", ["tenant_id", "user_id"]
    )
    op.create_index("ix_face_embeddings_active", "face_embeddings", ["is_active"])

    # Create proctor_sessions table
    op.create_table(
        "proctor_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("exam_id", sa.String(255), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("session_status", create_type=False),
            nullable=False,
            server_default="created",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("frame_count", sa.Integer, nullable=False, default=0),
        sa.Column("incident_count", sa.Integer, nullable=False, default=0),
        sa.Column("risk_score", sa.Float, nullable=False, default=0.0),
        sa.Column("integrity_score", sa.Float, nullable=False, default=1.0),
        sa.Column("verification_attempts", sa.Integer, nullable=False, default=0),
        sa.Column("successful_verifications", sa.Integer, nullable=False, default=0),
        sa.Column("config", postgresql.JSONB, nullable=True),
        sa.Column("termination_reason", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # Create indexes for proctor_sessions
    op.create_index("ix_proctor_sessions_tenant_id", "proctor_sessions", ["tenant_id"])
    op.create_index("ix_proctor_sessions_exam_id", "proctor_sessions", ["exam_id"])
    op.create_index("ix_proctor_sessions_user_id", "proctor_sessions", ["user_id"])
    op.create_index(
        "ix_proctor_sessions_tenant_exam", "proctor_sessions", ["tenant_id", "exam_id"]
    )
    op.create_index("ix_proctor_sessions_status", "proctor_sessions", ["status"])
    op.create_index("ix_proctor_sessions_created", "proctor_sessions", ["created_at"])

    # Create proctor_incidents table
    op.create_table(
        "proctor_incidents",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("proctor_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "incident_type",
            postgresql.ENUM("incident_type", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "severity",
            postgresql.ENUM("incident_severity", create_type=False),
            nullable=False,
            server_default="low",
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column("frame_number", sa.Integer, nullable=True),
        sa.Column("risk_contribution", sa.Float, nullable=False, default=0.0),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("details", postgresql.JSONB, nullable=True),
        sa.Column(
            "review_action",
            postgresql.ENUM("review_action", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("reviewed_by", sa.String(255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # Create indexes for proctor_incidents
    op.create_index("ix_proctor_incidents_session_id", "proctor_incidents", ["session_id"])
    op.create_index(
        "ix_proctor_incidents_session_type",
        "proctor_incidents",
        ["session_id", "incident_type"],
    )
    op.create_index("ix_proctor_incidents_severity", "proctor_incidents", ["severity"])
    op.create_index("ix_proctor_incidents_detected", "proctor_incidents", ["detected_at"])

    # Create incident_evidence table
    op.create_table(
        "incident_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "incident_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("proctor_incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("evidence_type", sa.String(50), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=True),
        sa.Column("storage_bucket", sa.String(100), nullable=True),
        sa.Column("data", postgresql.JSONB, nullable=True),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, default=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # Create indexes for incident_evidence
    op.create_index("ix_incident_evidence_incident_id", "incident_evidence", ["incident_id"])


def downgrade() -> None:
    """Drop all tables and types."""

    # Drop tables in reverse order of dependencies
    op.drop_table("incident_evidence")
    op.drop_table("proctor_incidents")
    op.drop_table("proctor_sessions")
    op.drop_table("face_embeddings")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS review_action")
    op.execute("DROP TYPE IF EXISTS incident_severity")
    op.execute("DROP TYPE IF EXISTS incident_type")
    op.execute("DROP TYPE IF EXISTS session_status")
