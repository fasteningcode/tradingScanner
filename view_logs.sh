#!/bin/bash
# Script to view Flask logs in real-time
# Usage: ./view_logs.sh

echo "=== Flask Application Logs ==="
echo "Monitoring server logs... Press Ctrl+C to stop"
echo "=============================================="
echo ""

# Find the latest Flask process and show its output
tail -f /tmp/flask_app.log 2>/dev/null || echo "Log file not found. Server logs will appear below when available..."
