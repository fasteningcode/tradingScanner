#!/usr/bin/env python3
"""
Script to fix NIFTY 500 stock classifications
- Add missing stocks
- Fix sector/subsector assignments for all stocks
"""

import sys
import os

# Add the project root directory to the path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app import create_app, db
from app.models import Instrument, Sector, SubSector

# Complete NIFTY 500 stock list with sector classification
COMPLETE_STOCK_CLASSIFICATION = {
    # 1. BANKING & FINANCIAL SERVICES
    'Private Banks': [
        'AXISBANK', 'ICICIBANK', 'HDFCBANK', 'KOTAKBANK', 'INDUSINDBK',
        'RBLBANK', 'YESBANK', 'BANDHANBNK', 'FEDERALBNK', 'AUBANK',
        'CUB', 'KARURVYSYA', 'IDFCFIRSTB'
    ],
    'Public Sector Banks': [
        'SBIN', 'CANBK', 'BANKBARODA', 'PNB', 'UNIONBANK', 'BANKINDIA',
        'CENTRALBK', 'INDIANB', 'J&KBANK', 'IOB', 'UCOBANK', 'MAHABANK'
    ],
    'NBFCs & Finance': [
        'BAJFINANCE', 'BAJAJFINSV', 'BAJAJHFL', 'MUTHOOTFIN', 'M&MFIN',
        'CHOLAFIN', 'SHRIRAMFIN', 'LICHSGFIN', 'POONAWALLA', 'MANAPPURAM',
        'IIFL', 'JMFINANCIL', 'PNBHOUSING', 'CANFINHOME', 'APTUS',
        'AADHARHFC', 'HOMEFIRST', 'SBFC', 'CREDITACC', 'SUNDARMFIN',
        'AAVAS'
    ],
    'Insurance': [
        'SBILIFE', 'HDFCLIFE', 'ICICIPRULI', 'LICI', 'ICICIGI',
        'STARHEALTH', 'NIACL', 'NIVABUPA', 'GODIGIT', 'POLICYBZR',
        'SAILIFE', 'GICRE'
    ],
    'AMC & Broking': [
        'HDFCAMC', 'UTIAMC', 'ABSLAMC', 'ANGELONE', 'NUVAMA',
        'MOTILALOFS', '360ONE', 'ANANDRATHI'
    ],
    'Other Financial Services': [
        'BAJAJHLDNG', 'CHOLAHLDNG', 'MFSL', 'ABCAPITAL', 'SAMMAANCAP',
        'IDBI', 'IKS', 'IFCI', 'PFC', 'RECLTD', 'IRFC', 'CRISIL',
        'SBICARD', 'CDSL', 'KFINTECH', 'CAMS'
    ],

    # 2. INFORMATION TECHNOLOGY & TECHNOLOGY SERVICES
    'Large Cap IT Services': [
        'TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM', 'LTTS', 'LTIM'
    ],
    'Mid/Small Cap IT': [
        'PERSISTENT', 'COFORGE', 'KPITTECH', 'MPHASIS', 'SONATSOFTW',
        'CYIENT', 'BSOFT', 'TATAELXSI', 'HAPPSTMNDS', 'ZENSARTECH',
        'INTELLECT', 'LATENTVIEW', 'BLS', 'ZENTEC', 'OFSS'
    ],
    'Specialized Tech/Platforms': [
        'ECLERX', 'NEWGEN', 'DATAPATTNS', 'PAYTM', 'NAUKRI', 'AFFLE',
        'INDIAMART', 'MAPMYINDIA', 'FIRSTCRY', 'NYKAA', 'SWIGGY'
    ],
    'Fintech/Digital': [
        'BSE', 'MCX'
    ],

    # 3. PHARMACEUTICALS & HEALTHCARE
    'Large Cap Pharma': [
        'SUNPHARMA', 'DRREDDY', 'CIPLA', 'LUPIN', 'DIVISLAB', 'BIOCON',
        'ALKEM', 'TORNTPHARM', 'AUROPHARMA', 'ZYDUSLIFE'
    ],
    'Mid Cap Pharma': [
        'GLENMARK', 'NATCOPHARM', 'AJANTPHARM', 'JUBLPHARMA', 'MANKIND',
        'LAURUSLABS', 'IPCALAB', 'EMCURE', 'AKUMS'
    ],
    'Specialty Pharma': [
        'GLAND', 'NEULANDLAB', 'SYNGENE', 'LALPATHLAB', 'POLYMED',
        'GRANULES', 'ERIS', 'PPLPHARMA', 'WOCKPHARMA', 'ALKYLAMINE',
        'JBCHEPHARM'
    ],
    'Healthcare Services': [
        'APOLLOHOSP', 'MAXHEALTH', 'FORTIS', 'METROPOLIS', 'KIMS',
        'ASTERDM', 'RAINBOW', 'MEDANTA', 'AGARWALEYE'
    ],
    'MNC Pharma': [
        'ABBOTINDIA', 'PFIZER', 'GLAXO', 'ASTRAZEN'
    ],

    # 4. AUTOMOTIVE & AUTO COMPONENTS
    'Passenger Vehicles': [
        'MARUTI', 'M&M', 'HYUNDAI'
    ],
    'Two Wheelers': [
        'HEROMOTOCO', 'BAJAJ-AUTO', 'TVSMOTOR', 'EICHERMOT'
    ],
    'Commercial Vehicles': [
        'ASHOKLEY', 'ESCORTS', 'FORCEMOT'
    ],
    'EV/New Age Auto': [
        'OLAELEC', 'ATHERENERG'
    ],
    'Auto Components - Tier 1': [
        'MOTHERSON', 'BOSCHLTD', 'MSUMI', 'ENDURANCE', 'SCHAEFFLER',
        'BHARATFORG', 'SUNDRMFAST', 'SONACOMS'
    ],
    'Auto Components - Others': [
        'APOLLOTYRE', 'CEATLTD', 'MRF', 'BALKRISIND', 'JKTYRE',
        'EXIDEIND', 'UNOMINDA'
    ],
    'Auto Ancillaries': [
        'FINCABLES', 'RKFORGE'
    ],

    # 5. CAPITAL GOODS, ENGINEERING & INFRASTRUCTURE
    'Heavy Engineering & Defense': [
        'BEL', 'HAL', 'BDL', 'BEML', 'BHEL', 'GRSE', 'COCHINSHIP',
        'MAZDOCK', 'GESHIP', 'TITAGARH'
    ],
    'Capital Goods': [
        'ABB', 'SIEMENS', 'CUMMINSIND', 'THERMAX', 'HBLENGINE',
        'KIRLOSENG', 'ELECON', 'CRAFTSMAN', 'ELGIEQUIP', 'KSB',
        'POWERINDIA'
    ],
    'Infrastructure - Construction': [
        'LT', 'NCC', 'IRB', 'AFCONS', 'NBCC'
    ],
    'Infrastructure - Power Transmission': [
        'KEC', 'KPIL'
    ],
    'Bearings & Industrial': [
        'TIMKEN', 'SKFINDIA'
    ],
    'Railways': [
        'IRCON', 'RVNL', 'RITES', 'RAILTEL', 'IRCTC'
    ],
    'Cables & Wires': [
        'POLYCAB', 'KEI', 'RRKABEL'
    ],
    'Pumps & Valves': [
        'KIRLOSBROS'
    ],
    'Precision Engineering': [
        'KAYNES', 'SYRMA', 'JYOTICNC'
    ],

    # 6. OIL, GAS & ENERGY
    'Upstream': [
        'ONGC', 'OIL', 'GAIL'
    ],
    'Refining & Marketing': [
        'RELIANCE', 'IOC', 'BPCL', 'HINDPETRO', 'CHENNPETRO', 'MRPL'
    ],
    'Gas Distribution': [
        'IGL', 'MGL', 'GUJGASLTD', 'GSPL'
    ],
    'Gas Transportation': [
        'PETRONET'
    ],
    'Oil Storage': [
        'AEGISVOPAK'
    ],

    # 7. POWER & UTILITIES
    'Power Generation': [
        'NTPC', 'TATAPOWER', 'ADANIPOWER', 'TORNTPOWER', 'JPPOWER',
        'CESC', 'NHPC', 'SJVN', 'JSWENERGY', 'RELINFRA'
    ],
    'Renewable Energy': [
        'ADANIGREEN', 'ADANIENSOL', 'SUZLON', 'INOXWIND', 'WAAREEENER',
        'PREMIERENE', 'ACMESOLAR', 'NTPCGREEN', 'IREDA'
    ],
    'Power Equipment': [
        'CROMPTON', 'HAVELLS', 'VOLTAS', 'BLUESTARCO', 'VGUARD'
    ],
    'Transmission': [
        'POWERGRID', 'ATGL'
    ],

    # 8. METALS & MINING
    'Steel - Integrated': [
        'TATASTEEL', 'JSWSTEEL', 'SAIL', 'JINDALSTEL'
    ],
    'Steel - Secondary': [
        'JSL', 'JSWINFRA'
    ],
    'Aluminum': [
        'HINDALCO', 'NATIONALUM', 'VEDL'
    ],
    'Zinc/Lead': [
        'HINDZINC'
    ],
    'Copper': [
        'HINDCOPPER'
    ],
    'Iron Ore/Coal': [
        'NMDC', 'COALINDIA'
    ],
    'Specialty Metals': [
        'MAHSEAMLES', 'JINDALSAW'
    ],
    'Ferrous/Non-Ferrous': [
        'GRAVITA', 'APLLTD', 'LLOYDSME', 'APARINDS'
    ],

    # 9. CEMENT & BUILDING MATERIALS
    'Cement - Large Cap': [
        'ULTRACEMCO', 'SHREECEM', 'AMBUJACEM', 'ACC', 'DALBHARAT',
        'JKCEMENT', 'RAMCOCEM'
    ],
    'Cement - Mid Cap': [
        'INDIACEM', 'NUVOCO'
    ],
    'Building Materials': [
        'CENTURYPLY'
    ],

    # 10. CHEMICALS & PETROCHEMICALS
    'Specialty Chemicals': [
        'SRF', 'AARTIIND', 'DEEPAKNTR', 'CLEAN', 'NAVINFLUOR',
        'FLUOROCHEM', 'TATACHEM'
    ],
    'Agrochemicals': [
        'UPL', 'PIIND', 'SUMICHEM'
    ],
    'Commodity Chemicals': [
        'DCMSHRIRAM', 'BALRAMCHIN', 'FACT', 'RCF', 'COROMANDEL',
        'DEEPAKFERT', 'CHAMBLFERT', 'EIDPARRY'
    ],
    'Paints & Coatings': [
        'ASIANPAINT', 'BERGEPAINT', 'AKZOINDIA'
    ],
    'Other Chemicals': [
        'ATUL', 'BASF', 'CASTROLIND', 'PIDILITIND'
    ],

    # 11. CONSUMER GOODS - FMCG
    'Diversified FMCG': [
        'HINDUNILVR', 'ITC', 'BRITANNIA', 'NESTLEIND', 'DABUR',
        'MARICO', 'GODREJCP', 'EMAMILTD', 'JYOTHYLAB', 'COLPAL'
    ],
    'Food & Beverages': [
        'TATACONSUM', 'VBL', 'BIKAJI', 'DEVYANI', 'JUBLFOOD',
        'SAPPHIRE', 'LTFOODS', 'UBL', 'RADICO'
    ],
    'Personal Care': [
        'HONASA'
    ],
    'Tobacco': [
        'GODFRYPHLP'
    ],
    'Staples': [],

    # 12. CONSUMER DURABLES & RETAIL
    'Consumer Durables': [
        'WHIRLPOOL', 'DIXON'
    ],
    'Retail': [
        'TRENT', 'DMART', 'ABFRL'
    ],
    'Jewelry': [
        'TITAN', 'KALYANKJIL'
    ],
    'Eyewear': [],

    # 13. REAL ESTATE & CONSTRUCTION
    'Real Estate - Residential': [
        'DLF', 'GODREJPROP', 'PRESTIGE', 'OBEROIRLTY', 'BRIGADE',
        'SOBHA', 'LODHA', 'PHOENIXLTD', 'ANANTRAJ', 'SIGNATURE',
        'DBREALTY'
    ],
    'Real Estate - Commercial': [],
    'Real Estate - Affordable': [],
    'Construction Materials': [],

    # 14. TELECOM & TOWER
    'Telecom Services': [
        'BHARTIARTL', 'JIOFIN', 'IDEA', 'TTML', 'TATACOMM',
        'BHARTIHEXA'
    ],
    'Tower Infrastructure': [
        'INDUSTOWER'
    ],

    # 15. MEDIA, ENTERTAINMENT & HOSPITALITY
    'Media & Broadcasting': [
        'ZEEL', 'SUNTV', 'SAREGAMA', 'HATHWAY'
    ],
    'Hospitality': [
        'INDHOTEL', 'LEMONTREE', 'EIHOTEL', 'CHALET', 'THELEELA',
        'ITCHOTELS'
    ],
    'QSR/Food Services': [],
    'Multiplexes': [
        'PVRINOX'
    ],

    # 16. LOGISTICS, TRANSPORTATION & INFRASTRUCTURE
    'Logistics': [
        'BLUEDART', 'DELHIVERY', 'AEGISLOG', 'CONCOR', 'VRL'
    ],
    'Ports': [
        'ADANIPORTS'
    ],
    'Shipping': [
        'SCI'
    ],
    'Aviation': [
        'INDIGO'
    ],
    'Others': [
        'GMRAIRPORT'
    ],

    # 17. TEXTILES & APPAREL
    'Textiles': [
        'TRIDENT', 'WELCORP', 'WELSPUNLIV', 'KPRMILL', 'CCL',
        'GRASIM'
    ],
    'Apparel/Fashion': [
        'MANYAVAR', 'PAGEIND'
    ],
    'Home Textiles': [],

    # 18. MISCELLANEOUS & DIVERSIFIED
    'Conglomerates': [
        'ADANIENT'
    ],
    'Trading & Distribution': [
        'REDINGTON', 'BBTC', 'MMTC'
    ],
    'Paper & Packaging': [],
    'Agriculture/Fertilizers': [],
    'Services': [
        'SAGILITY', 'COHANCE'
    ],
    'New Age/Platform': [],
    'Others': [
        'GODREJIND', 'GODREJAGRO', 'PATANJALI', 'PRAJIND',
        'BATAINDIA', 'AWL', 'ALOKINDS', 'VIJAYA', 'ABLBL',
        'TEJASNET', 'AMBER', 'TATAINVEST', 'VMM', 'TMPV',
        'PGHH', 'PGEL', 'IGIL', 'CHOICEIN', 'RHIM', 'BLUEJET',
        'FIVESTAR', 'DOMS', 'TRITURBINE', 'PTCIL', 'LTF',
        'OLECTRA', 'VENTIVE', 'USHAMART', 'NAM-INDIA', 'TRIVENI',
        'FSL', 'ONESOURCE', 'SOLARINDS', 'ABREL', 'VTL',
        'NAVA', 'CAPLIPOINT', 'AIIL', 'GPIL', 'CONCORDBIO',
        'CAMPUS', 'GMDCLTD', 'NLCINDIA', '3MINDIA', 'MINDACORP',
        'AIAENG', 'BAYERCROP', 'ENRIN', 'ACE', 'SWANCORP',
        'GVT&D', 'SARDAEN', 'NSLNISP', 'JUBLINGREA', 'ARE&M',
        'HONAUT', 'TIINDIA', 'HUDCO', 'SYRMA', 'HSCL', 'JWL',
        'TATATECH', 'UNITDSPR', 'CGPOWER', 'GILLETTE', 'SCHNEIDER',
        'NH', 'CGCL', 'HEXT', 'JBMA', 'INDGN', 'SHYAMMETL',
        'IEX', 'ETERNAL', 'ZFCVINDIA', 'HFCL'
    ],

    # 19. SPECIALIZED INDUSTRIAL & MANUFACTURING
    'Glass & Ceramics': [
        'ASAHIINDIA', 'KAJARIACER', 'CERA'
    ],
    'Abrasives & Refractories': [
        'CARBORUNIV'
    ],
    'Plastics & Pipes': [
        'ASTRAL', 'SUPREMEIND', 'FINPIPE', 'APLAPOLLO'
    ],
    'Electrical Equipment': [
        'TECHNOE'
    ],
    'Industrial Gases': [
        'INOXINDIA', 'LINDEINDIA'
    ],
    'Graphite & Electrodes': [
        'GRAPHITE', 'HEG'
    ],
    'Engineering Services': [
        'ENGINERSIN'
    ],

    # 20. EMERGING/THEMATIC SECTORS
    'EV Ecosystem': [],
    'Digital/Fintech': [],
    'Green Energy/ESG Focus': [],
    'Defense & Aerospace': [],
    'Data Centers/Cloud': [
        'NETWEB', 'TBOTEK'
    ]
}


def build_subsector_lookup():
    """Build subsector name -> ID lookup"""
    print("\n" + "="*80)
    print("STEP 1: Building Subsector Lookup")
    print("="*80)

    subsectors = SubSector.query.join(Sector).filter(
        SubSector.is_active == True,
        Sector.is_active == True
    ).all()

    lookup = {}
    for ss in subsectors:
        lookup[ss.name] = ss.id

    print(f"✓ Built lookup for {len(lookup)} subsectors")
    return lookup


def build_symbol_to_subsector_map(subsector_lookup):
    """Create symbol -> subsector_id mapping"""
    print("\n" + "="*80)
    print("STEP 2: Building Symbol to Subsector Mapping")
    print("="*80)

    symbol_map = {}
    unmapped_subsectors = []

    for subsector_name, symbols in COMPLETE_STOCK_CLASSIFICATION.items():
        if not symbols:  # Skip empty lists
            continue

        if subsector_name not in subsector_lookup:
            unmapped_subsectors.append(subsector_name)
            continue

        subsector_id = subsector_lookup[subsector_name]
        for symbol in symbols:
            if symbol not in symbol_map:  # First occurrence wins
                symbol_map[symbol] = subsector_id

    print(f"✓ Mapped {len(symbol_map)} symbols to subsectors")

    if unmapped_subsectors:
        print(f"\n⚠ Warning: {len(unmapped_subsectors)} subsectors not found:")
        for name in unmapped_subsectors[:5]:
            print(f"  - {name}")

    return symbol_map


def add_missing_stocks(symbol_map):
    """Add stocks that are missing from database"""
    print("\n" + "="*80)
    print("STEP 3: Adding Missing Stocks")
    print("="*80)

    all_symbols = set(symbol_map.keys())
    existing_symbols = set(
        s[0] for s in db.session.query(Instrument.tradingsymbol).filter_by(
            exchange='NSE', is_nifty500=True
        ).all()
    )

    missing_symbols = all_symbols - existing_symbols

    if not missing_symbols:
        print("✓ No missing stocks")
        return 0

    print(f"\nFound {len(missing_symbols)} missing stocks:")
    for symbol in sorted(list(missing_symbols)[:10]):
        print(f"  - {symbol}")

    added = 0
    for symbol in missing_symbols:
        try:
            instrument_token = abs(hash(symbol)) % (10 ** 10)

            instrument = Instrument(
                instrument_token=instrument_token,
                tradingsymbol=symbol,
                name=symbol,
                exchange='NSE',
                segment='NSE',
                instrument_type='EQ',
                is_nifty500=True,
                sub_sector_id=symbol_map.get(symbol)
            )

            db.session.add(instrument)
            added += 1

            if added % 10 == 0:
                db.session.commit()

        except Exception as e:
            print(f"  ⚠ Error adding {symbol}: {str(e)}")
            db.session.rollback()

    db.session.commit()
    print(f"\n✓ Added {added} missing stocks")
    return added


def fix_sector_classifications(symbol_map):
    """Fix sector classifications for existing stocks"""
    print("\n" + "="*80)
    print("STEP 4: Fixing Sector Classifications")
    print("="*80)

    stocks = Instrument.query.filter_by(exchange='NSE', is_nifty500=True).all()

    fixed = 0
    unchanged = 0

    for stock in stocks:
        correct_subsector_id = symbol_map.get(stock.tradingsymbol)

        if correct_subsector_id != stock.sub_sector_id:
            stock.sub_sector_id = correct_subsector_id
            fixed += 1

            if fixed % 50 == 0:
                db.session.commit()
                print(f"  Fixed {fixed} classifications...")
        else:
            unchanged += 1

    db.session.commit()

    print(f"\n✓ Fixed {fixed} stock classifications")
    print(f"✓ {unchanged} stocks already had correct classification")

    return fixed


def verify_results():
    """Verify the final state"""
    print("\n" + "="*80)
    print("STEP 5: Verification")
    print("="*80)

    total = Instrument.query.filter_by(exchange='NSE', is_nifty500=True).count()
    with_sectors = Instrument.query.filter(
        Instrument.exchange == 'NSE',
        Instrument.is_nifty500 == True,
        Instrument.sub_sector_id.isnot(None)
    ).count()
    without_sectors = total - with_sectors

    print(f"\nFinal state:")
    print(f"  - Total NIFTY 500 stocks: {total}")
    print(f"  - Stocks with classification: {with_sectors} ({100*with_sectors//total}%)")
    print(f"  - Stocks without classification: {without_sectors}")

    if without_sectors > 0:
        print(f"\nStocks without classification:")
        unclassified = Instrument.query.filter(
            Instrument.exchange == 'NSE',
            Instrument.is_nifty500 == True,
            Instrument.sub_sector_id.is_(None)
        ).limit(20).all()

        for stock in unclassified:
            print(f"  - {stock.tradingsymbol}")

    print("\n✓ Verification completed!")


def main():
    """Main function"""
    print("\n" + "="*80)
    print("FIX NIFTY 500 STOCK CLASSIFICATIONS")
    print("="*80)

    try:
        app = create_app()
        with app.app_context():
            # Step 1: Build subsector lookup
            subsector_lookup = build_subsector_lookup()

            # Step 2: Build symbol mapping
            symbol_map = build_symbol_to_subsector_map(subsector_lookup)

            # Step 3: Add missing stocks
            added = add_missing_stocks(symbol_map)

            # Step 4: Fix classifications
            fixed = fix_sector_classifications(symbol_map)

            # Step 5: Verify
            verify_results()

            print("\n" + "="*80)
            print("FIX COMPLETED SUCCESSFULLY")
            print("="*80)
            print(f"\nSummary:")
            print(f"  - Stocks added: {added}")
            print(f"  - Classifications fixed: {fixed}")
            print("="*80 + "\n")

            return 0

    except Exception as e:
        print(f"\n❌ ERROR: Fix failed!")
        print(f"Error details: {str(e)}")
        db.session.rollback()
        return 1


if __name__ == '__main__':
    sys.exit(main())
