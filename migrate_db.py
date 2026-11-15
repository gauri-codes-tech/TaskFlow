
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tasks.db"

# Create a database backup before making changes
backup_name = f"tasks_backup_{datetime.now():%Y%m%d_%H%M%S}.db"
backup_path = BASE_DIR / backup_name

shutil.copy2(DB_PATH, backup_path)
print("Database backup created:", backup_name)

# Add category column if it does not exist
conn = sqlite3.connect(DB_PATH)

columns = [
    row[1] for row in conn.execute("PRAGMA table_info(tasks)")
]

if "category" not in columns:
    conn.execute(
        "ALTER TABLE tasks ADD COLUMN category TEXT DEFAULT 'Other'"
    )
    print("Category column added successfully.")
else:
    print("Category column already exists.")

conn.execute("""
    UPDATE tasks
    SET category = 'Other'
    WHERE category IS NULL OR category = ''
""")

conn.commit()
conn.close()

print("Database updated successfully!")
