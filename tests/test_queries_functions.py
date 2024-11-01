# test_queries_function.py

import logging
import unittest
import os
from app.database.init_db import init_db, get_db_connection
from app.services import AppService

# Define mock latitude and longitude values
MOCK_LATITUDE = 37.7749
MOCK_LONGITUDE = -122.4194

class TestDatabaseAndIntegration(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Check if TEST_DATABASE_URL is available
        test_db_url = os.getenv("TEST_DATABASE_URL")
        if not test_db_url:
            raise EnvironmentError("TEST_DATABASE_URL is not set in environment variables.")
        
        # Initialize the database in testing mode
        init_db(testing=True)

        # Establish a connection using the testing database URL
        cls.connection = get_db_connection(testing=True)
        cls.app_service = AppService(google_api_key=os.getenv("GOOGLE_API_KEY"))

    @classmethod
    def tearDownClass(cls):
        # Clean up database tables after all tests
        cursor = cls.connection.cursor()
        cursor.execute("DELETE FROM user_coordinates;")
        cursor.execute("DELETE FROM google_nearby_places;")
        cls.connection.commit()
        cursor.close()
        cls.connection.close()

    def setUp(self):
        # Start each test with a fresh cursor
        self.cursor = self.connection.cursor()

    def tearDown(self):
        # Close the cursor after each test
        self.cursor.close()

    # Database-specific tests
    def test_insert_user_coordinates(self):
        visitor_id = "test_user_1"  # Unique identifier to prevent conflict
        latitude, longitude = MOCK_LATITUDE, MOCK_LONGITUDE
        timestamp = "2024-01-01T00:00:00Z"
        self.cursor.execute('''
            INSERT INTO user_coordinates (visitor_id, latitude, longitude, timestamp)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (visitor_id) DO NOTHING
        ''', (visitor_id, latitude, longitude, timestamp))
        self.connection.commit()

        # Verify the entry exists in the table
        self.cursor.execute("SELECT * FROM user_coordinates WHERE visitor_id = %s;", (visitor_id,))
        result = self.cursor.fetchone()
        self.assertIsNotNone(result)
        self.assertEqual(result['latitude'], latitude)

    def test_insert_google_nearby_places(self):
        place_id = "test_place_1"  # Unique place ID to prevent conflict
        latitude, longitude = MOCK_LATITUDE, MOCK_LONGITUDE
        name = "Test Place"
        self.cursor.execute('''
            INSERT INTO google_nearby_places (latitude, longitude, place_id, name)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (place_id) DO NOTHING
        ''', (latitude, longitude, place_id, name))
        self.connection.commit()

        # Verify the entry exists in the table
        self.cursor.execute("SELECT * FROM google_nearby_places WHERE place_id = %s;", (place_id,))
        result = self.cursor.fetchone()
        self.assertIsNotNone(result)
        self.assertEqual(result['name'], name)

    # Integration-specific tests
    def test_generate_entry(self):
        # Insert a user coordinate entry, ensuring it does not conflict with previous tests
        result = self.app_service.generate_entry(MOCK_LATITUDE, MOCK_LONGITUDE, testing=True)
        self.assertTrue(result, "Failed to insert entry into user_coordinates")

        # Use a new connection to verify the entry exists in the database
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT * FROM user_coordinates WHERE latitude = %s AND longitude = %s;", 
                        (MOCK_LATITUDE, MOCK_LONGITUDE))
            result = cursor.fetchone()
            logging.debug(f"Verified entry in user_coordinates: {result}")
            self.assertIsNotNone(result, "No entry found in user_coordinates table for test coordinates")



    def test_rank_nearby_places(self):
        # Insert mock data for ranking test with unique place IDs to avoid conflicts
        mock_data = [
            (MOCK_LATITUDE, MOCK_LONGITUDE, "1", "Place A", "OPERATIONAL", 4.5, 100, "Location A", "['restaurant']", 2, "icon_a", "color_a", "mask_a", "photo_ref_a", 400, 400, True),
            (MOCK_LATITUDE, MOCK_LONGITUDE, "2", "Place B", "OPERATIONAL", 4.0, 150, "Location B", "['cafe']", 1, "icon_b", "color_b", "mask_b", "photo_ref_b", 300, 300, False),
            (MOCK_LATITUDE, MOCK_LONGITUDE, "3", "Place C", "OPERATIONAL", 5.0, 50, "Location C", "['bar']", 3, "icon_c", "color_c", "mask_c", "photo_ref_c", 500, 500, True)
        ]

        self.cursor.executemany('''
            INSERT INTO google_nearby_places (
                latitude, longitude, place_id, name, business_status, rating, 
                user_ratings_total, vicinity, types, price_level, icon, 
                icon_background_color, icon_mask_base_uri, photo_reference, 
                photo_height, photo_width, open_now
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (place_id) DO NOTHING
        ''', mock_data)
        self.connection.commit()

        # Debug: Confirm data in google_nearby_places after insertion
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT * FROM google_nearby_places WHERE latitude = %s AND longitude = %s", 
                        (MOCK_LATITUDE, MOCK_LONGITUDE))
            inserted_data = cursor.fetchall()
            logging.debug(f"Inserted data for ranking test in google_nearby_places: {inserted_data}")

        # Check if ranking works as expected
        ranked_places = self.app_service.rank_nearby_places(MOCK_LATITUDE, MOCK_LONGITUDE, testing=True)
        self.assertEqual(len(ranked_places), 3, "Ranking did not retrieve expected number of places")

        # Assert that the place with the highest rating (5.0) is ranked first
        self.assertEqual(ranked_places[0]['name'], "Place C", "The place with the highest rating is not ranked first")

if __name__ == "__main__":
    unittest.main()
