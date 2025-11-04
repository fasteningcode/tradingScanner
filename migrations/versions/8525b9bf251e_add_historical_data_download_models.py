"""Add historical data download models

Revision ID: 8525b9bf251e
Revises: 7cd284eab3f2
Create Date: 2025-11-04 19:54:52.719651

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8525b9bf251e'
down_revision = '7cd284eab3f2'
branch_labels = None
depends_on = None


def upgrade():
    # Create historical_data table
    op.create_table('historical_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('instrument_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('interval', sa.String(length=20), nullable=False),
        sa.Column('open', sa.Float(), nullable=False),
        sa.Column('high', sa.Float(), nullable=False),
        sa.Column('low', sa.Float(), nullable=False),
        sa.Column('close', sa.Float(), nullable=False),
        sa.Column('volume', sa.Integer(), nullable=True),
        sa.Column('oi', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['instrument_id'], ['instruments.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('instrument_id', 'timestamp', 'interval', name='uq_instrument_timestamp_interval')
    )
    op.create_index(op.f('ix_historical_data_instrument_id'), 'historical_data', ['instrument_id'], unique=False)
    op.create_index(op.f('ix_historical_data_interval'), 'historical_data', ['interval'], unique=False)
    op.create_index(op.f('ix_historical_data_timestamp'), 'historical_data', ['timestamp'], unique=False)
    op.create_index('ix_historical_data_lookup', 'historical_data', ['instrument_id', 'interval', 'timestamp'], unique=False)

    # Create download_tasks table
    op.create_table('download_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('interval', sa.String(length=20), nullable=False),
        sa.Column('from_date', sa.Date(), nullable=False),
        sa.Column('to_date', sa.Date(), nullable=False),
        sa.Column('requests_per_second', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('progress_percentage', sa.Float(), nullable=True),
        sa.Column('total_stocks', sa.Integer(), nullable=True),
        sa.Column('completed_stocks', sa.Integer(), nullable=True),
        sa.Column('failed_stocks', sa.Integer(), nullable=True),
        sa.Column('skipped_stocks', sa.Integer(), nullable=True),
        sa.Column('current_stock_symbol', sa.String(length=50), nullable=True),
        sa.Column('current_stock_id', sa.Integer(), nullable=True),
        sa.Column('total_records_downloaded', sa.Integer(), nullable=True),
        sa.Column('total_api_calls', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('paused_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_download_tasks_status'), 'download_tasks', ['status'], unique=False)
    op.create_index(op.f('ix_download_tasks_user_id'), 'download_tasks', ['user_id'], unique=False)

    # Create download_logs table
    op.create_table('download_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('instrument_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('records_downloaded', sa.Integer(), nullable=True),
        sa.Column('api_calls_made', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['instrument_id'], ['instruments.id'], ),
        sa.ForeignKeyConstraint(['task_id'], ['download_tasks.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_download_logs_instrument_id'), 'download_logs', ['instrument_id'], unique=False)
    op.create_index(op.f('ix_download_logs_task_id'), 'download_logs', ['task_id'], unique=False)


def downgrade():
    # Drop tables in reverse order
    op.drop_index(op.f('ix_download_logs_task_id'), table_name='download_logs')
    op.drop_index(op.f('ix_download_logs_instrument_id'), table_name='download_logs')
    op.drop_table('download_logs')

    op.drop_index(op.f('ix_download_tasks_user_id'), table_name='download_tasks')
    op.drop_index(op.f('ix_download_tasks_status'), table_name='download_tasks')
    op.drop_table('download_tasks')

    op.drop_index('ix_historical_data_lookup', table_name='historical_data')
    op.drop_index(op.f('ix_historical_data_timestamp'), table_name='historical_data')
    op.drop_index(op.f('ix_historical_data_interval'), table_name='historical_data')
    op.drop_index(op.f('ix_historical_data_instrument_id'), table_name='historical_data')
    op.drop_table('historical_data')
