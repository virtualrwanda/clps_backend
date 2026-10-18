"""Add persisted email OTP login challenges."""

from alembic import op
import sqlalchemy as sa


revision = "20261013_01"
down_revision = "20261012_00"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_otps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_login_otps_user", "login_otps", ["user_id"])
    op.create_index("ix_login_otps_expires_at", "login_otps", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_login_otps_expires_at", table_name="login_otps")
    op.drop_index("ix_login_otps_user", table_name="login_otps")
    op.drop_table("login_otps")