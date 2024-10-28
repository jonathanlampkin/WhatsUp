# main/app.py
from flask import Flask, request, render_template, jsonify
import os
from dotenv import load_dotenv
from app_service import AppService
import logging

load_dotenv()
db_path = os.path.join(os.path.dirname(__file__), '../database/database.db')
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

app = Flask(__name__, 
            template_folder='../frontend/templates', 
            static_folder='../frontend/static')

# Create a single instance of AppService without passing coordinates
app_service_instance = AppService(db_path=db_path, google_api_key=GOOGLE_API_KEY)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api-key', methods=['GET'])
def api_key():
    return app_service_instance.get_google_api_key()

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


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint that verifies functionality by calling the main app service."""
    try:
        # Check database connection
        conn = sqlite3.connect(app_service.db_path)
        conn.execute("SELECT 1")
        conn.close()

        # Perform a test call to the /save-coordinates endpoint
        test_coords = {"latitude": 40.7128, "longitude": -74.0060}
        with app.test_client() as client:
            response = client.post("/save-coordinates", json=test_coords)
            response_json = response.get_json()

            # Check the response structure
            if response.status_code == 200 and "ranked_places" in response_json:
                return jsonify({
                    "status": "healthy",
                    "database": "connected",
                    "api_key_present": bool(app_service_instance.google_api_key),
                    "upload_check": "successful",
                    "nearby_places_count": len(response_json["ranked_places"])
                }), 200
            else:
                return jsonify({
                    "status": "unhealthy",
                    "error": "Failed to retrieve expected nearby places response."
                }), 500

    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(debug=True)
