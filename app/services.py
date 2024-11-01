import os
import requests
import json
import uuid
from datetime import datetime
import logging
import pika
from psycopg2 import DatabaseError
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from urllib.parse import urlparse
from contextlib import contextmanager
from app.database.init_db import get_db_connection

load_dotenv()

@contextmanager
def db_connection(testing=False):
    """Context manager for database connection, ensuring cleanup."""
    conn = get_db_connection(testing=testing)
    try:
        yield conn
    finally:
        conn.close()

class AppService:
    def __init__(self, google_api_key=None):
        self.google_api_key = google_api_key
        self.places = []

    def process_coordinates(self, coords):
        latitude, longitude = coords
        if not self.check_existing_places(latitude, longitude):
            self.call_google_places_api(latitude, longitude)
        self.rank_nearby_places(latitude, longitude)
        return self.places

    def get_rabbitmq_connection(self):
        rabbitmq_url = os.getenv("RABBITMQ_URL")
        if not rabbitmq_url:
            logging.error("RABBITMQ_URL is not set in environment variables.")
            return None
        params = pika.URLParameters(rabbitmq_url)
        return pika.BlockingConnection(params)

    def send_coordinates(self, latitude, longitude):
        connection = self.get_rabbitmq_connection()
        if connection:
            channel = connection.channel()
            queue_name = "coordinates_queue"
            channel.queue_declare(queue=queue_name)
            message = json.dumps({"latitude": latitude, "longitude": longitude})
            channel.basic_publish(exchange='', routing_key=queue_name, body=message)
            logging.info(f"[x] Sent {message} to RabbitMQ")
            connection.close()
        else:
            logging.error("Failed to send coordinates: RabbitMQ connection is not established.")

    def check_database_connection(self):
        try:
            with db_connection() as conn:
                pass
            return True
        except DatabaseError:
            return False

    def check_existing_places(self, latitude, longitude):
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 1 FROM google_nearby_places 
                WHERE latitude = %s AND longitude = %s
            ''', (latitude, longitude))
            result = cursor.fetchone()
            return result is not None

    def generate_entry(self, latitude, longitude):
        visitor_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        try:
            with db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO user_coordinates (visitor_id, latitude, longitude, timestamp)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (visitor_id) DO NOTHING
                ''', (visitor_id, latitude, longitude, timestamp))
                conn.commit()
            logging.info(f"Coordinates saved: {latitude}, {longitude}")
            return True
        except DatabaseError as e:
            logging.error(f"Error saving coordinates: {e}")
            return False

    def call_google_places_api(self, latitude, longitude, radius=1500, place_type="restaurant"):
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
            return response.status_code, google_places
        else:
            logging.error(f"Failed to fetch places from Google API: {response.status_code} - {response.text}")
            return response.status_code, []

    def insert_place_data(self, latitude, longitude, place):
        with db_connection() as conn:
            cursor = conn.cursor()
            photo_data = place.get('photos', [{}])[0]
            data_tuple = (
                latitude, longitude, place.get("place_id"), place.get("name"),
                place.get("business_status"), place.get("rating"), 
                place.get("user_ratings_total"), place.get("vicinity"), 
                json.dumps(place.get("types", [])), place.get("price_level"), 
                place.get("icon"), place.get("icon_background_color"), 
                place.get("icon_mask_base_uri"), photo_data.get("photo_reference"),
                photo_data.get("height"), photo_data.get("width"),
                place.get("opening_hours", {}).get("open_now")
            )
            cursor.execute('''
                INSERT INTO google_nearby_places (
                    latitude, longitude, place_id, name, business_status, rating, 
                    user_ratings_total, vicinity, types, price_level, icon, 
                    icon_background_color, icon_mask_base_uri, photo_reference, 
                    photo_height, photo_width, open_now
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (place_id) DO NOTHING
            ''', data_tuple)
            conn.commit()

    def rank_nearby_places(self, latitude, longitude):
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    name, rating, user_ratings_total, price_level, open_now, 
                    (ABS(latitude - %s) + ABS(longitude - %s)) AS proximity
                FROM google_nearby_places
                WHERE latitude = %s AND longitude = %s
                ORDER BY rating DESC, proximity ASC
                LIMIT 10;
            ''', (latitude, longitude, latitude, longitude))
            results = cursor.fetchall()
            self.places = [
                {"name": row["name"], "rating": row["rating"], "user_ratings_total": row["user_ratings_total"],
                 "price_level": row["price_level"], "open_now": row["open_now"]}
                for row in results
            ]
            logging.debug(f"Ranked places: {self.places}")
            return self.places
