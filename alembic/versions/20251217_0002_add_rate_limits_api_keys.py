"""Add rate_limits and api_keys tables.

Revision ID: 0002_rate_limits_api_keys
Revises: 0001_initial
Create Date: 2025-12-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_rate_limits_api_keys"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add rate_limits and api_keys tables."""

    # Create rate_limits table
    op.create_table(
        "rate_limits",
        sa.Column("key", sa.String(255), primary_key=True),
        sa.Column("count", sa.Integer, nullable=False, default=0),
        sa.Column("window_start", sa.BigInteger, nullable=False),
        sa.Column("tier", sa.String(50), nullable=False, server_default="standard"),
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

    # Create indexes for rate_limits
    op.create_index("ix_rate_limits_window_start", "rate_limits", ["window_start"])
    op.create_index("ix_rate_limits_tier", "rate_limits", ["tier"])

    # Create api_keys table
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("key_prefix", sa.String(8), nullable=False),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("scopes", sa.Text, nullable=False, server_default="read,write"),
        sa.Column("tier", sa.String(50), nullable=False, server_default="standard"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
    )

    # Create indexes for api_keys
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)
    op.create_index("ix_api_keys_key_prefix", "api_keys", ["key_prefix"])
    op.create_index("ix_api_keys_tenant_id", "api_keys", ["tenant_id"])
    op.create_index("ix_api_keys_is_active", "api_keys", ["is_active"])
    op.create_index(
        "ix_api_keys_tenant_active", "api_keys", ["tenant_id", "is_active"]
    )


def downgrade() -> None:
    """Drop rate_limits and api_keys tables."""

    # Drop api_keys indexes and table
    op.drop_index("ix_api_keys_tenant_active", table_name="api_keys")
    op.drop_index("ix_api_keys_is_active", table_name="api_keys")
    op.drop_index("ix_api_keys_tenant_id", table_name="api_keys")
    op.drop_index("ix_api_keys_key_prefix", table_name="api_keys")
    op.drop_index("ix_api_keys_key_hash", table_name="api_keys")
    op.drop_table("api_keys")

    # Drop rate_limits indexes and table
    op.drop_index("ix_rate_limits_tier", table_name="rate_limits")
    op.drop_index("ix_rate_limits_window_start", table_name="rate_limits")
    op.drop_table("rate_limits")
