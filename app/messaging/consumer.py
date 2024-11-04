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

            # Send the ranked places to the WebSocket client
            try:
                await websocket.send_json({'latitude': latitude, 'longitude': longitude, 'places': ranked_places})
                logging.info("Sent data to WebSocket client.")
            except Exception as e:
                logging.error(f"Error sending data to WebSocket: {e}")
        else:
            logging.warning("No places found from Google Places API.")

async def start_rabbitmq_consumer(websocket: WebSocket, app_service: AppService):
    while True:
        try:
            connection = await connect_robust(os.getenv("RABBITMQ_URL"), heartbeat=30)
            channel = await connection.channel()
            queue = await channel.declare_queue("coordinates_queue", durable=True)

            async for message in queue:
                await process_message(message, app_service, websocket)

        except Exception as e:
            logging.error(f"RabbitMQ connection error: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
        finally:
            if connection and not connection.is_closed:
                await connection.close()
