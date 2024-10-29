# database/create_tables.py
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'database.db')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Drop tables if they already exist for a fresh setup
# cursor.execute('DROP TABLE IF EXISTS user_coordinates')
# cursor.execute('DROP TABLE IF EXISTS google_nearby_places')

# Create user_coordinates table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_coordinates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        visitor_id TEXT UNIQUE,
        latitude REAL,
        longitude REAL,
        timestamp TEXT
    )
''')

# Create google_nearby_places table without viewport fields
cursor.execute('''
    CREATE TABLE IF NOT EXISTS google_nearby_places (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        latitude REAL,
        longitude REAL,
        place_id TEXT UNIQUE,
        name TEXT,
        business_status TEXT,
        rating REAL,
        user_ratings_total INTEGER,
        vicinity TEXT,
        types TEXT,
        price_level INTEGER,
        icon TEXT,
        icon_background_color TEXT,
        icon_mask_base_uri TEXT,
        photo_reference TEXT,
        photo_height INTEGER,
        photo_width INTEGER,
        open_now BOOLEAN
    )
''')

conn.commit()
conn.close()
print("Database and tables created at", db_path)
