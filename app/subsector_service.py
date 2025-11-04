"""
Service layer for SubSector CRUD operations and stock assignment
Handles all business logic for sub-sector management
"""

from datetime import datetime
from flask import current_app
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import SubSector, Sector, Instrument


class SubSectorService:
    """Service class for SubSector management operations"""

    @staticmethod
    def create_sub_sector(sector_id, name, description=None, display_order=0):
        """
        Create a new sub-sector under a sector

        Args:
            sector_id: Parent sector ID
            name: Sub-sector name (required, unique within sector)
            description: Sub-sector description
            display_order: Display order for sorting

        Returns:
            tuple: (subsector_object, error_message)
        """
        try:
            # Validate sector exists
            sector = Sector.query.get(sector_id)
            if not sector:
                return None, f"Sector with ID {sector_id} not found"

            # Validate name
            if not name or len(name.strip()) < 3:
                return None, "Sub-sector name must be at least 3 characters"

            if len(name) > 100:
                return None, "Sub-sector name must not exceed 100 characters"

            # Check if sub-sector already exists in this sector (case-insensitive)
            existing = SubSector.query.filter(
                SubSector.sector_id == sector_id,
                db.func.lower(SubSector.name) == name.lower()
            ).first()

            if existing:
                return None, f"Sub-sector '{name}' already exists in sector '{sector.name}'"

            # Create sub-sector
            sub_sector = SubSector(
                name=name.strip(),
                sector_id=sector_id,
                description=description,
                display_order=display_order,
                is_active=True
            )

            db.session.add(sub_sector)
            db.session.commit()

            current_app.logger.info(
                f"Sub-sector created: {sub_sector.name} under {sector.name} (ID: {sub_sector.id})"
            )
            return sub_sector, None

        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f"Integrity error creating sub-sector: {str(e)}")
            return None, "Sub-sector with this name already exists in this sector"

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating sub-sector: {str(e)}")
            return None, f"Error creating sub-sector: {str(e)}"

    @staticmethod
    def update_sub_sector(sub_sector_id, name=None, description=None,
                         is_active=None, display_order=None):
        """
        Update an existing sub-sector

        Args:
            sub_sector_id: Sub-sector ID to update
            name: New sub-sector name (optional)
            description: New description (optional)
            is_active: Active status (optional)
            display_order: Display order (optional)

        Returns:
            tuple: (subsector_object, error_message)
        """
        try:
            sub_sector = SubSector.query.get(sub_sector_id)
            if not sub_sector:
                return None, f"Sub-sector with ID {sub_sector_id} not found"

            # Update name if provided
            if name is not None:
                if len(name.strip()) < 3:
                    return None, "Sub-sector name must be at least 3 characters"

                if len(name) > 100:
                    return None, "Sub-sector name must not exceed 100 characters"

                # Check if new name already exists in same sector (excluding current)
                existing = SubSector.query.filter(
                    SubSector.sector_id == sub_sector.sector_id,
                    db.func.lower(SubSector.name) == name.lower(),
                    SubSector.id != sub_sector_id
                ).first()

                if existing:
                    return None, f"Sub-sector '{name}' already exists in this sector"

                sub_sector.name = name.strip()

            # Update other fields
            if description is not None:
                sub_sector.description = description

            if is_active is not None:
                sub_sector.is_active = is_active

            if display_order is not None:
                sub_sector.display_order = display_order

            sub_sector.updated_at = datetime.utcnow()
            db.session.commit()

            current_app.logger.info(f"Sub-sector updated: {sub_sector.name} (ID: {sub_sector.id})")
            return sub_sector, None

        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f"Integrity error updating sub-sector: {str(e)}")
            return None, "Sub-sector with this name already exists in this sector"

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating sub-sector: {str(e)}")
            return None, f"Error updating sub-sector: {str(e)}"

    @staticmethod
    def delete_sub_sector(sub_sector_id, mode='soft', unassign_stocks=True):
        """
        Delete a sub-sector (soft or hard delete)

        Args:
            sub_sector_id: Sub-sector ID to delete
            mode: 'soft' (deactivate) or 'hard' (remove completely)
            unassign_stocks: If True, unassign stocks; if False, prevent deletion if stocks exist

        Returns:
            tuple: (success_boolean, error_message)
        """
        try:
            sub_sector = SubSector.query.get(sub_sector_id)
            if not sub_sector:
                return False, f"Sub-sector with ID {sub_sector_id} not found"

            # Check for assigned instruments
            instruments_count = sub_sector.instruments.filter_by(is_nifty500=True).count()

            if mode == 'soft':
                # Soft delete - just deactivate
                sub_sector.is_active = False
                sub_sector.updated_at = datetime.utcnow()
                db.session.commit()

                current_app.logger.info(
                    f"Sub-sector soft-deleted: {sub_sector.name} (ID: {sub_sector.id})"
                )
                return True, None

            elif mode == 'hard':
                # Hard delete - handle assigned instruments
                if instruments_count > 0:
                    if not unassign_stocks:
                        return False, (
                            f"Cannot delete sub-sector '{sub_sector.name}'. "
                            f"It has {instruments_count} assigned stocks. "
                            "Please unassign stocks first or use unassign_stocks=True."
                        )

                    # Unassign all instruments
                    sub_sector.instruments.update({
                        'sub_sector_id': None,
                        'last_updated': datetime.utcnow()
                    })

                # Delete the sub-sector
                db.session.delete(sub_sector)
                db.session.commit()

                current_app.logger.warning(
                    f"Sub-sector hard-deleted: {sub_sector.name} (ID: {sub_sector_id}), "
                    f"{instruments_count} instruments unassigned"
                )
                return True, None

            else:
                return False, f"Invalid delete mode: {mode}. Use 'soft' or 'hard'."

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting sub-sector: {str(e)}")
            return False, f"Error deleting sub-sector: {str(e)}"

    @staticmethod
    def get_sub_sector_by_id(sub_sector_id, include_inactive=False):
        """
        Get a sub-sector by ID

        Args:
            sub_sector_id: Sub-sector ID
            include_inactive: Whether to include inactive sub-sectors

        Returns:
            SubSector object or None
        """
        query = SubSector.query.filter_by(id=sub_sector_id)

        if not include_inactive:
            query = query.filter_by(is_active=True)

        return query.first()

    @staticmethod
    def get_sub_sectors_by_sector(sector_id, include_inactive=False):
        """
        Get all sub-sectors for a given sector

        Args:
            sector_id: Sector ID
            include_inactive: Whether to include inactive sub-sectors

        Returns:
            List of SubSector objects
        """
        query = SubSector.query.filter_by(sector_id=sector_id)

        if not include_inactive:
            query = query.filter_by(is_active=True)

        return query.order_by(SubSector.display_order, SubSector.name).all()

    @staticmethod
    def assign_stocks(sub_sector_id, instrument_ids):
        """
        Assign multiple stocks to a sub-sector

        Args:
            sub_sector_id: Sub-sector ID
            instrument_ids: List of instrument IDs to assign

        Returns:
            tuple: (success_count, error_message)
        """
        try:
            sub_sector = SubSector.query.get(sub_sector_id)
            if not sub_sector:
                return 0, f"Sub-sector with ID {sub_sector_id} not found"

            success_count = 0

            for instrument_id in instrument_ids:
                instrument = Instrument.query.get(instrument_id)
                if instrument and instrument.is_nifty500:
                    instrument.sub_sector_id = sub_sector_id
                    instrument.last_updated = datetime.utcnow()
                    success_count += 1

            db.session.commit()

            current_app.logger.info(
                f"Assigned {success_count} stocks to sub-sector '{sub_sector.name}'"
            )
            return success_count, None

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error assigning stocks: {str(e)}")
            return 0, f"Error assigning stocks: {str(e)}"

    @staticmethod
    def remove_stocks(sub_sector_id, instrument_ids):
        """
        Remove multiple stocks from a sub-sector

        Args:
            sub_sector_id: Sub-sector ID
            instrument_ids: List of instrument IDs to remove

        Returns:
            tuple: (success_count, error_message)
        """
        try:
            sub_sector = SubSector.query.get(sub_sector_id)
            if not sub_sector:
                return 0, f"Sub-sector with ID {sub_sector_id} not found"

            success_count = 0

            for instrument_id in instrument_ids:
                instrument = Instrument.query.filter_by(
                    id=instrument_id,
                    sub_sector_id=sub_sector_id
                ).first()

                if instrument:
                    instrument.sub_sector_id = None
                    instrument.last_updated = datetime.utcnow()
                    success_count += 1

            db.session.commit()

            current_app.logger.info(
                f"Removed {success_count} stocks from sub-sector '{sub_sector.name}'"
            )
            return success_count, None

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error removing stocks: {str(e)}")
            return 0, f"Error removing stocks: {str(e)}"

    @staticmethod
    def move_stocks(from_sub_sector_id, to_sub_sector_id, instrument_ids):
        """
        Move stocks from one sub-sector to another

        Args:
            from_sub_sector_id: Source sub-sector ID
            to_sub_sector_id: Destination sub-sector ID
            instrument_ids: List of instrument IDs to move

        Returns:
            tuple: (success_count, error_message)
        """
        try:
            from_sub_sector = SubSector.query.get(from_sub_sector_id)
            to_sub_sector = SubSector.query.get(to_sub_sector_id)

            if not from_sub_sector:
                return 0, f"Source sub-sector with ID {from_sub_sector_id} not found"

            if not to_sub_sector:
                return 0, f"Destination sub-sector with ID {to_sub_sector_id} not found"

            success_count = 0

            for instrument_id in instrument_ids:
                instrument = Instrument.query.filter_by(
                    id=instrument_id,
                    sub_sector_id=from_sub_sector_id
                ).first()

                if instrument:
                    instrument.sub_sector_id = to_sub_sector_id
                    instrument.last_updated = datetime.utcnow()
                    success_count += 1

            db.session.commit()

            current_app.logger.info(
                f"Moved {success_count} stocks from '{from_sub_sector.name}' "
                f"to '{to_sub_sector.name}'"
            )
            return success_count, None

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error moving stocks: {str(e)}")
            return 0, f"Error moving stocks: {str(e)}"

    @staticmethod
    def get_unassigned_stocks(sector_id=None, search=None, limit=100):
        """
        Get stocks that are not assigned to any sub-sector

        Args:
            sector_id: Optional sector ID to filter by legacy sector field
            search: Optional search term for symbol or name
            limit: Maximum number of results

        Returns:
            List of Instrument objects
        """
        query = Instrument.query.filter_by(
            exchange='NSE',
            instrument_type='EQ',
            is_nifty500=True,
            sub_sector_id=None
        )

        # Filter by legacy sector field if provided
        if sector_id:
            sector = Sector.query.get(sector_id)
            if sector:
                query = query.filter_by(sector=sector.name)

        # Apply search filter
        if search:
            from sqlalchemy import or_
            query = query.filter(or_(
                Instrument.tradingsymbol.ilike(f'%{search}%'),
                Instrument.name.ilike(f'%{search}%')
            ))

        return query.order_by(Instrument.tradingsymbol).limit(limit).all()

    @staticmethod
    def get_stocks_by_subsector(sub_sector_id, search=None, page=1, per_page=50):
        """
        Get stocks assigned to a specific sub-sector with pagination

        Args:
            sub_sector_id: Sub-sector ID
            search: Optional search term
            page: Page number
            per_page: Items per page

        Returns:
            Pagination object
        """
        sub_sector = SubSector.query.get(sub_sector_id)
        if not sub_sector:
            return None

        query = sub_sector.instruments.filter_by(is_nifty500=True)

        # Apply search filter
        if search:
            from sqlalchemy import or_
            query = query.filter(or_(
                Instrument.tradingsymbol.ilike(f'%{search}%'),
                Instrument.name.ilike(f'%{search}%')
            ))

        return query.order_by(Instrument.tradingsymbol).paginate(
            page=page, per_page=per_page, error_out=False
        )

    @staticmethod
    def reorder_subsectors(sub_sector_ids):
        """
        Update display order for multiple sub-sectors

        Args:
            sub_sector_ids: List of sub-sector IDs in desired order

        Returns:
            tuple: (success_boolean, error_message)
        """
        try:
            for index, sub_sector_id in enumerate(sub_sector_ids):
                sub_sector = SubSector.query.get(sub_sector_id)
                if sub_sector:
                    sub_sector.display_order = index
                    sub_sector.updated_at = datetime.utcnow()

            db.session.commit()
            current_app.logger.info(f"Reordered {len(sub_sector_ids)} sub-sectors")
            return True, None

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error reordering sub-sectors: {str(e)}")
            return False, f"Error reordering sub-sectors: {str(e)}"
