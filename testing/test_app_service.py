# testing/test_app_service.py

import unittest
from unittest.mock import patch, MagicMock
from main.app_service import AppService
import sqlite3

class TestAppService(unittest.TestCase):

    def setUp(self):
        # Set up a test instance of AppService with an in-memory database
        self.app_service = AppService(db_path=":memory:", google_api_key="test_key")

        # Create the required tables in the in-memory database
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

    @patch("main.app_service.requests.get")
    def test_call_google_places_api_success(self, mock_get):
        # Mock a successful response from the Google Places API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [{"name": "Test Place"}]}
        mock_get.return_value = mock_response

        # Call the method and check results
        result = self.app_service.call_google_places_api(40.7128, -74.0060)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Test Place")

    @patch("main.app_service.requests.get")
    def test_call_google_places_api_failure(self, mock_get):
        # Simulate a failed response with a non-200 status code
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = self.app_service.call_google_places_api(40.7128, -74.0060)
        self.assertEqual(result, [])  # Expect an empty list on failure

    # @patch("main.app_service.sqlite3.connect")
    # def test_generate_entry(self, mock_connect):
    #     # Test that generate_entry creates a new entry in the database
    #     mock_conn = mock_connect.return_value
    #     mock_cursor = mock_conn.cursor.return_value

    #     # Call the method
    #     visitor_id = self.app_service.generate_entry(40.7128, -74.0060)
        
    #     # Verify that a visitor ID was returned and an insertion was attempted
    #     self.assertTrue(visitor_id)
    #     mock_cursor.execute.assert_called_once()

if __name__ == "__main__":
    unittest.main()
