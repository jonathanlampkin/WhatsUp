import os
import requests
import json
import uuid
from datetime import datetime
import logging
import pika  # RabbitMQ
from psycopg2 import DatabaseError
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from flask import jsonify
from urllib.parse import urlparse
from app.database.init_db import get_db_connection
from contextlib import contextmanager

load_dotenv()

class AppService:
    def __init__(self, google_api_key=None):
        self.google_api_key = google_api_key
        self.places = []
        self.results = []
        self.coords = []

    @contextmanager
    def db_connection(self):
        """Context manager for database connection."""
        conn = get_db_connection()
        try:
            yield conn
        finally:
            conn.close()

    def process_coordinates(self, coords):
        latitude, longitude = coords
        visitor_id = self.generate_entry(latitude, longitude)
        if self.check_existing_places(latitude, longitude):
            self.rank_nearby_places(latitude, longitude)
        else:
            self.call_google_places_api(latitude, longitude)
            self.rank_nearby_places(latitude, longitude)
        return self.places

    def get_rabbitmq_connection(self):
        rabbitmq_url = os.getenv("RABBITMQ_URL")
        params = pika.URLParameters(rabbitmq_url)
        return pika.BlockingConnection(params)

    def send_coordinates(self, latitude, longitude):
        connection = self.get_rabbitmq_connection()
        channel = connection.channel()
        queue_name = "coordinates_queue"
        channel.queue_declare(queue=queue_name)
        message = json.dumps({"latitude": latitude, "longitude": longitude})
        channel.basic_publish(exchange='', routing_key=queue_name, body=message)
        logging.info(f"[x] Sent {message} to RabbitMQ")
        connection.close()

    def get_google_api_key(self):
        return jsonify({"apiKey": self.google_api_key})

    def check_database_connection(self):
        try:
            with self.db_connection() as conn:
                return True
        except DatabaseError:
            return False

    def check_existing_places(self, latitude, longitude):
        with self.db_connection() as conn:
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
            with self.db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO user_coordinates (visitor_id, latitude, longitude, timestamp)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (visitor_id) DO NOTHING
                ''', (visitor_id, latitude, longitude, timestamp))
                conn.commit()
                
                # Debug: Verify insertion by querying the row
                cursor.execute("SELECT * FROM user_coordinates WHERE visitor_id = %s", (visitor_id,))
                inserted_entry = cursor.fetchone()
                logging.debug(f"Inserted entry into user_coordinates: {inserted_entry}")
                return inserted_entry is not None
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
            return (response.status_code, google_places)
        return (response.status_code, [])

    def insert_place_data(self, latitude, longitude, place):
        with self.db_connection() as conn:
            cursor = conn.cursor()
            photo_data = place['photos'][0] if 'photos' in place and place['photos'] else None
            data_tuple = (
                latitude,
                longitude,
                place.get("place_id"),
                place.get("name"),
                place.get("business_status"),
                place.get("rating"),
                place.get("user_ratings_total"),
                place.get("vicinity"),
                json.dumps(place.get("types", [])),
                place.get("price_level"),
                place.get("icon"),
                place.get("icon_background_color"),
                place.get("icon_mask_base_uri"),
                photo_data["photo_reference"] if photo_data else None,
                photo_data["height"] if photo_data else None,
                photo_data["width"] if photo_data else None,
                place.get("opening_hours", {}).get("open_now", None)
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
        try:
            with self.db_connection() as conn:
                cursor = conn.cursor()
                query = '''
                    SELECT 
                        name, rating, user_ratings_total, price_level, open_now, 
                        (ABS(latitude - %s) + ABS(longitude - %s)) AS proximity
                    FROM google_nearby_places
                    WHERE latitude = %s AND longitude = %s
                    ORDER BY rating DESC, proximity ASC
                    LIMIT 10;
                '''
                cursor.execute(query, (latitude, longitude, latitude, longitude))
                results = cursor.fetchall()
                
                # Debug: Print the retrieved places
                logging.debug(f"Retrieved ranked places from google_nearby_places: {results}")
                
                self.places = [
                    {"name": row["name"], "rating": row["rating"], "user_ratings_total": row["user_ratings_total"], "price_level": row["price_level"], "open_now": row["open_now"]}
                    for row in results
                ]
                return self.places
        except DatabaseError as e:
            logging.error(f"Database error: {e}")
            self.places = []
            return self.places
