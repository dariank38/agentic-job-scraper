"""Reset the database by deleting and reinitializing."""

import os
from pathlib import Path

from app.connection import DATABASE_PATH, init_db

def reset_database():
    """Delete the database file and reinitialize."""
    db_path = Path(DATABASE_PATH)
    
    if db_path.exists():
        print(f"Deleting database: {db_path}")
        os.remove(db_path)
    else:
        print(f"Database not found: {db_path}")
    
    print("Reinitializing database...")
    init_db()
    print("Database reset complete!")

if __name__ == "__main__":
    reset_database()
