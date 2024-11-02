from flask import Flask, request, render_template, jsonify, Response, abort
import os
from dotenv import load_dotenv
from app.services import AppService
from prometheus_client import Counter, Histogram, generate_latest
import logging
import time

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")  # API key for secure access
METRICS_USERNAME = os.getenv("METRICS_USERNAME")
METRICS_PASSWORD = os.getenv("METRICS_PASSWORD")

app = Flask(__name__, template_folder='templates', static_folder='static')

# Initialize AppService with the Google API key
app_service_instance = AppService(google_api_key=GOOGLE_API_KEY)

# Prometheus metrics
request_counter = Counter('request_count', 'Total number of requests')
response_counter = Counter('response_count', 'Total number of responses')
coordinates_saved_counter = Counter('coordinates_saved_total', 'Total number of coordinates saved')
api_call_counter = Counter('google_api_calls_total', 'Total number of Google API calls')
response_time_histogram = Histogram('response_time_seconds', 'Response time for endpoints', ['endpoint'])
errors_counter = Counter('errors_total', 'Total number of errors')

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logging.debug("Starting Flask application.")

@app.route('/get-google-maps-key')
def get_google_maps_key():
    logging.debug("Fetching Google Maps API key.")
    if not GOOGLE_API_KEY:
        logging.error("Google Maps API key not found.")
        abort(404)
    return jsonify({"key": GOOGLE_API_KEY})

# Track requests for Prometheus
@app.before_request
def before_request():
    logging.debug("Incrementing request counter.")
    request_counter.inc()

@app.after_request
def after_request(response):
    logging.debug("Incrementing response counter.")
    response_counter.inc()
    return response

# Authentication check for securing /metrics endpoint
def check_auth(username, password):
    return username == METRICS_USERNAME and password == METRICS_PASSWORD

def authenticate():
    return Response(
        'Could not verify your access level for that URL.\n'
        'You have to login with proper credentials', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )

# Secure /metrics endpoint
@app.route('/metrics')
def metrics():
    auth = request.authorization
    if not auth or not check_auth(auth.username, auth.password):
        logging.warning("Unauthorized access attempt to /metrics.")
        return authenticate()
    logging.debug("Serving /metrics data.")
    return Response(generate_latest(), mimetype='text/plain')

@app.route('/')
def index():
    logging.debug("Rendering index.html for user.")
    return render_template('index.html')

@app.route('/health', methods=['GET'])
def health_check():
    logging.debug("Performing health check.")
    db_connected = app_service_instance.check_database_connection()
    api_key_present = bool(app_service_instance.google_api_key)
    
    places = app_service_instance.call_google_places_api(latitude=40.7128, longitude=-74.0060)
    nearby_places_count = len(places)
    if db_connected and nearby_places_count > 0:
        logging.debug("Health check successful.")
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "api_key_present": api_key_present,
            "upload_check": "successful",
            "nearby_places_count": nearby_places_count
        }), 200
    else:
        error_message = "Database error" if not db_connected else "Upload check failed"
        logging.error(f"Health check failed: {error_message}")
        return jsonify({
            "status": "unhealthy",
            "database": "disconnected" if not db_connected else "connected",
            "api_key_present": api_key_present,
            "error": error_message
        }), 500

@app.route('/process-coordinates', methods=['POST'])
def process_coordinates():
    logging.debug("Hit /process-coordinates endpoint.")
    start_time = time.time()
    data = request.json
    logging.debug(f"Received request data: {data}")

    latitude = data.get('latitude')
    longitude = data.get('longitude')

    if latitude is None or longitude is None:
        logging.error("Invalid coordinates received.")
        errors_counter.inc()
        return jsonify({"error": "Invalid coordinates"}), 400
    
    latitude = round(latitude, 4)
    longitude = round(longitude, 4)
    logging.debug(f"Processed coordinates: latitude={latitude}, longitude={longitude}")

    app_service_instance.send_coordinates(latitude, longitude)
    coordinates_saved_counter.inc()
    logging.debug(f"Coordinates saved and sent to RabbitMQ: {latitude}, {longitude}")
    
    places = app_service_instance.process_coordinates((latitude, longitude))

    if not places:
        logging.warning("No places found for given coordinates.")
        errors_counter.inc()
        return jsonify({"error": "No places found"}), 404

    response_time_histogram.labels(endpoint='/process-coordinates').observe(time.time() - start_time)
    logging.debug(f"Returning places data: {places}")
    return jsonify({"places": places}), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
