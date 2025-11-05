#!/usr/bin/env python3
"""
Script to import NIFTY 500 stocks with institutional sector classification
"""

import sys
import os
from datetime import datetime

# Add the project root directory to the path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app import create_app, db
from app.models import Instrument, Sector, SubSector
from app.instruments_manager import InstrumentsManager

# Symbol to SubSector mapping based on institutional classification
STOCK_CLASSIFICATION = {
    # 1. BANKING & FINANCIAL SERVICES
    'Private Banks': ['AXISBANK', 'ICICIBANK', 'HDFCBANK', 'KOTAKBANK', 'INDUSINDBK', 'RBLBANK', 'YESBANK', 'BANDHANBNK', 'FEDERALBNK', 'AUBANK', 'CUB', 'KARURVYSYA'],
    'Public Sector Banks': ['SBIN', 'CANBK', 'BANKBARODA', 'PNB', 'UNIONBANK', 'BANKINDIA', 'CENTRALBK', 'INDIANB', 'J&KBANK', 'IOB', 'UCOBANK', 'MAHABANK'],
    'NBFCs & Finance': ['BAJFINANCE', 'BAJAJFINSV', 'BAJAJHFL', 'MUTHOOTFIN', 'M&MFIN', 'CHOLAFIN', 'SHRIRAMFIN', 'LICHSGFIN', 'POONAWALLA', 'MANAPPURAM', 'IIFL', 'JMFINANCIL', 'PNBHOUSING', 'CANFINHOME', 'APTUS', 'AADHARHFC', 'HOMEFIRST', 'SBFC', 'CREDITACC', 'SUNDARMFIN'],
    'Insurance': ['SBILIFE', 'HDFCLIFE', 'ICICIPRULI', 'LICI', 'ICICIGI', 'STARHEALTH', 'NIACL', 'NIVABUPA', 'GODIGIT', 'POLICYBZR', 'SAILIFE'],
    'AMC & Broking': ['HDFCAMC', 'UTIAMC', 'ABSLAMC', 'ANGELONE', 'NUVAMA', 'MOTILALOFS', '360ONE', 'ANANDRATHI'],
    'Other Financial Services': ['BAJAJHLDNG', 'CHOLAHLDNG', 'MFSL', 'ABCAPITAL', 'SAMMAANCAP', 'IDBI', 'IKS', 'IFCI'],

    # 2. INFORMATION TECHNOLOGY & TECHNOLOGY SERVICES
    'Large Cap IT Services': ['TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM', 'LTTS', 'LTIM'],
    'Mid/Small Cap IT': ['PERSISTENT', 'COFORGE', 'KPITTECH', 'MPHASIS', 'SONATSOFTW', 'CYIENT', 'BSOFT', 'TATAELXSI', 'HAPPSTMNDS', 'ZENSARTECH', 'INTELLECT'],
    'Specialized Tech/Platforms': ['ECLERX', 'NEWGEN', 'DATAPATTNS', 'PAYTM', 'NAUKRI', 'AFFLE', 'INDIAMART', 'MAPMYINDIA', 'FIRSTCRY', 'NYKAA', 'SWIGGY'],
    'Fintech/Digital': ['KFINTECH', 'CDSL', 'CAMS', 'BSE', 'MCX'],

    # 3. PHARMACEUTICALS & HEALTHCARE
    'Large Cap Pharma': ['SUNPHARMA', 'DRREDDY', 'CIPLA', 'LUPIN', 'DIVISLAB', 'BIOCON', 'ALKEM', 'TORNTPHARM', 'AUROPHARMA'],
    'Mid Cap Pharma': ['GLENMARK', 'NATCOPHARM', 'ZYDUSLIFE', 'AJANTPHARM', 'JUBLPHARMA', 'MANKIND', 'LAURUSLABS', 'IPCALAB', 'EMCURE', 'AKUMS'],
    'Specialty Pharma': ['GLAND', 'NEULANDLAB', 'SYNGENE', 'LALPATHLAB', 'POLYMED', 'GRANULES', 'ERIS', 'PPLPHARMA', 'WOCKPHARMA', 'ALKYLAMINE', 'JBCHEPHARM'],
    'Healthcare Services': ['APOLLOHOSP', 'MAXHEALTH', 'FORTIS', 'METROPOLIS', 'KIMS', 'ASTERDM', 'RAINBOW', 'MEDANTA', 'AGARWALEYE'],
    'MNC Pharma': ['ABBOTINDIA', 'PFIZER', 'GLAXO', 'ASTRAZEN'],

    # 4. AUTOMOTIVE & AUTO COMPONENTS
    'Passenger Vehicles': ['MARUTI', 'M&M', 'HYUNDAI'],
    'Two Wheelers': ['HEROMOTOCO', 'BAJAJ-AUTO', 'TVSMOTOR', 'EICHERMOT'],
    'Commercial Vehicles': ['ASHOKLEY', 'ESCORTS'],
    'EV/New Age Auto': ['OLAELEC', 'ATHERENERG'],
    'Auto Components - Tier 1': ['MOTHERSON', 'BOSCHLTD', 'MSUMI', 'ENDURANCE', 'SCHAEFFLER', 'BHARATFORG', 'SUNDRMFAST', 'SONACOMS'],
    'Auto Components - Others': ['APOLLOTYRE', 'CEATLTD', 'MRF', 'BALKRISIND', 'JKTYRE', 'EXIDEIND', 'UNOMINDA'],
    'Auto Ancillaries': ['FINCABLES', 'RKFORGE'],

    # 5. CAPITAL GOODS, ENGINEERING & INFRASTRUCTURE
    'Heavy Engineering & Defense': ['BEL', 'HAL', 'BDL', 'BEML', 'BHEL', 'GRSE', 'COCHINSHIP', 'MAZDOCK', 'GESHIP', 'TITAGARH'],
    'Capital Goods': ['ABB', 'SIEMENS', 'CUMMINSIND', 'THERMAX', 'HBLENGINE', 'KIRLOSENG', 'ELECON', 'CRAFTSMAN', 'ELGIEQUIP', 'KSB', 'POWERINDIA'],
    'Infrastructure - Construction': ['LT', 'NCC', 'IRB', 'AFCONS', 'NBCC'],
    'Infrastructure - Power Transmission': ['KEC', 'KPIL'],
    'Bearings & Industrial': ['TIMKEN', 'SKFINDIA'],
    'Railways': ['IRCON', 'RVNL', 'RITES', 'RAILTEL'],
    'Cables & Wires': ['POLYCAB', 'KEI', 'RRKABEL'],
    'Pumps & Valves': ['KIRLOSBROS'],
    'Precision Engineering': ['KAYNES', 'SYRMA', 'JYOTICNC'],

    # 6. OIL, GAS & ENERGY
    'Upstream': ['ONGC', 'OIL', 'GAIL'],
    'Refining & Marketing': ['RELIANCE', 'IOC', 'BPCL', 'HINDPETRO', 'CHENNPETRO', 'MRPL'],
    'Gas Distribution': ['IGL', 'MGL', 'GUJGASLTD', 'GSPL'],
    'Gas Transportation': ['PETRONET'],
    'Oil Storage': ['AEGISVOPAK'],

    # 7. POWER & UTILITIES
    'Power Generation': ['NTPC', 'TATAPOWER', 'ADANIPOWER', 'TORNTPOWER', 'JPPOWER', 'CESC', 'NHPC', 'SJVN', 'JSWENERGY', 'RELINFRA'],
    'Renewable Energy': ['ADANIGREEN', 'ADANIENSOL', 'SUZLON', 'INOXWIND', 'WAAREEENER', 'PREMIERENE', 'ACMESOLAR', 'NTPCGREEN', 'IREDA'],
    'Power Equipment': ['CROMPTON', 'HAVELLS', 'VOLTAS', 'BLUESTARCO', 'VGUARD'],
    'Transmission': ['POWERGRID', 'ATGL'],

    # 8. METALS & MINING
    'Steel - Integrated': ['TATASTEEL', 'JSWSTEEL', 'SAIL', 'JINDALSTEL'],
    'Steel - Secondary': ['JSL'],
    'Aluminum': ['HINDALCO', 'NATIONALUM', 'VEDL'],
    'Zinc/Lead': ['HINDZINC'],
    'Copper': ['HINDCOPPER'],
    'Iron Ore/Coal': ['NMDC', 'COALINDIA'],
    'Specialty Metals': ['MAHSEAMLES'],
    'Ferrous/Non-Ferrous': ['GRAVITA', 'APLLTD', 'LLOYDSME'],

    # 9. CEMENT & BUILDING MATERIALS
    'Cement - Large Cap': ['ULTRACEMCO', 'SHREECEM', 'AMBUJACEM', 'ACC', 'DALBHARAT', 'JKCEMENT', 'RAMCOCEM'],
    'Cement - Mid Cap': ['INDIACEM', 'NUVOCO'],
    'Building Materials': ['CENTURYPLY'],

    # 10. CHEMICALS & PETROCHEMICALS
    'Specialty Chemicals': ['SRF', 'AARTIIND', 'DEEPAKNTR', 'CLEAN', 'NAVINFLUOR', 'FLUOROCHEM'],
    'Agrochemicals': ['UPL', 'PIIND', 'SUMICHEM'],
    'Commodity Chemicals': ['TATACHEM', 'DCMSHRIRAM', 'BALRAMCHIN', 'FACT', 'RCF', 'COROMANDEL'],
    'Paints & Coatings': ['ASIANPAINT', 'BERGEPAINT', 'AKZOINDIA'],
    'Other Chemicals': ['ATUL', 'BASF', 'CASTROLIND', 'PIDILITIND'],

    # 11. CONSUMER GOODS - FMCG
    'Diversified FMCG': ['HINDUNILVR', 'ITC', 'BRITANNIA', 'NESTLEIND', 'DABUR', 'MARICO', 'GODREJCP', 'EMAMILTD', 'JYOTHYLAB'],
    'Food & Beverages': ['TATACONSUM', 'VBL', 'BIKAJI', 'DEVYANI'],
    'Personal Care': ['HONASA'],
    'Tobacco': ['GODFRYPHLP'],
    'Staples': [],

    # 12. CONSUMER DURABLES & RETAIL
    'Consumer Durables': ['WHIRLPOOL'],
    'Retail': ['TRENT', 'DMART', 'ABFRL'],
    'Jewelry': ['TITAN', 'KALYANKJIL'],
    'Eyewear': [],

    # 13. REAL ESTATE & CONSTRUCTION
    'Real Estate - Residential': ['DLF', 'GODREJPROP', 'PRESTIGE', 'OBEROIRLTY', 'BRIGADE', 'SOBHA', 'LODHA', 'PHOENIXLTD', 'ANANTRAJ'],
    'Real Estate - Commercial': [],
    'Real Estate - Affordable': ['SIGNATURE'],
    'Construction Materials': [],

    # 14. TELECOM & TOWER
    'Telecom Services': ['BHARTIARTL', 'JIOFIN', 'IDEA', 'TTML'],
    'Tower Infrastructure': ['INDUSTOWER'],

    # 15. MEDIA, ENTERTAINMENT & HOSPITALITY
    'Media & Broadcasting': ['ZEEL', 'SUNTV', 'SAREGAMA'],
    'Hospitality': ['INDHOTEL', 'LEMONTREE', 'EIHOTEL', 'CHALET', 'THELEELA'],
    'QSR/Food Services': ['JUBLFOOD', 'SAPPHIRE'],
    'Multiplexes': ['PVRINOX'],

    # 16. LOGISTICS, TRANSPORTATION & INFRASTRUCTURE
    'Logistics': ['BLUEDART', 'DELHIVERY', 'AEGISLOG', 'CONCOR'],
    'Ports': ['ADANIPORTS'],
    'Shipping': ['SCI'],
    'Aviation': ['INDIGO'],
    'Others': ['IRCTC'],

    # 17. TEXTILES & APPAREL
    'Textiles': ['TRIDENT', 'WELCORP', 'WELSPUNLIV', 'KPRMILL'],
    'Apparel/Fashion': ['MANYAVAR', 'PAGEIND'],
    'Home Textiles': [],

    # 18. MISCELLANEOUS & DIVERSIFIED
    'Conglomerates': ['ADANIENT'],
    'Trading & Distribution': ['REDINGTON'],
    'Paper & Packaging': [],
    'Agriculture/Fertilizers': ['CHAMBLFERT', 'DEEPAKFERT', 'EIDPARRY'],
    'Services': ['SAGILITY', 'COHANCE'],
    'New Age/Platform': [],
    'Others': ['MMTC', 'BBTC'],

    # 19. SPECIALIZED INDUSTRIAL & MANUFACTURING
    'Glass & Ceramics': ['ASAHIINDIA', 'KAJARIACER', 'CERA'],
    'Abrasives & Refractories': ['CARBORUNIV'],
    'Plastics & Pipes': ['ASTRAL', 'SUPREMEIND', 'FINPIPE', 'APLAPOLLO'],
    'Electrical Equipment': ['TECHNOE'],
    'Industrial Gases': ['INOXINDIA', 'LINDEINDIA'],
    'Graphite & Electrodes': ['GRAPHITE', 'HEG'],
    'Engineering Services': [],

    # 20. EMERGING/THEMATIC SECTORS
    'EV Ecosystem': [],
    'Digital/Fintech': [],
    'Green Energy/ESG Focus': [],
    'Defense & Aerospace': [],
    'Data Centers/Cloud': []
}

# Additional stocks not in classification (will be imported without sector)
ADDITIONAL_NIFTY500_STOCKS = [
    'NAVINFLUOR', 'CHOICEIN', 'RHIM', 'GODREJIND', 'BLUEJET', 'FIVESTAR', 'DOMS',
    'TRITURBINE', 'PTCIL', 'LTF', 'OLECTRA', 'VENTIVE', 'USHAMART', 'NAM-INDIA',
    'TRIVENI', 'FSL', 'ONESOURCE', 'GODREJAGRO', 'SOLARINDS', 'DEEPAKFERT', 'NAVA',
    'CAPLIPOINT', 'AIIL', 'GPIL', 'CRISIL', 'CONCORDBIO', 'CAMPUS', 'RADICO',
    'CENTURYPLY', 'GMDCLTD', 'BATAINDIA', 'AWL', 'JINDALSAW', 'PGHH', 'PGEL',
    'BBTC', 'PFC', 'VMM', 'ITCHOTELS', 'IRFC', 'TMPV', 'BHARTIHEXA', 'ABLBL',
    'ALOKINDS', 'VIJAYA', 'TEJASNET', 'TATAINVEST', 'AMBER', 'SBICARD', 'GMRAIRPORT',
    'PRAJIND', 'AFCONS', 'RPOWER', 'NLCINDIA', '3MINDIA', 'MINDACORP', 'AIAENG',
    'BAYERCROP', 'ENRIN', 'ACE', 'DIXON', 'SWANCORP', 'GVT&D', 'SARDAEN', 'NSLNISP',
    'JUBLINGREA', 'ARE&M', 'PATANJALI', 'HONAUT', 'TIINDIA', 'HUDCO', 'HSCL', 'JWL',
    'TATATECH', 'DBREALTY', 'RELINFRA', 'IDFCFIRSTB', 'FORCEMOT', 'UNITDSPR',
    'COLPAL', 'IGIL', 'HSIL', 'RECLTD', 'GILLETTE', 'ZENTEC', 'JSWINFRA', 'CHALET',
    'TARIL', 'ITI', 'GRASIM', 'ENGINERSIN', 'NETWEB', 'AAVAS', 'PCBL', 'TBOTEK',
    'SCHNEIDER', 'NH', 'CGCL', 'GICRE', 'HEXT', 'JBMA', 'INDGN', 'SHYAMMETL',
    'IEX', 'ETERNAL', 'ZFCVINDIA', 'APARINDS', 'LTFOODS', 'CCL', 'UBL', 'VTL',
    'NUVOCO', 'CGPOWER', 'ABREL', 'ABLBL'
]


def build_subsector_mapping():
    """Build a mapping of symbol -> subsector_id from database"""
    print("\n" + "="*80)
    print("STEP 1: Building Subsector Mapping")
    print("="*80)

    # Get all subsectors from database
    subsectors = SubSector.query.join(Sector).filter(
        SubSector.is_active == True,
        Sector.is_active == True
    ).all()

    subsector_map = {}
    for subsector in subsectors:
        subsector_map[subsector.name] = subsector.id

    # Build symbol -> subsector_id mapping
    symbol_to_subsector = {}
    unmatched_subsectors = []

    for subsector_name, symbols in STOCK_CLASSIFICATION.items():
        if subsector_name not in subsector_map:
            unmatched_subsectors.append(subsector_name)
            continue

        subsector_id = subsector_map[subsector_name]
        for symbol in symbols:
            # Handle duplicates - use first occurrence
            if symbol not in symbol_to_subsector:
                symbol_to_subsector[symbol] = subsector_id

    print(f"\n✓ Mapped {len(symbol_to_subsector)} symbols to subsectors")

    if unmatched_subsectors:
        print(f"\n⚠ Warning: {len(unmatched_subsectors)} subsectors not found in database:")
        for name in unmatched_subsectors[:5]:
            print(f"  - {name}")
        if len(unmatched_subsectors) > 5:
            print(f"  ... and {len(unmatched_subsectors) - 5} more")

    return symbol_to_subsector


def fetch_and_import_stocks(symbol_to_subsector):
    """Fetch stock data from Kite API and import to database"""
    print("\n" + "="*80)
    print("STEP 2: Fetching and Importing Stocks")
    print("="*80)

    # Get all symbols
    all_symbols = list(symbol_to_subsector.keys()) + ADDITIONAL_NIFTY500_STOCKS
    all_symbols = list(set(all_symbols))  # Remove duplicates

    print(f"\nTotal symbols to import: {len(all_symbols)}")

    # Initialize instruments manager
    manager = InstrumentsManager()

    # Fetch all instruments from Kite
    print("\n  → Fetching instruments from Kite API...")
    try:
        all_instruments = manager.download_instruments(exchange='NSE')
        print(f"  ✓ Fetched {len(all_instruments)} instruments from Kite")
    except Exception as e:
        print(f"  ❌ Error fetching from Kite: {str(e)}")
        print("  → Will try to import with basic data only")
        all_instruments = []

    # Create lookup dictionary for instruments
    instruments_by_symbol = {}
    for inst in all_instruments:
        if inst.get('exchange') == 'NSE' and inst.get('instrument_type') == 'EQ':
            symbol = inst.get('tradingsymbol', '')
            if symbol:
                instruments_by_symbol[symbol] = inst

    print(f"  ✓ Found {len(instruments_by_symbol)} NSE EQ instruments")

    # Import stocks
    imported_count = 0
    skipped_count = 0
    error_count = 0

    print("\n  → Importing stocks to database...")

    for symbol in all_symbols:
        try:
            # Check if already exists
            existing = Instrument.query.filter_by(tradingsymbol=symbol, exchange='NSE').first()
            if existing:
                skipped_count += 1
                continue

            # Get instrument data
            inst_data = instruments_by_symbol.get(symbol)
            if not inst_data:
                # Create basic record without Kite data - generate unique token
                # Use hash of symbol to generate unique instrument_token
                instrument_token = abs(hash(symbol)) % (10 ** 10)  # Ensure positive 10-digit number

                instrument = Instrument(
                    instrument_token=instrument_token,
                    tradingsymbol=symbol,
                    name=symbol,
                    exchange='NSE',
                    segment='NSE',
                    instrument_type='EQ',
                    is_nifty500=True,
                    sub_sector_id=symbol_to_subsector.get(symbol)
                )
            else:
                # Create full record with Kite data
                instrument = Instrument(
                    instrument_token=inst_data.get('instrument_token'),
                    exchange_token=inst_data.get('exchange_token'),
                    tradingsymbol=inst_data.get('tradingsymbol'),
                    name=inst_data.get('name', inst_data.get('tradingsymbol')),
                    last_price=inst_data.get('last_price', 0.0),
                    expiry=inst_data.get('expiry'),
                    strike=inst_data.get('strike', 0.0),
                    tick_size=inst_data.get('tick_size', 0.05),
                    lot_size=inst_data.get('lot_size', 1),
                    instrument_type=inst_data.get('instrument_type', 'EQ'),
                    segment=inst_data.get('segment', 'NSE'),
                    exchange=inst_data.get('exchange', 'NSE'),
                    is_nifty500=True,
                    sub_sector_id=symbol_to_subsector.get(symbol)
                )

            db.session.add(instrument)
            imported_count += 1

            # Commit in batches
            if imported_count % 50 == 0:
                try:
                    db.session.commit()
                    print(f"    Imported {imported_count} stocks...")
                except Exception as commit_error:
                    print(f"  ⚠ Error committing batch: {str(commit_error)}")
                    db.session.rollback()
                    error_count += 1

        except Exception as e:
            error_count += 1
            print(f"  ⚠ Error importing {symbol}: {str(e)}")
            db.session.rollback()
            continue

    # Final commit
    try:
        db.session.commit()
    except Exception as e:
        print(f"  ⚠ Error in final commit: {str(e)}")
        db.session.rollback()

    print(f"\n✓ Import completed!")
    print(f"  - Imported: {imported_count}")
    print(f"  - Skipped (already exist): {skipped_count}")
    print(f"  - Errors: {error_count}")

    return imported_count, skipped_count, error_count


def verify_import():
    """Verify the imported stocks"""
    print("\n" + "="*80)
    print("STEP 3: Verification")
    print("="*80)

    # Count stocks
    total_stocks = Instrument.query.filter_by(exchange='NSE', is_nifty500=True).count()
    stocks_with_sectors = Instrument.query.filter(
        Instrument.exchange == 'NSE',
        Instrument.is_nifty500 == True,
        Instrument.sub_sector_id.isnot(None)
    ).count()
    stocks_without_sectors = total_stocks - stocks_with_sectors

    print(f"\nFinal state:")
    print(f"  - Total NIFTY 500 stocks: {total_stocks}")
    print(f"  - Stocks with sector classification: {stocks_with_sectors}")
    print(f"  - Stocks without classification: {stocks_without_sectors}")

    # Count by sector
    print("\nTop 5 sectors by stock count:")
    sectors = db.session.query(
        Sector.name,
        db.func.count(Instrument.id).label('stock_count')
    ).select_from(Sector).join(SubSector).join(Instrument).filter(
        Instrument.exchange == 'NSE',
        Instrument.is_nifty500 == True
    ).group_by(Sector.id, Sector.name).order_by(db.text('stock_count DESC')).limit(5).all()

    for sector_name, count in sectors:
        print(f"  - {sector_name}: {count} stocks")

    print("\n✓ Verification completed!")


def main():
    """Main import function"""
    print("\n" + "="*80)
    print("NIFTY 500 STOCKS IMPORT WITH INSTITUTIONAL CLASSIFICATION")
    print("="*80)
    print("\nThis script will:")
    print("  1. Map stock symbols to subsectors from institutional classification")
    print("  2. Fetch stock metadata from Kite Connect API")
    print("  3. Import ~500 stocks with sector assignments")
    print("="*80)

    try:
        app = create_app()
        with app.app_context():
            # Step 1: Build subsector mapping
            symbol_to_subsector = build_subsector_mapping()

            # Step 2: Fetch and import stocks
            imported, skipped, errors = fetch_and_import_stocks(symbol_to_subsector)

            # Step 3: Verify
            verify_import()

            print("\n" + "="*80)
            print("IMPORT COMPLETED SUCCESSFULLY")
            print("="*80)
            print("\nYou can now:")
            print("  - View stocks at: http://localhost:5002/stocks/")
            print("  - Filter by sectors and subsectors")
            print("  - Edit individual stocks to adjust classifications")
            print("="*80 + "\n")

            return 0

    except Exception as e:
        print(f"\n❌ ERROR: Import failed!")
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
