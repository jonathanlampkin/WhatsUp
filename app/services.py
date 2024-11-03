import os
import requests
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
import uuid
from datetime import datetime
from dotenv import load_dotenv
import logging
import pika
from urllib.parse import urlparse
from cachetools import TTLCache
from urllib3.util.retry import Retry  # Updated import
from requests.adapters import HTTPAdapter
import time

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.DEBUG)

class AppService:
    def __init__(self, google_api_key=None):
        self.google_api_key = google_api_key
        self.db_pool = pool.SimpleConnectionPool(1, 10, dsn=os.getenv("DATABASE_URL"))
        self.cache = TTLCache(maxsize=100, ttl=600)  # Cache up to 100 coordinates for 10 minutes
        
        # Set up RabbitMQ parameters with a fallback URL
        rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
        self.rabbitmq_params = pika.URLParameters(rabbitmq_url)
        
        self.rabbitmq_connection = None
        self.rabbitmq_channel = None
        self.connect_to_rabbitmq()

    def connect_to_rabbitmq(self, max_retries=5, delay=2):
        for attempt in range(max_retries):
            try:
                self.rabbitmq_connection = pika.BlockingConnection(self.rabbitmq_params)
                self.rabbitmq_channel = self.rabbitmq_connection.channel()
                logging.info("Connected to RabbitMQ.")
                return
            except pika.exceptions.AMQPConnectionError as e:
                logging.error(f"RabbitMQ connection attempt {attempt + 1} failed: {e}")
                time.sleep(delay)

    # 1. Check if coordinates are cached
    def is_coordinates_cached(self, latitude, longitude):
        cache_key = f"{latitude}_{longitude}"
        return self.cache.get(cache_key)

    # 2. Send coordinates to RabbitMQ if not cached
    def send_coordinates_if_not_cached(self, latitude, longitude):
        if not self.is_coordinates_cached(latitude, longitude):
            message = json.dumps({"latitude": latitude, "longitude": longitude})
            self.rabbitmq_channel.basic_publish(exchange='', routing_key="coordinates_queue", body=message)
            logging.info(f"Sent {message} to RabbitMQ")

    # 3. Check if coordinates exist in the database
    def check_coordinates_in_db(self, latitude, longitude):
        query = "SELECT 1 FROM google_nearby_places WHERE latitude = %s AND longitude = %s"
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, (latitude, longitude))
                exists = cursor.fetchone() is not None
                logging.debug(f"Checked database for ({latitude}, {longitude}): {'Found' if exists else 'Not found'}")
                return exists
        finally:
            self.release_db_connection(conn)

    # 4. Call Google Places API with retry
    def fetch_from_google_places_api(self, latitude, longitude, radius=5000, place_type="restaurant"):
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            'location': f"{latitude},{longitude}",
            'radius': radius,
            'type': place_type,
            'key': self.google_api_key
        }
        
        session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
        session.mount("https://", HTTPAdapter(max_retries=retries))
        
        response = session.get(url, params=params)
        if response.status_code == 200:
            google_places = response.json().get('results', [])
            logging.info(f"Fetched {len(google_places)} places from Google API.")
            return google_places
        else:
            logging.warning(f"Google Places API call failed with status: {response.status_code}")
            return []

    # 5. Store API results in the database and cache
    def store_places_in_db_and_cache(self, latitude, longitude, places):
        for place in places:
            self.insert_place_data(latitude, longitude, place)
        
        cache_key = f"{latitude}_{longitude}"
        self.cache[cache_key] = places

    # Helper method: Insert a single place entry into the database
    def insert_place_data(self, latitude, longitude, place):
        photo_data = place['photos'][0] if 'photos' in place and place['photos'] else None
        data_tuple = (
            latitude, longitude, place.get("place_id"), place.get("name"),
            place.get("business_status"), place.get("rating"), place.get("user_ratings_total"),
            place.get("vicinity"), json.dumps(place.get("types", [])), place.get("price_level"),
            place.get("icon"), place.get("icon_background_color"), place.get("icon_mask_base_uri"),
            photo_data["photo_reference"] if photo_data else None,
            photo_data["height"] if photo_data else None, photo_data["width"] if photo_data else None,
            place.get("opening_hours", {}).get("open_now", None)
        )

        query = '''
            INSERT INTO google_nearby_places (
                latitude, longitude, place_id, name, business_status, rating, 
                user_ratings_total, vicinity, types, price_level, icon, 
                icon_background_color, icon_mask_base_uri, photo_reference, 
                photo_height, photo_width, open_now
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (place_id) DO NOTHING
        '''
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, data_tuple)
                conn.commit()
                logging.debug(f"Inserted place data for {place.get('name')}")
        finally:
            self.release_db_connection(conn)

    # Consumer functionality: Process coordinates from RabbitMQ
    def process_coordinates_message(self, latitude, longitude):
        """Process coordinates by checking the database and fetching from Google if needed."""
        if self.check_coordinates_in_db(latitude, longitude):
            logging.info(f"Coordinates ({latitude}, {longitude}) found in database.")
            return self.rank_nearby_places(latitude, longitude)
        else:
            places = self.fetch_from_google_places_api(latitude, longitude)
            if places:
                self.store_places_in_db_and_cache(latitude, longitude, places)
            return places

    # Additional database-related helper methods
    def get_db_connection(self):
        """Get a database connection from the pool."""
        return self.db_pool.getconn()

    def release_db_connection(self, conn):
        """Release a database connection back to the pool."""
        self.db_pool.putconn(conn)

    # Rank places by proximity and other criteria
    def rank_nearby_places(self, latitude, longitude):
        query = '''
            SELECT name, rating, user_ratings_total, price_level, open_now, 
                (ABS(latitude - %s) + ABS(longitude - %s)) AS proximity
            FROM google_nearby_places
            WHERE latitude = %s AND longitude = %s
            ORDER BY open_now DESC, rating DESC, proximity ASC
            LIMIT 10;
        '''
        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, (latitude, longitude, latitude, longitude))
                results = cursor.fetchall()
                self.places = [
                    {
                        "name": row["name"],
                        "rating": row["rating"],
                        "user_ratings_total": row["user_ratings_total"],
                        "price_level": row["price_level"],
                        "open_now": row["open_now"]
                    }
                    for row in results
                ]
                logging.debug(f"Ranked places: {self.places}")
        finally:
            self.release_db_connection(conn)
        return self.places
