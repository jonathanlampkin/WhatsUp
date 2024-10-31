# tests/test_database.py

import pytest
from app.database import SessionLocal, init_db
from app.models import UserCoordinates, GoogleNearbyPlaces

@pytest.fixture(scope="module")
def test_db():
    init_db()
    db = SessionLocal()
    yield db
    db.close()

def test_database_connection(test_db):
    # Simple query to test connection
    result = test_db.execute("SELECT 1").scalar()
    assert result == 1

def test_insert_user_coordinates(test_db):
    # Insert a test entry
    new_coord = UserCoordinates(visitor_id="test_user", latitude=37.7749, longitude=-122.4194, timestamp="2024-01-01T00:00:00Z")
    test_db.add(new_coord)
    test_db.commit()

    # Verify the entry exists
    result = test_db.query(UserCoordinates).filter_by(visitor_id="test_user").first()
    assert result is not None
    assert result.latitude == 37.7749
