# Project Structure

This document describes the organized structure of the V1 project.

## Directory Organization

```
V1/
├── app/                    # Main application code
│   ├── __init__.py        # Flask app factory
│   ├── models.py          # Database models
│   ├── routes/            # Route handlers
│   └── services/          # Business logic
│
├── tests/                 # Test files
│   ├── test_exact_postman.py
│   ├── test_json_storage.py
│   ├── test_kite_direct.py
│   └── test_kite_token.py
│
├── scripts/               # Utility and migration scripts
│   ├── clear_all_stocks.py
│   ├── fix_nifty500_classification.py
│   ├── import_nifty500_stocks.py
│   ├── manage_nifty500.py
│   ├── migrate_add_nifty500.py
│   ├── migrate_institutional_sectors.py
│   ├── migrate_sectors.py
│   ├── sync_instruments_cli.py
│   ├── update_instrument_tokens.py
│   └── view_logs.sh
│
├── docs/                  # Documentation
│   ├── README.md          # Developer documentation
│   ├── QUICK_START.md     # Quick start guide
│   ├── QUICK_TEST_GUIDE.md
│   ├── requirement.md     # Requirements specification
│   ├── setup.sh           # Setup script
│   ├── PROJECT_STRUCTURE.md  # This file
│   └── archive/           # Historical documentation
│       ├── DEBUG_FINDINGS.md
│       ├── DETAILED_DEBUG_LOGS_ADDED.md
│       ├── FINAL_STATUS_REPORT.md
│       ├── FORCE_RESET_FEATURE.md
│       ├── HISTORICAL_DATA_FIXES_APPLIED.md
│       ├── HISTORICAL_DATA_ISSUE_REPORT.md
│       ├── INSTRUMENT_TOKENS_UPDATED.md
│       ├── JAVASCRIPT_FIXES.md
│       ├── MONITORING_LOGS.md
│       ├── PROJECT_STATUS.md
│       ├── RESOLUTION_FOUND.md
│       └── SECTOR_MANAGEMENT_README.md
│
├── migrations/            # Database migrations
├── instance/              # Instance-specific data (databases)
├── logs/                  # Application logs
├── venv/                  # Python virtual environment
│
├── config.py             # Application configuration
├── run.py                # Application entry point
├── requirements.txt      # Python dependencies
└── README.md             # Project overview

```

## Running Scripts

All scripts in the `scripts/` directory can be run from the project root:

```bash
# Example: Sync instruments from Kite
python scripts/sync_instruments_cli.py

# Example: Update instrument tokens
python scripts/update_instrument_tokens.py

# Example: View logs
./scripts/view_logs.sh
```

## Running Tests

All tests in the `tests/` directory can be run from the project root:

```bash
# Example: Run a specific test
python tests/test_json_storage.py

# Example: Run all tests (if using pytest)
pytest tests/
```

## Important Notes

1. **Always run scripts/tests from the project root directory**
2. All Python scripts automatically add the project root to their Python path
3. The virtual environment must be activated before running any scripts
4. Database files are stored in `instance/`
5. Log files are stored in `logs/`

## Archive Directory

The `docs/archive/` directory contains historical documentation from development and debugging sessions. These files are kept for reference but are not part of the active documentation.
