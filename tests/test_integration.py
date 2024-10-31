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
        status_code = self.app_service.call_google_places_api(MOCK_LATITUDE, MOCK_LONGITUDE)
        self.assertEqual(status_code, 200, "Google API call did not succeed")

    def test_rank_nearby_places(self):
        # Insert mock data for ranking
        conn = get_db_connection()
        cursor = conn.cursor()
        mock_data = [
            (37.7749, -122.4194, "1", "Place A", "OPERATIONAL", 4.5, 100, "Location A", "['restaurant']", 2, "icon_a", "color_a", "mask_a", "photo_ref_a", 400, 400, True),
            (37.7749, -122.4194, "2", "Place B", "OPERATIONAL", 4.0, 150, "Location B", "['cafe']", 1, "icon_b", "color_b", "mask_b", "photo_ref_b", 300, 300, False)
        ]
        cursor.executemany('''
            INSERT INTO google_nearby_places (
                latitude, longitude, place_id, name, business_status, rating, 
                user_ratings_total, vicinity, types, price_level, icon, 
                icon_background_color, icon_mask_base_uri, photo_reference, 
                photo_height, photo_width, open_now
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (place_id) DO NOTHING
        ''', mock_data)
        conn.commit()

        # Verify data insertion
        cursor.execute("SELECT * FROM google_nearby_places WHERE latitude = %s AND longitude = %s", (37.7749, -122.4194))
        rows = cursor.fetchall()
        print("Inserted rows:", rows)  # Debugging output to verify data insertion
        cursor.close()
        conn.close()

        # Run the ranking method
        ranked_places = self.app_service.rank_nearby_places(37.7749, -122.4194)
        print("Ranked places:", ranked_places)  # Debugging output for ranked places
        self.assertEqual(len(ranked_places), 2, "Ranking did not retrieve expected number of places")

if __name__ == "__main__":
    unittest.main()
