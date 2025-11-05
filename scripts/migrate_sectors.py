"""
Data Migration Script: Convert String-Based Sectors to Relational Structure

This script:
1. Extracts unique sectors from Instrument.sector field
2. Creates Sector records with appropriate icons and colors
3. Extracts unique sub-sectors from Instrument.sub_sector field
4. Creates SubSector records linked to sectors
5. Updates Instrument.sub_sector_id to link to SubSector records
6. Preserves original string fields for reference

Run with: python migrate_sectors.py
"""

import sys
import os
from datetime import datetime

# Add the project root directory to the path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app import create_app, db
from app.models import Instrument, Sector, SubSector
from app.sector_service import SectorService
from app.subsector_service import SubSectorService

# Sector configuration with icons and colors (from sectors.py)
SECTOR_CONFIG = {
    'Financial Services': {'icon': 'bi-bank2', 'color': '#667eea', 'order': 1},
    'IT': {'icon': 'bi-laptop', 'color': '#764ba2', 'order': 2},
    'Healthcare': {'icon': 'bi-heart-pulse', 'color': '#11998e', 'order': 3},
    'Consumer Goods': {'icon': 'bi-cart4', 'color': '#38ef7d', 'order': 4},
    'Automobile': {'icon': 'bi-car-front', 'color': '#f093fb', 'order': 5},
    'Energy': {'icon': 'bi-lightning-charge', 'color': '#f5576c', 'order': 6},
    'Telecom': {'icon': 'bi-telephone', 'color': '#4facfe', 'order': 7},
    'Metals': {'icon': 'bi-gem', 'color': '#00f2fe', 'order': 8},
    'Infrastructure': {'icon': 'bi-buildings', 'color': '#fa709a', 'order': 9},
    'Media': {'icon': 'bi-broadcast', 'color': '#fee140', 'order': 10},
    'Pharma': {'icon': 'bi-capsule', 'color': '#30cfd0', 'order': 11},
    'Realty': {'icon': 'bi-house', 'color': '#330867', 'order': 12},
    'Textiles': {'icon': 'bi-palette', 'color': '#a8edea', 'order': 13},
}


def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def get_or_create_sector(sector_name, sector_map):
    """Get existing sector or create new one"""
    if sector_name in sector_map:
        return sector_map[sector_name]

    # Get configuration
    config = SECTOR_CONFIG.get(sector_name, {
        'icon': 'bi-grid',
        'color': '#6c757d',
        'order': 99
    })

    # Try to create sector
    sector, error = SectorService.create_sector(
        name=sector_name,
        description=f"Automatically migrated from legacy data",
        icon=config['icon'],
        color=config['color'],
        display_order=config['order']
    )

    if error:
        print(f"  ⚠️  Error creating sector '{sector_name}': {error}")
        return None

    print(f"  ✓ Created sector: {sector_name}")
    sector_map[sector_name] = sector
    return sector


def migrate_sectors():
    """Main migration function"""
    print_section("SECTOR MIGRATION SCRIPT")
    print("This script will migrate your existing sector data to the new relational structure.")
    print("The original string fields will be preserved for reference.")

    response = input("\nDo you want to continue? (yes/no): ").strip().lower()
    if response != 'yes':
        print("Migration cancelled.")
        return

    app = create_app()

    with app.app_context():
        print_section("Step 1: Analyzing Existing Data")

        # Get all NIFTY 500 instruments
        total_instruments = Instrument.query.filter_by(
            exchange='NSE',
            instrument_type='EQ',
            is_nifty500=True
        ).count()

        print(f"Total NIFTY 500 instruments: {total_instruments}")

        # Get unique sectors
        unique_sectors = db.session.query(
            Instrument.sector
        ).filter(
            Instrument.exchange == 'NSE',
            Instrument.instrument_type == 'EQ',
            Instrument.is_nifty500 == True,
            Instrument.sector.isnot(None)
        ).distinct().all()

        unique_sectors = [s[0] for s in unique_sectors if s[0]]
        print(f"Unique sectors found: {len(unique_sectors)}")
        for sector in sorted(unique_sectors):
            count = Instrument.query.filter_by(
                exchange='NSE',
                instrument_type='EQ',
                is_nifty500=True,
                sector=sector
            ).count()
            print(f"  - {sector}: {count} stocks")

        # Get unique sub-sectors
        unique_subsectors = db.session.query(
            Instrument.sector,
            Instrument.sub_sector
        ).filter(
            Instrument.exchange == 'NSE',
            Instrument.instrument_type == 'EQ',
            Instrument.is_nifty500 == True,
            Instrument.sector.isnot(None),
            Instrument.sub_sector.isnot(None)
        ).distinct().all()

        print(f"\nUnique sub-sectors found: {len(unique_subsectors)}")

        print_section("Step 2: Creating Sector Records")

        sector_map = {}  # Maps sector_name -> Sector object

        for sector_name in sorted(unique_sectors):
            get_or_create_sector(sector_name, sector_map)

        print(f"\n✓ Created {len(sector_map)} sector records")

        print_section("Step 3: Creating SubSector Records")

        subsector_map = {}  # Maps (sector_name, subsector_name) -> SubSector object
        subsector_count = 0

        for sector_name, subsector_name in sorted(unique_subsectors, key=lambda x: (x[0], x[1])):
            if not sector_name or not subsector_name:
                continue

            key = (sector_name, subsector_name)
            if key in subsector_map:
                continue

            # Get parent sector
            sector = sector_map.get(sector_name)
            if not sector:
                print(f"  ⚠️  Sector not found for sub-sector: {sector_name} -> {subsector_name}")
                continue

            # Create sub-sector
            subsector, error = SubSectorService.create_sub_sector(
                sector_id=sector.id,
                name=subsector_name,
                description=f"Automatically migrated from legacy data",
                display_order=0
            )

            if error:
                print(f"  ⚠️  Error creating sub-sector '{subsector_name}' under '{sector_name}': {error}")
                continue

            print(f"  ✓ Created sub-sector: {sector_name} -> {subsector_name}")
            subsector_map[key] = subsector
            subsector_count += 1

        print(f"\n✓ Created {subsector_count} sub-sector records")

        print_section("Step 4: Linking Instruments to SubSectors")

        updated_count = 0
        skipped_count = 0
        error_count = 0

        # Update instruments in batches
        instruments = Instrument.query.filter_by(
            exchange='NSE',
            instrument_type='EQ',
            is_nifty500=True
        ).filter(
            Instrument.sector.isnot(None),
            Instrument.sub_sector.isnot(None)
        ).all()

        for instrument in instruments:
            key = (instrument.sector, instrument.sub_sector)

            if key not in subsector_map:
                skipped_count += 1
                continue

            subsector = subsector_map[key]

            try:
                instrument.sub_sector_id = subsector.id
                instrument.last_updated = datetime.utcnow()
                updated_count += 1

                if updated_count % 50 == 0:
                    db.session.commit()
                    print(f"  Progress: {updated_count} instruments linked...")

            except Exception as e:
                error_count += 1
                print(f"  ⚠️  Error linking {instrument.tradingsymbol}: {str(e)}")

        # Final commit
        db.session.commit()

        print(f"\n✓ Linked {updated_count} instruments to sub-sectors")
        if skipped_count > 0:
            print(f"⚠️  Skipped {skipped_count} instruments (no matching sub-sector)")
        if error_count > 0:
            print(f"❌ Errors: {error_count} instruments")

        print_section("Step 5: Migration Summary")

        print("Database Statistics:")
        print(f"  Sectors created: {Sector.query.count()}")
        print(f"  Sub-sectors created: {SubSector.query.count()}")
        print(f"  Instruments linked: {Instrument.query.filter(Instrument.sub_sector_id.isnot(None)).count()}")
        print(f"  Instruments unlinked: {Instrument.query.filter_by(exchange='NSE', instrument_type='EQ', is_nifty500=True, sub_sector_id=None).count()}")

        print("\n✓ Migration completed successfully!")

        print("\n" + "=" * 70)
        print("IMPORTANT NOTES:")
        print("=" * 70)
        print("1. Original string fields (sector, sub_sector) are preserved for reference")
        print("2. New relational fields (sub_sector_id) have been populated")
        print("3. You can now use the Sector Management UI at /sector-management")
        print("4. Unlinked instruments can be assigned through the management interface")
        print("=" * 70)


if __name__ == '__main__':
    try:
        migrate_sectors()
    except KeyboardInterrupt:
        print("\n\nMigration interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Migration failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
