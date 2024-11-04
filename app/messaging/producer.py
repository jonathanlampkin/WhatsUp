import json
import logging
from aio_pika import connect_robust, Message, DeliveryMode
from dotenv import load_dotenv
import os

load_dotenv()

class RabbitMQProducer:
    def __init__(self):
        self.rabbitmq_url = os.getenv("RABBITMQ_URL")
        self.connection = None
        self.channel = None

    async def connect(self):
        self.connection = await connect_robust(self.rabbitmq_url)
        self.channel = await self.connection.channel()
        await self.channel.declare_queue("coordinates_queue", durable=True)

    async def send_message(self, queue_name, message):
        if not self.channel:
            await self.connect()
        await self.channel.default_exchange.publish(
            Message(body=json.dumps(message).encode(), delivery_mode=DeliveryMode.PERSISTENT),
            routing_key=queue_name,
        )
        logging.info(f"Sent '{message}' to {queue_name}")

    async def close(self):
        if self.connection:
            await self.connection.close()
            logging.info("RabbitMQ connection closed.")
