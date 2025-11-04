import csv
import io
from datetime import datetime, date
from flask import current_app
from app import db
from app.models import Instrument, Nifty500List
from app.kite_auth import get_kite_client


class InstrumentsManager:
    """
    Manager class for handling instrument data from Kite Connect
    Provides methods for downloading, storing, and querying instruments
    """

    @staticmethod
    def download_instruments(exchange='NSE'):
        """
        Download instruments list from Kite Connect

        Args:
            exchange: Exchange name (NSE, BSE, NFO, etc.)

        Returns:
            list: List of instrument dictionaries
        """
        try:
            kite = get_kite_client()
            instruments = kite.instruments(exchange)
            current_app.logger.info(f'Downloaded {len(instruments)} instruments from {exchange}')
            return instruments

        except Exception as e:
            current_app.logger.error(f'Error downloading instruments from {exchange}: {str(e)}')
            raise

    @staticmethod
    def sync_instruments(exchange='NSE'):
        """
        Download and sync instruments to database
        Updates existing instruments or creates new ones

        Args:
            exchange: Exchange name (NSE, BSE, NFO, etc.)

        Returns:
            dict: Statistics about sync operation
        """
        try:
            instruments_data = InstrumentsManager.download_instruments(exchange)

            created_count = 0
            updated_count = 0
            skipped_count = 0

            for inst_data in instruments_data:
                try:
                    instrument_token = inst_data.get('instrument_token')
                    if not instrument_token:
                        skipped_count += 1
                        continue

                    # Check if instrument exists
                    instrument = Instrument.query.filter_by(instrument_token=instrument_token).first()

                    # Parse expiry date
                    expiry = None
                    if inst_data.get('expiry'):
                        if isinstance(inst_data.get('expiry'), date):
                            expiry = inst_data.get('expiry')
                        elif isinstance(inst_data.get('expiry'), str):
                            try:
                                expiry = datetime.strptime(inst_data.get('expiry'), '%Y-%m-%d').date()
                            except:
                                pass

                    if instrument:
                        # Update existing instrument
                        instrument.exchange_token = inst_data.get('exchange_token')
                        instrument.tradingsymbol = inst_data.get('tradingsymbol')
                        instrument.name = inst_data.get('name')
                        instrument.expiry = expiry
                        instrument.strike = inst_data.get('strike', 0.0)
                        instrument.tick_size = inst_data.get('tick_size', 0.05)
                        instrument.lot_size = inst_data.get('lot_size', 1)
                        instrument.instrument_type = inst_data.get('instrument_type', 'EQ')
                        instrument.segment = inst_data.get('segment', exchange)
                        instrument.exchange = inst_data.get('exchange', exchange)
                        instrument.last_updated = datetime.utcnow()
                        updated_count += 1

                    else:
                        # Create new instrument
                        instrument = Instrument(
                            instrument_token=instrument_token,
                            exchange_token=inst_data.get('exchange_token'),
                            tradingsymbol=inst_data.get('tradingsymbol'),
                            name=inst_data.get('name'),
                            expiry=expiry,
                            strike=inst_data.get('strike', 0.0),
                            tick_size=inst_data.get('tick_size', 0.05),
                            lot_size=inst_data.get('lot_size', 1),
                            instrument_type=inst_data.get('instrument_type', 'EQ'),
                            segment=inst_data.get('segment', exchange),
                            exchange=inst_data.get('exchange', exchange)
                        )
                        db.session.add(instrument)
                        created_count += 1

                    # Commit in batches of 100
                    if (created_count + updated_count) % 100 == 0:
                        db.session.commit()

                except Exception as e:
                    current_app.logger.warning(f'Error processing instrument {inst_data.get("tradingsymbol")}: {str(e)}')
                    skipped_count += 1
                    continue

            # Final commit
            db.session.commit()

            # Auto-sync NIFTY 500 status after NSE instruments sync
            if exchange == 'NSE':
                try:
                    nifty500_synced = InstrumentsManager._sync_nifty500_flags()
                    current_app.logger.info(f'NIFTY 500 sync: {nifty500_synced} instruments marked')
                except Exception as e:
                    current_app.logger.warning(f'NIFTY 500 sync failed: {str(e)}')

            stats = {
                'exchange': exchange,
                'created': created_count,
                'updated': updated_count,
                'skipped': skipped_count,
                'total': len(instruments_data)
            }

            current_app.logger.info(f'Instrument sync completed: {stats}')
            return stats

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error syncing instruments: {str(e)}')
            raise

    @staticmethod
    def get_instruments_by_exchange(exchange='NSE', instrument_type='EQ'):
        """
        Get instruments filtered by exchange and type

        Args:
            exchange: Exchange name (NSE, BSE, NFO, etc.)
            instrument_type: Instrument type (EQ, FUT, CE, PE, etc.)

        Returns:
            list: List of Instrument objects
        """
        return Instrument.query.filter_by(
            exchange=exchange,
            instrument_type=instrument_type
        ).all()

    @staticmethod
    def search_instruments(query, exchange=None, limit=50):
        """
        Search instruments by trading symbol or name

        Args:
            query: Search query string
            exchange: Optional exchange filter
            limit: Maximum number of results

        Returns:
            list: List of matching Instrument objects
        """
        search_filter = Instrument.tradingsymbol.ilike(f'%{query}%') | Instrument.name.ilike(f'%{query}%')

        if exchange:
            search_filter = search_filter & (Instrument.exchange == exchange)

        return Instrument.query.filter(search_filter).limit(limit).all()

    @staticmethod
    def get_instrument_by_token(instrument_token):
        """
        Get instrument by instrument token

        Args:
            instrument_token: Kite instrument token

        Returns:
            Instrument: Instrument object or None
        """
        return Instrument.query.filter_by(instrument_token=instrument_token).first()

    @staticmethod
    def get_instrument_by_tradingsymbol(tradingsymbol, exchange='NSE'):
        """
        Get instrument by trading symbol and exchange

        Args:
            tradingsymbol: Trading symbol (e.g., 'RELIANCE', 'INFY')
            exchange: Exchange name

        Returns:
            Instrument: Instrument object or None
        """
        return Instrument.query.filter_by(
            tradingsymbol=tradingsymbol,
            exchange=exchange
        ).first()

    @staticmethod
    def update_instrument_sector(instrument_id, sector, sub_sector=None):
        """
        Update custom sector/sub-sector classification for an instrument

        Args:
            instrument_id: Instrument database ID
            sector: Sector name
            sub_sector: Optional sub-sector name

        Returns:
            bool: True if successful
        """
        try:
            instrument = Instrument.query.get(instrument_id)
            if not instrument:
                return False

            instrument.sector = sector
            instrument.sub_sector = sub_sector
            instrument.last_updated = datetime.utcnow()
            db.session.commit()

            return True

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error updating instrument sector: {str(e)}')
            return False

    @staticmethod
    def get_instruments_by_sector(sector, sub_sector=None):
        """
        Get instruments filtered by sector and optional sub-sector

        Args:
            sector: Sector name
            sub_sector: Optional sub-sector name

        Returns:
            list: List of Instrument objects
        """
        query = Instrument.query.filter_by(sector=sector)

        if sub_sector:
            query = query.filter_by(sub_sector=sub_sector)

        return query.all()

    @staticmethod
    def get_all_sectors():
        """
        Get list of all unique sectors

        Returns:
            list: List of sector names
        """
        sectors = db.session.query(Instrument.sector).distinct().filter(
            Instrument.sector.isnot(None)
        ).all()

        return [s[0] for s in sectors if s[0]]

    @staticmethod
    def get_sub_sectors_for_sector(sector):
        """
        Get list of all sub-sectors for a given sector

        Args:
            sector: Sector name

        Returns:
            list: List of sub-sector names
        """
        sub_sectors = db.session.query(Instrument.sub_sector).distinct().filter(
            Instrument.sector == sector,
            Instrument.sub_sector.isnot(None)
        ).all()

        return [s[0] for s in sub_sectors if s[0]]

    @staticmethod
    def get_equity_instruments(exchange='NSE'):
        """
        Get all equity instruments for an exchange

        Args:
            exchange: Exchange name (NSE or BSE)

        Returns:
            list: List of equity Instrument objects
        """
        return Instrument.query.filter_by(
            exchange=exchange,
            instrument_type='EQ'
        ).all()

    @staticmethod
    def bulk_update_sectors(sector_mapping):
        """
        Bulk update sectors for multiple instruments

        Args:
            sector_mapping: Dictionary mapping tradingsymbol to (sector, sub_sector)
                          Example: {'RELIANCE': ('Energy', 'Oil & Gas'), ...}

        Returns:
            dict: Statistics about update operation
        """
        try:
            updated_count = 0
            not_found_count = 0

            for tradingsymbol, (sector, sub_sector) in sector_mapping.items():
                instrument = Instrument.query.filter_by(tradingsymbol=tradingsymbol).first()

                if instrument:
                    instrument.sector = sector
                    instrument.sub_sector = sub_sector
                    instrument.last_updated = datetime.utcnow()
                    updated_count += 1

                    # Commit in batches of 50
                    if updated_count % 50 == 0:
                        db.session.commit()
                else:
                    not_found_count += 1

            # Final commit
            db.session.commit()

            stats = {
                'updated': updated_count,
                'not_found': not_found_count,
                'total': len(sector_mapping)
            }

            current_app.logger.info(f'Bulk sector update completed: {stats}')
            return stats

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error in bulk sector update: {str(e)}')
            raise

    @staticmethod
    def _sync_nifty500_flags():
        """
        Internal method to sync is_nifty500 flags based on Nifty500List
        Called automatically after NSE instrument sync

        Returns:
            int: Number of instruments marked as NIFTY 500
        """
        try:
            # Get all active NIFTY 500 symbols
            nifty500_symbols = {entry.symbol for entry in Nifty500List.query.filter_by(is_active=True).all()}

            if not nifty500_symbols:
                current_app.logger.warning('No NIFTY 500 symbols found in database')
                return 0

            # Reset all instruments first
            Instrument.query.update({'is_nifty500': False})

            # Mark NIFTY 500 stocks (NSE, EQ type only)
            marked_count = 0
            for symbol in nifty500_symbols:
                result = Instrument.query.filter_by(
                    tradingsymbol=symbol,
                    exchange='NSE',
                    instrument_type='EQ'
                ).update({'is_nifty500': True})
                marked_count += result

            db.session.commit()
            return marked_count

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error syncing NIFTY 500 flags: {str(e)}')
            raise
