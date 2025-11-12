#!/usr/bin/env python3
"""
Fix user passwords by rehashing them with pbkdf2:sha256 method.
This is needed when migrating from scrypt to pbkdf2 due to Python/OpenSSL compatibility.

Usage:
    python scripts/fix_user_passwords.py

This will reset all user passwords to a temporary password: "TempPass123!"
Users should change their password after logging in.
"""

import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import User

def fix_passwords():
    """Reset all user passwords to a temporary password using pbkdf2:sha256"""
    app = create_app('development')

    with app.app_context():
        # Get all users
        users = User.query.all()

        if not users:
            print("No users found in database.")
            return

        print(f"Found {len(users)} user(s) in database.")
        print("\nResetting passwords to temporary password: 'TempPass123!'")
        print("Users should change their password after logging in.\n")

        temp_password = "TempPass123!"

        for user in users:
            print(f"Resetting password for user: {user.username} ({user.email})")
            user.set_password(temp_password)

        # Commit changes
        db.session.commit()
        print(f"\n✓ Successfully reset passwords for {len(users)} user(s).")
        print("\nTemporary login credentials:")
        for user in users:
            print(f"  Username: {user.username}")
            print(f"  Email: {user.email}")
            print(f"  Password: {temp_password}\n")

if __name__ == '__main__':
    fix_passwords()
