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

    # Create biometric_data table (matches pgvector repository schema)
    # This table stores face embeddings as vectors for efficient similarity search
    op.create_table(
        "biometric_data",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=True),  # Nullable for single-tenant mode
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("biometric_type", sa.String(50), nullable=False, server_default="FACE"),  # FACE, FINGERPRINT, etc.
        sa.Column("embedding_model", sa.String(100), nullable=False, server_default="Facenet512"),
        sa.Column("quality_score", sa.Float, nullable=False, default=0.0),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column("is_primary", sa.Boolean, nullable=False, default=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),  # For soft delete
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

    # Add embedding column as vector type (requires pgvector extension)
    # Note: Column is added separately because SQLAlchemy doesn't have native vector type
    op.execute("""
        ALTER TABLE biometric_data
        ADD COLUMN embedding vector(512);
    """)

    # Create unique constraint for active embeddings (prevents duplicate enrollments)
    # Uses partial index to allow multiple soft-deleted records
    op.execute("""
        CREATE UNIQUE INDEX ix_biometric_data_user_tenant_type_active
        ON biometric_data (user_id, tenant_id, biometric_type)
        WHERE deleted_at IS NULL;
    """)

    # Create indexes for biometric_data (optimized for common queries)
    op.create_index("ix_biometric_data_tenant_id", "biometric_data", ["tenant_id"])
    op.create_index("ix_biometric_data_user_id", "biometric_data", ["user_id"])
    op.create_index(
        "ix_biometric_data_tenant_user", "biometric_data", ["tenant_id", "user_id"]
    )
    op.create_index("ix_biometric_data_active", "biometric_data", ["is_active"])
    op.create_index("ix_biometric_data_type", "biometric_data", ["biometric_type"])

    # Create HNSW vector index for fast similarity search
    # HNSW (Hierarchical Navigable Small World) provides excellent query performance
    # Parameters: m=16 (connections per layer), ef_construction=64 (build-time accuracy)
    # This index enables sub-second similarity search even with millions of faces
    op.execute("""
        CREATE INDEX ix_biometric_data_embedding_hnsw
        ON biometric_data
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)

    # Alternative: IVFFlat index (uncomment if HNSW is too slow to build for large datasets)
    # IVFFlat is faster to build but provides lower query accuracy
    # op.execute("""
    #     CREATE INDEX ix_biometric_data_embedding_ivfflat
    #     ON biometric_data
    #     USING ivfflat (embedding vector_cosine_ops)
    #     WITH (lists = 100);
    # """)

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
    op.drop_table("biometric_data")  # Updated to match new table name

    # Drop enums
    op.execute("DROP TYPE IF EXISTS review_action")
    op.execute("DROP TYPE IF EXISTS incident_severity")
    op.execute("DROP TYPE IF EXISTS incident_type")
    op.execute("DROP TYPE IF EXISTS session_status")

    # Note: pgvector extension is not dropped to avoid affecting other databases
    # If you need to remove it: DROP EXTENSION IF EXISTS vector CASCADE;
