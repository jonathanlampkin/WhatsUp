# test_queries_functions.py

import logging
import unittest
import os
from app.database.init_db import init_db, get_db_connection
from app.services import AppService

MOCK_LATITUDE = 37.7749
MOCK_LONGITUDE = -122.4194

class TestDatabaseAndIntegration(unittest.TestCase):
    
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
        cursor = cls.connection.cursor()
        cursor.execute("DELETE FROM user_coordinates;")
        cursor.execute("DELETE FROM google_nearby_places;")
        cls.connection.commit()
        cursor.close()
        cls.connection.close()

    def setUp(self):
        self.cursor = self.connection.cursor()

    def tearDown(self):
        self.cursor.close()

    # def test_generate_entry(self):
    #     """Verify that generate_entry correctly inserts a unique coordinate entry."""
    #     # Call generate_entry and assert it returns success
    #     insertion_success = self.app_service.generate_entry(MOCK_LATITUDE, MOCK_LONGITUDE)
    #     self.assertTrue(insertion_success, "generate_entry failed to insert entry")

    #     # Verify the insertion directly
    #     self.connection.commit()  # Ensure all transactions are committed
    #     with self.connection.cursor() as cursor:
    #         cursor.execute("SELECT * FROM user_coordinates WHERE latitude = %s AND longitude = %s;", 
    #                        (MOCK_LATITUDE, MOCK_LONGITUDE))
    #         db_result = cursor.fetchone()
    #         logging.debug(f"Entry found in user_coordinates: {db_result}")
    #         self.assertIsNotNone(db_result, "No entry found in user_coordinates table for test coordinates")

    # def test_rank_nearby_places(self):
    #     """Insert mock data and verify the ranking function returns expected places."""
    #     mock_data = [
    #         (MOCK_LATITUDE, MOCK_LONGITUDE, "1", "Place A", "OPERATIONAL", 4.5, 100, "Location A", "['restaurant']", 2, "icon_a", "color_a", "mask_a", "photo_ref_a", 400, 400, True),
    #         (MOCK_LATITUDE, MOCK_LONGITUDE, "2", "Place B", "OPERATIONAL", 4.0, 150, "Location B", "['cafe']", 1, "icon_b", "color_b", "mask_b", "photo_ref_b", 300, 300, False),
    #         (MOCK_LATITUDE, MOCK_LONGITUDE, "3", "Place C", "OPERATIONAL", 5.0, 50, "Location C", "['bar']", 3, "icon_c", "color_c", "mask_c", "photo_ref_c", 500, 500, True)
    #     ]

    #     # Insert mock data and ensure commit
    #     self.cursor.executemany('''
    #         INSERT INTO google_nearby_places (
    #             latitude, longitude, place_id, name, business_status, rating, 
    #             user_ratings_total, vicinity, types, price_level, icon, 
    #             icon_background_color, icon_mask_base_uri, photo_reference, 
    #             photo_height, photo_width, open_now
    #         ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    #         ON CONFLICT (place_id) DO NOTHING
    #     ''', mock_data)
    #     self.connection.commit()  # Ensure all transactions are committed

    #     # Call rank_nearby_places and validate results
    #     ranked_places = self.app_service.rank_nearby_places(MOCK_LATITUDE, MOCK_LONGITUDE)
    #     logging.debug(f"Ranked places: {ranked_places}")
    #     self.assertEqual(len(ranked_places), 3, "Ranking did not retrieve expected number of places")
    #     self.assertEqual(ranked_places[0]['name'], "Place C", "The place with the highest rating is not ranked first")
