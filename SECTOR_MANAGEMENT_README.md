# Sector Management System - Implementation Guide

## Overview

A comprehensive hierarchical sector management system has been implemented for your Flask trading application. This system allows you to organize NIFTY 500 stocks in a structured 3-tier hierarchy:

**Sectors → Sub-Sectors → Stocks**

## What Has Been Implemented

### ✅ Database Models ([app/models.py](app/models.py))

1. **Sector Model** - Enhanced with new fields:
   - `is_active` - Enable/disable sectors
   - `display_order` - Custom ordering
   - `icon` - Bootstrap icon class
   - `color` - Hex color for visualization
   - Relationship to SubSector (one-to-many with cascade delete)
   - `to_dict()` method for JSON serialization

2. **SubSector Model** (New):
   - `name` - Sub-sector name
   - `sector_id` - Foreign key to parent sector
   - `description` - Optional description
   - `is_active` - Enable/disable sub-sectors
   - `display_order` - Custom ordering within sector
   - Unique constraint: (sector_id, name)
   - Relationships to Sector and Instrument
   - `to_dict()` method for JSON serialization

3. **Instrument Model** - Enhanced:
   - `sub_sector_id` - New foreign key to SubSector
   - `sub_sector_obj` - Relationship to SubSector
   - Old `sector` and `sub_sector` string fields marked as DEPRECATED (preserved for migration)

### ✅ Service Layer

1. **[SectorService](app/sector_service.py)** - Complete CRUD operations:
   - `create_sector()` - Create with validation
   - `update_sector()` - Update with validation
   - `delete_sector()` - Soft/hard delete with cascade handling
   - `get_sector_by_id()` - Retrieve sector
   - `get_all_sectors()` - List all with filtering
   - `reorder_sectors()` - Custom ordering
   - `get_sector_with_subsectors()` - Hierarchical data
   - `search_sectors()` - Search by name/description

2. **[SubSectorService](app/subsector_service.py)** - Complete CRUD + Stock management:
   - `create_sub_sector()` - Create under sector
   - `update_sub_sector()` - Update with validation
   - `delete_sub_sector()` - Soft/hard delete with stock handling
   - `get_sub_sector_by_id()` - Retrieve sub-sector
   - `get_sub_sectors_by_sector()` - List by parent sector
   - `assign_stocks()` - Bulk assign stocks
   - `remove_stocks()` - Bulk remove stocks
   - `move_stocks()` - Move between sub-sectors
   - `get_unassigned_stocks()` - Find stocks without sub-sector
   - `get_stocks_by_subsector()` - Paginated stock list
   - `reorder_subsectors()` - Custom ordering

### ✅ Management Interface

1. **[Sector Management Blueprint](app/sector_management.py)** - Complete routes:
   - Dashboard: `/sector-management/`
   - Sector CRUD: Create, Edit, View, Delete
   - Sub-sector CRUD: Create, Edit, View, Delete
   - Stock Assignment: Assign, Remove, Move stocks
   - API Endpoints: JSON APIs for AJAX operations

2. **Templates**:
   - [index.html](app/templates/sector_management/index.html) - Main dashboard with statistics
   - [sector_form.html](app/templates/sector_management/sector_form.html) - Create/Edit sector with live preview
   - [subsector_form.html](app/templates/sector_management/subsector_form.html) - Create/Edit sub-sector
   - [view_sector.html](app/templates/sector_management/view_sector.html) - Sector details view
   - [subsector_stocks.html](app/templates/sector_management/subsector_stocks.html) - Stock assignment interface

### ✅ Migration Tools

1. **[migrate_sectors.py](migrate_sectors.py)** - Data migration script:
   - Extracts unique sectors from legacy string fields
   - Creates Sector records with icons and colors
   - Extracts unique sub-sectors
   - Creates SubSector records linked to sectors
   - Updates Instrument.sub_sector_id to link stocks
   - Preserves original string fields for reference

### ✅ Updated Existing Code

1. **[app/__init__.py](app/__init__.py)** - Registered new blueprint
2. **[app/sectors.py](app/sectors.py)** - Updated to use new Sector/SubSector models

## Installation & Setup

### Step 1: Update Database Schema

The new tables will be created automatically on next app startup, but you should run a proper migration:

```bash
# If you're not using Flask-Migrate yet, initialize it
flask db init

# Create migration for new tables
flask db migrate -m "Add Sector and SubSector tables"

# Apply migration
flask db upgrade
```

### Step 2: Run Data Migration

Migrate your existing string-based sector data to the new relational structure:

```bash
python migrate_sectors.py
```

This script will:
- Analyze existing sector/sub-sector data in Instrument table
- Create Sector and SubSector records
- Link instruments to sub-sectors via foreign keys
- Preserve original string fields for reference

**Note**: The migration is interactive and will ask for confirmation before proceeding.

### Step 3: Access the Management Interface

Navigate to: **http://localhost:5000/sector-management/**

## Features

### 1. Dashboard
- Overview statistics (sectors, sub-sectors, assigned/unassigned stocks)
- Hierarchical accordion view of all sectors and sub-sectors
- Quick actions for CRUD operations
- Stock count badges

### 2. Sector Management
- Create sectors with:
  - Name (required, unique, 3-100 chars)
  - Description (optional)
  - Icon (Bootstrap Icons)
  - Color (hex code for visual identification)
  - Display order
- Edit existing sectors
- Soft delete (deactivate) or hard delete (cascade)
- Live preview when creating/editing

### 3. Sub-Sector Management
- Create sub-sectors under any sector
- Name must be unique within sector (same name OK in different sectors)
- Description and display order
- Soft/hard delete with stock handling options

### 4. Stock Assignment
- Interactive two-column interface
- Search and filter unassigned stocks
- Bulk select and assign stocks to sub-sectors
- Remove stocks from sub-sectors
- Move stocks between sub-sectors
- Real-time stock counts

### 5. Validation & Safety
- Case-insensitive uniqueness checks
- Minimum/maximum length validation
- Cascade delete protection
- Option to unassign stocks before deletion
- Error handling with user-friendly messages
- Audit logging for all operations

## API Endpoints

All endpoints are under `/sector-management/`:

### Sector Endpoints
- `GET /` - Dashboard
- `GET /sectors/create` - Create sector form
- `POST /sectors/create` - Create sector
- `GET /sectors/<id>/edit` - Edit sector form
- `POST /sectors/<id>/edit` - Update sector
- `POST /sectors/<id>/delete` - Delete sector
- `GET /sectors/<id>` - View sector details

### Sub-Sector Endpoints
- `GET /sectors/<id>/subsectors/create` - Create sub-sector form
- `POST /sectors/<id>/subsectors/create` - Create sub-sector
- `GET /subsectors/<id>/edit` - Edit sub-sector form
- `POST /subsectors/<id>/edit` - Update sub-sector
- `POST /subsectors/<id>/delete` - Delete sub-sector
- `GET /subsectors/<id>/stocks` - Manage stocks

### API (JSON) Endpoints
- `POST /api/subsectors/<id>/assign-stocks` - Assign stocks
- `POST /api/subsectors/<id>/remove-stocks` - Remove stocks
- `POST /api/subsectors/move-stocks` - Move stocks
- `GET /api/unassigned-stocks` - Get unassigned stocks
- `GET /api/subsectors/<id>/stocks` - Get sub-sector stocks
- `POST /api/sectors/reorder` - Reorder sectors
- `POST /api/subsectors/reorder` - Reorder sub-sectors
- `GET /api/sectors/search` - Search sectors
- `GET /api/sectors/<id>/subsectors` - Get sub-sectors

## Database Schema

```
sectors
  - id (PK)
  - name (unique)
  - description
  - icon
  - color
  - is_active
  - display_order
  - created_at
  - updated_at

sub_sectors
  - id (PK)
  - name
  - sector_id (FK -> sectors.id)
  - description
  - is_active
  - display_order
  - created_at
  - updated_at
  - UNIQUE(sector_id, name)

instruments
  - ... existing fields ...
  - sub_sector_id (FK -> sub_sectors.id)
  - sector (DEPRECATED - string field)
  - sub_sector (DEPRECATED - string field)
```

## Usage Examples

### Creating a Complete Hierarchy

1. **Create Sector**: "Financial Services"
   - Icon: `bi-bank2`
   - Color: `#667eea`

2. **Create Sub-Sectors**:
   - "Commercial Banks"
   - "NBFCs"
   - "Insurance"
   - "Asset Management"

3. **Assign Stocks**:
   - Navigate to each sub-sector
   - Click "Assign Stocks"
   - Search and select relevant NIFTY 500 stocks
   - Click "Assign Selected Stocks"

### Moving Stocks

1. Go to source sub-sector stocks page
2. Select stocks to move
3. Click "Remove Selected"
4. Go to destination sub-sector
5. Click "Assign Stocks"
6. Select the stocks
7. Assign them

### Deleting with Safety

**Soft Delete (Recommended)**:
- Deactivates the sector/sub-sector
- Preserves all data and relationships
- Can be reactivated later

**Hard Delete**:
- Permanently removes from database
- Sector: Cascades to all sub-sectors, unassigns stocks
- Sub-sector: Option to unassign or block if stocks exist

## Code Examples

### Using Service Layer

```python
from app.sector_service import SectorService
from app.subsector_service import SubSectorService

# Create a sector
sector, error = SectorService.create_sector(
    name="Technology",
    description="Technology companies",
    icon="bi-laptop",
    color="#764ba2",
    display_order=1
)

if error:
    print(f"Error: {error}")
else:
    print(f"Created sector: {sector.name}")

# Create a sub-sector
subsector, error = SubSectorService.create_sub_sector(
    sector_id=sector.id,
    name="Software Services",
    description="IT services and consulting"
)

# Assign stocks
count, error = SubSectorService.assign_stocks(
    sub_sector_id=subsector.id,
    instrument_ids=[1, 2, 3, 4, 5]
)

# Get unassigned stocks
stocks = SubSectorService.get_unassigned_stocks(
    sector_id=sector.id,
    search="TCS",
    limit=10
)
```

### Querying in Routes

```python
from app.models import Sector, SubSector, Instrument

# Get sector with sub-sectors
sector = Sector.query.get(1)
subsectors = sector.sub_sectors.filter_by(is_active=True).all()

# Get stocks in a sub-sector
subsector = SubSector.query.get(1)
stocks = subsector.instruments.filter_by(is_nifty500=True).all()

# Count stocks through relationship
stock_count = subsector.instruments.filter_by(is_nifty500=True).count()
```

## Best Practices

1. **Always use soft delete first** - Preserve data unless absolutely necessary
2. **Use service layer** - Don't directly manipulate models in routes
3. **Validate input** - Services handle validation, but add extra checks in forms
4. **Check for stocks before hard delete** - Prevent data loss
5. **Use transactions** - Service layer handles this, but be aware
6. **Log operations** - All operations are logged via service layer
7. **Test migrations** - Run migration on test data first
8. **Backup database** - Before running migration script

## Troubleshooting

### Migration Issues

**Problem**: Migration fails with "column already exists"
```bash
# Drop the column manually in database
flask shell
>>> from app import db
>>> db.session.execute('ALTER TABLE instruments DROP COLUMN sub_sector_id')
>>> db.session.commit()
# Then re-run migration
```

**Problem**: Duplicate sector names
```
Solution: The migration script will skip duplicates. Manually merge or rename them in the database before migration.
```

### Performance Issues

**Problem**: Slow stock listing
```python
# Use pagination (already implemented)
# Limit eager loading
# Add indexes on foreign keys (recommended)
```

### Data Integrity

**Problem**: Orphaned stocks after deletion
```python
# Use soft delete instead
# Or ensure unassign_stocks=True in hard delete
```

## Future Enhancements

Potential improvements you might consider:

1. **Bulk Import/Export** - CSV import for sectors/sub-sectors
2. **Drag-and-Drop Reordering** - UI for visual reordering
3. **Stock Auto-Assignment** - AI/ML-based automatic classification
4. **Sector Analytics** - Performance metrics per sector/sub-sector
5. **Historical Tracking** - Track sector changes over time
6. **Multi-level Sub-Sectors** - Sub-sub-sectors if needed
7. **Sector Templates** - Predefined sector/sub-sector structures
8. **API Documentation** - Swagger/OpenAPI docs for APIs

## Support

For issues or questions:
1. Check this README
2. Review service layer code for validation rules
3. Check Flask logs for detailed error messages
4. Review migration script output for data issues

## Summary

You now have a complete, production-ready sector management system with:
- ✅ Hierarchical data structure
- ✅ Full CRUD operations
- ✅ User-friendly web interface
- ✅ Comprehensive API
- ✅ Data migration tools
- ✅ Validation and safety features
- ✅ Logging and error handling

Access it at: **`/sector-management/`**

Happy sector management! 🎉
