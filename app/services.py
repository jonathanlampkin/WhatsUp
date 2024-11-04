import os
import json
import logging
import aiohttp
import asyncpg
from dotenv import load_dotenv
from cachetools import TTLCache
from aio_pika import connect_robust, Message, DeliveryMode
from typing import List, Optional

load_dotenv()
logging.basicConfig(level=logging.INFO)

class AppService:
    def __init__(self):
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.cache = TTLCache(maxsize=int(os.getenv("CACHE_SIZE", 100)), ttl=int(os.getenv("CACHE_TTL", 600)))
        self.db_pool = None
        self.rabbitmq_connection = None

    async def initialize(self):
        self.db_pool = await asyncpg.create_pool(dsn=os.getenv("DATABASE_URL"))
        self.rabbitmq_connection = await connect_robust(os.getenv("RABBITMQ_URL"))

    async def send_coordinates_if_not_cached(self, latitude, longitude):
        if not self.is_coordinates_cached(latitude, longitude):
            message = json.dumps({"latitude": latitude, "longitude": longitude})
            await self.publish_message("coordinates_queue", message)

    def is_coordinates_cached(self, latitude, longitude) -> Optional[dict]:
        return self.cache.get(f"{latitude}_{longitude}")

    async def publish_message(self, queue_name, message):
        async with self.rabbitmq_connection.channel() as channel:
            await channel.declare_queue(queue_name, durable=True)
            await channel.default_exchange.publish(
                Message(body=message.encode(), delivery_mode=DeliveryMode.PERSISTENT),
                routing_key=queue_name,
            )
            logging.info(f"Sent {message} to RabbitMQ")

    async def check_database_connection(self):
        async with self.db_pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1;")
            return result is not None

    async def check_coordinates_in_db(self, latitude, longitude) -> bool:
        query = "SELECT 1 FROM google_nearby_places WHERE latitude = $1 AND longitude = $2"
        async with self.db_pool.acquire() as conn:
            result = await conn.fetchval(query, latitude, longitude)
            return result is not None

    async def fetch_from_google_places_api(self, latitude, longitude, radius=5000, place_type="restaurant") -> List[dict]:
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {'location': f"{latitude},{longitude}", 'radius': radius, 'type': place_type, 'key': self.google_api_key}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("results", [])
                return []

    async def store_places_in_db_and_cache(self, latitude, longitude, places: List[dict]):
        async with self.db_pool.acquire() as conn:
            for place in places:
                await conn.execute(
                    '''
                    INSERT INTO google_nearby_places (latitude, longitude, place_id, name, business_status, rating, 
                                                      user_ratings_total, vicinity, types, price_level, icon, 
                                                      icon_background_color, icon_mask_base_uri, photo_reference, 
                                                      photo_height, photo_width, open_now) 
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                    ON CONFLICT (place_id) DO NOTHING
                    ''',
                    latitude, longitude, place.get("place_id"), place.get("name"), place.get("business_status"),
                    place.get("rating"), place.get("user_ratings_total"), place.get("vicinity"), 
                    json.dumps(place.get("types", [])), place.get("price_level"), place.get("icon"),
                    place.get("icon_background_color"), place.get("icon_mask_base_uri"), 
                    (place['photos'][0]['photo_reference'] if 'photos' in place and place['photos'] else None), 
                    (place['photos'][0]['height'] if 'photos' in place and place['photos'] else None), 
                    (place['photos'][0]['width'] if 'photos' in place and place['photos'] else None), 
                    place.get("opening_hours", {}).get("open_now")
                )
        self.cache[f"{latitude}_{longitude}"] = places

    async def rank_nearby_places(self, latitude, longitude) -> List[dict]:
        query = '''
            SELECT name, rating, user_ratings_total, price_level, open_now, 
                (ABS(latitude - $1) + ABS(longitude - $2)) AS proximity
            FROM google_nearby_places
            WHERE latitude = $1 AND longitude = $2
            ORDER BY open_now DESC NULLS LAST, rating DESC, proximity ASC, user_ratings_total DESC
            LIMIT 10;
        '''
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, latitude, longitude)
            return [
                {
                    "name": row["name"],
                    "rating": row["rating"],
                    "user_ratings_total": row["user_ratings_total"],
                    "price_level": row["price_level"],
                    "open_now": row["open_now"]
                }
                for row in rows
            ]
