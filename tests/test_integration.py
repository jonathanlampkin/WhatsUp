# tests/test_integration.py

import os
import unittest
from unittest.mock import patch
from app.services import AppService
from urllib.parse import urlparse
from app.database.init_db import init_db, get_db_connection

MOCK_LATITUDE = 37.7749
MOCK_LONGITUDE = -122.4194

class TestIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app_service = AppService(google_api_key=os.getenv("GOOGLE_API_KEY"))
        init_db()  # Ensures the database and tables are set up

    def test_generate_entry(self):
        result = self.app_service.generate_entry(MOCK_LATITUDE, MOCK_LONGITUDE)
        self.assertTrue(result, "Failed to insert entry into user_coordinates")

    @patch("app.services.AppService.call_google_places_api", return_value=200)
    def test_call_google_places_api(self, mock_api_call):
        status_code, _ = self.app_service.call_google_places_api(MOCK_LATITUDE, MOCK_LONGITUDE)
        self.assertEqual(status_code, 200, "Google API call did not succeed")

    def test_rank_nearby_places(self):
        # Insert mock data to test ranking
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO google_nearby_places (latitude, longitude, place_id, name, rating)
            VALUES (%s, %s, '1', 'Place A', 4.5), (%s, %s, '2', 'Place B', 4.0)
            ON CONFLICT (place_id) DO NOTHING
        ''', (MOCK_LATITUDE, MOCK_LONGITUDE, MOCK_LATITUDE, MOCK_LONGITUDE))
        conn.commit()
        conn.close()

        ranked_places = self.app_service.rank_nearby_places(MOCK_LATITUDE, MOCK_LONGITUDE)
        self.assertEqual(len(ranked_places), 2, "Ranking did not retrieve expected number of places")

if __name__ == "__main__":
    unittest.main()
