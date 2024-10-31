# messaging/producer.py
import os
import pika
import json

def send_message(queue_name, message):
    # Setup RabbitMQ connection using the environment variable
    rabbitmq_url = os.getenv("RABBITMQ_URL")
    connection_params = pika.URLParameters(rabbitmq_url)
    
    # Establish a connection and channel for each message sent
    with pika.BlockingConnection(connection_params) as connection:
        channel = connection.channel()
        
        # Declare the queue (idempotent declaration)
        channel.queue_declare(queue=queue_name)

        # Ensure the message is JSON-formatted
        message_body = json.dumps(message)

        # Publish the JSON-formatted message
        channel.basic_publish(exchange='', routing_key=queue_name, body=message_body)
        print(f" [x] Sent '{message_body}' to {queue_name}")
