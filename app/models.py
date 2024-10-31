# app/models.py

from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Set up the SQLAlchemy engine and session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class UserCoordinates(Base):
    __tablename__ = 'user_coordinates'
    id = Column(Integer, primary_key=True, autoincrement=True)
    visitor_id = Column(String, unique=True, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    timestamp = Column(Text, nullable=False)

class GoogleNearbyPlaces(Base):
    __tablename__ = 'google_nearby_places'
    id = Column(Integer, primary_key=True, autoincrement=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    place_id = Column(String, unique=True, nullable=False)
    name = Column(Text)
    business_status = Column(Text)
    rating = Column(Float)
    user_ratings_total = Column(Integer)
    vicinity = Column(Text)
    types = Column(Text)
    price_level = Column(Integer)
    icon = Column(Text)
    icon_background_color = Column(Text)
    icon_mask_base_uri = Column(Text)
    photo_reference = Column(Text)
    photo_height = Column(Integer)
    photo_width = Column(Integer)
    open_now = Column(Boolean)

# Ensure tables are created in the database
Base.metadata.create_all(bind=engine)
