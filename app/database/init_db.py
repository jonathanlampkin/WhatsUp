import os
import asyncpg
import logging
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()
logging.basicConfig(level=logging.INFO)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:admin@localhost:5432/test_db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

async def get_db_connection():
    """
    Establish an asynchronous connection to the database.
    """
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    """
    Initialize the database tables asynchronously.
    """
    conn = await get_db_connection()
    try:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_coordinates (
                id SERIAL PRIMARY KEY,
                visitor_id TEXT,
                latitude REAL,
                longitude REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(latitude, longitude)
            )
        ''')

        await conn.execute('''
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
        logging.info("Database initialized successfully.")
    except Exception as e:
        logging.error(f"Error initializing database: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(init_db())
