# tests/test_database.py

import unittest
from app.database.init_db import init_db, get_db_connection
from app.models import UserCoordinates, GoogleNearbyPlaces
import os

class TestDatabase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Initialize the database and ensure tables are created
        init_db()
        cls.connection = get_db_connection()
        cls.cursor = cls.connection.cursor()

    @classmethod
    def tearDownClass(cls):
        # Clean up database tables after testing
        cls.cursor.execute("DELETE FROM user_coordinates;")
        cls.cursor.execute("DELETE FROM google_nearby_places;")
        cls.connection.commit()
        cls.cursor.close()
        cls.connection.close()

    def test_insert_user_coordinates(self):
        # Insert a test entry to verify functionality
        visitor_id = "test_user"
        latitude, longitude = 37.7749, -122.4194
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
        # Insert a test entry to verify functionality
        place_id = "test_place"
        latitude, longitude = 37.7749, -122.4194
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

if __name__ == "__main__":
    unittest.main()
