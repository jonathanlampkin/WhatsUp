# testing/test_rabbitmq.py
import os
import pika
import unittest
from dotenv import load_dotenv
from messaging.producer import send_message
from main.app_service import AppService

load_dotenv()

class TestRabbitMQMessaging(unittest.TestCase):
    def setUp(self):
        # Set up RabbitMQ connection
        rabbitmq_url = os.getenv("RABBITMQ_URL")
        connection_params = pika.URLParameters(rabbitmq_url)
        self.connection = pika.BlockingConnection(connection_params)
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
        message = '{"latitude": 40.7128, "longitude": -74.0060}'
        send_message(self.queue_name, message)
        
        # Verify message is in the queue
        method_frame, _, body = self.channel.basic_get(self.queue_name, auto_ack=True)
        self.assertIsNotNone(method_frame, "Message not received in queue.")
        self.assertEqual(body.decode(), message)

    def test_consumer_receives_message(self):
        # Publish a test message
        message = '{"latitude": 40.7128, "longitude": -74.0060}'
        self.channel.basic_publish(exchange='', routing_key=self.queue_name, body=message)
        
        # Mock the consumer’s callback to verify message processing
        def mock_callback(ch, method, properties, body):
            coords = self.app_service.process_coordinates((40.7128, -74.0060))
            self.assertEqual(coords, (40.7128, -74.0060))
        
        self.channel.basic_consume(queue=self.queue_name, on_message_callback=mock_callback, auto_ack=True)
        
        # Start consuming (this is synchronous and will block until done)
        self.channel.start_consuming()

if __name__ == "__main__":
    unittest.main()
