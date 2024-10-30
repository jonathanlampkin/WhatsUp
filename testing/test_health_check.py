# testing/test_health_check.py
import unittest
from unittest.mock import patch
from main.app import app
import os

class TestHealthCheck(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    @patch.dict(os.environ, {"GOOGLE_API_KEY": "dummy_key"})
    @patch("main.app_service.AppService.check_database_connection", return_value=True)
    @patch("main.app_service.AppService.call_google_places_api", return_value=[{'name': 'Place1'}])
    def test_health_check_healthy(self, mock_db, mock_places):
        response = self.client.get("/health")
        json_data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json_data["api_key_present"])
        self.assertEqual(json_data["status"], "healthy")

    @patch("main.app_service.AppService.check_database_connection", return_value=False)
    @patch("main.app_service.AppService.call_google_places_api", return_value=[])
    def test_health_check_unhealthy_database(self, mock_check_db, mock_call_google_places_api):
        response = self.client.get("/health")
        json_data = response.get_json()
        
        self.assertEqual(response.status_code, 500)
        self.assertEqual(json_data["status"], "unhealthy")
        self.assertEqual(json_data["error"], "Database error")

if __name__ == "__main__":
    unittest.main()
