import os
import unittest
import logging
import asyncio
from aio_pika import connect_robust, Message, exceptions
from app.messaging.producer import RabbitMQProducer
from app.services import AppService
from dotenv import load_dotenv

load_dotenv()

class TestRabbitMQMessaging(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.rabbitmq_url = os.getenv("RABBITMQ_URL")
        if not self.rabbitmq_url:
            raise unittest.SkipTest("RABBITMQ_URL not set in environment variables.")
        
        self.connection = await connect_robust(self.rabbitmq_url)
        self.channel = await self.connection.channel()
        self.queue = await self.channel.declare_queue("test_queue", durable=True)

        # Initialize AppService
        self.app_service = AppService()
        await self.app_service.connect_db()

    async def asyncTearDown(self):
        await self.queue.delete()
        await self.connection.close()

    async def test_producer_sends_message(self):
        producer = RabbitMQProducer(self.rabbitmq_url)
        message = {"latitude": 40.7128, "longitude": -74.0060}
        
        await producer.send_message("test_queue", message)
        
        # Retry mechanism to ensure message is in queue
        retries = 5
        for _ in range(retries):
            incoming_message = await self.queue.get(timeout=5)
            if incoming_message:
                await incoming_message.ack()
                break
            await asyncio.sleep(1)
        
        self.assertIsNotNone(incoming_message, "Message not received in queue.")
        self.assertEqual(incoming_message.body.decode(), str(message), "Received message does not match expected content.")
        await producer.close()

    async def test_consumer_receives_message(self):
        # Additional consumer test here if needed
        pass

if __name__ == "__main__":
    unittest.main()
