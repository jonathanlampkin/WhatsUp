# testing/test_integration.py

import os
import unittest
import json
import sqlite3
import pika
from main.app_service import AppService
from messaging.producer import send_message

# Mock latitude and longitude values for testing
MOCK_LATITUDE = 37.7749
MOCK_LONGITUDE = -122.4194

class TestIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Initialize AppService with an in-memory database and real API key for integration testing
        cls.app_service = AppService(db_path=":memory:", google_api_key=os.getenv("GOOGLE_API_KEY"))

        # Set up in-memory database tables
        with sqlite3.connect(cls.app_service.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_coordinates (
                    visitor_id TEXT PRIMARY KEY,
                    latitude REAL,
                    longitude REAL,
                    timestamp TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS google_nearby_places (
                    latitude REAL,
                    longitude REAL,
                    place_id TEXT PRIMARY KEY,
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
        """Test generate_entry inserts a new record in user_coordinates."""
        result = self.app_service.generate_entry(MOCK_LATITUDE, MOCK_LONGITUDE)
        self.assertTrue(result, "Failed to insert entry into user_coordinates")

        # Verify insertion in the database
        with sqlite3.connect(self.app_service.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_coordinates WHERE latitude=? AND longitude=?", 
                           (MOCK_LATITUDE, MOCK_LONGITUDE))
            record = cursor.fetchone()
            self.assertIsNotNone(record, "Record not found in user_coordinates table")

    def test_call_google_places_api(self):
        """Test call_google_places_api to ensure API connection and data insertion."""
        status_code, places = self.app_service.call_google_places_api(MOCK_LATITUDE, MOCK_LONGITUDE)
        self.assertEqual(status_code, 200, "Google API call did not succeed")

        # Verify insertion into google_nearby_places
        with sqlite3.connect(self.app_service.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM google_nearby_places WHERE latitude=? AND longitude=?", 
                           (MOCK_LATITUDE, MOCK_LONGITUDE))
            record = cursor.fetchone()
            self.assertIsNotNone(record, "No data inserted into google_nearby_places table")

    def test_check_existing_places(self):
        """Test check_existing_places should return False, then True after insertion."""
        # Verify no existing places initially
        existing = self.app_service.check_existing_places(MOCK_LATITUDE, MOCK_LONGITUDE)
        self.assertFalse(existing, "Places already exist unexpectedly")

        # Call Google API and verify check_existing_places returns True
        self.app_service.call_google_places_api(MOCK_LATITUDE, MOCK_LONGITUDE)
        existing = self.app_service.check_existing_places(MOCK_LATITUDE, MOCK_LONGITUDE)
        self.assertTrue(existing, "check_existing_places did not return True after insertion")

    def test_rank_nearby_places(self):
        """Test rank_nearby_places orders and retrieves places correctly."""
        # Insert mock data to test ranking
        with sqlite3.connect(self.app_service.db_path) as conn:
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT INTO google_nearby_places (
                    latitude, longitude, place_id, name, business_status, rating, 
                    user_ratings_total, vicinity, types, price_level, icon, 
                    icon_background_color, icon_mask_base_uri, photo_reference, 
                    photo_height, photo_width, open_now
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', [
                (MOCK_LATITUDE, MOCK_LONGITUDE, "1", "Place A", "OPERATIONAL", 4.5, 100, "Location A", "['restaurant']", 2, "icon_a", "color_a", "mask_a", "photo_ref_a", 400, 400, True),
                (MOCK_LATITUDE, MOCK_LONGITUDE, "2", "Place B", "OPERATIONAL", 4.0, 150, "Location B", "['cafe']", 1, "icon_b", "color_b", "mask_b", "photo_ref_b", 300, 300, False)
            ])
            conn.commit()

        # Test ranking functionality
        ranked_places = self.app_service.rank_nearby_places(MOCK_LATITUDE, MOCK_LONGITUDE)
        self.assertEqual(len(ranked_places), 2, "Ranking did not retrieve expected number of places")
        self.assertEqual(ranked_places[0]["name"], "Place A", "Place A should be ranked higher than Place B")


if __name__ == "__main__":
    unittest.main()
