import os
from main.app import app as flask_app
from main.app_service import AppService
import pytest


@pytest.fixture
def app():
    # Configure the app for testing
    flask_app.config["TESTING"] = True
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"  # Use an in-memory database for tests
    return flask_app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def app_service():
    # Set up AppService with an in-memory database
    return AppService(db_path=":memory:", google_api_key="test_key")

def test_save_coordinates(client, app_service):
    # Mock request data
    data = {
        "latitude": 40.7128,
        "longitude": -74.0060
    }

    # Send a POST request to /save-coordinates endpoint
    response = client.post("/save-coordinates", json=data)
    assert response.status_code == 200
    json_data = response.get_json()
    assert "ranked_places" in json_data

def test_api_key(client, app_service):
    # Test the /api-key endpoint to ensure it returns the API key
    response = client.get("/api-key")
    assert response.status_code == 200
    json_data = response.get_json()
    assert "apiKey" in json_data
    assert json_data["apiKey"] == app_service.google_api_key

def test_check_existing_places(app_service):
    # Insert a mock record to simulate an existing place
    app_service.generate_entry(40.7128, -74.0060)
    
    # Check if the mock coordinates exist
    exists = app_service.check_existing_places(40.7128, -74.0060)
    assert exists
