import os
import pika

# Setup RabbitMQ connection using the environment variable
rabbitmq_url = os.getenv("RABBITMQ_URL")
connection_params = pika.URLParameters(rabbitmq_url)
connection = pika.BlockingConnection(connection_params)
channel = connection.channel()

def send_message(queue_name, message):
    # Declare the queue (idempotent declaration)
    channel.queue_declare(queue=queue_name)

    # Publish message
    channel.basic_publish(exchange='', routing_key=queue_name, body=message)
    print(f" [x] Sent '{message}'")
