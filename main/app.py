# main/app.py
from flask import Flask, request, render_template, jsonify, Response
import os
from dotenv import load_dotenv
from .app_service import AppService
from prometheus_client import Counter, generate_latest
import logging

load_dotenv()
db_path = os.path.join(os.path.dirname(__file__), '../database/database.db')
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

app = Flask(__name__, 
            template_folder='../frontend/templates', 
            static_folder='../frontend/static')

# Create a single instance of AppService without passing coordinates
app_service_instance = AppService(db_path=db_path, google_api_key=GOOGLE_API_KEY)

# Define Prometheus counters
request_counter = Counter('request_count', 'Total number of requests')
response_counter = Counter('response_count', 'Total number of responses')

# Track requests and responses for Prometheus
@app.before_request
def before_request():
    request_counter.inc()

@app.after_request
def after_request(response):
    response_counter.inc()
    return response

# Endpoint for Prometheus metrics
@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype='text/plain')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api-key', methods=['GET'])
def api_key():
    return app_service_instance.get_google_api_key()

@app.route('/health', methods=['GET'])
def health_check():
    app_service = AppService(db_path=":memory:", google_api_key="test_key")
    
    # Check if the database connection is successful
    db_connected = app_service.check_database_connection()
    api_key_present = bool(app_service.google_api_key)
    
    # Fetch places and get the count
    places = app_service.call_google_places_api(latitude=40.7128, longitude=-74.0060)
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
        return jsonify({
            "status": "unhealthy",
            "database": "disconnected" if not db_connected else "connected",
            "api_key_present": api_key_present,
            "error": "Upload check failed" if nearby_places_count == 0 else "Database error"
        }), 500

@app.route('/save-coordinates', methods=['POST'])
def save_user_coordinates():
    data = request.json
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    
    if latitude is None or longitude is None:
        return jsonify({"error": "Invalid coordinates"}), 400

    # Round and validate
    latitude = round(float(latitude), 4)
    longitude = round(float(longitude), 4)
    
    if not all(isinstance(c, float) and round(c, 4) == c for c in [latitude, longitude]):
        return jsonify({"error": "Coordinates must be floats with 4 decimal places"}), 400

    app_service_instance.process_coordinates((latitude, longitude)) 
    logging.info(app_service_instance.results)
    return jsonify({"ranked_places": app_service_instance.results}), 200

if __name__ == "__main__":
    app.run(debug=True)
