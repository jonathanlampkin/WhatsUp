import unittest
from unittest.mock import patch, MagicMock
from main.app import app
import sqlite3

class TestHealthCheck(unittest.TestCase):

    @patch("main.app.sqlite3.connect")
    @patch("main.app.app_service.call_google_places_api")
    def test_health_check_healthy(self, mock_call_google_places_api, mock_connect):
        # Mock database connection
        mock_conn = mock_connect.return_value
        mock_conn.execute.return_value = None

        # Mock successful call to the Google Places API with sample data
        mock_call_google_places_api.return_value = [{"name": "Test Place"}]

        # Test client for the Flask app
        with app.test_client() as client:
            response = client.get("/health")
            self.assertEqual(response.status_code, 200)

            json_data = response.get_json()
            self.assertEqual(json_data["status"], "healthy")
            self.assertEqual(json_data["database"], "connected")
            self.assertTrue(json_data["api_key_present"])
            self.assertEqual(json_data["upload_check"], "successful")
            self.assertGreaterEqual(json_data["nearby_places_count"], 1)

    @patch("main.app.sqlite3.connect")
    def test_health_check_unhealthy_database(self, mock_connect):
        # Simulate a database connection error
        mock_connect.side_effect = sqlite3.OperationalError("Database error")

        with app.test_client() as client:
            response = client.get("/health")
            self.assertEqual(response.status_code, 500)

            json_data = response.get_json()
            self.assertEqual(json_data["status"], "unhealthy")
            self.assertEqual(json_data["database"], "disconnected")
            self.assertIn("error", json_data)
            self.assertEqual(json_data["error"], "Database error")

    @patch("main.app.sqlite3.connect")
    @patch("main.app.app_service.call_google_places_api")
    def test_health_check_upload_failure(self, mock_call_google_places_api, mock_connect):
        # Mock database connection
        mock_conn = mock_connect.return_value
        mock_conn.execute.return_value = None

        # Mock a failure in the nearby places response (e.g., empty response)
        mock_call_google_places_api.return_value = []

        with app.test_client() as client:
            response = client.get("/health")
            self.assertEqual(response.status_code, 500)

            json_data = response.get_json()
            self.assertEqual(json_data["status"], "unhealthy")
            self.assertIn("error", json_data)
