import json
import logging
from app.services import AppService
from aio_pika import connect_robust, IncomingMessage
from fastapi import WebSocket
import os

async def process_message(message: IncomingMessage, app_service: AppService, websocket: WebSocket):
    async with message.process():
        coords = json.loads(message.body.decode())
        latitude = coords['latitude']
        longitude = coords['longitude']
        logging.info(f"Processing coordinates {latitude}, {longitude}")

        # Check cache, database, or fetch from API as necessary
        if app_service.is_coordinates_cached(latitude, longitude):
            ranked_places = await app_service.rank_nearby_places(latitude, longitude)
        elif await app_service.check_coordinates_in_db(latitude, longitude):
            ranked_places = await app_service.rank_nearby_places(latitude, longitude)
        else:
            places = await app_service.fetch_from_google_places_api(latitude, longitude)
            if places:
                await app_service.store_places_in_db_and_cache(latitude, longitude, places)
                ranked_places = await app_service.rank_nearby_places(latitude, longitude)
            else:
                ranked_places = []

        # Send the ranked places to the WebSocket client
        await websocket.send_json({'latitude': latitude, 'longitude': longitude, 'places': ranked_places})

async def start_rabbitmq_consumer(websocket: WebSocket, app_service: AppService):
    connection = await connect_robust(os.getenv("RABBITMQ_URL"))
    channel = await connection.channel()
    queue = await channel.declare_queue("coordinates_queue", durable=True)

    async for message in queue:
        await process_message(message, app_service, websocket)
