#!/bin/bash
# Check if database is locked by another process

echo "Checking database locks..."
echo ""

DB_FILE="instance/app.db"

if [ ! -f "$DB_FILE" ]; then
    echo "❌ Database file not found: $DB_FILE"
    exit 1
fi

# Check for processes using the database
PROCESSES=$(lsof "$DB_FILE" 2>/dev/null)

if [ -z "$PROCESSES" ]; then
    echo "✅ Database is not locked - safe to run the app!"
else
    echo "⚠️  Database is currently locked by:"
    echo ""
    echo "$PROCESSES" | head -20
    echo ""
    echo "To unlock, either:"
    echo "  1. Close the application using the database"
    echo "  2. Run: kill <PID> (use the PID from above)"
fi

# Check WAL files
if [ -f "instance/app.db-wal" ]; then
    WAL_SIZE=$(ls -lh instance/app.db-wal | awk '{print $5}')
    echo ""
    echo "📝 WAL file exists (size: $WAL_SIZE)"
    echo "   This is normal if database was recently accessed"
fi
