# main/app.py
from flask import Flask, request, render_template, jsonify, Response, abort
import os
from dotenv import load_dotenv
from .app_service import AppService
from prometheus_client import Counter, Histogram, generate_latest
import logging
import sqlite3
import time

# Load environment variables
load_dotenv()
db_path = os.path.join(os.path.dirname(__file__), '../database/database.db')
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

app = Flask(__name__, 
            template_folder='../frontend/templates', 
            static_folder='../frontend/static')

# Initialize AppService with the database path and Google API key
app_service_instance = AppService(db_path=db_path, google_api_key=GOOGLE_API_KEY)

# Prometheus metrics
request_counter = Counter('request_count', 'Total number of requests')
response_counter = Counter('response_count', 'Total number of responses')
coordinates_saved_counter = Counter('coordinates_saved_total', 'Total number of coordinates saved')
api_call_counter = Counter('google_api_calls_total', 'Total number of Google API calls')
response_time_histogram = Histogram('response_time_seconds', 'Response time for endpoints', ['endpoint'])
errors_counter = Counter('errors_total', 'Total number of errors')


@app.route('/get-google-maps-key')
def get_google_maps_key():
    print("Google Maps Key endpoint accessed")
    if not GOOGLE_API_KEY:
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


# Endpoint for Prometheus metrics
@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype='text/plain')


@app.route('/')
def index():
    logging.debug("Rendering index.html for user.")
    return render_template('index.html')


@app.route('/health', methods=['GET'])
def health_check():
    db_connected = app_service_instance.check_database_connection()
    api_key_present = bool(app_service_instance.google_api_key)
    
    # Fetch places and get the count
    places = app_service_instance.call_google_places_api(latitude=40.7128, longitude=-74.0060)
    nearby_places_count = len(places)

    if db_connected and nearby_places_count > 0:
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "api_key_present": api_key_present,
            "upload_check": "successful",
            "nearby_places_count": nearby_places_count
        }), 200
    else:
        error_message = "Database error" if not db_connected else "Upload check failed"
        return jsonify({
            "status": "unhealthy",
            "database": "disconnected" if not db_connected else "connected",
            "api_key_present": api_key_present,
            "error": error_message
        }), 500


@app.route('/save-coordinates', methods=['POST'])
def save_user_coordinates():
    start_time = time.time()
    data = request.json
    latitude = data.get('latitude')
    longitude = data.get('longitude')

    if latitude is None or longitude is None:
        errors_counter.inc()
        return jsonify({"error": "Invalid coordinates"}), 400

    # Process coordinates
    latitude = round(float(latitude), 4)
    longitude = round(float(longitude), 4)

    # Store coordinates in the database first
    visitor_id = app_service_instance.generate_entry(latitude, longitude)
    if not visitor_id:
        logging.error("Failed to save coordinates in database")
        errors_counter.inc()
        return jsonify({"error": "Failed to save coordinates"}), 500
    
    # If saving to the database was successful, proceed to send coordinates to RabbitMQ
    app_service_instance.send_coordinates(latitude, longitude)
    logging.debug(f"Coordinates saved and sent to RabbitMQ: {latitude}, {longitude}")
    
    coordinates_saved_counter.inc()  # Increment coordinates saved counter
    response_time_histogram.labels(endpoint='/save-coordinates').observe(time.time() - start_time)  # Track response time
    
    return jsonify({"status": "Coordinates saved in database and sent to RabbitMQ"}), 200


@app.route('/get-all-coordinates', methods=['GET'])
def get_all_coordinates():
    start_time = time.time()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT visitor_id, latitude, longitude, timestamp FROM user_coordinates")
    rows = cursor.fetchall()
    conn.close()

    # Convert rows to JSON format
    coordinates = [
        {"visitor_id": row[0], "latitude": row[1], "longitude": row[2], "timestamp": row[3]}
        for row in rows
    ]
    logging.debug(f"Retrieved coordinates: {coordinates}")
    response_time_histogram.labels(endpoint='/get-all-coordinates').observe(time.time() - start_time)
    return jsonify({"coordinates": coordinates})


@app.route('/get-nearby-places', methods=['POST'])
def get_nearby_places():
    start_time = time.time()
    data = request.json
    latitude = data.get('latitude')
    longitude = data.get('longitude')

    if latitude is None or longitude is None:
        errors_counter.inc()
        return jsonify({"error": "Invalid coordinates"}), 400

    # Use the AppService instance to get places
    places = app_service_instance.call_google_places_api(latitude, longitude)
    if not places:
        return jsonify({"error": "No places found"}), 404

    api_call_counter.inc()  # Increment Google API call counter
    response_time_histogram.labels(endpoint='/get-nearby-places').observe(time.time() - start_time)
    
    return jsonify({"places": places})


@app.route('/get-ranked-places', methods=['POST'])
def get_ranked_places():
    start_time = time.time()
    data = request.json
    latitude = data.get('latitude')
    longitude = data.get('longitude')

    if latitude is None or longitude is None:
        errors_counter.inc()
        return jsonify({"error": "Invalid coordinates"}), 400

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT name, vicinity, rating FROM ranked_nearby_places
        WHERE latitude = ? AND longitude = ?
        ORDER BY rating DESC
    ''', (latitude, longitude))
    rows = cursor.fetchall()
    conn.close()

    ranked_places = [
        {"name": row[0], "vicinity": row[1], "rating": row[2]}
        for row in rows
    ]
    response_time_histogram.labels(endpoint='/get-ranked-places').observe(time.time() - start_time)
    return jsonify({"ranked_places": ranked_places})


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logging.debug("Starting Flask application.")
    port = int(os.getenv("PORT", 5000))  # Default to 5000 if PORT is not set
    app.run(host="0.0.0.0", port=port)
