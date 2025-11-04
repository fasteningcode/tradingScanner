"""
Service layer for Sector CRUD operations
Handles all business logic for sector management
"""

from datetime import datetime
from flask import current_app
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import Sector, SubSector, Instrument


class SectorService:
    """Service class for Sector management operations"""

    @staticmethod
    def create_sector(name, description=None, icon=None, color=None, display_order=0):
        """
        Create a new sector

        Args:
            name: Sector name (required, unique, case-insensitive)
            description: Sector description
            icon: Bootstrap icon class (e.g., 'bi-bank2')
            color: Hex color for visualization (e.g., '#667eea')
            display_order: Display order for sorting

        Returns:
            tuple: (sector_object, error_message)
        """
        try:
            # Validate name
            if not name or len(name.strip()) < 3:
                return None, "Sector name must be at least 3 characters"

            if len(name) > 100:
                return None, "Sector name must not exceed 100 characters"

            # Check if sector already exists (case-insensitive)
            existing = Sector.query.filter(
                db.func.lower(Sector.name) == name.lower()
            ).first()

            if existing:
                return None, f"Sector '{name}' already exists"

            # Validate color format if provided
            if color and not color.startswith('#'):
                color = f'#{color}'

            # Create sector
            sector = Sector(
                name=name.strip(),
                description=description,
                icon=icon,
                color=color,
                display_order=display_order,
                is_active=True
            )

            db.session.add(sector)
            db.session.commit()

            current_app.logger.info(f"Sector created: {sector.name} (ID: {sector.id})")
            return sector, None

        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f"Integrity error creating sector: {str(e)}")
            return None, "Sector with this name already exists"

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating sector: {str(e)}")
            return None, f"Error creating sector: {str(e)}"

    @staticmethod
    def update_sector(sector_id, name=None, description=None, icon=None, color=None,
                     is_active=None, display_order=None):
        """
        Update an existing sector

        Args:
            sector_id: Sector ID to update
            name: New sector name (optional)
            description: New description (optional)
            icon: New icon class (optional)
            color: New color (optional)
            is_active: Active status (optional)
            display_order: Display order (optional)

        Returns:
            tuple: (sector_object, error_message)
        """
        try:
            sector = Sector.query.get(sector_id)
            if not sector:
                return None, f"Sector with ID {sector_id} not found"

            # Update name if provided
            if name is not None:
                if len(name.strip()) < 3:
                    return None, "Sector name must be at least 3 characters"

                if len(name) > 100:
                    return None, "Sector name must not exceed 100 characters"

                # Check if new name already exists (case-insensitive, excluding current)
                existing = Sector.query.filter(
                    db.func.lower(Sector.name) == name.lower(),
                    Sector.id != sector_id
                ).first()

                if existing:
                    return None, f"Sector '{name}' already exists"

                sector.name = name.strip()

            # Update other fields
            if description is not None:
                sector.description = description

            if icon is not None:
                sector.icon = icon

            if color is not None:
                if color and not color.startswith('#'):
                    color = f'#{color}'
                sector.color = color

            if is_active is not None:
                sector.is_active = is_active

            if display_order is not None:
                sector.display_order = display_order

            sector.updated_at = datetime.utcnow()
            db.session.commit()

            current_app.logger.info(f"Sector updated: {sector.name} (ID: {sector.id})")
            return sector, None

        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f"Integrity error updating sector: {str(e)}")
            return None, "Sector with this name already exists"

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating sector: {str(e)}")
            return None, f"Error updating sector: {str(e)}"

    @staticmethod
    def delete_sector(sector_id, mode='soft'):
        """
        Delete a sector (soft or hard delete)

        Args:
            sector_id: Sector ID to delete
            mode: 'soft' (deactivate) or 'hard' (cascade delete)

        Returns:
            tuple: (success_boolean, error_message)
        """
        try:
            sector = Sector.query.get(sector_id)
            if not sector:
                return False, f"Sector with ID {sector_id} not found"

            # Check for sub-sectors
            sub_sectors_count = sector.sub_sectors.count()

            if mode == 'soft':
                # Soft delete - just deactivate
                sector.is_active = False
                sector.updated_at = datetime.utcnow()
                db.session.commit()

                current_app.logger.info(f"Sector soft-deleted: {sector.name} (ID: {sector.id})")
                return True, None

            elif mode == 'hard':
                # Hard delete - cascade delete sub-sectors and unassign instruments
                if sub_sectors_count > 0:
                    # Count affected instruments
                    affected_instruments = 0
                    for sub_sector in sector.sub_sectors:
                        affected_instruments += sub_sector.instruments.count()

                    # Unassign all instruments from sub-sectors
                    for sub_sector in sector.sub_sectors:
                        sub_sector.instruments.update({'sub_sector_id': None})

                # Delete the sector (sub-sectors will cascade delete)
                db.session.delete(sector)
                db.session.commit()

                current_app.logger.warning(
                    f"Sector hard-deleted: {sector.name} (ID: {sector_id}), "
                    f"{sub_sectors_count} sub-sectors deleted, "
                    f"{affected_instruments if sub_sectors_count > 0 else 0} instruments unassigned"
                )
                return True, None

            else:
                return False, f"Invalid delete mode: {mode}. Use 'soft' or 'hard'."

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting sector: {str(e)}")
            return False, f"Error deleting sector: {str(e)}"

    @staticmethod
    def get_sector_by_id(sector_id, include_inactive=False):
        """
        Get a sector by ID

        Args:
            sector_id: Sector ID
            include_inactive: Whether to include inactive sectors

        Returns:
            Sector object or None
        """
        query = Sector.query.filter_by(id=sector_id)

        if not include_inactive:
            query = query.filter_by(is_active=True)

        return query.first()

    @staticmethod
    def get_all_sectors(include_inactive=False, order_by='display_order'):
        """
        Get all sectors

        Args:
            include_inactive: Whether to include inactive sectors
            order_by: Field to order by ('display_order', 'name', 'created_at')

        Returns:
            List of Sector objects
        """
        query = Sector.query

        if not include_inactive:
            query = query.filter_by(is_active=True)

        # Apply ordering
        if order_by == 'name':
            query = query.order_by(Sector.name)
        elif order_by == 'created_at':
            query = query.order_by(Sector.created_at.desc())
        else:  # display_order
            query = query.order_by(Sector.display_order, Sector.name)

        return query.all()

    @staticmethod
    def reorder_sectors(sector_ids):
        """
        Update display order for multiple sectors

        Args:
            sector_ids: List of sector IDs in desired order

        Returns:
            tuple: (success_boolean, error_message)
        """
        try:
            for index, sector_id in enumerate(sector_ids):
                sector = Sector.query.get(sector_id)
                if sector:
                    sector.display_order = index
                    sector.updated_at = datetime.utcnow()

            db.session.commit()
            current_app.logger.info(f"Reordered {len(sector_ids)} sectors")
            return True, None

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error reordering sectors: {str(e)}")
            return False, f"Error reordering sectors: {str(e)}"

    @staticmethod
    def get_sector_with_subsectors(sector_id, include_inactive=False):
        """
        Get a sector with all its sub-sectors

        Args:
            sector_id: Sector ID
            include_inactive: Whether to include inactive sub-sectors

        Returns:
            tuple: (sector, list_of_subsectors)
        """
        sector = SectorService.get_sector_by_id(sector_id, include_inactive=include_inactive)
        if not sector:
            return None, []

        query = sector.sub_sectors

        if not include_inactive:
            query = query.filter_by(is_active=True)

        sub_sectors = query.order_by(SubSector.display_order, SubSector.name).all()

        return sector, sub_sectors

    @staticmethod
    def search_sectors(search_term, include_inactive=False):
        """
        Search sectors by name or description

        Args:
            search_term: Search string
            include_inactive: Whether to include inactive sectors

        Returns:
            List of matching Sector objects
        """
        query = Sector.query.filter(
            db.or_(
                Sector.name.ilike(f'%{search_term}%'),
                Sector.description.ilike(f'%{search_term}%')
            )
        )

        if not include_inactive:
            query = query.filter_by(is_active=True)

        return query.order_by(Sector.name).all()
