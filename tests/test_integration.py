# tests/test_integration.py

import os
import unittest
import json
import psycopg2
from app.services import AppService
from urllib.parse import urlparse

MOCK_LATITUDE = 37.7749
MOCK_LONGITUDE = -122.4194

def get_test_db_connection():
    database_url = os.getenv("DATABASE_URL")
    result = urlparse(database_url)
    connection = psycopg2.connect(
        database=result.path[1:],
        user=result.username,
        password=result.password,
        host=result.hostname,
        port=result.port
    )
    return connection

class TestIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app_service = AppService(google_api_key=os.getenv("GOOGLE_API_KEY"))

        # Set up tables in PostgreSQL for testing
        with get_test_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_coordinates (
                    id SERIAL PRIMARY KEY,
                    visitor_id TEXT UNIQUE,
                    latitude REAL,
                    longitude REAL,
                    timestamp TEXT
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
            conn.commit()

    def test_generate_entry(self):
        result = self.app_service.generate_entry(MOCK_LATITUDE, MOCK_LONGITUDE)
        self.assertTrue(result, "Failed to insert entry into user_coordinates")

    def test_call_google_places_api(self):
        status_code, places = self.app_service.call_google_places_api(MOCK_LATITUDE, MOCK_LONGITUDE)
        self.assertEqual(status_code, 200, "Google API call did not succeed")

    def test_check_existing_places(self):
        existing = self.app_service.check_existing_places(MOCK_LATITUDE, MOCK_LONGITUDE)
        self.assertFalse(existing, "Places already exist unexpectedly")

    def test_rank_nearby_places(self):
        ranked_places = self.app_service.rank_nearby_places(MOCK_LATITUDE, MOCK_LONGITUDE)
        self.assertEqual(len(ranked_places), 2, "Ranking did not retrieve expected number of places")

if __name__ == "__main__":
    unittest.main()
