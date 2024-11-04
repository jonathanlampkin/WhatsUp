import os
import aiohttp
import asyncpg
import logging
from cachetools import TTLCache
from dotenv import load_dotenv
import aio_pika
import asyncio
import json

load_dotenv()
logging.basicConfig(level=logging.DEBUG)

class AppService:
    def __init__(self):
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.db_pool = None
        self.cache = TTLCache(maxsize=int(os.getenv("CACHE_SIZE", 100)), ttl=int(os.getenv("CACHE_TTL", 600)))
        self.rabbitmq_url = os.getenv("RABBITMQ_URL")

    async def initialize(self):
        await self.connect_db()

    async def connect_db(self):
        logging.debug("Initializing database connection pool.")
        self.db_pool = await asyncpg.create_pool(dsn=os.getenv("DATABASE_URL"))
        logging.debug("Database connection pool initialized.")

    async def generate_entry(self, latitude, longitude):
        latitude, longitude = round(latitude, 4), round(longitude, 4)
        logging.debug(f"Generating entry for coordinates: ({latitude}, {longitude})")
        if not await self.check_coordinates_in_db(latitude, longitude):
            async with self.db_pool.acquire() as conn:
                logging.debug(f"Inserting new entry into user_coordinates for ({latitude}, {longitude})")
                await conn.execute('''
                    INSERT INTO user_coordinates (latitude, longitude) 
                    VALUES ($1, $2)
                    ON CONFLICT DO NOTHING;
                ''', latitude, longitude)

    async def process_coordinates(self, latitude, longitude):
        latitude, longitude = round(latitude, 4), round(longitude, 4)
        logging.debug(f"Processing coordinates: ({latitude}, {longitude})")
        
        # Check cache
        if self.is_coordinates_cached(latitude, longitude):
            logging.debug(f"Coordinates found in cache: ({latitude}, {longitude})")
            return await self.rank_nearby_places(latitude, longitude)

        # Check database
        if await self.check_coordinates_in_db(latitude, longitude):
            logging.debug(f"Coordinates found in database: ({latitude}, {longitude})")
            places = await self.rank_nearby_places(latitude, longitude)
            self.cache[f"{latitude}_{longitude}"] = places  # Update cache
            return places
        
        # Fetch from Google API
        logging.debug(f"Fetching from Google API for coordinates: ({latitude}, {longitude})")
        places = await self.fetch_from_google_places_api(latitude, longitude)
        if places:
            logging.debug(f"Fetched {len(places)} places from Google Places API.")
            await self.store_places_in_db_and_cache(latitude, longitude, places)
            return await self.rank_nearby_places(latitude, longitude)
        else:
            logging.warning(f"No places found from Google API for coordinates: ({latitude}, {longitude})")
        return []

    async def send_coordinates_if_not_cached(self, latitude, longitude):
        latitude, longitude = round(latitude, 4), round(longitude, 4)
        if not self.is_coordinates_cached(latitude, longitude):
            message = {"latitude": latitude, "longitude": longitude}
            await self.send_to_rabbitmq(message)
            logging.debug(f"Sent coordinates to RabbitMQ: {message}")
        else:
            logging.debug(f"Coordinates already cached, skipping RabbitMQ send: ({latitude}, {longitude})")

    def is_coordinates_cached(self, latitude, longitude):
        is_cached = self.cache.get(f"{latitude}_{longitude}") is not None
        logging.debug(f"Cache check for ({latitude}, {longitude}): {'HIT' if is_cached else 'MISS'}")
        return is_cached

    async def check_coordinates_in_db(self, latitude, longitude):
        async with self.db_pool.acquire() as conn:
            logging.debug(f"Checking database for coordinates: ({latitude}, {longitude})")
            query = "SELECT 1 FROM user_coordinates WHERE latitude = $1 AND longitude = $2"
            result = await conn.fetchrow(query, latitude, longitude)
            exists = result is not None
            logging.debug(f"Database check for ({latitude}, {longitude}): {'FOUND' if exists else 'NOT FOUND'}")
            return exists

    async def fetch_from_google_places_api(self, latitude, longitude, radius=5000, place_type="restaurant"):
        retry_attempts = 3
        for attempt in range(retry_attempts):
            logging.debug(f"Attempt {attempt + 1}/{retry_attempts} fetching from Google API for coordinates: ({latitude}, {longitude})")
            async with aiohttp.ClientSession() as session:
                params = {
                    'location': f"{latitude},{longitude}",
                    'radius': radius,
                    'type': place_type,
                    'key': self.google_api_key
                }
                async with session.get("https://maps.googleapis.com/maps/api/place/nearbysearch/json", params=params) as response:
                    if response.status == 200:
                        result = await response.json()
                        logging.debug(f"Google API returned {len(result['results'])} places for coordinates: ({latitude}, {longitude})")
                        return result.get('results', [])
                    else:
                        logging.error(f"Google API error: {response.status} {await response.text()}")
            await asyncio.sleep(1)  # Short delay before retry
        logging.warning(f"Failed to retrieve data from Google API after {retry_attempts} attempts for coordinates: ({latitude}, {longitude})")
        return []

    async def store_places_in_db_and_cache(self, latitude, longitude, places):
        logging.debug(f"Storing {len(places)} places in database for coordinates: ({latitude}, {longitude})")
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                for place in places:
                    await self.insert_place_data(conn, latitude, longitude, place)
        self.cache[f"{latitude}_{longitude}"] = places
        logging.debug(f"Stored {len(places)} places in database and cache for ({latitude}, {longitude})")

    async def insert_place_data(self, conn, latitude, longitude, place):
        logging.debug(f"Inserting place data for {place.get('name', 'Unknown')} at ({latitude}, {longitude})")
        await conn.execute('''
            INSERT INTO google_nearby_places (
                latitude, longitude, place_id, name, business_status, rating, 
                user_ratings_total, vicinity, types, price_level, icon, 
                icon_background_color, icon_mask_base_uri, photo_reference, 
                photo_height, photo_width, open_now
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
            ON CONFLICT (place_id) DO NOTHING
        ''', latitude, longitude, place.get("place_id"), place.get("name"), place.get("business_status"),
        place.get("rating"), place.get("user_ratings_total"), place.get("vicinity"), 
        ','.join(place.get("types", [])), place.get("price_level"), place.get("icon"),
        place.get("icon_background_color"), place.get("icon_mask_base_uri"), 
        (place['photos'][0]['photo_reference'] if 'photos' in place and place['photos'] else None), 
        (place['photos'][0]['height'] if 'photos' in place and place['photos'] else None), 
        (place['photos'][0]['width'] if 'photos' in place and place['photos'] else None), 
        place.get("opening_hours", {}).get("open_now"))

    async def rank_nearby_places(self, latitude, longitude):
        logging.debug(f"Ranking nearby places for coordinates: ({latitude}, {longitude})")
        async with self.db_pool.acquire() as conn:
            query = '''
                SELECT name, rating, user_ratings_total, price_level, open_now, 
                    (ABS(latitude - $1) + ABS(longitude - $2)) AS proximity
                FROM google_nearby_places
                WHERE latitude = $1 AND longitude = $2
                ORDER BY open_now DESC NULLS LAST, rating DESC, proximity ASC, user_ratings_total DESC
                LIMIT 10;
            '''
            results = await conn.fetch(query, latitude, longitude)
            places = [dict(record) for record in results]
            logging.debug(f"Ranked places for ({latitude}, {longitude}): {places}")
            return places


    async def send_to_rabbitmq(self, message):
        logging.debug(f"Sending message to RabbitMQ: {message}")
        connection = await aio_pika.connect_robust(self.rabbitmq_url)
        async with connection:
            channel = await connection.channel()
            await channel.default_exchange.publish(
                aio_pika.Message(body=json.dumps(message).encode()),
                routing_key="coordinates_queue"
            )
        logging.debug(f"Message sent to RabbitMQ: {message}")
