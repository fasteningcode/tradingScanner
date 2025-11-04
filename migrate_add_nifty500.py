#!/usr/bin/env python
"""
Migration script to add is_nifty500 column to instruments table
"""

from app import create_app, db
import sqlite3

def add_nifty500_column():
    """Add is_nifty500 column to instruments table"""
    app = create_app()

    with app.app_context():
        # Get database path - handle both relative and absolute paths
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']
        if db_uri.startswith('sqlite:///'):
            db_path = db_uri.replace('sqlite:///', '')
            # If relative path, make it absolute from app root
            if not db_path.startswith('/'):
                import os
                db_path = os.path.join(app.root_path, '..', db_path)
                db_path = os.path.abspath(db_path)
        else:
            db_path = 'instance/app.db'  # fallback

        print(f"Adding is_nifty500 column to instruments table...")
        print(f"Database: {db_path}")

        try:
            # Connect directly to SQLite
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check if column exists
            cursor.execute("PRAGMA table_info(instruments)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'is_nifty500' in columns:
                print("✓ Column 'is_nifty500' already exists")
            else:
                # Add the column
                cursor.execute("""
                    ALTER TABLE instruments
                    ADD COLUMN is_nifty500 BOOLEAN NOT NULL DEFAULT 0
                """)

                # Create index
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS ix_instruments_is_nifty500
                    ON instruments (is_nifty500)
                """)

                conn.commit()
                print("✓ Column 'is_nifty500' added successfully")
                print("✓ Index created on is_nifty500")

            conn.close()

        except Exception as e:
            print(f"✗ Error: {str(e)}")
            raise

if __name__ == '__main__':
    add_nifty500_column()
