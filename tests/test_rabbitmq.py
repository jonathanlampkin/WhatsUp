# tests/test_rabbitmq.py
import os
import unittest
from unittest.mock import patch
from app.services import AppService
import pika
import json

class TestRabbitMQMessaging(unittest.TestCase):
    def setUp(self):
        self.rabbitmq_url = os.getenv("RABBITMQ_URL")
        self.connection_params = pika.URLParameters(self.rabbitmq_url)
        self.connection = pika.BlockingConnection(self.connection_params)
        self.channel = self.connection.channel()
        self.queue_name = "test_queue"
        self.app_service = AppService()
        self.channel.queue_declare(queue=self.queue_name)

    def tearDown(self):
        self.channel.queue_delete(queue=self.queue_name)
        self.connection.close()

    def test_producer_sends_message(self):
        message = {"latitude": 40.7128, "longitude": -74.0060}
        self.app_service.send_coordinates(40.7128, -74.0060)
        method_frame, _, body = self.channel.basic_get(self.queue_name, auto_ack=True)
        self.assertIsNotNone(method_frame, "Message not received in queue.")
        self.assertEqual(json.loads(body), message)

    @patch.object(AppService, 'process_coordinates')
    def test_consumer_receives_message(self, mock_process_coordinates):
        message = {"latitude": 40.7128, "longitude": -74.0060}
        self.channel.basic_publish(exchange='', routing_key=self.queue_name, body=json.dumps(message))

        def mock_callback(ch, method, properties, body):
            coords = json.loads(body)
            self.assertEqual(coords, message)
            mock_process_coordinates(coords)

        method_frame, _, body = self.channel.basic_get(self.queue_name, auto_ack=True)
        mock_callback(self.channel, method_frame, None, body)
        mock_process_coordinates.assert_called_once_with(message)

if __name__ == "__main__":
    unittest.main()
