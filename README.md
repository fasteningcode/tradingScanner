# Flask Dashboard Application

A modern, secure Flask web application with user authentication and dashboard interface.

## Quick Start

### 1. Setup
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate     # On Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure
Create your environment file from the template:
```bash
cp .env.example .env
```

Generate a secure secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output and update `SECRET_KEY` in `.env` file.

### 3. Run
```bash
python run.py
```

Visit: **http://localhost:5000**

### 4. First Use
1. Register a new account at `/auth/register`
2. Login with your credentials
3. Access your dashboard

## Features

- User authentication (register, login, logout)
- Secure password hashing
- Modern dashboard with Bootstrap 5
- Responsive design
- User profile management
- Session management with "Remember Me"

## Project Structure

```
V1/
├── app/                  # Application package
│   ├── templates/        # HTML templates
│   ├── static/          # CSS, JS, images
│   └── *.py             # Application modules
├── tests/               # Test files
├── scripts/             # Utility & migration scripts
├── docs/                # Documentation
│   ├── archive/         # Historical docs
│   └── *.md            # Active documentation
├── migrations/          # Database migrations
├── instance/            # Database files
├── logs/                # Application logs
├── config.py           # Configuration
├── run.py              # Entry point
└── requirements.txt    # Dependencies
```

## Documentation

- [Quick Start Guide](docs/QUICK_START.md) - Get started quickly
- [Project Structure](docs/PROJECT_STRUCTURE.md) - Detailed structure documentation
- [Developer Documentation](docs/README.md) - Full documentation

## Technologies

- Flask 3.0
- SQLAlchemy (SQLite)
- Flask-Login
- Bootstrap 5
- WTForms

## Security Notes

- Change `SECRET_KEY` in `.env` before deployment
- Use HTTPS in production
- Consider PostgreSQL/MySQL for production database

---

Built with Flask & Bootstrap 5
