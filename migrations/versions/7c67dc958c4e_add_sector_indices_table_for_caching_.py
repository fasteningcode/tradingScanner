"""Add sector_indices table for caching calculated indices

Revision ID: 7c67dc958c4e
Revises: fce52a7b285b
Create Date: 2025-11-05 22:09:36.413856

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c67dc958c4e'
down_revision = 'fce52a7b285b'
branch_labels = None
depends_on = None


def upgrade():
    # Create sector_indices table
    op.create_table(
        'sector_indices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('index_type', sa.String(length=20), nullable=False),
        sa.Column('sector_id', sa.Integer(), nullable=True),
        sa.Column('subsector_id', sa.Integer(), nullable=True),
        sa.Column('index_value', sa.Float(), nullable=False),
        sa.Column('total_market_cap', sa.Float(), nullable=True),
        sa.Column('stock_count', sa.Integer(), nullable=True),
        sa.Column('change_1d', sa.Float(), nullable=True),
        sa.Column('change_1w', sa.Float(), nullable=True),
        sa.Column('change_1m', sa.Float(), nullable=True),
        sa.Column('calculated_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['sector_id'], ['sectors.id'], ),
        sa.ForeignKeyConstraint(['subsector_id'], ['sub_sectors.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indices for better query performance
    op.create_index(op.f('ix_sector_indices_index_type'), 'sector_indices', ['index_type'], unique=False)
    op.create_index(op.f('ix_sector_indices_sector_id'), 'sector_indices', ['sector_id'], unique=False)
    op.create_index(op.f('ix_sector_indices_subsector_id'), 'sector_indices', ['subsector_id'], unique=False)
    op.create_index(op.f('ix_sector_indices_calculated_at'), 'sector_indices', ['calculated_at'], unique=False)
    op.create_index('idx_sector_index_type', 'sector_indices', ['index_type', 'sector_id', 'subsector_id'], unique=False)


def downgrade():
    # Drop indices
    op.drop_index('idx_sector_index_type', table_name='sector_indices')
    op.drop_index(op.f('ix_sector_indices_calculated_at'), table_name='sector_indices')
    op.drop_index(op.f('ix_sector_indices_subsector_id'), table_name='sector_indices')
    op.drop_index(op.f('ix_sector_indices_sector_id'), table_name='sector_indices')
    op.drop_index(op.f('ix_sector_indices_index_type'), table_name='sector_indices')

    # Drop table
    op.drop_table('sector_indices')
