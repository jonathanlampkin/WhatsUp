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
    @patch("main.app_service.AppService.call_google_places_api")
    def test_process_coordinates_existing_places(self, mock_call_google_places_api, mock_check_existing_places):
        # Simulate that coordinates already exist in the database
        mock_check_existing_places.return_value = True
        mock_call_google_places_api.return_value = []

        data = {"latitude": 40.7128, "longitude": -74.0060}
        response = self.client.post("/process-coordinates", json=data)
        json_data = response.get_json()
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("places", json_data)

    @patch.dict(os.environ, {"RABBITMQ_URL": "amqp://guest:guest@localhost:5672/"})
    @patch("main.app_service.AppService.call_google_places_api")
    @patch("main.app_service.AppService.check_existing_places")
    def test_process_coordinates_no_existing_places(self, mock_check_existing_places, mock_call_google_places_api):
        # Simulate no existing places, so it will call the Google API
        mock_check_existing_places.return_value = False
        mock_call_google_places_api.return_value = [
            {"name": "New Place", "vicinity": "123 New St", "rating": 4.0}
        ]

        data = {"latitude": 40.7128, "longitude": -74.0060}
        response = self.client.post("/process-coordinates", json=data)
        json_data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertIn("places", json_data)
        self.assertEqual(len(json_data["places"]), 1)
        self.assertEqual(json_data["places"][0]["name"], "New Place")

if __name__ == "__main__":
    unittest.main()
