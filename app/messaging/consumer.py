import json
import logging
from app.services import AppService
from aio_pika import connect_robust, IncomingMessage
from fastapi import WebSocket
import os
import asyncio

async def process_message(message: IncomingMessage, app_service: AppService, websocket: WebSocket):
    async with message.process():
        coords = json.loads(message.body.decode())
        latitude = coords['latitude']
        longitude = coords['longitude']
        logging.info(f"Processing coordinates {latitude}, {longitude}")

        # Fetch places from Google Places API
        places = await app_service.fetch_from_google_places_api(latitude, longitude)
        if places:
            await app_service.store_places_in_db_and_cache(latitude, longitude, places)
            ranked_places = await app_service.rank_nearby_places(latitude, longitude)
            logging.info(f"Ranked places found: {ranked_places}")
        else:
            ranked_places = []
            logging.warning("No places found from Google Places API.")

        # Send the ranked places to the WebSocket client
        await websocket.send_json({'latitude': latitude, 'longitude': longitude, 'places': ranked_places})


async def start_rabbitmq_consumer(websocket: WebSocket, app_service: AppService):
    while True:
        try:
            connection = await connect_robust(os.getenv("RABBITMQ_URL"), heartbeat=30)  # Set heartbeat to 30 seconds
            channel = await connection.channel()
            queue = await channel.declare_queue("coordinates_queue", durable=True)

            async for message in queue:
                await process_message(message, app_service, websocket)

        except Exception as e:
            logging.error(f"RabbitMQ connection error: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)  # Wait before reconnecting
        finally:
            # Ensure that the connection is closed properly
            if connection and not connection.is_closed:
                await connection.close()
