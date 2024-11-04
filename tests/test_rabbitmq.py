import os
import unittest
import logging
from app.messaging.producer import RabbitMQProducer
from app.services import AppService
from dotenv import load_dotenv
import asyncio
import json
import aio_pika

load_dotenv()

class TestRabbitMQMessaging(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.rabbitmq_url = os.getenv("RABBITMQ_URL")
        if not self.rabbitmq_url:
            raise unittest.SkipTest("RABBITMQ_URL not set in environment variables.")
        
        self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
        self.channel = await self.connection.channel()
        self.queue = await self.channel.declare_queue("test_queue", durable=True)

    async def asyncTearDown(self):
        await self.queue.delete()
        await self.connection.close()

    async def test_producer_sends_message(self):
        producer = RabbitMQProducer()
        message = {"latitude": 40.7128, "longitude": -74.0060}
        
        await producer.send_message("test_queue", message)
        
        incoming_message = await self.queue.get(timeout=5)
        self.assertIsNotNone(incoming_message, "Message not received in queue.")
        self.assertEqual(json.loads(incoming_message.body.decode()), message, "Received message does not match expected content.")
        await producer.close()

if __name__ == "__main__":
    unittest.main()
