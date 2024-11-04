import unittest
import os
import asyncio
from app.database.init_db import init_db, get_db_connection
from app.services import AppService
from unittest.mock import patch
from dotenv import load_dotenv

# Load environment variables explicitly for the test environment
load_dotenv()

MOCK_LATITUDE = 37.7749
MOCK_LONGITUDE = -122.4194

class TestQueriesFunctions(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        # Ensure DATABASE_URL is set for testing
        test_db_url = os.getenv("DATABASE_URL")
        if not test_db_url:
            raise EnvironmentError("DATABASE_URL for testing is not set in environment variables.")
        
        # Run init_db to ensure tables are created
        await init_db()

        # Initialize the database connection and AppService instance
        print("Setting up app_service for each test...")
        self.app_service = AppService()  # Instantiate AppService
        await self.app_service.connect_db()  # Connect db_pool explicitly
        print("AppService initialized:", self.app_service)
        print("db_pool connected:", self.app_service.db_pool is not None)

    async def asyncTearDown(self):
        # Cleanup database and close the connection after all tests
        await self.cleanup_database()
        await self.app_service.db_pool.close()

    async def cleanup_database(self):
        """Helper method to clear test data from the database."""
        async with self.app_service.db_pool.acquire() as conn:
            await conn.execute("DELETE FROM user_coordinates;")
            await conn.execute("DELETE FROM google_nearby_places;")

    async def test_generate_entry(self):
        """Verify that generate_entry correctly inserts a unique coordinate entry."""
        await self.app_service.generate_entry(MOCK_LATITUDE, MOCK_LONGITUDE)

        async with self.app_service.db_pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT * FROM user_coordinates WHERE latitude = $1 AND longitude = $2;", 
                MOCK_LATITUDE, MOCK_LONGITUDE
            )
        
        self.assertIsNotNone(result, "Entry not found in user_coordinates for test coordinates.")
        self.assertEqual(result["latitude"], MOCK_LATITUDE)
        self.assertEqual(result["longitude"], MOCK_LONGITUDE)

    async def test_rank_nearby_places(self):
        """Insert mock data and verify the ranking function returns expected places."""
        mock_data = [
            (MOCK_LATITUDE, MOCK_LONGITUDE, "1", "Place A", "OPERATIONAL", 4.5, 100, "Location A", "['restaurant']", 2, "icon_a", "color_a", "mask_a", "photo_ref_a", 400, 400, True),
            (MOCK_LATITUDE, MOCK_LONGITUDE, "2", "Place B", "OPERATIONAL", 4.0, 150, "Location B", "['cafe']", 1, "icon_b", "color_b", "mask_b", "photo_ref_b", 300, 300, False),
            (MOCK_LATITUDE, MOCK_LONGITUDE, "3", "Place C", "OPERATIONAL", 5.0, 50, "Location C", "['bar']", 3, "icon_c", "color_c", "mask_c", "photo_ref_c", 500, 500, True)
        ]

        await self.insert_mock_places(mock_data)
        ranked_places = await self.app_service.rank_nearby_places(MOCK_LATITUDE, MOCK_LONGITUDE)
        
        self.assertEqual(len(ranked_places), 3, "Ranking did not retrieve expected number of places")
        self.assertEqual(ranked_places[0]['name'], "Place C", "Highest-rated place is not ranked first.")

    async def insert_mock_places(self, data):
        """Helper function to insert mock data for testing ranking."""
        async with self.app_service.db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany('''
                    INSERT INTO google_nearby_places (
                        latitude, longitude, place_id, name, business_status, rating, 
                        user_ratings_total, vicinity, types, price_level, icon, 
                        icon_background_color, icon_mask_base_uri, photo_reference, 
                        photo_height, photo_width, open_now
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                    ON CONFLICT (place_id) DO NOTHING
                ''', data)

if __name__ == "__main__":
    unittest.main()
