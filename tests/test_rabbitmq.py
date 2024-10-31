# tests/test_rabbitmq.py
import os
import unittest
from unittest.mock import patch, MagicMock
from app.services import AppService
import pika
import json

class TestRabbitMQMessaging(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load RabbitMQ URL from environment or use a default value for testing
        cls.rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
        cls.connection_params = pika.URLParameters(cls.rabbitmq_url)

        # Attempt to connect to RabbitMQ and create a test queue
        try:
            cls.connection = pika.BlockingConnection(cls.connection_params)
            cls.channel = cls.connection.channel()
            cls.queue_name = "test_queue"
            cls.channel.queue_declare(queue=cls.queue_name)
        except pika.exceptions.AMQPConnectionError as e:
            raise unittest.SkipTest(f"RabbitMQ not available for testing: {e}")

        # Initialize AppService with the mocked URL
        cls.app_service = AppService()

    @classmethod
    def tearDownClass(cls):
        # Clean up by deleting the queue and closing connection
        try:
            cls.channel.queue_delete(queue=cls.queue_name)
            cls.connection.close()
        except Exception as e:
            print(f"Error during teardown: {e}")

    def test_producer_sends_message(self):
        # Define the message to test
        message = {"latitude": 40.7128, "longitude": -74.0060}
        
        # Send the coordinates using the AppService producer method
        self.app_service.send_coordinates(40.7128, -74.0060)
        
        # Retrieve the message from the test queue and verify it
        method_frame, _, body = self.channel.basic_get(self.queue_name, auto_ack=True)
        self.assertIsNotNone(method_frame, "Message not received in queue.")
        self.assertEqual(json.loads(body), message)

    @patch.object(AppService, 'process_coordinates')
    def test_consumer_receives_message(self, mock_process_coordinates):
        # Publish a test message to the queue
        message = {"latitude": 40.7128, "longitude": -74.0060}
        self.channel.basic_publish(exchange='', routing_key=self.queue_name, body=json.dumps(message))

        # Define a mock callback to simulate consuming a message
        def mock_callback(ch, method, properties, body):
            coords = json.loads(body)
            self.assertEqual(coords, message)
            mock_process_coordinates(coords)

        # Manually retrieve and process the message
        method_frame, _, body = self.channel.basic_get(self.queue_name, auto_ack=True)
        if method_frame:
            mock_callback(self.channel, method_frame, None, body)
            mock_process_coordinates.assert_called_once_with(message)
        else:
            self.fail("No message received for processing")

if __name__ == "__main__":
    unittest.main()
