# testing/test_integration.py
import unittest
from unittest.mock import patch, MagicMock
from main.app import app
from main.app_service import AppService
import os

class TestIntegration(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.app_service = AppService(db_path=":memory:", google_api_key="test_key")

    @patch.dict(os.environ, {"RABBITMQ_URL": "amqp://guest:guest@localhost:5672/"})
    @patch("main.app_service.AppService.check_existing_places")
    @patch("main.app_service.AppService.insert_place_data")
    def test_save_coordinates(self, mock_check_existing_places, mock_insert_place_data):
        data = {"latitude": 40.7128, "longitude": -74.0060}
        response = self.client.post("/save-coordinates", json=data)
        json_data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json_data["status"], "Coordinates sent to RabbitMQ and saved in database")

    @patch("main.app_service.AppService.call_google_places_api")
    def test_get_nearby_places(self, mock_call_google_places_api):
        mock_call_google_places_api.return_value = [
            {"name": "Test Place", "vicinity": "123 Test St", "rating": 4.5}
        ]
        
        response = self.client.post("/get-nearby-places", json={"latitude": 40.7128, "longitude": -74.0060})
        json_data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertIn("places", json_data)
        self.assertEqual(len(json_data["places"]), 1)
        self.assertEqual(json_data["places"][0]["name"], "Test Place")

    @patch("main.app_service.sqlite3.connect")
    def test_check_existing_places(self, mock_connect):
        mock_conn = mock_connect.return_value
        mock_cursor = mock_conn.cursor.return_value

        # Coordinates that exist
        mock_cursor.fetchone.return_value = (1,)
        result = self.app_service.check_existing_places(38.7219, -9.1607)
        self.assertTrue(result)

        # Coordinates that do not exist
        mock_cursor.fetchone.return_value = None
        result = self.app_service.check_existing_places(40.7128, -74.0060)
        self.assertFalse(result)

if __name__ == "__main__":
    unittest.main()
