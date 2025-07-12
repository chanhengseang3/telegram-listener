#!/usr/bin/env python3
"""
Script to create the shift_configurations table.
Run this after implementing the auto close functionality.
"""

from config.database_config import engine
from models.shift_configuration_model import ShiftConfiguration

def create_shift_configuration_table():
    """Create the shift_configurations table"""
    print("Creating shift_configurations table...")
    try:
        # Create the table
        ShiftConfiguration.__table__.create(engine, checkfirst=True)
        print("✅ shift_configurations table created successfully!")
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        return False
    return True

if __name__ == "__main__":
    create_shift_configuration_table()