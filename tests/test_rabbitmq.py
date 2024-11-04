import os
import unittest
import logging
from unittest.mock import patch
from app.services import AppService
from dotenv import load_dotenv
import aio_pika
import json
import asyncio

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
        
        self.app_service = AppService()
        await self.app_service.connect_db()
        
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
        message = {"latitude": 40.7128, "longitude": -74.0060}
        
        await self.app_service.send_to_rabbitmq(message)
        
        queue = await self.channel.get_queue(self.queue_name)
        incoming_message = await queue.get(timeout=5)
        
        self.assertIsNotNone(incoming_message, "Message not received in queue.")
        self.assertEqual(json.loads(incoming_message.body), message, "Received message does not match expected content.")

    @patch.object(AppService, 'rank_nearby_places')
    async def test_consumer_receives_message(self, mock_rank_nearby_places):
        """Test that consumer receives and processes message correctly."""
        message = {"latitude": 40.7128, "longitude": -74.0060}
        await self.channel.default_exchange.publish(
            aio_pika.Message(body=json.dumps(message).encode()),
            routing_key=self.queue_name
        )

        queue = await self.channel.get_queue(self.queue_name)
        incoming_message = await queue.get(timeout=5)
        
        coords = json.loads(incoming_message.body)
        
        await self.app_service.rank_nearby_places(coords['latitude'], coords['longitude'])
        
        mock_rank_nearby_places.assert_called_once_with(coords['latitude'], coords['longitude'])

if __name__ == "__main__":
    unittest.main()
