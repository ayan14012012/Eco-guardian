# clean_reset.py
import os
import sqlite3

# Delete the database file if it exists
db_path = 'instance/database.db'
if os.path.exists(db_path):
    os.remove(db_path)
    print(f"Deleted old database: {db_path}")
else:
    print("No existing database found")

# Create the instance directory if it doesn't exist
os.makedirs('instance', exist_ok=True)

# Now create a simple database with just the structure
print("Creating new database...")

# Create a simple SQLite connection to set up tables
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create smart_bin table with the correct schema
cursor.execute('''
CREATE TABLE smart_bin (
    id INTEGER PRIMARY KEY,
    location VARCHAR(100) NOT NULL,
    fill_level FLOAT DEFAULT 0,
    last_updated DATETIME,
    name VARCHAR(100)
)
''')

# Create litter_alert table
cursor.execute('''
CREATE TABLE litter_alert (
    id INTEGER PRIMARY KEY,
    location VARCHAR(100) NOT NULL,
    confidence FLOAT DEFAULT 0,
    image_url VARCHAR(200),
    timestamp DATETIME,
    description VARCHAR(500)
)
''')

conn.commit()
conn.close()
print("Database created successfully with correct schema!")