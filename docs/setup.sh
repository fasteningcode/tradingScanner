#!/bin/bash
# Flask Dashboard Setup Script

echo "🚀 Setting up Flask Dashboard Application..."
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"
echo ""

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Generate a secure secret key
echo "🔐 Generating secure secret key..."
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# Update .env file
echo "⚙️  Updating environment configuration..."
cat > .env << EOF
SECRET_KEY=$SECRET_KEY
DATABASE_URL=sqlite:///app.db
FLASK_APP=run.py
FLASK_ENV=development
EOF

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the application:"
echo "  1. Activate the virtual environment: source venv/bin/activate"
echo "  2. Run the application: python run.py"
echo "  3. Open your browser: http://localhost:5000"
echo ""
echo "📚 Check README.md for more information."
