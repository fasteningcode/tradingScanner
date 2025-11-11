"""add aligned breakout strategy tables

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2025-11-09 19:22:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7c8d9e0f1a2'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # Create aligned_breakout_profiles table
    op.create_table('aligned_breakout_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),

        # Sector Alignment Criteria
        sa.Column('sector_stage', sa.Integer(), nullable=True),
        sa.Column('sector_max_weeks_in_stage', sa.Integer(), nullable=True),
        sa.Column('sector_rs_min', sa.Float(), nullable=True),
        sa.Column('subsector_rs_min', sa.Float(), nullable=True),

        # Stock Stage Criteria
        sa.Column('stock_stage', sa.Integer(), nullable=True),
        sa.Column('stock_max_weeks_in_stage', sa.Integer(), nullable=True),
        sa.Column('price_above_150ma', sa.Boolean(), nullable=True),
        sa.Column('ma_150_slope_min', sa.Float(), nullable=True),
        sa.Column('distance_from_52w_high_min', sa.Float(), nullable=True),
        sa.Column('distance_from_52w_high_max', sa.Float(), nullable=True),

        # Volume Confirmation Criteria
        sa.Column('breakout_volume_min_pct', sa.Float(), nullable=True),
        sa.Column('accumulation_days', sa.Integer(), nullable=True),

        # Relative Strength Criteria
        sa.Column('stock_rs_vs_sector_min', sa.Float(), nullable=True),
        sa.Column('stock_rs_vs_subsector_min', sa.Float(), nullable=True),
        sa.Column('stock_rs_vs_nifty50_min', sa.Float(), nullable=True),
        sa.Column('rs_trend_weeks', sa.Integer(), nullable=True),
        sa.Column('rs_trend_direction', sa.String(length=20), nullable=True),

        # Scoring Weights
        sa.Column('weight_sector_alignment', sa.Float(), nullable=True),
        sa.Column('weight_stock_stage', sa.Float(), nullable=True),
        sa.Column('weight_volume', sa.Float(), nullable=True),
        sa.Column('weight_rs', sa.Float(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),

        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    with op.batch_alter_table('aligned_breakout_profiles', schema=None) as batch_op:
        batch_op.create_index('ix_aligned_breakout_profiles_name', ['name'], unique=True)
        batch_op.create_index('ix_aligned_breakout_profiles_is_active', ['is_active'], unique=False)

    # Create aligned_breakout_scan_results table
    op.create_table('aligned_breakout_scan_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('total_stocks_scanned', sa.Integer(), nullable=True),
        sa.Column('matched_stocks', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),

        sa.ForeignKeyConstraint(['profile_id'], ['aligned_breakout_profiles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    with op.batch_alter_table('aligned_breakout_scan_results', schema=None) as batch_op:
        batch_op.create_index('ix_aligned_breakout_scan_results_profile_id', ['profile_id'], unique=False)
        batch_op.create_index('ix_aligned_breakout_scan_results_status', ['status'], unique=False)
        batch_op.create_index('ix_aligned_breakout_scan_results_created_at', ['created_at'], unique=False)

    # Create aligned_breakout_stock_metrics table
    op.create_table('aligned_breakout_stock_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('instrument_id', sa.Integer(), nullable=False),
        sa.Column('week_52_high', sa.Float(), nullable=True),
        sa.Column('week_52_low', sa.Float(), nullable=True),
        sa.Column('week_52_high_date', sa.Date(), nullable=True),
        sa.Column('week_52_low_date', sa.Date(), nullable=True),
        sa.Column('distance_from_52w_high_pct', sa.Float(), nullable=True),
        sa.Column('ma_150_value', sa.Float(), nullable=True),
        sa.Column('ma_150_slope', sa.Float(), nullable=True),
        sa.Column('rs_vs_nifty50', sa.Float(), nullable=True),
        sa.Column('rs_vs_nifty50_trend', sa.String(length=20), nullable=True),
        sa.Column('current_stage', sa.Integer(), nullable=True),
        sa.Column('stage_entry_date', sa.Date(), nullable=True),
        sa.Column('weeks_in_stage', sa.Integer(), nullable=True),
        sa.Column('avg_volume_50d', sa.BigInteger(), nullable=True),
        sa.Column('last_volume', sa.BigInteger(), nullable=True),
        sa.Column('volume_breakout_detected', sa.Boolean(), nullable=True),
        sa.Column('accumulation_pattern_days', sa.Integer(), nullable=True),
        sa.Column('calculated_at', sa.DateTime(), nullable=True),

        sa.ForeignKeyConstraint(['instrument_id'], ['instruments.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('instrument_id')
    )

    with op.batch_alter_table('aligned_breakout_stock_metrics', schema=None) as batch_op:
        batch_op.create_index('ix_aligned_breakout_stock_metrics_instrument_id', ['instrument_id'], unique=True)
        batch_op.create_index('ix_aligned_breakout_stock_metrics_distance_from_52w_high_pct', ['distance_from_52w_high_pct'], unique=False)
        batch_op.create_index('ix_aligned_breakout_stock_metrics_ma_150_slope', ['ma_150_slope'], unique=False)
        batch_op.create_index('ix_aligned_breakout_stock_metrics_rs_vs_nifty50', ['rs_vs_nifty50'], unique=False)
        batch_op.create_index('ix_aligned_breakout_stock_metrics_current_stage', ['current_stage'], unique=False)
        batch_op.create_index('ix_aligned_breakout_stock_metrics_weeks_in_stage', ['weeks_in_stage'], unique=False)
        batch_op.create_index('ix_aligned_breakout_stock_metrics_volume_breakout_detected', ['volume_breakout_detected'], unique=False)
        batch_op.create_index('ix_aligned_breakout_stock_metrics_calculated_at', ['calculated_at'], unique=False)

    # Create aligned_breakout_sector_metrics table
    op.create_table('aligned_breakout_sector_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=20), nullable=False),
        sa.Column('sector_id', sa.Integer(), nullable=True),
        sa.Column('subsector_id', sa.Integer(), nullable=True),
        sa.Column('rs_vs_nifty50', sa.Float(), nullable=True),
        sa.Column('rs_vs_nifty50_trend', sa.String(length=20), nullable=True),
        sa.Column('current_stage', sa.Integer(), nullable=True),
        sa.Column('stage_entry_date', sa.Date(), nullable=True),
        sa.Column('weeks_in_stage', sa.Integer(), nullable=True),
        sa.Column('calculated_at', sa.DateTime(), nullable=True),

        sa.ForeignKeyConstraint(['sector_id'], ['sectors.id'], ),
        sa.ForeignKeyConstraint(['subsector_id'], ['sub_sectors.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entity_type', 'sector_id', 'subsector_id', name='uq_entity_sector_subsector')
    )

    with op.batch_alter_table('aligned_breakout_sector_metrics', schema=None) as batch_op:
        batch_op.create_index('ix_aligned_breakout_sector_metrics_entity_type', ['entity_type'], unique=False)
        batch_op.create_index('ix_aligned_breakout_sector_metrics_sector_id', ['sector_id'], unique=False)
        batch_op.create_index('ix_aligned_breakout_sector_metrics_subsector_id', ['subsector_id'], unique=False)
        batch_op.create_index('ix_aligned_breakout_sector_metrics_rs_vs_nifty50', ['rs_vs_nifty50'], unique=False)
        batch_op.create_index('ix_aligned_breakout_sector_metrics_current_stage', ['current_stage'], unique=False)
        batch_op.create_index('ix_aligned_breakout_sector_metrics_weeks_in_stage', ['weeks_in_stage'], unique=False)
        batch_op.create_index('ix_aligned_breakout_sector_metrics_calculated_at', ['calculated_at'], unique=False)
        batch_op.create_index('idx_entity_lookup', ['entity_type', 'sector_id', 'subsector_id'], unique=False)

    # Create aligned_breakout_watchlist table
    op.create_table('aligned_breakout_watchlist',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scan_result_id', sa.Integer(), nullable=False),
        sa.Column('instrument_id', sa.Integer(), nullable=False),
        sa.Column('tradingsymbol', sa.String(length=50), nullable=False),
        sa.Column('sector_name', sa.String(length=100), nullable=True),
        sa.Column('subsector_name', sa.String(length=100), nullable=True),
        sa.Column('score_sector_alignment', sa.Float(), nullable=True),
        sa.Column('score_stock_stage', sa.Float(), nullable=True),
        sa.Column('score_volume', sa.Float(), nullable=True),
        sa.Column('score_rs', sa.Float(), nullable=True),
        sa.Column('score_total', sa.Float(), nullable=True),
        sa.Column('current_price', sa.Float(), nullable=True),
        sa.Column('distance_from_52w_high_pct', sa.Float(), nullable=True),
        sa.Column('rs_vs_nifty50', sa.Float(), nullable=True),
        sa.Column('rs_vs_sector', sa.Float(), nullable=True),
        sa.Column('rs_vs_subsector', sa.Float(), nullable=True),
        sa.Column('volume_ratio_pct', sa.Float(), nullable=True),
        sa.Column('passed_sector_stage', sa.Boolean(), nullable=True),
        sa.Column('passed_sector_rs', sa.Boolean(), nullable=True),
        sa.Column('passed_stock_stage', sa.Boolean(), nullable=True),
        sa.Column('passed_volume', sa.Boolean(), nullable=True),
        sa.Column('passed_rs', sa.Boolean(), nullable=True),
        sa.Column('added_at', sa.DateTime(), nullable=True),

        sa.ForeignKeyConstraint(['scan_result_id'], ['aligned_breakout_scan_results.id'], ),
        sa.ForeignKeyConstraint(['instrument_id'], ['instruments.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scan_result_id', 'instrument_id', name='uq_scan_instrument')
    )

    with op.batch_alter_table('aligned_breakout_watchlist', schema=None) as batch_op:
        batch_op.create_index('ix_aligned_breakout_watchlist_scan_result_id', ['scan_result_id'], unique=False)
        batch_op.create_index('ix_aligned_breakout_watchlist_instrument_id', ['instrument_id'], unique=False)
        batch_op.create_index('ix_aligned_breakout_watchlist_tradingsymbol', ['tradingsymbol'], unique=False)
        batch_op.create_index('ix_aligned_breakout_watchlist_score_total', ['score_total'], unique=False)
        batch_op.create_index('ix_aligned_breakout_watchlist_added_at', ['added_at'], unique=False)
        batch_op.create_index('idx_watchlist_score', ['scan_result_id', 'score_total'], unique=False)

    # Create aligned_breakout_stage_transitions table
    op.create_table('aligned_breakout_stage_transitions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=20), nullable=False),
        sa.Column('instrument_id', sa.Integer(), nullable=True),
        sa.Column('sector_id', sa.Integer(), nullable=True),
        sa.Column('subsector_id', sa.Integer(), nullable=True),
        sa.Column('from_stage', sa.Integer(), nullable=True),
        sa.Column('to_stage', sa.Integer(), nullable=False),
        sa.Column('transition_date', sa.Date(), nullable=False),
        sa.Column('stage_confidence', sa.Float(), nullable=True),
        sa.Column('price_at_transition', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),

        sa.ForeignKeyConstraint(['instrument_id'], ['instruments.id'], ),
        sa.ForeignKeyConstraint(['sector_id'], ['sectors.id'], ),
        sa.ForeignKeyConstraint(['subsector_id'], ['sub_sectors.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    with op.batch_alter_table('aligned_breakout_stage_transitions', schema=None) as batch_op:
        batch_op.create_index('ix_aligned_breakout_stage_transitions_entity_type', ['entity_type'], unique=False)
        batch_op.create_index('ix_aligned_breakout_stage_transitions_instrument_id', ['instrument_id'], unique=False)
        batch_op.create_index('ix_aligned_breakout_stage_transitions_sector_id', ['sector_id'], unique=False)
        batch_op.create_index('ix_aligned_breakout_stage_transitions_subsector_id', ['subsector_id'], unique=False)
        batch_op.create_index('ix_aligned_breakout_stage_transitions_to_stage', ['to_stage'], unique=False)
        batch_op.create_index('ix_aligned_breakout_stage_transitions_transition_date', ['transition_date'], unique=False)
        batch_op.create_index('idx_transition_lookup', ['entity_type', 'instrument_id', 'sector_id', 'subsector_id', 'transition_date'], unique=False)

    # Create aligned_breakout_rs_history table
    op.create_table('aligned_breakout_rs_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=20), nullable=False),
        sa.Column('instrument_id', sa.Integer(), nullable=True),
        sa.Column('sector_id', sa.Integer(), nullable=True),
        sa.Column('subsector_id', sa.Integer(), nullable=True),
        sa.Column('rs_vs_nifty50', sa.Float(), nullable=True),
        sa.Column('rs_vs_sector', sa.Float(), nullable=True),
        sa.Column('rs_vs_subsector', sa.Float(), nullable=True),
        sa.Column('calculated_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),

        sa.ForeignKeyConstraint(['instrument_id'], ['instruments.id'], ),
        sa.ForeignKeyConstraint(['sector_id'], ['sectors.id'], ),
        sa.ForeignKeyConstraint(['subsector_id'], ['sub_sectors.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entity_type', 'instrument_id', 'sector_id', 'subsector_id', 'calculated_date', name='uq_rs_entity_date')
    )

    with op.batch_alter_table('aligned_breakout_rs_history', schema=None) as batch_op:
        batch_op.create_index('ix_aligned_breakout_rs_history_entity_type', ['entity_type'], unique=False)
        batch_op.create_index('ix_aligned_breakout_rs_history_instrument_id', ['instrument_id'], unique=False)
        batch_op.create_index('ix_aligned_breakout_rs_history_sector_id', ['sector_id'], unique=False)
        batch_op.create_index('ix_aligned_breakout_rs_history_subsector_id', ['subsector_id'], unique=False)
        batch_op.create_index('ix_aligned_breakout_rs_history_calculated_date', ['calculated_date'], unique=False)
        batch_op.create_index('idx_rs_lookup', ['entity_type', 'instrument_id', 'sector_id', 'subsector_id', 'calculated_date'], unique=False)

    # Create aligned_breakout_volume_events table
    op.create_table('aligned_breakout_volume_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('instrument_id', sa.Integer(), nullable=False),
        sa.Column('event_date', sa.Date(), nullable=False),
        sa.Column('event_type', sa.String(length=20), nullable=False),
        sa.Column('volume', sa.BigInteger(), nullable=True),
        sa.Column('volume_ratio_pct', sa.Float(), nullable=True),
        sa.Column('price_at_event', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),

        sa.ForeignKeyConstraint(['instrument_id'], ['instruments.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    with op.batch_alter_table('aligned_breakout_volume_events', schema=None) as batch_op:
        batch_op.create_index('ix_aligned_breakout_volume_events_instrument_id', ['instrument_id'], unique=False)
        batch_op.create_index('ix_aligned_breakout_volume_events_event_date', ['event_date'], unique=False)
        batch_op.create_index('idx_volume_event_lookup', ['instrument_id', 'event_date', 'event_type'], unique=False)

    # Create aligned_breakout_52week_tracking table
    op.create_table('aligned_breakout_52week_tracking',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('instrument_id', sa.Integer(), nullable=False),
        sa.Column('week_52_high', sa.Float(), nullable=True),
        sa.Column('week_52_low', sa.Float(), nullable=True),
        sa.Column('week_52_high_date', sa.Date(), nullable=True),
        sa.Column('week_52_low_date', sa.Date(), nullable=True),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),

        sa.ForeignKeyConstraint(['instrument_id'], ['instruments.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('instrument_id', 'snapshot_date', name='uq_52week_instrument_date')
    )

    with op.batch_alter_table('aligned_breakout_52week_tracking', schema=None) as batch_op:
        batch_op.create_index('ix_aligned_breakout_52week_tracking_instrument_id', ['instrument_id'], unique=False)
        batch_op.create_index('ix_aligned_breakout_52week_tracking_snapshot_date', ['snapshot_date'], unique=False)
        batch_op.create_index('idx_52week_lookup', ['instrument_id', 'snapshot_date'], unique=False)

    # Create aligned_breakout_ma_calculations table
    op.create_table('aligned_breakout_ma_calculations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('instrument_id', sa.Integer(), nullable=False),
        sa.Column('ma_150_value', sa.Float(), nullable=True),
        sa.Column('ma_150_slope', sa.Float(), nullable=True),
        sa.Column('calculated_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),

        sa.ForeignKeyConstraint(['instrument_id'], ['instruments.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('instrument_id', 'calculated_date', name='uq_ma_instrument_date')
    )

    with op.batch_alter_table('aligned_breakout_ma_calculations', schema=None) as batch_op:
        batch_op.create_index('ix_aligned_breakout_ma_calculations_instrument_id', ['instrument_id'], unique=False)
        batch_op.create_index('ix_aligned_breakout_ma_calculations_calculated_date', ['calculated_date'], unique=False)
        batch_op.create_index('idx_ma_lookup', ['instrument_id', 'calculated_date'], unique=False)

    # Create aligned_breakout_scan_snapshots table
    op.create_table('aligned_breakout_scan_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scan_result_id', sa.Integer(), nullable=False),
        sa.Column('snapshot_data', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),

        sa.ForeignKeyConstraint(['scan_result_id'], ['aligned_breakout_scan_results.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    with op.batch_alter_table('aligned_breakout_scan_snapshots', schema=None) as batch_op:
        batch_op.create_index('ix_aligned_breakout_scan_snapshots_scan_result_id', ['scan_result_id'], unique=False)
        batch_op.create_index('ix_aligned_breakout_scan_snapshots_created_at', ['created_at'], unique=False)


def downgrade():
    # Drop tables in reverse order (respecting foreign key constraints)
    op.drop_table('aligned_breakout_scan_snapshots')
    op.drop_table('aligned_breakout_ma_calculations')
    op.drop_table('aligned_breakout_52week_tracking')
    op.drop_table('aligned_breakout_volume_events')
    op.drop_table('aligned_breakout_rs_history')
    op.drop_table('aligned_breakout_stage_transitions')
    op.drop_table('aligned_breakout_watchlist')
    op.drop_table('aligned_breakout_sector_metrics')
    op.drop_table('aligned_breakout_stock_metrics')
    op.drop_table('aligned_breakout_scan_results')
    op.drop_table('aligned_breakout_profiles')
