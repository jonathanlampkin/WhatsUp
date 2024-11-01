import unittest
import os
from app.database.init_db import init_db, get_db_connection
from app.services import AppService

class TestDatabaseAndIntegration(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Check if TEST_DATABASE_URL is available
        if not os.getenv("TEST_DATABASE_URL"):
            raise EnvironmentError("TEST_DATABASE_URL is not set in environment variables.")
        
        # Initialize the database and establish a test connection
        init_db()
        cls.connection = get_db_connection(testing=True)
        cls.cursor = cls.connection.cursor()
        cls.app_service = AppService(google_api_key=os.getenv("GOOGLE_API_KEY"))

    @classmethod
    def tearDownClass(cls):
        # Clean up database tables after all tests
        cls.cursor.execute("DELETE FROM user_coordinates;")
        cls.cursor.execute("DELETE FROM google_nearby_places;")
        cls.connection.commit()
        cls.cursor.close()
        cls.connection.close()

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
        result = self.app_service.generate_entry(MOCK_LATITUDE, MOCK_LONGITUDE)
        self.assertTrue(result, "Failed to insert entry into user_coordinates")

        # Verify the entry exists in the database
        self.cursor.execute("SELECT * FROM user_coordinates WHERE latitude = %s AND longitude = %s;", 
                            (MOCK_LATITUDE, MOCK_LONGITUDE))
        result = self.cursor.fetchone()
        self.assertIsNotNone(result, "No entry found in user_coordinates table for test coordinates")

    def test_rank_nearby_places(self):
        # Insert mock data for ranking test with unique place IDs to avoid conflicts
        mock_data = [
            (37.7749, -122.4194, "1", "Place A", "OPERATIONAL", 4.5, 100, "Location A", "['restaurant']", 2, "icon_a", "color_a", "mask_a", "photo_ref_a", 400, 400, True),
            (37.7749, -122.4194, "2", "Place B", "OPERATIONAL", 4.0, 150, "Location B", "['cafe']", 1, "icon_b", "color_b", "mask_b", "photo_ref_b", 300, 300, False),
            (37.7749, -122.4194, "3", "Place C", "OPERATIONAL", 5.0, 50, "Location C", "['bar']", 3, "icon_c", "color_c", "mask_c", "photo_ref_c", 500, 500, True)
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

        # Check if ranking works as expected
        ranked_places = self.app_service.rank_nearby_places(37.7749, -122.4194)
        self.assertEqual(len(ranked_places), 3, "Ranking did not retrieve expected number of places")

        # Assert that the place with the highest rating (5.0) is ranked first
        self.assertEqual(ranked_places[0]['name'], "Place C", "The place with the highest rating is not ranked first")

if __name__ == "__main__":
    unittest.main()