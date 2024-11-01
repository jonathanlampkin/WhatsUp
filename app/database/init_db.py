# init_db.py

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

# Replace "postgres://" with "postgresql://" for compatibility
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
if TEST_DATABASE_URL and TEST_DATABASE_URL.startswith("postgres://"):
    TEST_DATABASE_URL = TEST_DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_db_connection(testing=False):
    """Establishes a connection to the specified database (testing or production)."""
    database_url = TEST_DATABASE_URL if testing else DATABASE_URL
    print(f"Connecting to database at: {database_url}")
    if not database_url:
        raise ValueError("Database URL is not set. Please check environment variables.")
    
    result = urlparse(database_url)
    connection = psycopg2.connect(
        dbname=result.path[1:],  # Remove leading "/" from the path
        user=result.username,
        password=result.password,
        host=result.hostname or "localhost",
        port=result.port or 5432,
        cursor_factory=RealDictCursor
    )
    return connection

def init_db(testing=False):
    """Initialize tables in the database if they do not exist."""
    connection = None
    cursor = None
    try:
        db_type = "TEST_DATABASE_URL" if testing else "DATABASE_URL"
        print(f"Initializing database with {db_type}: {TEST_DATABASE_URL if testing else DATABASE_URL}")
        
        # Get a connection to the test or production database
        connection = get_db_connection(testing=testing)
        cursor = connection.cursor()
        
        # Create the user_coordinates table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_coordinates (
                id SERIAL PRIMARY KEY,
                visitor_id TEXT UNIQUE,
                latitude REAL,
                longitude REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create the google_nearby_places table
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
        
        # Commit the transactions
        connection.commit()
        print("Database initialized successfully.")
        
    except psycopg2.DatabaseError as error:
        print(f"Database initialization failed: {error}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

if __name__ == "__main__":
    # Run init_db for the production database by default
    init_db()
