import os
import pika
import json
import logging
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()
RABBITMQ_URL = os.getenv("RABBITMQ_URL")

# Set up logging
logging.basicConfig(level=logging.INFO)

class RabbitMQProducer:
    def __init__(self, rabbitmq_url):
        self.connection_params = pika.URLParameters(rabbitmq_url)
        self.connection = None
        self.channel = None
        self.connect_to_rabbitmq()

    def connect_to_rabbitmq(self, max_retries=5, delay=2):
        for attempt in range(max_retries):
            try:
                self.connection = pika.BlockingConnection(self.connection_params)
                self.channel = self.connection.channel()
                # Declare queue as durable to ensure consistency
                self.channel.queue_declare(queue="coordinates_queue", durable=True)
                logging.info("Connected to RabbitMQ.")
                return
            except pika.exceptions.AMQPConnectionError as e:
                logging.error(f"RabbitMQ connection attempt {attempt + 1} failed: {e}")
                time.sleep(delay)
                if self.connection and self.connection.is_open:
                    self.connection.close()
        raise RuntimeError("Could not establish RabbitMQ connection after multiple attempts")

    def send_message(self, queue_name, message):
        try:
            if not self.channel or self.channel.is_closed:
                self.connect_to_rabbitmq()
            self.channel.queue_declare(queue=queue_name, durable=True)
            message_body = json.dumps(message)
            self.channel.basic_publish(exchange='', routing_key=queue_name, body=message_body)
            logging.info(f"Sent '{message_body}' to {queue_name}")
        except Exception as e:
            logging.error(f"Failed to send message to RabbitMQ: {e}")
            self.connect_to_rabbitmq()

    def close(self):
        if self.connection and self.connection.is_open:
            self.connection.close()
            logging.info("RabbitMQ connection closed.")

if __name__ == "__main__":
    producer = RabbitMQProducer(RABBITMQ_URL)
    producer.close()
