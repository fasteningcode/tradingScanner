"""migrate historical data to json schema

Revision ID: 02de6ea09777
Revises: 8525b9bf251e
Create Date: 2025-11-04 21:35:04.961142

"""
from alembic import op
import sqlalchemy as sa
import json
from datetime import datetime


# revision identifiers, used by Alembic.
revision = '02de6ea09777'
down_revision = '8525b9bf251e'
branch_labels = None
depends_on = None


def upgrade():
    """Migrate from row-per-candle to JSON-per-stock schema"""

    # Step 1: Create temporary table with new schema
    op.create_table('historical_data_new',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tradingsymbol', sa.String(length=50), nullable=False),
        sa.Column('last_downloaded', sa.DateTime(), nullable=True),
        sa.Column('interval', sa.String(length=20), nullable=False),
        sa.Column('candlestick_data', sa.Text(), nullable=False),
        sa.Column('created_on', sa.DateTime(), nullable=True),
        sa.Column('updated_on', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tradingsymbol', 'interval', name='uq_tradingsymbol_interval')
    )

    # Create indexes
    op.create_index('ix_historical_data_new_tradingsymbol', 'historical_data_new', ['tradingsymbol'], unique=False)
    op.create_index('ix_historical_data_new_interval', 'historical_data_new', ['interval'], unique=False)
    op.create_index('ix_historical_data_new_lookup', 'historical_data_new', ['tradingsymbol', 'interval'], unique=False)

    # Step 2: Migrate data using raw SQL (SQLite specific)
    connection = op.get_bind()

    # Get all old records grouped by instrument_id and interval
    old_data = connection.execute(sa.text("""
        SELECT
            i.tradingsymbol,
            h.interval,
            h.timestamp,
            h.open,
            h.high,
            h.low,
            h.close,
            h.volume,
            h.oi,
            MAX(h.created_at) as last_download
        FROM historical_data h
        JOIN instruments i ON h.instrument_id = i.id
        ORDER BY i.tradingsymbol, h.interval, h.timestamp
    """)).fetchall()

    # Group by tradingsymbol and interval
    grouped_data = {}
    for row in old_data:
        key = (row.tradingsymbol, row.interval)
        if key not in grouped_data:
            grouped_data[key] = {
                'candles': [],
                'last_downloaded': row.last_download
            }

        # Add candle to list
        # Convert timestamp to string if it's a datetime object
        if row.timestamp:
            if isinstance(row.timestamp, str):
                date_str = row.timestamp.split(' ')[0]  # Get just the date part
            else:
                date_str = row.timestamp.strftime('%Y-%m-%d')
        else:
            date_str = None

        grouped_data[key]['candles'].append({
            'date': date_str,
            'open': float(row.open) if row.open else 0.0,
            'high': float(row.high) if row.high else 0.0,
            'low': float(row.low) if row.low else 0.0,
            'close': float(row.close) if row.close else 0.0,
            'volume': int(row.volume) if row.volume else 0,
            'oi': int(row.oi) if row.oi else 0
        })

    # Insert grouped data into new table
    now = datetime.utcnow()
    for (tradingsymbol, interval), data in grouped_data.items():
        candles_json = json.dumps(data['candles'])
        connection.execute(sa.text("""
            INSERT INTO historical_data_new
            (tradingsymbol, interval, candlestick_data, last_downloaded, created_on, updated_on)
            VALUES (:symbol, :interval, :data, :last_dl, :created, :updated)
        """), {
            'symbol': tradingsymbol,
            'interval': interval,
            'data': candles_json,
            'last_dl': data['last_downloaded'],
            'created': now,
            'updated': now
        })

    # Step 3: Drop old table
    op.drop_index('ix_historical_data_lookup', table_name='historical_data')
    op.drop_index(op.f('ix_historical_data_timestamp'), table_name='historical_data')
    op.drop_index(op.f('ix_historical_data_interval'), table_name='historical_data')
    op.drop_index(op.f('ix_historical_data_instrument_id'), table_name='historical_data')
    op.drop_table('historical_data')

    # Step 4: Rename new table to historical_data
    op.rename_table('historical_data_new', 'historical_data')

    # Step 5: Rename indexes to match model expectations
    op.execute('DROP INDEX IF EXISTS ix_historical_data_new_tradingsymbol')
    op.execute('DROP INDEX IF EXISTS ix_historical_data_new_interval')
    op.execute('DROP INDEX IF EXISTS ix_historical_data_new_lookup')

    op.create_index('ix_historical_data_tradingsymbol', 'historical_data', ['tradingsymbol'], unique=False)
    op.create_index('ix_historical_data_interval', 'historical_data', ['interval'], unique=False)
    op.create_index('ix_historical_data_lookup', 'historical_data', ['tradingsymbol', 'interval'], unique=False)


def downgrade():
    """Revert back to row-per-candle schema"""

    # Step 1: Create old table structure
    op.create_table('historical_data_old',
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

    # Create indexes
    op.create_index('ix_historical_data_old_instrument_id', 'historical_data_old', ['instrument_id'], unique=False)
    op.create_index('ix_historical_data_old_interval', 'historical_data_old', ['interval'], unique=False)
    op.create_index('ix_historical_data_old_timestamp', 'historical_data_old', ['timestamp'], unique=False)
    op.create_index('ix_historical_data_old_lookup', 'historical_data_old', ['instrument_id', 'interval', 'timestamp'], unique=False)

    # Step 2: Migrate JSON data back to rows (using raw SQL)
    connection = op.get_bind()

    # Get all JSON records
    json_data = connection.execute(sa.text("""
        SELECT id, tradingsymbol, interval, candlestick_data, last_downloaded
        FROM historical_data
    """)).fetchall()

    # Expand JSON to rows
    for row in json_data:
        try:
            candles = json.loads(row.candlestick_data)

            # Get instrument_id from tradingsymbol
            instrument = connection.execute(sa.text("""
                SELECT id FROM instruments WHERE tradingsymbol = :symbol LIMIT 1
            """), {'symbol': row.tradingsymbol}).fetchone()

            if not instrument:
                continue

            instrument_id = instrument.id

            # Insert each candle as a row
            for candle in candles:
                connection.execute(sa.text("""
                    INSERT INTO historical_data_old
                    (instrument_id, timestamp, interval, open, high, low, close, volume, oi, created_at)
                    VALUES (:inst_id, :ts, :interval, :open, :high, :low, :close, :volume, :oi, :created)
                """), {
                    'inst_id': instrument_id,
                    'ts': datetime.strptime(candle['date'], '%Y-%m-%d'),
                    'interval': row.interval,
                    'open': candle.get('open', 0),
                    'high': candle.get('high', 0),
                    'low': candle.get('low', 0),
                    'close': candle.get('close', 0),
                    'volume': candle.get('volume', 0),
                    'oi': candle.get('oi', 0),
                    'created': row.last_downloaded
                })
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Error migrating {row.tradingsymbol}: {e}")
            continue

    # Step 3: Drop new table
    op.drop_index('ix_historical_data_lookup', table_name='historical_data')
    op.drop_index('ix_historical_data_interval', table_name='historical_data')
    op.drop_index('ix_historical_data_tradingsymbol', table_name='historical_data')
    op.drop_table('historical_data')

    # Step 4: Rename old table back
    op.rename_table('historical_data_old', 'historical_data')

    # Step 5: Rename indexes
    op.execute('DROP INDEX IF EXISTS ix_historical_data_old_instrument_id')
    op.execute('DROP INDEX IF EXISTS ix_historical_data_old_interval')
    op.execute('DROP INDEX IF EXISTS ix_historical_data_old_timestamp')
    op.execute('DROP INDEX IF EXISTS ix_historical_data_old_lookup')

    op.create_index('ix_historical_data_instrument_id', 'historical_data', ['instrument_id'], unique=False)
    op.create_index('ix_historical_data_interval', 'historical_data', ['interval'], unique=False)
    op.create_index('ix_historical_data_timestamp', 'historical_data', ['timestamp'], unique=False)
    op.create_index('ix_historical_data_lookup', 'historical_data', ['instrument_id', 'interval', 'timestamp'], unique=False)
