"""add volume dryup analysis fields

Revision ID: a1b2c3d4e5f6
Revises: 1cc07932927c
Create Date: 2025-11-08 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '1cc07932927c'
branch_labels = None
depends_on = None


def upgrade():
    # Add volume dry-up analysis fields to instruments table
    with op.batch_alter_table('instruments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('volume_dryup_status', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('volume_ratio_pct', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('consolidation_5d_pct', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('volume_dryup_updated_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('volume_dryup_classification', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('volume_declining_days', sa.Integer(), nullable=True))

        # Add indices for efficient querying
        batch_op.create_index('ix_instruments_volume_dryup_status', ['volume_dryup_status'], unique=False)
        batch_op.create_index('ix_instruments_volume_ratio_pct', ['volume_ratio_pct'], unique=False)

    # Create volume_dryup_tasks table
    op.create_table('volume_dryup_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),

        # Configuration
        sa.Column('min_volume_pct', sa.Float(), nullable=False),
        sa.Column('max_consolidation_pct', sa.Float(), nullable=False),

        # Progress tracking
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('progress_percentage', sa.Float(), nullable=False),
        sa.Column('total_stocks', sa.Integer(), nullable=False),
        sa.Column('analyzed_stocks', sa.Integer(), nullable=False),
        sa.Column('qualified_stocks', sa.Integer(), nullable=False),
        sa.Column('failed_stocks', sa.Integer(), nullable=False),
        sa.Column('current_stock_symbol', sa.String(length=50), nullable=True),

        # Timestamps
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),

        # Error handling
        sa.Column('error_message', sa.Text(), nullable=True),

        # Constraints
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indices
    with op.batch_alter_table('volume_dryup_tasks', schema=None) as batch_op:
        batch_op.create_index('ix_volume_dryup_tasks_user_id', ['user_id'], unique=False)
        batch_op.create_index('ix_volume_dryup_tasks_status', ['status'], unique=False)


def downgrade():
    # Drop volume_dryup_tasks table
    op.drop_table('volume_dryup_tasks')

    # Remove volume dry-up fields from instruments table
    with op.batch_alter_table('instruments', schema=None) as batch_op:
        batch_op.drop_index('ix_instruments_volume_ratio_pct')
        batch_op.drop_index('ix_instruments_volume_dryup_status')
        batch_op.drop_column('volume_declining_days')
        batch_op.drop_column('volume_dryup_classification')
        batch_op.drop_column('volume_dryup_updated_at')
        batch_op.drop_column('consolidation_5d_pct')
        batch_op.drop_column('volume_ratio_pct')
        batch_op.drop_column('volume_dryup_status')
