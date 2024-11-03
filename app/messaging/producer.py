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
        """Establish a connection to RabbitMQ with retry logic and handle connection closure on failure."""
        for attempt in range(max_retries):
            try:
                self.connection = pika.BlockingConnection(self.connection_params)
                self.channel = self.connection.channel()
                logging.info("Connected to RabbitMQ.")
                return
            except pika.exceptions.AMQPConnectionError as e:
                logging.error(f"RabbitMQ connection attempt {attempt + 1} failed: {e}")
                time.sleep(delay)
                if self.connection and self.connection.is_open:
                    self.connection.close()
        raise RuntimeError("Could not establish RabbitMQ connection after multiple attempts")

    def send_message(self, queue_name, message):
        """Send a message to the specified queue with retry if publishing fails."""
        try:
            if not self.channel or self.channel.is_closed:
                self.connect_to_rabbitmq()
            self.channel.queue_declare(queue=queue_name, durable=True)  # Declare queue as durable if it is persistent
            message_body = json.dumps(message)
            self.channel.basic_publish(exchange='', routing_key=queue_name, body=message_body)
            logging.info(f"Sent '{message_body}' to {queue_name}")
        except Exception as e:
            logging.error(f"Failed to send message to RabbitMQ: {e}")
            self.connect_to_rabbitmq()  # Retry connection on failure

    def close(self):
        if self.connection and self.connection.is_open:
            self.connection.close()
            logging.info("RabbitMQ connection closed.")


if __name__ == "__main__":
    producer = RabbitMQProducer(RABBITMQ_URL)
    producer.close()
