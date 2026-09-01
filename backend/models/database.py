"""
Database & Storage Subsystem (backend/models/database.py)
Smart Traffic Monitoring & Prediction System (SIH26222)

Defines SQL models for camera registrations and historical traffic observations.
Supports PostgreSQL production URL with transparent SQLite fallback for minimal local dev.
"""

import os
from datetime import datetime, timezone
from typing import Generator
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Boolean,
    Text,
    Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./smart_traffic.db")

# SQLite needs connect_args for multithreading
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class CameraModel(Base):
    """Registered camera metadata."""
    __tablename__ = "cameras"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    stream_url = Column(Text, nullable=False)
    junction_name = Column(String(128), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    enabled = Column(Boolean, default=True)
    fps = Column(Float, default=5.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class TrafficObservationModel(Base):
    """Normalized historical traffic observation logs."""
    __tablename__ = "traffic_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(String(64), index=True, nullable=False)
    timestamp = Column(DateTime, index=True, default=lambda: datetime.now(timezone.utc))
    frame_id = Column(Integer, default=0)
    vehicle_count = Column(Integer, default=0)
    cars = Column(Integer, default=0)
    buses = Column(Integer, default=0)
    trucks = Column(Integer, default=0)
    bikes = Column(Integer, default=0)
    pedestrians = Column(Integer, default=0)
    density = Column(Float, default=0.0)
    queue_length = Column(Float, default=0.0)
    processing_time_ms = Column(Float, default=0.0)

    __table_args__ = (
        Index("idx_camera_timestamp", "camera_id", "timestamp"),
    )


def init_db():
    """Initializes the database schema."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency provider for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
