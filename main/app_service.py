import os
import requests
import json
import sqlite3
import uuid
from datetime import datetime
from flask import jsonify
from dotenv import load_dotenv
import logging

import os
import pika  # RabbitMQ
import sqlite3
import uuid
from datetime import datetime
from dotenv import load_dotenv
import json
import logging
import requests

class AppService:
    def __init__(self, db_path, google_api_key=None):
        self.db_path = db_path
        self.google_api_key = google_api_key
        self.places = []
        self.results = []
        self.coords = []
        load_dotenv()

    def process_coordinates(self, coords):
        """Process each coordinate and fetch, store, and rank places."""
        self.coords.append(coords)

        while self.coords:
            latitude, longitude = self.coords.pop(0)
            if self.check_existing_places(latitude, longitude):
                self.rank_nearby_places(latitude, longitude)
            else:
                # Load Google API key from .env only if required
                self.generate_entry(latitude, longitude)
                self.call_google_places_api(latitude, longitude)
                for place in self.places:
                    self.insert_place_data(latitude, longitude, place)
                self.rank_nearby_places(latitude, longitude)

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
        print(f" [x] Sent {message} to RabbitMQ")
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
        """Create an entry dictionary with rounded coordinates and a timestamp."""
        visitor_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_coordinates (visitor_id, latitude, longitude, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (visitor_id, latitude, longitude, timestamp))
            conn.commit()
            conn.close()
            return visitor_id
        except sqlite3.DatabaseError as e:
            print(f"Error saving coordinates: {e}")
            return None

    def call_google_places_api(self, latitude, longitude, radius=1500, place_type="restaurant"):
        """Call the Google Places API to fetch nearby places."""
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            'location': f"{latitude},{longitude}",
            'radius': radius,
            'type': place_type,
            'key': self.google_api_key  # Use the key directly from environment variable
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            self.places = response.json().get('results', [])
            print(f"Fetched {len(self.places)} places from Google API")
        else:
            print(f"Error Google Places API Response: {response.status_code} - {response.text}")
        return self.places


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
                    name, vicinity, rating, latitude, longitude, 
                    (ABS(latitude - ?) + ABS(longitude - ?)) AS proximity
                FROM google_nearby_places
                WHERE open_now = 1
                ORDER BY rating DESC, proximity ASC
                LIMIT 10;
                '''
                cursor.execute(query, (latitude, longitude))
                results = cursor.fetchall()
                self.results = [
                    {"name": row[0], "vicinity": row[1], "rating": row[2], "latitude": row[3], "longitude": row[4]}
                    for row in results
                ]
                return self.results
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            self.results = []
            return self.results
            
# easter egg