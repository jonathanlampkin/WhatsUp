import os
import requests
import json
import sqlite3
import uuid
from datetime import datetime
from flask import jsonify
from dotenv import load_dotenv
import logging
import pika  # RabbitMQ

class AppService:
    def __init__(self, db_path, google_api_key=None):
        self.db_path = db_path
        self.google_api_key = google_api_key
        self.places = []
        self.results = []
        self.coords = []
        load_dotenv()
        
    def process_coordinates(self, coords):
        """Process each coordinate: store, check, fetch, and rank nearby places."""
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

        # Publish the coordinates as a message
        message = json.dumps({"latitude": latitude, "longitude": longitude})
        channel.basic_publish(exchange='', routing_key=queue_name, body=message)
        logging.info(f"[x] Sent {message} to RabbitMQ")
        connection.close()

    def get_google_api_key(self):
        """Return the Google API key as JSON for frontend use."""
        return jsonify({"apiKey": self.google_api_key})

    def check_database_connection(self):
        """Check if the database connection is working."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("SELECT 1")  # Run a simple query to verify the connection
            conn.close()
            return True
        except sqlite3.OperationalError:
            return False

    def check_existing_places(self, latitude, longitude):
        """Check if places exist at the given coordinates in the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 1 FROM google_nearby_places 
            WHERE latitude = ? AND longitude = ?
        ''', (latitude, longitude))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def generate_entry(self, latitude, longitude):
        visitor_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_coordinates (visitor_id, latitude, longitude, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (visitor_id, latitude, longitude, timestamp))
            conn.commit()  # Ensure commit
            logging.info(f"Coordinates saved: {latitude}, {longitude}")
            conn.close()
            return True
        except sqlite3.DatabaseError as e:
            logging.error(f"Error saving coordinates: {e}")
            return False
    

    def call_google_places_api(self, latitude, longitude, radius=1500, place_type="restaurant"):
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
                self.insert_place_data(place)
            print(f"Fetched and Stored {len(google_places)} places from Google API")
            return (response.status_code, google_places)
        else:
            print(f"Error Google Places API Response: {response.status_code} - {response.text}")
            return response.status_code

    def insert_place_data(self, latitude, longitude, place):
        """Insert a single place entry into the database."""
        conn = sqlite3.connect(self.db_path)
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
            INSERT OR IGNORE INTO google_nearby_places (
                latitude, longitude, place_id, name, business_status, rating, 
                user_ratings_total, vicinity, types, price_level, icon, 
                icon_background_color, icon_mask_base_uri, photo_reference, 
                photo_height, photo_width, open_now
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', data_tuple)

        conn.commit()
        conn.close()

    def rank_nearby_places(self, latitude, longitude):
        """Select results ordered by rating and proximity."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                query = '''
                SELECT 
                    name, rating, user_ratings_total, price_level, open_now, 
                    (ABS(latitude - ?) + ABS(longitude - ?)) AS proximity
                FROM google_nearby_places
                WHERE latitude = ? AND longitude = ?
                ORDER BY rating DESC, proximity ASC
                LIMIT 10;
                '''
                cursor.execute(query, (latitude, longitude, latitude, longitude))
                results = cursor.fetchall()
                self.places = [
                    {"name": row[0], "rating": row[1], "user_ratings_total":row[2], "price_level": row[3], "open_now": row[4]}
                    for row in results
                ]
                logging.debug(f"Ranked places: {self.places}")
                return self.places
        except sqlite3.Error as e:
            logging.error(f"Database error: {e}")
            self.places = []
            return self.places