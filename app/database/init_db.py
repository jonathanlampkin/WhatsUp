# init_db.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:admin@localhost:5432/test_db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_db_connection():
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL not set.")
    
    result = urlparse(DATABASE_URL)
    connection = psycopg2.connect(
        dbname=result.path[1:],
        user=result.username,
        password=result.password,
        host=result.hostname or "localhost",
        port=result.port or 5432,
        cursor_factory=RealDictCursor
    )
    return connection

def init_db():
    connection = get_db_connection()
    cursor = connection.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_coordinates (
            id SERIAL PRIMARY KEY,
            visitor_id TEXT UNIQUE,
            latitude REAL,
            longitude REAL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS google_nearby_places (
            id SERIAL PRIMARY KEY,
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
    
    connection.commit()
    cursor.close()
    connection.close()
    print("Database initialized successfully.")

if __name__ == "__main__":
    init_db()
