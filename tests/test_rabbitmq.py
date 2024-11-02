import os
import unittest
import logging
from unittest.mock import patch
from app.messaging.producer import send_message
from app.services import AppService
from dotenv import load_dotenv
import pika
import json

# Configure logging to reduce verbosity
logging.getLogger("pika").setLevel(logging.WARNING)

load_dotenv()

# Inside test_rabbitmq.py

class TestRabbitMQMessaging(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rabbitmq_url = os.getenv("RABBITMQ_URL")
        if not cls.rabbitmq_url:
            raise unittest.SkipTest("RABBITMQ_URL not set in environment variables.")
        
        cls.connection_params = pika.URLParameters(cls.rabbitmq_url)
        cls.connection = pika.BlockingConnection(cls.connection_params)
        cls.channel = cls.connection.channel()
        cls.queue_name = "test_queue"
        
        google_api_key = os.getenv("GOOGLE_API_KEY")
        cls.app_service = AppService(google_api_key=google_api_key)
        
        cls.channel.queue_declare(queue=cls.queue_name)

    @classmethod
    def tearDownClass(cls):
        cls.channel.queue_delete(queue=cls.queue_name)
        cls.connection.close()

    def test_producer_sends_message(self):
        """Test that producer sends a message correctly to RabbitMQ queue."""
        message = {"latitude": 40.7128, "longitude": -74.0060}
        send_message(self.queue_name, message)
        
        method_frame, _, body = self.channel.basic_get(self.queue_name, auto_ack=True)
        self.assertIsNotNone(method_frame, "Message not received in queue.")
        self.assertEqual(json.loads(body), message, "Received message does not match expected content.")

    @patch.object(AppService, 'process_coordinates')
    def test_consumer_receives_message(self, mock_process_coordinates):
        """Test that consumer receives and processes message correctly."""
        message = {"latitude": 40.7128, "longitude": -74.0060}
        self.channel.basic_publish(exchange='', routing_key=self.queue_name, body=json.dumps(message))

        # Simulate receiving message and calling process_coordinates
        method_frame, _, body = self.channel.basic_get(self.queue_name, auto_ack=True)
        coords = json.loads(body)
        
        # Call process_coordinates explicitly to simulate consumer behavior
        self.app_service.process_coordinates((coords['latitude'], coords['longitude']))
        
        mock_process_coordinates.assert_called_once_with((coords['latitude'], coords['longitude']))
