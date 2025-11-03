# Flask Dashboard Application

A modern, secure Flask web application with user authentication and a beautiful dashboard interface built with Bootstrap 5.

## Features

- **User Authentication System**
  - User registration with email validation
  - Secure login/logout functionality
  - Password hashing with Werkzeug
  - Session management with Flask-Login
  - "Remember Me" functionality

- **Modern Dashboard Interface**
  - Responsive design with Bootstrap 5
  - Clean and intuitive UI
  - Statistics cards
  - User profile management
  - Mobile-friendly layout

- **Security Features**
  - CSRF protection with Flask-WTF
  - Password hashing (bcrypt-style)
  - Secure session cookies
  - SQL injection prevention with SQLAlchemy ORM
  - Input validation on forms

- **Database**
  - SQLite database (easy development setup)
  - SQLAlchemy ORM for database operations
  - User model with timestamps
  - Easy migration to PostgreSQL/MySQL for production

## Project Structure

```
V1/
├── app/
│   ├── __init__.py           # Flask app factory
│   ├── models.py             # Database models (User)
│   ├── auth.py               # Authentication routes
│   ├── dashboard.py          # Dashboard routes
│   ├── forms.py              # WTForms for authentication
│   ├── templates/
│   │   ├── base.html         # Base template
│   │   ├── auth/
│   │   │   ├── login.html    # Login page
│   │   │   └── register.html # Registration page
│   │   └── dashboard/
│   │       ├── index.html    # Main dashboard
│   │       └── profile.html  # User profile
│   └── static/
│       ├── css/
│       │   └── style.css     # Custom styles
│       └── js/
│           └── main.js       # Custom JavaScript
├── config.py                 # Configuration settings
├── run.py                    # Application entry point
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables
└── .gitignore               # Git ignore rules
```

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Virtual environment (recommended)

### Setup Instructions

1. **Clone or download the project**
   ```bash
   cd /Users/codenear/codenear-project-files/Aadhith/V1
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   ```

3. **Activate the virtual environment**
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure environment variables**
   - Edit the `.env` file and change the `SECRET_KEY`:
     ```
     SECRET_KEY=your-secret-key-here-change-this
     ```
   - You can generate a secure secret key with:
     ```bash
     python -c "import secrets; print(secrets.token_hex(32))"
     ```

6. **Initialize the database**
   The database will be automatically created when you first run the application.

## Running the Application

### Development Server

```bash
python run.py
```

Or using Flask CLI:

```bash
flask run
```

The application will be available at: **http://localhost:5000**

### Default Access

The application starts with no users. You need to:
1. Navigate to http://localhost:5000/auth/register
2. Create your first account
3. Login with your credentials
4. Access the dashboard

## Usage

### Registration
1. Go to http://localhost:5000/auth/register
2. Fill in your username, email, and password
3. Click "Register"
4. You'll be redirected to the login page

### Login
1. Go to http://localhost:5000/auth/login
2. Enter your email and password
3. Optionally check "Remember Me" to stay logged in
4. Click "Sign In"
5. You'll be redirected to your dashboard

### Dashboard
- View your account statistics
- See account information
- Access quick actions
- Navigate to your profile

### Logout
- Click on your username in the navbar
- Select "Logout" from the dropdown menu

## Configuration

The application supports multiple configurations:

- **Development** (default): Debug mode enabled, SQLite database
- **Production**: Debug mode disabled, secure cookies required
- **Testing**: In-memory database, CSRF disabled

To change configuration, set the `FLASK_CONFIG` environment variable:
```bash
export FLASK_CONFIG=production
```

## Security Considerations

### For Production Deployment

1. **Change the SECRET_KEY**
   - Generate a strong, random secret key
   - Never commit the secret key to version control

2. **Use HTTPS**
   - Enable `SESSION_COOKIE_SECURE = True` in production config
   - Use a reverse proxy (nginx, Apache) with SSL/TLS

3. **Database**
   - Migrate from SQLite to PostgreSQL or MySQL
   - Update `DATABASE_URL` in `.env`

4. **Environment Variables**
   - Store sensitive data in environment variables
   - Use a service like AWS Secrets Manager or HashiCorp Vault

5. **Additional Security Headers**
   - Consider using Flask-Talisman for security headers
   - Implement rate limiting with Flask-Limiter

## Technologies Used

- **Backend**: Flask 3.0.0
- **Database**: SQLAlchemy with SQLite
- **Authentication**: Flask-Login
- **Forms**: Flask-WTF with WTForms
- **Frontend**: Bootstrap 5.3.2
- **Icons**: Bootstrap Icons
- **Password Hashing**: Werkzeug Security

## Development

### Adding New Features

1. **New Routes**: Add them to appropriate blueprint files (`auth.py`, `dashboard.py`)
2. **Database Models**: Add to `models.py` and create migrations
3. **Templates**: Add to `app/templates/` directory
4. **Static Files**: Add to `app/static/` directory

### Database Migrations

For production, consider using Flask-Migrate (Alembic):
```bash
pip install Flask-Migrate
```

## Troubleshooting

### Common Issues

1. **Database locked error**
   - This can happen with SQLite when multiple requests occur simultaneously
   - Solution: Use PostgreSQL for production

2. **Secret key not set**
   - Make sure `.env` file exists and contains `SECRET_KEY`
   - Check that python-dotenv is installed

3. **Templates not found**
   - Verify the `templates` directory structure
   - Check that Flask can find the `app` package

4. **Static files not loading**
   - Clear browser cache
   - Check the `static` directory structure
   - Verify file paths in templates

## License

This project is provided as-is for educational and development purposes.

## Support

For issues or questions:
- Check the troubleshooting section above
- Review Flask documentation: https://flask.palletsprojects.com/
- Review Flask-Login documentation: https://flask-login.readthedocs.io/

## Contributing

Feel free to fork this project and add your own features!

## Acknowledgments

- Flask framework and community
- Bootstrap team for the excellent CSS framework
- All the contributors to the Flask extensions used in this project
