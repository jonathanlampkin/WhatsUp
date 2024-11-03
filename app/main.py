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
    metrics.get(metric_name).inc()

def record_response_time(endpoint, start_time):
    metrics["response_time_histogram"].labels(endpoint=endpoint).observe(time.time() - start_time)

@app.route('/get-google-maps-key')
def get_google_maps_key():
    if not GOOGLE_API_KEY:
        return jsonify({"error": "Google Maps API key not found"}), 404
    return jsonify({"key": GOOGLE_API_KEY})

@app.before_request
def log_request():
    increment_metric("request_counter")

@app.after_request
def log_response(response):
    increment_metric("response_counter")
    return response

@app.route('/metrics')
def metrics_endpoint():
    return Response(generate_latest(), mimetype='text/plain')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health', methods=['GET'])
def health_check():
    db_connected = app_service_instance.check_database_connection()
    api_key_present = bool(app_service_instance.google_api_key)
    status = "healthy" if db_connected else "unhealthy"
    return jsonify({
        "status": status,
        "database": "connected" if db_connected else "disconnected",
        "api_key_present": api_key_present,
    }), 200 if status == "healthy" else 500

@app.route('/process-coordinates', methods=['POST'])
def process_coordinates():
    start_time = time.time()
    data = request.json
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    if latitude is None or longitude is None:
        increment_metric("errors_counter")
        return jsonify({"error": "Invalid coordinates"}), 400
    latitude, longitude = round(latitude, 4), round(longitude, 4)
    app_service_instance.send_coordinates_if_not_cached(latitude, longitude)
    increment_metric("coordinates_saved_counter")
    places = app_service_instance.process_coordinates(latitude, longitude)
    record_response_time('/process-coordinates', start_time)
    return jsonify({"places": places}), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
