#!/usr/bin/env python
"""
Management script for NIFTY 500 stocks list
"""

from app import create_app, db
from app.models import Nifty500List, Instrument
from datetime import datetime

# NIFTY 500 stock symbols
NIFTY_500_SYMBOLS = [
    'NAVINFLUOR', 'CHENNPETRO', 'INTELLECT', 'LATENTVIEW', 'IDBI', 'IKS', 'UNIONBANK', 'WELCORP',
    'BEL', 'TIMKEN', 'AUROPHARMA', 'FORCEMOT', 'IDFCFIRSTB', 'STARHEALTH', 'CANBK', 'FLUOROCHEM',
    'SCHAEFFLER', 'UNITDSPR', 'CHOICEIN', 'SOBHA', 'NEULANDLAB', 'YESBANK', 'PNB', 'LODHA',
    'UCOBANK', 'APTUS', 'MRPL', 'BANKBARODA', 'SAMMAANCAP', 'EICHERMOT', 'ESCORTS', 'SHRIRAMFIN',
    'HONASA', 'AEGISVOPAK', 'IOC', 'BLUEJET', 'LALPATHLAB', 'RHIM', 'GODREJIND', 'MCX',
    'BSE', 'OBEROIRLTY', 'GESHIP', 'ADANIENSOL', 'SUZLON', 'DIVISLAB', 'DATAPATTNS', 'HINDPETRO',
    'BDL', 'POLYMED', 'FIVESTAR', 'LUPIN', 'GLAND', 'BHEL', 'DOMS', 'MAHABANK',
    'TRITURBINE', 'ACC', 'PTCIL', 'CERA', 'LT', 'LTF', 'OLECTRA', 'BANKINDIA',
    'JPPOWER', 'HAL', 'TCS', 'FEDERALBNK', 'LTFOODS', 'CCL', 'UNOMINDA', 'RRKABEL',
    'IRB', 'HYUNDAI', 'VENTIVE', 'APLAPOLLO', 'HEROMOTOCO', 'SBFC', 'METROPOLIS', 'GODREJCP',
    'CENTRALBK', 'INDIANB', 'COCHINSHIP', 'TVSMOTOR', 'ONGC', 'GLENMARK', 'INDIACEM', 'ASHOKLEY',
    'UBL', 'USHAMART', 'NIVABUPA', 'COALINDIA', 'RBLBANK', 'NAM-INDIA', 'ASTRAZEN', 'IFCI',
    'SBIN', 'LICHSGFIN', 'TRIVENI', 'ITC', 'J&KBANK', 'ECLERX', 'BHARATFORG', 'LTTS',
    'BOSCHLTD', 'FSL', 'HDFCAMC', 'GRSE', 'SYNGENE', 'CRAFTSMAN', 'NEWGEN', 'MGL',
    'CGPOWER', 'IOB', 'TORNTPOWER', 'ONESOURCE', 'GODREJAGRO', 'SOLARINDS', 'MARICO', 'ANANTRAJ',
    'AJANTPHARM', 'DEEPAKFERT', 'DALBHARAT', 'INOXWIND', 'HEG', 'ABREL', 'AGARWALEYE', 'VTL',
    'M&MFIN', 'NCC', 'UTIAMC', 'MUTHOOTFIN', 'IGL', 'CESC', 'HBLENGINE', 'GLAXO',
    'NAVA', 'CAPLIPOINT', 'MRF', 'AIIL', 'RELIANCE', 'IDEA', 'SUPREMEIND', 'HINDZINC',
    'JSWSTEEL', 'BRITANNIA', 'APLLTD', 'JINDALSTEL', 'GPIL', 'PRESTIGE', 'TITAN', 'DMART',
    'EIDPARRY', 'EXIDEIND', 'JKCEMENT', 'PAGEIND', 'BHARTIARTL', 'COLPAL', 'SJVN', 'NMDC',
    'BAJAJ-AUTO', 'AUBANK', 'WAAREEENER', 'TTML', 'BRIGADE', 'CRISIL', 'OIL', 'KPITTECH',
    'CONCORDBIO', 'CAMPUS', 'MARUTI', 'MAZDOCK', 'RADICO', 'POONAWALLA', 'PETRONET', 'M&M',
    'LTIM', 'FINCABLES', 'HINDUNILVR', 'KSB', 'DRREDDY', 'APOLLOTYRE', 'CENTURYPLY', 'ADANIGREEN',
    'ABCAPITAL', 'GMDCLTD', 'AMBUJACEM', 'BATAINDIA', 'BPCL', 'AFFLE', 'IGIL', 'WIPRO',
    'BAJAJHFL', 'SONATSOFTW', 'SAIL', 'UPL', 'AWL', 'JINDALSAW', 'SAILIFE', 'GRAVITA',
    'SBILIFE', 'PIIND', 'CONCOR', 'PGHH', 'GAIL', 'KPIL', 'KALYANKJIL', 'PGEL',
    'AARTIIND', 'BBTC', 'AXISBANK', 'PFC', 'ADANIPORTS', 'VMM', 'INDIAMART', 'BERGEPAINT',
    'BASF', 'LICI', 'ITCHOTELS', 'PPLPHARMA', 'CLEAN', 'RAINBOW', 'IRFC', 'RKFORGE',
    'FACT', 'ENDURANCE', 'SUNDARMFIN', 'BIKAJI', 'TMPV', 'GODREJPROP', 'BHARTIHEXA', 'ABLBL',
    'ALOKINDS', 'VIJAYA', 'ICICIGI', 'TEJASNET', 'ASIANPAINT', 'KARURVYSYA', 'INDHOTEL', 'ALKEM',
    'TATAINVEST', 'HCLTECH', 'CHOLAFIN', 'NESTLEIND', 'AKZOINDIA', 'CASTROLIND', 'AMBER', 'SBICARD',
    'NAUKRI', 'PAYTM', 'MFSL', 'MSUMI', 'TECHM', 'PERSISTENT', 'GMRAIRPORT', 'BAJFINANCE',
    'ATUL', 'PNBHOUSING', 'SIEMENS', 'JYOTICNC', 'SUNPHARMA', 'AFCONS', 'TRIDENT', 'ANGELONE',
    'RVNL', 'CHAMBLFERT', 'FIRSTCRY', 'CUMMINSIND', 'RPOWER', 'CAMS', 'KEC', 'LINDEINDIA',
    'TATASTEEL', 'PHOENIXLTD', 'INFY', 'BLS', 'CHOLAHLDNG', 'INDUSINDBK', 'MAPMYINDIA', 'RECLTD',
    'DEEPAKNTR', 'JIOFIN', 'NLCINDIA', 'GUJGASLTD', 'AADHARHFC', 'CYIENT', '3MINDIA', 'MINDACORP',
    'ELGIEQUIP', 'AIAENG', 'BAYERCROP', 'ENRIN', 'WOCKPHARMA', 'ACE', 'GSPL', 'POWERINDIA',
    'DIXON', 'SWANCORP', 'TRENT', 'NBCC', 'TATACHEM', 'THELEELA', 'GVT&D', 'RAILTEL',
    'BEML', 'BIOCON', 'ZYDUSLIFE', 'HDFCBANK', 'HAVELLS', 'OFSS', 'RITES', 'GILLETTE',
    'COFORGE', 'ABB', 'IREDA', 'KIMS', 'BAJAJHLDNG', 'ZENSARTECH', 'ULTRACEMCO', 'SARDAEN',
    'NSLNISP', 'JUBLINGREA', 'ARE&M', 'TECHNOE', 'INDUSTOWER', 'HOMEFIRST', 'SUNTV', 'POWERGRID',
    'PATANJALI', 'BAJAJFINSV', 'TATACONSUM', 'ASTRAL', 'FINPIPE', 'EIHOTEL', 'HAPPSTMNDS', 'HONAUT',
    'IIFL', 'TIINDIA', 'TATAPOWER', 'HUDCO', 'SYRMA', 'HSCL', 'JWL', 'ICICIBANK',
    'KAJARIACER', 'THERMAX', 'SKFINDIA', 'JKTYRE', 'TATATECH', 'KFINTECH', 'KAYNES', 'SIGNATURE',
    'DBREALTY', 'EMCURE', 'CROMPTON', 'CANFINHOME', 'SUMICHEM', 'RELINFRA', 'LLOYDSME', 'MOTHERSON',
    'ATGL', 'IRCON', 'INDIGO', 'IRCTC', 'MANAPPURAM', 'ICICIPRULI', 'HINDALCO', 'SHREECEM',
    'KIRLOSBROS', 'OLAELEC', 'APOLLOHOSP', 'BSOFT', 'ELECON', 'CDSL', 'ZEEL', 'ZENTEC',
    'IPCALAB', 'SAREGAMA', 'KOTAKBANK', 'NTPCGREEN', 'GRANULES', 'NIACL', 'NHPC', 'BLUESTARCO',
    'SCI', 'LAURUSLABS', 'TITAGARH', 'AKUMS', 'PREMIERENE', 'SUNDRMFAST', 'TORNTPHARM', 'ALKYLAMINE',
    'ERIS', 'NUVAMA', 'JYOTHYLAB', 'TATAELXSI', 'JSWINFRA', 'ANANDRATHI', 'SRF', 'EMAMILTD',
    'HFCL', 'REDINGTON', 'NATCOPHARM', 'RAMCOCEM', 'CHALET', 'MMTC', 'KIRLOSENG', 'JBCHEPHARM',
    'RCF', 'NATIONALUM', 'TARIL', 'ITI', 'COROMANDEL', 'GRASIM', 'POLYCAB', 'ENGINERSIN',
    'BALKRISIND', 'MAHSEAMLES', 'KPRMILL', 'VGUARD', 'NETWEB', 'INOXINDIA', 'DELHIVERY', 'CEATLTD',
    'AAVAS', 'PRAJIND', 'ASAHIINDIA', 'GODFRYPHLP', 'JSWENERGY', 'LEMONTREE', 'FORTIS', 'PFIZER',
    'SONACOMS', 'NUVOCO', 'SWIGGY', 'KEI', 'JMFINANCIL', 'ABBOTINDIA', 'PCBL', 'TBOTEK',
    'ADANIENT', 'GRAPHITE', 'ABFRL', 'HDFCLIFE', 'GODIGIT', 'TATACOMM', 'JUBLFOOD', 'SCHNEIDER',
    'NH', 'CGCL', 'WHIRLPOOL', 'HINDCOPPER', 'GICRE', 'BALRAMCHIN', 'CARBORUNIV', 'ABSLAMC',
    'HEXT', 'DLF', 'WELSPUNLIV', 'VEDL', 'MAXHEALTH', 'JBMA', 'CIPLA', 'NTPC',
    'JUBLPHARMA', 'INDGN', 'ACMESOLAR', 'PIDILITIND', 'ATHERENERG', 'DABUR', 'SHYAMMETL', 'VOLTAS',
    'ASTERDM', 'ADANIPOWER', 'IEX', 'MANKIND', 'BLUEDART', 'SAGILITY', 'DCMSHRIRAM', 'PVRINOX',
    'AEGISLOG', 'POLICYBZR', '360ONE', 'NYKAA', 'VBL', 'ETERNAL', 'COHANCE', 'JSL',
    'ZFCVINDIA', 'DEVYANI', 'MANYAVAR', 'CREDITACC', 'CUB', 'MEDANTA', 'MPHASIS', 'SAPPHIRE',
    'MOTILALOFS', 'APARINDS', 'BANDHANBNK'
]


def populate_nifty500():
    """Populate NIFTY 500 list in database"""
    app = create_app()

    with app.app_context():
        print("Populating NIFTY 500 stocks...")

        added_count = 0
        updated_count = 0

        for symbol in NIFTY_500_SYMBOLS:
            # Check if symbol already exists
            existing = Nifty500List.query.filter_by(symbol=symbol).first()

            if existing:
                # Update existing record
                existing.is_active = True
                existing.updated_at = datetime.utcnow()
                updated_count += 1
            else:
                # Add new record
                new_entry = Nifty500List(symbol=symbol, is_active=True)
                db.session.add(new_entry)
                added_count += 1

        # Commit all changes
        db.session.commit()

        print(f"✓ Added {added_count} new stocks")
        print(f"✓ Updated {updated_count} existing stocks")
        print(f"✓ Total NIFTY 500 stocks in database: {Nifty500List.query.filter_by(is_active=True).count()}")


def sync_instrument_nifty500_status():
    """Sync is_nifty500 flag in Instrument table based on Nifty500List"""
    app = create_app()

    with app.app_context():
        print("Syncing NIFTY 500 status in instruments...")

        # Get all NIFTY 500 symbols
        nifty500_symbols = {entry.symbol for entry in Nifty500List.query.filter_by(is_active=True).all()}

        # Reset all instruments first
        Instrument.query.update({'is_nifty500': False})

        # Mark NIFTY 500 stocks
        marked_count = 0
        for symbol in nifty500_symbols:
            # Update instruments matching this symbol (NSE exchange, EQ type)
            result = Instrument.query.filter_by(
                tradingsymbol=symbol,
                exchange='NSE',
                instrument_type='EQ'
            ).update({'is_nifty500': True})

            marked_count += result

        db.session.commit()

        print(f"✓ Marked {marked_count} instruments as NIFTY 500")
        print(f"✓ Total NIFTY 500 instruments: {Instrument.query.filter_by(is_nifty500=True).count()}")


def list_nifty500():
    """List all NIFTY 500 stocks in database"""
    app = create_app()

    with app.app_context():
        stocks = Nifty500List.query.filter_by(is_active=True).order_by(Nifty500List.symbol).all()

        print(f"\nNIFTY 500 Stocks ({len(stocks)} total):")
        print("-" * 50)

        for i, stock in enumerate(stocks, 1):
            print(f"{i:3}. {stock.symbol:15} (Added: {stock.added_at.strftime('%Y-%m-%d')})")


def clear_nifty500():
    """Clear all NIFTY 500 stocks from database"""
    app = create_app()

    with app.app_context():
        count = Nifty500List.query.delete()
        db.session.commit()

        print(f"✓ Removed {count} stocks from NIFTY 500 list")


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python manage_nifty500.py <command>")
        print("\nCommands:")
        print("  populate    - Populate NIFTY 500 stocks in database")
        print("  sync        - Sync is_nifty500 flag in instruments")
        print("  list        - List all NIFTY 500 stocks")
        print("  clear       - Clear all NIFTY 500 stocks")
        print("  refresh     - Populate + Sync (full refresh)")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == 'populate':
        populate_nifty500()
    elif command == 'sync':
        sync_instrument_nifty500_status()
    elif command == 'list':
        list_nifty500()
    elif command == 'clear':
        confirm = input("Are you sure you want to clear all NIFTY 500 stocks? (yes/no): ")
        if confirm.lower() == 'yes':
            clear_nifty500()
        else:
            print("Cancelled")
    elif command == 'refresh':
        populate_nifty500()
        print()
        sync_instrument_nifty500_status()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
