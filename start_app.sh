#!/bin/bash
# Start Flask Application
# This script properly starts the Flask app with the correct database configuration

echo "🚀 Starting Flask Application..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "   Please run: python3 -m venv venv"
    exit 1
fi

# Check if database is locked
if lsof instance/app.db 2>/dev/null | grep -q "app.db"; then
    echo "⚠️  Database is locked by another process:"
    lsof instance/app.db 2>/dev/null
    echo ""
    echo "Please close DB Browser or run: kill <PID>"
    exit 1
fi

# Activate virtual environment and start app
echo "✅ Activating virtual environment..."
source venv/bin/activate

# Unset DATABASE_URL to use default from config.py
unset DATABASE_URL

echo "✅ Starting Flask app..."
echo ""
python run.py
