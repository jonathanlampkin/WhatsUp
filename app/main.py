from flask import Flask, request, render_template, jsonify, Response
import os
from dotenv import load_dotenv
from app.services import AppService
from prometheus_client import Counter, Histogram, generate_latest
import logging
import time

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

app = Flask(__name__, template_folder='templates', static_folder='static')
app_service_instance = AppService(google_api_key=GOOGLE_API_KEY)

# Prometheus metrics
metrics = {
    "request_counter": Counter('request_count', 'Total number of requests'),
    "response_counter": Counter('response_count', 'Total number of responses'),
    "coordinates_saved_counter": Counter('coordinates_saved_total', 'Total number of coordinates saved'),
    "api_call_counter": Counter('google_api_calls_total', 'Total number of Google API calls'),
    "response_time_histogram": Histogram('response_time_seconds', 'Response time for endpoints', ['endpoint']),
    "errors_counter": Counter('errors_total', 'Total number of errors')
}

# Set up logging
logging.basicConfig(level=logging.INFO)
logging.info("Starting Flask application.")

def increment_metric(metric_name):
    """Helper function to increment a given Prometheus metric."""
    metrics.get(metric_name).inc()

def record_response_time(endpoint, start_time):
    """Helper function to record response time."""
    metrics["response_time_histogram"].labels(endpoint=endpoint).observe(time.time() - start_time)

@app.route('/get-google-maps-key')
def get_google_maps_key():
    logging.info("Fetching Google Maps API key.")
    if not GOOGLE_API_KEY:
        logging.error("Google Maps API key not found.")
        return jsonify({"error": "Google Maps API key not found"}), 404
    return jsonify({"key": GOOGLE_API_KEY})

@app.before_request
def log_request():
    logging.info(f"Received request: {request.method} {request.path}")
    increment_metric("request_counter")

@app.after_request
def log_response(response):
    increment_metric("response_counter")
    return response

@app.route('/metrics')
def metrics_endpoint():
    """Expose Prometheus metrics without authentication."""
    logging.info("Serving /metrics data.")
    return Response(generate_latest(), mimetype='text/plain')

@app.route('/')
def index():
    logging.info("Rendering index.html for user.")
    return render_template('index.html')

@app.route('/health', methods=['GET'])
def health_check():
    logging.info("Performing health check.")
    db_connected = app_service_instance.check_database_connection()
    api_key_present = bool(app_service_instance.google_api_key)
    
    # Test call to Google API for connection health
    places = app_service_instance.call_google_places_api(latitude=40.7128, longitude=-74.0060)
    status = "healthy" if db_connected and len(places) > 0 else "unhealthy"
    
    return jsonify({
        "status": status,
        "database": "connected" if db_connected else "disconnected",
        "api_key_present": api_key_present,
        "nearby_places_count": len(places)
    }), 200 if status == "healthy" else 500

@app.route('/process-coordinates', methods=['POST'])
def process_coordinates():
    logging.info("Processing coordinates.")
    start_time = time.time()
    data = request.json
    logging.info(f"Received request data: {data}")

    latitude = data.get('latitude')
    longitude = data.get('longitude')

    if latitude is None or longitude is None:
        logging.error("Invalid coordinates received.")
        increment_metric("errors_counter")
        return jsonify({"error": "Invalid coordinates"}), 400
    
    latitude, longitude = round(latitude, 4), round(longitude, 4)
    app_service_instance.send_coordinates_if_not_cached(latitude, longitude)
    increment_metric("coordinates_saved_counter")
    
    places = app_service_instance.process_coordinates((latitude, longitude))

    if not places:
        increment_metric("errors_counter")
        return jsonify({"error": "No places found"}), 404

    record_response_time('/process-coordinates', start_time)
    logging.info(f"Returning places data: {places}")
    return jsonify({"places": places}), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
