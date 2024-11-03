import os
import requests
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
from dotenv import load_dotenv
import logging
import pika
from cachetools import TTLCache
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import time

load_dotenv()
logging.basicConfig(level=logging.DEBUG)

import os
import requests
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
from dotenv import load_dotenv
import logging
import pika
from cachetools import TTLCache
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import time

load_dotenv()
logging.basicConfig(level=logging.DEBUG)

class AppService:
    def __init__(self, google_api_key=None):
        self.google_api_key = google_api_key
        self.db_pool = pool.SimpleConnectionPool(1, 10, dsn=os.getenv("DATABASE_URL"))
        self.cache = TTLCache(maxsize=int(os.getenv("CACHE_SIZE", 100)), ttl=int(os.getenv("CACHE_TTL", 600)))
        rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
        self.rabbitmq_params = pika.URLParameters(rabbitmq_url)
        self.rabbitmq_connection = None
        self.rabbitmq_channel = None
        self.connect_to_rabbitmq()

    def connect_to_rabbitmq(self, max_retries=5, delay=2):
        for attempt in range(max_retries):
            try:
                if self.rabbitmq_connection is None or self.rabbitmq_connection.is_closed:
                    self.rabbitmq_connection = pika.BlockingConnection(self.rabbitmq_params)
                    self.rabbitmq_channel = self.rabbitmq_connection.channel()
                    self.rabbitmq_channel.queue_declare(queue="coordinates_queue", durable=True)
                    logging.info("Connected to RabbitMQ.")
                return
            except pika.exceptions.AMQPConnectionError as e:
                logging.error(f"RabbitMQ connection attempt {attempt + 1} failed: {e}")
                time.sleep(delay)
        raise RuntimeError("Could not establish RabbitMQ connection after multiple attempts")

    def send_coordinates_if_not_cached(self, latitude, longitude):
        if not self.is_coordinates_cached(latitude, longitude):
            message = json.dumps({"latitude": latitude, "longitude": longitude})
            try:
                if not self.rabbitmq_channel or self.rabbitmq_channel.is_closed:
                    self.connect_to_rabbitmq()
                self.rabbitmq_channel.basic_publish(exchange='', routing_key="coordinates_queue", body=message)
                logging.info(f"Sent {message} to RabbitMQ")
            except Exception as e:
                logging.error(f"Failed to send message to RabbitMQ: {e}")
                self.connect_to_rabbitmq()

    def is_coordinates_cached(self, latitude, longitude):
        return self.cache.get(f"{latitude}_{longitude}")

    def process_coordinates(self, latitude, longitude):
        if self.check_coordinates_in_db(latitude, longitude):
            return self.rank_nearby_places(latitude, longitude)
        else:
            places = self.fetch_from_google_places_api(latitude, longitude)
            if places:
                self.store_places_in_db_and_cache(latitude, longitude, places)
            return places

    def fetch_from_google_places_api(self, latitude, longitude, radius=5000, place_type="restaurant"):
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {'location': f"{latitude},{longitude}", 'radius': radius, 'type': place_type, 'key': self.google_api_key}
        session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
        session.mount("https://", HTTPAdapter(max_retries=retries))
        response = session.get(url, params=params)
        return response.json().get('results', []) if response.status_code == 200 else []

    def store_places_in_db_and_cache(self, latitude, longitude, places):
        for place in places:
            self.insert_place_data(latitude, longitude, place)
        self.cache[f"{latitude}_{longitude}"] = places

    def insert_place_data(self, latitude, longitude, place):
        query = '''
            INSERT INTO google_nearby_places (latitude, longitude, place_id, name, business_status, rating, 
                                              user_ratings_total, vicinity, types, price_level, icon, 
                                              icon_background_color, icon_mask_base_uri, photo_reference, 
                                              photo_height, photo_width, open_now) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (place_id) DO NOTHING
        '''
        conn = self.db_pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, (
                    latitude, longitude, place.get("place_id"), place.get("name"), place.get("business_status"),
                    place.get("rating"), place.get("user_ratings_total"), place.get("vicinity"), 
                    json.dumps(place.get("types", [])), place.get("price_level"), place.get("icon"),
                    place.get("icon_background_color"), place.get("icon_mask_base_uri"), 
                    (place['photos'][0]['photo_reference'] if 'photos' in place and place['photos'] else None), 
                    (place['photos'][0]['height'] if 'photos' in place and place['photos'] else None), 
                    (place['photos'][0]['width'] if 'photos' in place and place['photos'] else None), 
                    place.get("opening_hours", {}).get("open_now")
                ))
                conn.commit()
        finally:
            self.db_pool.putconn(conn)

# triggering github actions