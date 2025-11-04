#!/usr/bin/env python3
"""
Migration Script: Indian Institutional Sector Classification
This script clears existing sectors and imports the institutional classification structure
"""

import sys
from app import create_app, db
from app.models import Sector, SubSector, Instrument

# Institutional Sector Classification Data
SECTORS_DATA = [
    {
        'name': 'BANKING & FINANCIAL SERVICES',
        'description': 'Banks, NBFCs, Insurance, AMCs and other financial services',
        'icon': 'bi-bank',
        'color': '#1e3a8a',
        'subsectors': [
            'Private Banks',
            'Public Sector Banks',
            'NBFCs & Finance',
            'Insurance',
            'AMC & Broking',
            'Other Financial Services'
        ]
    },
    {
        'name': 'INFORMATION TECHNOLOGY & TECHNOLOGY SERVICES',
        'description': 'IT services, software, fintech and digital platforms',
        'icon': 'bi-laptop',
        'color': '#7c3aed',
        'subsectors': [
            'Large Cap IT Services',
            'Mid/Small Cap IT',
            'Specialized Tech/Platforms',
            'Fintech/Digital'
        ]
    },
    {
        'name': 'PHARMACEUTICALS & HEALTHCARE',
        'description': 'Pharmaceuticals, healthcare services and medical equipment',
        'icon': 'bi-capsule',
        'color': '#dc2626',
        'subsectors': [
            'Large Cap Pharma',
            'Mid Cap Pharma',
            'Specialty Pharma',
            'Healthcare Services',
            'MNC Pharma'
        ]
    },
    {
        'name': 'AUTOMOTIVE & AUTO COMPONENTS',
        'description': 'Automobile manufacturers and component suppliers',
        'icon': 'bi-car-front',
        'color': '#ea580c',
        'subsectors': [
            'Passenger Vehicles',
            'Two Wheelers',
            'Commercial Vehicles',
            'EV/New Age Auto',
            'Auto Components - Tier 1',
            'Auto Components - Others',
            'Auto Ancillaries'
        ]
    },
    {
        'name': 'CAPITAL GOODS, ENGINEERING & INFRASTRUCTURE',
        'description': 'Heavy engineering, capital goods, defense and infrastructure',
        'icon': 'bi-gear',
        'color': '#0891b2',
        'subsectors': [
            'Heavy Engineering & Defense',
            'Capital Goods',
            'Infrastructure - Construction',
            'Infrastructure - Power Transmission',
            'Bearings & Industrial',
            'Railways',
            'Cables & Wires',
            'Pumps & Valves',
            'Precision Engineering'
        ]
    },
    {
        'name': 'OIL, GAS & ENERGY',
        'description': 'Oil & gas exploration, refining and distribution',
        'icon': 'bi-droplet',
        'color': '#15803d',
        'subsectors': [
            'Upstream',
            'Refining & Marketing',
            'Gas Distribution',
            'Gas Transportation',
            'Oil Storage'
        ]
    },
    {
        'name': 'POWER & UTILITIES',
        'description': 'Power generation, renewable energy and utilities',
        'icon': 'bi-lightning',
        'color': '#ca8a04',
        'subsectors': [
            'Power Generation',
            'Renewable Energy',
            'Power Equipment',
            'Transmission'
        ]
    },
    {
        'name': 'METALS & MINING',
        'description': 'Steel, aluminum, copper, zinc and mining',
        'icon': 'bi-gem',
        'color': '#71717a',
        'subsectors': [
            'Steel - Integrated',
            'Steel - Secondary',
            'Aluminum',
            'Zinc/Lead',
            'Copper',
            'Iron Ore/Coal',
            'Specialty Metals',
            'Ferrous/Non-Ferrous'
        ]
    },
    {
        'name': 'CEMENT & BUILDING MATERIALS',
        'description': 'Cement manufacturers and building material suppliers',
        'icon': 'bi-bricks',
        'color': '#78716c',
        'subsectors': [
            'Cement - Large Cap',
            'Cement - Mid Cap',
            'Building Materials'
        ]
    },
    {
        'name': 'CHEMICALS & PETROCHEMICALS',
        'description': 'Specialty chemicals, agrochemicals and petrochemicals',
        'icon': 'bi-droplet-half',
        'color': '#16a34a',
        'subsectors': [
            'Specialty Chemicals',
            'Agrochemicals',
            'Commodity Chemicals',
            'Paints & Coatings',
            'Other Chemicals'
        ]
    },
    {
        'name': 'CONSUMER GOODS - FMCG',
        'description': 'Fast moving consumer goods and food & beverages',
        'icon': 'bi-basket',
        'color': '#dc2626',
        'subsectors': [
            'Diversified FMCG',
            'Food & Beverages',
            'Personal Care',
            'Tobacco',
            'Staples'
        ]
    },
    {
        'name': 'CONSUMER DURABLES & RETAIL',
        'description': 'Consumer durables, retail chains and jewelry',
        'icon': 'bi-shop',
        'color': '#9333ea',
        'subsectors': [
            'Consumer Durables',
            'Retail',
            'Jewelry',
            'Eyewear'
        ]
    },
    {
        'name': 'REAL ESTATE & CONSTRUCTION',
        'description': 'Real estate developers and construction companies',
        'icon': 'bi-building',
        'color': '#0369a1',
        'subsectors': [
            'Real Estate - Residential',
            'Real Estate - Commercial',
            'Real Estate - Affordable',
            'Construction Materials'
        ]
    },
    {
        'name': 'TELECOM & TOWER',
        'description': 'Telecom services and tower infrastructure',
        'icon': 'bi-broadcast',
        'color': '#2563eb',
        'subsectors': [
            'Telecom Services',
            'Tower Infrastructure'
        ]
    },
    {
        'name': 'MEDIA, ENTERTAINMENT & HOSPITALITY',
        'description': 'Media, broadcasting, hospitality and entertainment',
        'icon': 'bi-film',
        'color': '#db2777',
        'subsectors': [
            'Media & Broadcasting',
            'Hospitality',
            'QSR/Food Services',
            'Multiplexes'
        ]
    },
    {
        'name': 'LOGISTICS, TRANSPORTATION & INFRASTRUCTURE',
        'description': 'Logistics, ports, shipping and aviation',
        'icon': 'bi-truck',
        'color': '#0d9488',
        'subsectors': [
            'Logistics',
            'Ports',
            'Shipping',
            'Aviation',
            'Others'
        ]
    },
    {
        'name': 'TEXTILES & APPAREL',
        'description': 'Textile manufacturing and apparel brands',
        'icon': 'bi-badge-tm',
        'color': '#7c2d12',
        'subsectors': [
            'Textiles',
            'Apparel/Fashion',
            'Home Textiles'
        ]
    },
    {
        'name': 'MISCELLANEOUS & DIVERSIFIED',
        'description': 'Conglomerates, trading and diversified businesses',
        'icon': 'bi-collection',
        'color': '#475569',
        'subsectors': [
            'Conglomerates',
            'Trading & Distribution',
            'Paper & Packaging',
            'Agriculture/Fertilizers',
            'Services',
            'New Age/Platform',
            'Others'
        ]
    },
    {
        'name': 'SPECIALIZED INDUSTRIAL & MANUFACTURING',
        'description': 'Glass, ceramics, plastics, pipes and industrial equipment',
        'icon': 'bi-tools',
        'color': '#64748b',
        'subsectors': [
            'Glass & Ceramics',
            'Abrasives & Refractories',
            'Plastics & Pipes',
            'Electrical Equipment',
            'Industrial Gases',
            'Graphite & Electrodes',
            'Engineering Services'
        ]
    },
    {
        'name': 'EMERGING/THEMATIC SECTORS',
        'description': 'EV ecosystem, digital/fintech, green energy and defense',
        'icon': 'bi-rocket-takeoff',
        'color': '#059669',
        'subsectors': [
            'EV Ecosystem',
            'Digital/Fintech',
            'Green Energy/ESG Focus',
            'Defense & Aerospace',
            'Data Centers/Cloud'
        ]
    }
]


def clear_existing_sectors():
    """Clear all existing stock-sector associations and delete sectors"""
    print("\n" + "="*80)
    print("STEP 1: Clearing Existing Sectors and Associations")
    print("="*80)

    # Count current data
    sector_count = Sector.query.count()
    subsector_count = SubSector.query.count()
    stocks_with_sectors = Instrument.query.filter(Instrument.sub_sector_id.isnot(None)).count()

    print(f"\nCurrent state:")
    print(f"  - Sectors: {sector_count}")
    print(f"  - Sub-Sectors: {subsector_count}")
    print(f"  - Stocks with sector assignments: {stocks_with_sectors}")

    if sector_count == 0 and subsector_count == 0:
        print("\nNo existing sectors found. Skipping cleanup.")
        return

    # Clear stock associations
    if stocks_with_sectors > 0:
        print(f"\n  → Clearing {stocks_with_sectors} stock-sector associations...")
        Instrument.query.update({'sub_sector_id': None})
        db.session.commit()
        print("  ✓ Stock associations cleared")

    # Delete subsectors first (explicit deletion)
    print(f"\n  → Deleting {subsector_count} subsectors...")
    SubSector.query.delete()
    db.session.commit()
    print("  ✓ Subsectors deleted")

    # Delete all sectors
    print(f"\n  → Deleting {sector_count} sectors...")
    Sector.query.delete()
    db.session.commit()
    print("  ✓ Sectors deleted")

    # Verify cleanup
    remaining_sectors = Sector.query.count()
    remaining_subsectors = SubSector.query.count()
    if remaining_sectors == 0 and remaining_subsectors == 0:
        print("\n✓ Cleanup completed successfully")
    else:
        raise Exception(f"Cleanup failed: {remaining_sectors} sectors and {remaining_subsectors} subsectors still remain")


def import_institutional_sectors():
    """Import the new institutional sector classification"""
    print("\n" + "="*80)
    print("STEP 2: Importing Institutional Sector Classification")
    print("="*80)

    total_sectors = len(SECTORS_DATA)
    total_subsectors = sum(len(s['subsectors']) for s in SECTORS_DATA)

    print(f"\nImporting {total_sectors} sectors with {total_subsectors} subsectors...")

    imported_sectors = 0
    imported_subsectors = 0

    for idx, sector_data in enumerate(SECTORS_DATA, 1):
        # Create sector
        sector = Sector(
            name=sector_data['name'],
            description=sector_data['description'],
            icon=sector_data['icon'],
            color=sector_data['color'],
            is_active=True,
            display_order=idx
        )
        db.session.add(sector)
        db.session.flush()  # Get sector ID

        imported_sectors += 1
        print(f"\n[{idx}/{total_sectors}] {sector.name}")

        # Create subsectors
        for sub_idx, subsector_name in enumerate(sector_data['subsectors'], 1):
            subsector = SubSector(
                name=subsector_name,
                sector_id=sector.id,
                is_active=True,
                display_order=sub_idx
            )
            db.session.add(subsector)
            imported_subsectors += 1
            print(f"      └─ {subsector_name}")

    db.session.commit()

    print("\n" + "="*80)
    print("✓ Import completed successfully!")
    print("="*80)
    print(f"\nSummary:")
    print(f"  - Sectors imported: {imported_sectors}")
    print(f"  - Sub-Sectors imported: {imported_subsectors}")


def verify_import():
    """Verify the imported data"""
    print("\n" + "="*80)
    print("STEP 3: Verification")
    print("="*80)

    sector_count = Sector.query.count()
    subsector_count = SubSector.query.count()

    print(f"\nFinal state:")
    print(f"  - Total Sectors: {sector_count}")
    print(f"  - Total Sub-Sectors: {subsector_count}")

    # Show sample data
    print("\nSample sectors:")
    sample_sectors = Sector.query.order_by(Sector.display_order).limit(3).all()
    for sector in sample_sectors:
        subsector_count = sector.sub_sectors.count()
        print(f"  - {sector.name} ({subsector_count} sub-sectors)")

    print("\n✓ Migration completed successfully!")
    print("="*80)


def main():
    """Main migration function"""
    print("\n" + "="*80)
    print("INDIAN INSTITUTIONAL SECTOR CLASSIFICATION MIGRATION")
    print("="*80)
    print("\nThis script will:")
    print("  1. Clear all existing stock-sector associations")
    print("  2. Delete all existing sectors and subsectors")
    print("  3. Import 20 institutional sectors with subsectors")
    print("\nNote: Stocks will NOT be deleted, only their sector associations.")
    print("="*80)

    try:
        # Create Flask app context
        app = create_app()
        with app.app_context():
            # Step 1: Clear existing data
            clear_existing_sectors()

            # Step 2: Import new sectors
            import_institutional_sectors()

            # Step 3: Verify
            verify_import()

            print("\n" + "="*80)
            print("MIGRATION COMPLETED SUCCESSFULLY")
            print("="*80)
            print("\nYou can now:")
            print("  - View sectors at: http://localhost:5002/sectors/")
            print("  - Assign stocks to sectors from the stocks page")
            print("="*80 + "\n")

            return 0

    except Exception as e:
        print(f"\n❌ ERROR: Migration failed!")
        print(f"Error details: {str(e)}")
        print("\nRolling back changes...")
        try:
            db.session.rollback()
            print("✓ Rollback completed")
        except:
            pass
        return 1


if __name__ == '__main__':
    sys.exit(main())
