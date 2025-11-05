#!/bin/bash
# Script to view Flask logs in real-time
# Usage: ./view_logs.sh [app|error|access|all]

LOG_TYPE="${1:-all}"

display_help() {
    echo "Usage: ./view_logs.sh [LOG_TYPE]"
    echo ""
    echo "LOG_TYPE options:"
    echo "  app      - View application logs (default)"
    echo "  error    - View error logs only"
    echo "  access   - View HTTP access logs"
    echo "  all      - View all logs (split screen)"
    echo ""
    echo "Examples:"
    echo "  ./view_logs.sh           # View application logs"
    echo "  ./view_logs.sh error     # View error logs"
    echo "  ./view_logs.sh access    # View access logs"
}

if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    display_help
    exit 0
fi

# Check if logs directory exists
if [ ! -d "logs" ]; then
    echo "Error: logs directory not found. Please start the Flask app first."
    exit 1
fi

case $LOG_TYPE in
    app)
        echo "=== Flask Application Logs ==="
        echo "Monitoring application logs... Press Ctrl+C to stop"
        echo "=============================================="
        echo ""
        tail -f logs/app.log 2>/dev/null || echo "Log file not found. Start the app to generate logs..."
        ;;
    error)
        echo "=== Flask Error Logs ==="
        echo "Monitoring error logs... Press Ctrl+C to stop"
        echo "=============================================="
        echo ""
        tail -f logs/error.log 2>/dev/null || echo "No errors logged yet..."
        ;;
    access)
        echo "=== Flask Access Logs ==="
        echo "Monitoring HTTP access logs... Press Ctrl+C to stop"
        echo "=============================================="
        echo ""
        tail -f logs/access.log 2>/dev/null || echo "No access logs yet..."
        ;;
    all)
        echo "=== Flask All Logs (Combined) ==="
        echo "Monitoring all logs... Press Ctrl+C to stop"
        echo "=============================================="
        echo ""
        # Use multitail if available, otherwise use tail on all files
        if command -v multitail &> /dev/null; then
            multitail logs/app.log logs/error.log logs/access.log
        else
            tail -f logs/*.log 2>/dev/null || echo "Log files not found. Start the app to generate logs..."
        fi
        ;;
    *)
        echo "Error: Unknown log type '$LOG_TYPE'"
        echo ""
        display_help
        exit 1
        ;;
esac
