# consumer.py

import os
import pika
import json
from services import AppService

# Setup database path and API key
db_path = os.path.join(os.path.dirname(__file__), '../database/database.db')
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
app_service = AppService(db_path=db_path, google_api_key=GOOGLE_API_KEY)

# Setup RabbitMQ connection
rabbitmq_url = os.getenv("RABBITMQ_URL")
connection_params = pika.URLParameters(rabbitmq_url)

with pika.BlockingConnection(connection_params) as connection:
    channel = connection.channel()
    queue_name = "coordinates_queue"
    
    # Declare the queue
    channel.queue_declare(queue=queue_name)

    # Define the callback function for message processing
    def callback(ch, method, properties, body):
        coords = json.loads(body)
        latitude = coords['latitude']
        longitude = coords['longitude']
        print(f" [x] Received coordinates {latitude}, {longitude}")

        # Use AppService to process the coordinates
        app_service.process_coordinates((latitude, longitude))

    # Set up consumer on the queue
    channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
    print(' [*] Waiting for coordinates. To exit press CTRL+C')
    
    # Start consuming messages
    channel.start_consuming()