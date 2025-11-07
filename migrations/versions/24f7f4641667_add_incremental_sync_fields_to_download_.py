"""add_incremental_sync_fields_to_download_task

Revision ID: 24f7f4641667
Revises: 3ffc33d1f6bb
Create Date: 2025-11-07 16:18:45.086594

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '24f7f4641667'
down_revision = '3ffc33d1f6bb'
branch_labels = None
depends_on = None


def upgrade():
    # Add new fields to download_tasks table for incremental sync support
    op.add_column('download_tasks', sa.Column('sync_mode', sa.String(length=20), nullable=True, server_default='full'))
    op.add_column('download_tasks', sa.Column('target_stocks', sa.Text(), nullable=True))
    op.add_column('download_tasks', sa.Column('auto_calculate_index', sa.Boolean(), nullable=True, server_default='0'))

    # Set default values for existing records
    op.execute("UPDATE download_tasks SET sync_mode = 'full' WHERE sync_mode IS NULL")
    op.execute("UPDATE download_tasks SET auto_calculate_index = 0 WHERE auto_calculate_index IS NULL")


def downgrade():
    # Remove the columns added for incremental sync
    op.drop_column('download_tasks', 'auto_calculate_index')
    op.drop_column('download_tasks', 'target_stocks')
    op.drop_column('download_tasks', 'sync_mode')
