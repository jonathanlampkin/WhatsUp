from fastapi import FastAPI, WebSocket, Request, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from prometheus_client import Counter, Histogram, generate_latest
from app.services import AppService
from app.messaging.consumer import start_rabbitmq_consumer
from dotenv import load_dotenv
import logging
import time
import os
from fastapi.staticfiles import StaticFiles

load_dotenv()
app = FastAPI()
app_service_instance = AppService()
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Prometheus metrics
metrics = {
    "request_counter": Counter('request_count', 'Total number of requests'),
    "response_counter": Counter('response_count', 'Total number of responses'),
    "coordinates_saved_counter": Counter('coordinates_saved_total', 'Total number of coordinates saved'),
    "api_call_counter": Counter('google_api_calls_total', 'Total number of Google API calls'),
    "response_time_histogram": Histogram('response_time_seconds', 'Response time for endpoints', ['endpoint']),
    "errors_counter": Counter('errors_total', 'Total number of errors')
}

logging.basicConfig(level=logging.INFO)

@app.on_event("startup")
async def startup_event():
    await app_service_instance.initialize()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    metrics["request_counter"].inc()
    start_time = time.time()
    response = await call_next(request)
    metrics["response_counter"].inc()
    metrics["response_time_histogram"].labels(endpoint=request.url.path).observe(time.time() - start_time)
    return response

@app.get('/metrics')
def metrics_endpoint():
    return JSONResponse(generate_latest(), media_type='text/plain')

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/get-google-maps-key")
def get_google_maps_key():
    google_maps_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_maps_api_key:
        return JSONResponse({"error": "Google Maps API key is not set."}, status_code=500)
    return {"key": google_maps_api_key}

@app.get('/health')
async def health_check():
    db_connected = await app_service_instance.check_database_connection()
    status = "healthy" if db_connected else "unhealthy"
    return JSONResponse({
        "status": status,
        "database": "connected" if db_connected else "disconnected",
    }, status_code=200 if status == "healthy" else 500)

@app.post('/process-coordinates')
async def process_coordinates(data: dict, background_tasks: BackgroundTasks):
    latitude = round(data.get('latitude', 0), 4)
    longitude = round(data.get('longitude', 0), 4)
    logging.info(f"Received coordinates for processing: ({latitude}, {longitude})")
    background_tasks.add_task(app_service_instance.send_coordinates_if_not_cached, latitude, longitude)
    metrics["coordinates_saved_counter"].inc()
    logging.debug("Coordinates saved counter incremented.")
    return {"status": "processing"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await start_rabbitmq_consumer(websocket, app_service_instance)
    await websocket.close()
