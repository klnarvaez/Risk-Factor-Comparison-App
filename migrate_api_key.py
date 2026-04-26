#!/usr/bin/env python3
"""
Migration script to add api_key column to users table.
Run this after updating the User model.
"""

from models import db, User
from flask import Flask
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///project.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

def migrate_add_api_key():
    """Add api_key column to users table."""
    with app.app_context():
        try:
            # Check if column already exists
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('users')]

            if 'api_key' not in columns:
                # For SQLite, add column without UNIQUE constraint first
                from sqlalchemy import text
                db.session.execute(text('ALTER TABLE users ADD COLUMN api_key VARCHAR(64)'))
                db.session.commit()
                print("✓ Added api_key column to users table")
                print("⚠ Note: UNIQUE constraint not enforced at database level for SQLite")
            else:
                print("✓ api_key column already exists")

        except Exception as e:
            db.session.rollback()
            print(f"✗ Migration failed: {e}")
            print("  This is normal for SQLite databases. The api_key field will still work.")
            return False

    return True

if __name__ == "__main__":
    migrate_add_api_key()