# testing/test_integration.py
import unittest
from unittest.mock import patch
from main.app import app
from main.app_service import AppService
import os
import sqlite3

class TestIntegration(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.app_service = AppService(db_path=":memory:", google_api_key="test_key")

        # Set up in-memory database tables
        with sqlite3.connect(self.app_service.db_path) as conn:
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

    @patch.dict(os.environ, {"RABBITMQ_URL": "amqp://guest:guest@localhost:5672/"})
    @patch("main.app_service.AppService.check_existing_places", return_value=True)
    @patch("main.app_service.AppService.rank_nearby_places", return_value=[
        {"name": "Test Place", "vicinity": "123 Test St", "rating": 4.5}
    ])
    def test_process_coordinates_existing_places(self, mock_rank_nearby_places, mock_check_existing_places):
        data = {"latitude": 40.7128, "longitude": -74.0060}
        response = self.client.post("/process-coordinates", json=data)
        json_data = response.get_json()
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("places", json_data)
        self.assertEqual(len(json_data["places"]), 1)
        self.assertEqual(json_data["places"][0]["name"], "Test Place")

    @patch.dict(os.environ, {"RABBITMQ_URL": "amqp://guest:guest@localhost:5672/"})
    @patch("main.app_service.AppService.check_existing_places", return_value=False)
    @patch("main.app_service.AppService.call_google_places_api", return_value=[
        {"name": "New Place", "vicinity": "123 New St", "rating": 4.0}
    ])
    def test_process_coordinates_no_existing_places(self, mock_call_google_places_api, mock_check_existing_places):
        data = {"latitude": 40.7128, "longitude": -74.0060}
        response = self.client.post("/process-coordinates", json=data)
        json_data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertIn("places", json_data)
        self.assertEqual(len(json_data["places"]), 1)
        self.assertEqual(json_data["places"][0]["name"], "New Place")

if __name__ == "__main__":
    unittest.main()
