import unittest
from unittest.mock import patch, MagicMock
from main.app import app
from main.app_service import AppService

class TestIntegration(unittest.TestCase):

    def setUp(self):
        # Configure the Flask app for testing
        app.config["TESTING"] = True
        self.client = app.test_client()

        # Set up AppService with an in-memory database
        self.app_service = AppService(db_path=":memory:", google_api_key="test_key")

    @patch("main.app_service.AppService.check_existing_places")
    @patch("main.app_service.AppService.insert_place_data")
    def test_save_coordinates(self, mock_insert_place_data, mock_check_existing_places):
        # Mock behavior for existing places and insertions
        mock_check_existing_places.return_value = False  # Simulate that place does not exist
        mock_insert_place_data.return_value = None  # No return needed for inserts

        # Mock request data
        data = {
            "latitude": 40.7128,
            "longitude": -74.0060
        }

        # Send a POST request to /save-coordinates endpoint
        response = self.client.post("/save-coordinates", json=data)
        
        # Assertions on response and API behavior
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertIn("ranked_places", json_data)

        # Ensure that the method was called with the right arguments
        mock_insert_place_data.assert_called()
        mock_check_existing_places.assert_called_with(40.7128, -74.0060)

    @patch("main.app_service.sqlite3.connect")
    def test_check_existing_places(self, mock_connect):
        # Mock database connection and cursor
        mock_conn = mock_connect.return_value
        mock_cursor = mock_conn.cursor.return_value

        # Case 1: Coordinates that exist (expect True)
        mock_cursor.fetchone.return_value = (1,)  # Simulate a result found
        result = self.app_service.check_existing_places(38.7219, -9.1607)
        self.assertTrue(result, "Expected True for coordinates that exist")

        # Case 2: Coordinates that do not exist (expect False)
        mock_cursor.fetchone.return_value = None  # Simulate no result found
        result = self.app_service.check_existing_places(40.7128, -74.0060)
        self.assertFalse(result, "Expected False for coordinates that do not exist")

if __name__ == "__main__":
    unittest.main()
