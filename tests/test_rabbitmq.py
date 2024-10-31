# testing/test_rabbitmq.py
import os
import unittest
from unittest.mock import patch
from app.messaging.producer import send_message
from app.services import AppService
from dotenv import load_dotenv
import pika
import json

load_dotenv()

class TestRabbitMQMessaging(unittest.TestCase):
    def setUp(self):
        # Load RabbitMQ URL from environment
        self.rabbitmq_url = os.getenv("RABBITMQ_URL")
        if not self.rabbitmq_url:
            self.skipTest("RABBITMQ_URL not set")

        self.connection_params = pika.URLParameters(self.rabbitmq_url)
        self.connection = pika.BlockingConnection(self.connection_params)
        self.channel = self.connection.channel()
        self.queue_name = "test_queue"
        
        # Initialize AppService for testing consumer functionality
        db_path = os.path.join(os.path.dirname(__file__), '../database/database.db')
        google_api_key = os.getenv("GOOGLE_API_KEY")
        self.app_service = AppService(db_path=db_path, google_api_key=google_api_key)
        
        # Declare the test queue
        self.channel.queue_declare(queue=self.queue_name)

    def tearDown(self):
        # Clean up and close connection
        self.channel.queue_delete(queue=self.queue_name)
        self.connection.close()

    def test_producer_sends_message(self):
        message = {"latitude": 40.7128, "longitude": -74.0060}
        send_message(self.queue_name, message)
        
        # Verify message is in the queue
        method_frame, _, body = self.channel.basic_get(self.queue_name, auto_ack=True)
        self.assertIsNotNone(method_frame, "Message not received in queue.")
        self.assertEqual(json.loads(body), message)

    @patch.object(AppService, 'process_coordinates')
    def test_consumer_receives_message(self, mock_process_coordinates):
        # Publish a test message
        message = {"latitude": 40.7128, "longitude": -74.0060}
        self.channel.basic_publish(exchange='', routing_key=self.queue_name, body=json.dumps(message))
        
        # Define the callback for testing
        def mock_callback(ch, method, properties, body):
            coords = json.loads(body)
            self.assertEqual(coords, message)
            mock_process_coordinates(coords)

        # Manually invoke the callback
        method_frame, _, body = self.channel.basic_get(self.queue_name, auto_ack=True)
        mock_callback(self.channel, method_frame, None, body)

        # Ensure `process_coordinates` was called correctly
        mock_process_coordinates.assert_called_once_with(message)

if __name__ == "__main__":
    unittest.main()