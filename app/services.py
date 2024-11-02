import os
import requests
import json
import psycopg2
from psycopg2.extras import RealDictCursor, pool
import uuid
from datetime import datetime
from dotenv import load_dotenv
import logging
import pika
from cachetools import TTLCache

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.DEBUG)

class AppService:
    def __init__(self, google_api_key=None):
        self.google_api_key = google_api_key
        self.places = []
        self.db_pool = pool.SimpleConnectionPool(1, 20, dsn=os.getenv("DATABASE_URL"))
        self.cache = TTLCache(maxsize=100, ttl=600)  # Cache up to 100 coordinates for 10 minutes
        
        # Set up persistent RabbitMQ connection
        self.rabbitmq_params = pika.URLParameters(os.getenv("RABBITMQ_URL"))
        self.rabbitmq_connection = pika.BlockingConnection(self.rabbitmq_params)
        self.rabbitmq_channel = self.rabbitmq_connection.channel()
        self.rabbitmq_channel.queue_declare(queue="coordinates_queue")

    def send_coordinates(self, latitude, longitude):
        """Send coordinates to RabbitMQ."""
        message = json.dumps({"latitude": latitude, "longitude": longitude})
        self.rabbitmq_channel.basic_publish(exchange='', routing_key="coordinates_queue", body=message)
        logging.info(f"Sent {message} to RabbitMQ")

    def process_coordinates(self, coords):
        latitude, longitude = coords
        cache_key = f"{latitude}_{longitude}"
        
        # Check cache before proceeding
        if cache_key in self.cache:
            logging.info("Using cached result.")
            return self.cache[cache_key]
        
        # Generate entry and check for existing places
        self.generate_entry(latitude, longitude)
        if self.check_existing_places(latitude, longitude):
            places = self.rank_nearby_places(latitude, longitude)
        else:
            places = self.call_google_places_api(latitude, longitude)
        
        # Cache the result
        self.cache[cache_key] = places
        return places

    def get_db_connection(self):
        """Get a database connection from the pool."""
        return self.db_pool.getconn()

    def release_db_connection(self, conn):
        """Release a database connection back to the pool."""
        self.db_pool.putconn(conn)

    def check_existing_places(self, latitude, longitude):
        """Check if places already exist in the database for given coordinates."""
        query = "SELECT 1 FROM google_nearby_places WHERE latitude = %s AND longitude = %s"
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, (latitude, longitude))
                exists = cursor.fetchone() is not None
                logging.debug(f"Checked existing places for ({latitude}, {longitude}): {'Found' if exists else 'Not found'}")
                return exists
        finally:
            self.release_db_connection(conn)

    def generate_entry(self, latitude, longitude):
        """Generate a unique visitor entry in the user_coordinates table."""
        visitor_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        query = '''
            INSERT INTO user_coordinates (visitor_id, latitude, longitude, timestamp)
            VALUES (%s, %s, %s, %s) ON CONFLICT (visitor_id) DO NOTHING
        '''
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, (visitor_id, latitude, longitude, timestamp))
                conn.commit()
                logging.info(f"Inserted user coordinate entry: {visitor_id}")
        finally:
            self.release_db_connection(conn)

    def call_google_places_api(self, latitude, longitude, radius=3000, place_type="point_of_interest"):
        """Call the Google Places API to fetch nearby places."""
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            'location': f"{latitude},{longitude}",
            'radius': radius,
            'type': place_type,
            'key': self.google_api_key
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            google_places = response.json().get('results', [])
            for place in google_places:
                self.insert_place_data(latitude, longitude, place)
            logging.info(f"Fetched and inserted {len(google_places)} places from Google API.")
            return google_places
        else:
            logging.warning(f"Google Places API call failed with status: {response.status_code}")
            return []

    def insert_place_data(self, latitude, longitude, place):
        """Insert a single place entry into the google_nearby_places table."""
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

    def rank_nearby_places(self, latitude, longitude):
        """Rank nearby places by rating, proximity, and open status."""
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
            with conn.cursor() as cursor:
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
