import os
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

def get_db_connection():
    """Establishes a connection to the database using DATABASE_URL."""
    database_url = os.getenv("DATABASE_URL")
    result = urlparse(database_url)
    connection = psycopg2.connect(
        dbname=result.path[1:],
        user=result.username,
        password=result.password,
        host=result.hostname,
        port=result.port,
        cursor_factory=RealDictCursor
    )
    return connection

def init_db():
    """Initialize tables in the database if they do not exist."""
    try:
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
        print("Database initialized successfully.")
        
    except psycopg2.DatabaseError as error:
        print(f"Database initialization failed: {error}")
    finally:
        cursor.close()
        connection.close()

if __name__ == "__main__":
    init_db()
