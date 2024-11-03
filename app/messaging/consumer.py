import os
import pika
import json
import logging
from dotenv import load_dotenv
from services import AppService
import time

load_dotenv()
RABBITMQ_URL = os.getenv("RABBITMQ_URL")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

app_service = AppService(google_api_key=GOOGLE_API_KEY)
logging.basicConfig(level=logging.INFO)

def connect_to_rabbitmq():
    connection_params = pika.URLParameters(RABBITMQ_URL)
    retries = 3
    for i in range(retries):
        try:
            return pika.BlockingConnection(connection_params)
        except pika.exceptions.AMQPConnectionError as e:
            logging.error(f"Connection attempt {i+1} failed: {e}")
            time.sleep(5)
    raise RuntimeError("Could not connect to RabbitMQ")

def process_message(ch, method, properties, body):
    try:
        coords = json.loads(body)
        latitude = coords['latitude']
        longitude = coords['longitude']
        logging.info("Received coordinates %s, %s", latitude, longitude)
        app_service.process_coordinates((latitude, longitude))
    except Exception as e:
        logging.error("Error processing message: %s", e)

def start_consumer():
    connection = connect_to_rabbitmq()
    channel = connection.channel()
    channel.queue_declare(queue="coordinates_queue")
    channel.basic_consume(queue="coordinates_queue", on_message_callback=process_message, auto_ack=True)
    logging.info("Waiting for messages.")
    channel.start_consuming()

if __name__ == "__main__":
    start_consumer()
