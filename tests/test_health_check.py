# tests/test_health_check.py

import unittest
from unittest.mock import patch
from app.main import app
import os

class TestHealthCheck(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    @patch.dict(os.environ, {"GOOGLE_API_KEY": "dummy_key"})
    @patch("app.services.AppService.check_database_connection", return_value=True)
    def test_health_check_healthy(self, mock_db):
        response = self.client.get("/health")
        json_data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json_data["api_key_present"])
        self.assertEqual(json_data["status"], "healthy")

    @patch("app.services.AppService.check_database_connection", return_value=False)
    def test_health_check_unhealthy_database(self, mock_check_db):
        response = self.client.get("/health")
        json_data = response.get_json()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(json_data["status"], "unhealthy")
        self.assertEqual(json_data["error"], "Database error")

if __name__ == "__main__":
    unittest.main()
