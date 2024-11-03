from flask_socketio import SocketIO
import json
import logging
import os
from app.services import AppService
import time
import pika

# Initialize SocketIO for messaging
socketio = SocketIO(message_queue=os.getenv("RABBITMQ_URL"))
app_service = AppService(google_api_key=os.getenv("GOOGLE_API_KEY"))

def process_message(ch, method, properties, body):
    try:
        coords = json.loads(body)
        latitude = coords['latitude']
        longitude = coords['longitude']
        logging.info(f"Processing coordinates {latitude}, {longitude}")

        # Check cache, database, or fetch from API as necessary
        if app_service.is_coordinates_cached(latitude, longitude):
            ranked_places = app_service.rank_nearby_places(latitude, longitude)
        elif app_service.check_coordinates_in_db(latitude, longitude):
            ranked_places = app_service.rank_nearby_places(latitude, longitude)
        else:
            places = app_service.fetch_from_google_places_api(latitude, longitude)
            if places:
                app_service.store_places_in_db_and_cache(latitude, longitude, places)
                ranked_places = app_service.rank_nearby_places(latitude, longitude)
            else:
                ranked_places = []

        # Emit the ranked places to WebSocket clients
        socketio.emit('update', {'latitude': latitude, 'longitude': longitude, 'places': ranked_places})
    except Exception as e:
        logging.error("Error processing message: %s", e)

def start_consumer():
    connection, channel = app_service.connect_to_rabbitmq()
    channel.basic_consume(queue="coordinates_queue", on_message_callback=process_message, auto_ack=True)
    logging.info("Waiting for messages.")
    while True:
        try:
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError:
            logging.error("Lost connection to RabbitMQ. Reconnecting...")
            time.sleep(5)
            connection, channel = app_service.connect_to_rabbitmq()

if __name__ == "__main__":
    start_consumer()
