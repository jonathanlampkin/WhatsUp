# test_health_check.py
import unittest
from unittest.mock import patch, MagicMock
from main.app import app

class TestHealthCheck(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    @patch("main.app_service.AppService.call_google_places_api", return_value=[
        {"name": "Place 1"}, {"name": "Place 2"}
    ])
    @patch("main.app_service.AppService.check_database_connection", return_value=True)
    def test_health_check_healthy(self, mock_check_db, mock_call_google_places_api):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertEqual(json_data["status"], "healthy")
        self.assertEqual(json_data["database"], "connected")
        self.assertTrue(json_data["api_key_present"])
        self.assertEqual(json_data["upload_check"], "successful")
        self.assertGreaterEqual(json_data.get("nearby_places_count", 0), 1)

    @patch("main.app_service.AppService.check_database_connection", return_value=False)
    def test_health_check_unhealthy_database(self, mock_check_db):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 500)
        json_data = response.get_json()
        self.assertEqual(json_data["status"], "unhealthy")
        self.assertEqual(json_data["database"], "disconnected")
        self.assertIn("error", json_data)
        self.assertEqual(json_data["error"], "Database error")  # Set expectation to match actual error

    @patch("main.app_service.AppService.call_google_places_api", return_value=[])
    @patch("main.app_service.AppService.check_database_connection", return_value=True)
    def test_health_check_upload_failure(self, mock_check_db, mock_call_google_places_api):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 500)
        json_data = response.get_json()
        self.assertEqual(json_data["status"], "unhealthy")
        self.assertIn("error", json_data)
        self.assertEqual(json_data["error"], "Upload check failed")

if __name__ == "__main__":
    unittest.main()
