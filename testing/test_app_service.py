# testing/test_app_service.py
import unittest
from unittest.mock import patch, MagicMock
from main.app_service import AppService
import sqlite3

class TestAppService(unittest.TestCase):

    def setUp(self):
        # Set up a test instance of AppService with an in-memory database
        self.app_service = AppService(db_path=":memory:", google_api_key="test_key")

        # Create required tables in the in-memory database
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
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ranked_nearby_places (
                    latitude REAL,
                    longitude REAL,
                    name TEXT,
                    rating REAL,
                    user_ratings_total INTEGER,
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

    @patch("main.app_service.sqlite3.connect")
    def test_check_existing_places(self, mock_connect):
        # Mock database connection and cursor
        mock_conn = mock_connect.return_value
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchone.return_value = (1,)

        # Call the method to check if the place exists
        exists = self.app_service.check_existing_places(40.7128, -74.0060)
        self.assertTrue(exists)

    @patch("main.app_service.sqlite3.connect")
    def test_generate_entry(self, mock_connect):
        # Test that generate_entry creates a new entry in the database
        mock_conn = mock_connect.return_value
        mock_cursor = mock_conn.cursor.return_value

        # Call the method
        visitor_id = self.app_service.generate_entry(40.7128, -74.0060)
        
        # Verify that a visitor ID was returned and an insertion was attempted
        self.assertIsNotNone(visitor_id)
        mock_cursor.execute.assert_called_once()

    @patch("main.app_service.sqlite3.connect")
    def test_insert_place_data(self, mock_connect):
        # Mock database connection and cursor
        mock_conn = mock_connect.return_value
        mock_cursor = mock_conn.cursor.return_value

        # Test data for insertion
        place = {
            "place_id": "123",
            "name": "Test Place",
            "business_status": "OPERATIONAL",
            "rating": 4.5,
            "user_ratings_total": 100,
            "vicinity": "123 Test St",
            "types": ["restaurant"],
            "price_level": 2,
            "icon": "test_icon_url",
            "icon_background_color": "#FFFFFF",
            "icon_mask_base_uri": "test_mask_url",
            "photos": [{"photo_reference": "ref123", "height": 100, "width": 200}],
            "opening_hours": {"open_now": True}
        }

        # Call the method to insert place data
        self.app_service.insert_place_data(40.7128, -74.0060, place)
        mock_cursor.execute.assert_called_once()

if __name__ == "__main__":
    unittest.main()
