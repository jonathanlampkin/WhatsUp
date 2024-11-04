import os
import unittest
import logging
from unittest.mock import patch
from app.messaging.producer import RabbitMQProducer
from app.services import AppService
from dotenv import load_dotenv
import aio_pika
import json
import asyncio

# Load environment variables
load_dotenv()

logging.getLogger("aio_pika").setLevel(logging.WARNING)

class TestRabbitMQMessaging(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.rabbitmq_url = os.getenv("RABBITMQ_URL")
        if not self.rabbitmq_url:
            self.skipTest("RABBITMQ_URL not set in environment variables.")
        
        self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
        self.channel = await self.connection.channel()
        self.queue_name = "test_queue"

        google_api_key = os.getenv("GOOGLE_API_KEY")
        self.app_service = AppService(google_api_key=google_api_key)
        
        # Declare the queue
        await self.channel.declare_queue(self.queue_name, durable=True)
        logging.info("Connected to RabbitMQ for tests.")

    async def asyncTearDown(self):
        queue = await self.channel.get_queue(self.queue_name)
        await queue.delete()
        await self.connection.close()
        logging.info("RabbitMQ connection closed after tests.")

    async def test_producer_sends_message(self):
        """Test that producer sends a message correctly to RabbitMQ queue."""
        producer = RabbitMQProducer(self.rabbitmq_url)
        await producer.connect()
        message = {"latitude": 40.7128, "longitude": -74.0060}
        
        await producer.send_message(self.queue_name, message)
        
        queue = await self.channel.get_queue(self.queue_name)
        incoming_message = await queue.get(timeout=5)
        
        self.assertIsNotNone(incoming_message, "Message not received in queue.")
        self.assertEqual(json.loads(incoming_message.body), message, "Received message does not match expected content.")
        await producer.close()

    @patch.object(AppService, 'process_coordinates')
    async def test_consumer_receives_message(self, mock_process_coordinates):
        """Test that consumer receives and processes message correctly."""
        message = {"latitude": 40.7128, "longitude": -74.0060}
        await self.channel.default_exchange.publish(
            aio_pika.Message(body=json.dumps(message).encode()),
            routing_key=self.queue_name
        )

        queue = await self.channel.get_queue(self.queue_name)
        incoming_message = await queue.get(timeout=5)
        
        coords = json.loads(incoming_message.body)
        
        await self.app_service.process_coordinates(coords['latitude'], coords['longitude'])
        
        mock_process_coordinates.assert_called_once_with(coords['latitude'], coords['longitude'])
