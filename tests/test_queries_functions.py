import unittest
import os
from app.database.init_db import init_db, get_db_connection
from app.services import AppService
from unittest.mock import patch

MOCK_LATITUDE = 37.7749
MOCK_LONGITUDE = -122.4194

class TestQueriesFunctions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        test_db_url = os.getenv("DATABASE_URL")
        if not test_db_url:
            raise EnvironmentError("DATABASE_URL for testing is not set in environment variables.")
        
        init_db()  # Ensure tables exist
        cls.connection = get_db_connection()
        cls.app_service = AppService(google_api_key=os.getenv("GOOGLE_API_KEY"))

    @classmethod
    def tearDownClass(cls):
        cls.cleanup_database()
        cls.connection.close()

    @classmethod
    def cleanup_database(cls):
        """Helper method to clear test data from database."""
        with cls.connection.cursor() as cursor:
            cursor.execute("DELETE FROM user_coordinates;")
            cursor.execute("DELETE FROM google_nearby_places;")
            cls.connection.commit()

    @unittest.skip("Skipping test_generate_entry temporarily")
    def test_generate_entry(self):
        """Verify that generate_entry correctly inserts a unique coordinate entry."""
        self.app_service.generate_entry(MOCK_LATITUDE, MOCK_LONGITUDE)

        with self.connection.cursor() as cursor:
            cursor.execute("SELECT * FROM user_coordinates WHERE latitude = %s AND longitude = %s;", 
                           (MOCK_LATITUDE, MOCK_LONGITUDE))
            db_result = cursor.fetchone()
        
        self.assertIsNotNone(db_result, "Entry not found in user_coordinates for test coordinates.")
        self.assertEqual(db_result["latitude"], MOCK_LATITUDE)
        self.assertEqual(db_result["longitude"], MOCK_LONGITUDE)

    @unittest.skip("Skipping test_rank_nearby_places temporarily")
    def test_rank_nearby_places(self):
        """Insert mock data and verify the ranking function returns expected places."""
        mock_data = [
            (MOCK_LATITUDE, MOCK_LONGITUDE, "1", "Place A", "OPERATIONAL", 4.5, 100, "Location A", "['restaurant']", 2, "icon_a", "color_a", "mask_a", "photo_ref_a", 400, 400, True),
            (MOCK_LATITUDE, MOCK_LONGITUDE, "2", "Place B", "OPERATIONAL", 4.0, 150, "Location B", "['cafe']", 1, "icon_b", "color_b", "mask_b", "photo_ref_b", 300, 300, False),
            (MOCK_LATITUDE, MOCK_LONGITUDE, "3", "Place C", "OPERATIONAL", 5.0, 50, "Location C", "['bar']", 3, "icon_c", "color_c", "mask_c", "photo_ref_c", 500, 500, True)
        ]

        self.insert_mock_places(mock_data)
        ranked_places = self.app_service.rank_nearby_places(MOCK_LATITUDE, MOCK_LONGITUDE)
        
        self.assertEqual(len(ranked_places), 3, "Ranking did not retrieve expected number of places")
        self.assertEqual(ranked_places[0]['name'], "Place C", "Highest-rated place is not ranked first.")

    def insert_mock_places(self, data):
        """Helper function to insert mock data for testing ranking."""
        with self.connection.cursor() as cursor:
            cursor.executemany('''
                INSERT INTO google_nearby_places (
                    latitude, longitude, place_id, name, business_status, rating, 
                    user_ratings_total, vicinity, types, price_level, icon, 
                    icon_background_color, icon_mask_base_uri, photo_reference, 
                    photo_height, photo_width, open_now
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (place_id) DO NOTHING
            ''', data)
            self.connection.commit()

    # Test for Cache Management in AppService
    def test_cache_management(self):
        """Test the caching mechanism to ensure coordinates are stored and retrieved correctly."""
        latitude, longitude = MOCK_LATITUDE, MOCK_LONGITUDE
        cache_key = f"{latitude}_{longitude}"

        # Clear cache and ensure coordinates are not cached initially
        self.app_service.cache.clear()
        self.assertIsNone(self.app_service.is_coordinates_cached(latitude, longitude))

        # Populate cache and check if data is cached correctly
        self.app_service.cache[cache_key] = "Test Data"
        self.assertEqual(self.app_service.is_coordinates_cached(latitude, longitude), "Test Data")

        # Test cache expiration by setting a short TTL and waiting
        with patch('cachetools.TTLCache.__contains__', return_value=False):
            self.assertIsNone(self.app_service.is_coordinates_cached(latitude, longitude), 
                              "Cache did not expire as expected.")

if __name__ == "__main__":
    unittest.main()
