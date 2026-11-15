
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "tasks.db"

conn = sqlite3.connect(DB_PATH)

try:
    columns = [
        row[1]
        for row in conn.execute("PRAGMA table_info(users)").fetchall()
    ]

    if "first_name" not in columns:
        conn.execute(
            "ALTER TABLE users ADD COLUMN first_name TEXT DEFAULT ''"
        )
        print("Added first_name column.")

    if "last_name" not in columns:
        conn.execute(
            "ALTER TABLE users ADD COLUMN last_name TEXT DEFAULT ''"
        )
        print("Added last_name column.")

    users = conn.execute(
        "SELECT id, username FROM users ORDER BY id"
    ).fetchall()

    if len(users) != 1:
        raise RuntimeError(
            "Expected exactly one existing account. "
            "No profile was updated. Please contact me with this output."
        )

    conn.execute("""
        UPDATE users
        SET first_name = ?, last_name = ?
        WHERE id = ?
    """, ("Gauri", "Purohit", users[0][0]))

    conn.commit()

    print("\nProfile updated successfully!")
    print("First name: Gauri")
    print("Last name: Purohit")
    print("Initials: GP")

    task_count = conn.execute(
        "SELECT COUNT(*) FROM tasks"
    ).fetchone()[0]

    print("Existing tasks preserved:", task_count)

except Exception:
    conn.rollback()
    raise

finally:
    conn.close()
