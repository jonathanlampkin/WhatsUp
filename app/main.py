from flask import Flask, request, render_template, jsonify, Response
from flask_socketio import SocketIO
import os
from dotenv import load_dotenv
from app.services import AppService
from prometheus_client import Counter, Histogram, generate_latest
import logging
import time
import json

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
RABBITMQ_URL = os.getenv("RABBITMQ_URL")

app = Flask(__name__, template_folder='templates', static_folder='static')
socketio = SocketIO(app, message_queue=RABBITMQ_URL, async_mode='eventlet')  # Enable message queuing with RabbitMQ
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
    return render_template('index.html', google_maps_api_key=GOOGLE_API_KEY)

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
    latitude = round(data.get('latitude', 0), 4)
    longitude = round(data.get('longitude', 0), 4)

    # Send coordinates to AppService for processing
    app_service_instance.send_coordinates_if_not_cached(latitude, longitude)
    increment_metric("coordinates_saved_counter")
    record_response_time('/process-coordinates', start_time)

    return jsonify({"status": "processing"}), 202

# WebSocket events for real-time updates
@socketio.on('connect')
def on_connect():
    logging.info("Client connected for WebSocket updates.")

@socketio.on('disconnect')
def on_disconnect():
    logging.info("Client disconnected.")

def send_updates(data):
    # Emit data to clients via WebSocket
    socketio.emit('update', data)

def start_rabbitmq_consumer():
    """
    Starts a background task to consume messages from RabbitMQ and
    emit real-time updates to WebSocket clients.
    """
    def consume():
        import pika
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        channel = connection.channel()
        channel.queue_declare(queue='coordinates_queue', durable=True)

        def callback(ch, method, properties, body):
            data = json.loads(body)
            send_updates(data)  # Emit data to WebSocket clients
            ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_consume(queue='coordinates_queue', on_message_callback=callback)
        channel.start_consuming()

    socketio.start_background_task(consume)

# Start the RabbitMQ consumer in a background task
start_rabbitmq_consumer()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
