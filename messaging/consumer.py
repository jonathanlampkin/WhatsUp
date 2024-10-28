# consumer.py
import os
from main.app_service import AppService

# Initialize AppService with necessary configs
db_path = os.path.join(os.path.dirname(__file__), 'database/database.db')
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
app_service = AppService(db_path=db_path, google_api_key=GOOGLE_API_KEY)

# Start consuming coordinates
app_service.receive_coordinates()
