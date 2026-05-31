import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nickname = Column(String(50), nullable=True)
    preferences = Column(JSON, default={})
    sleep_time = Column(String(10), nullable=True)  # e.g., "23:00"
    wake_time = Column(String(10), nullable=True)  # e.g., "07:00"
    created_at = Column(DateTime, default=datetime.utcnow)

    sessions = relationship("HealingSession", back_populates="user")


class HealingSession(Base):
    __tablename__ = "healing_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    time_period = Column(String(20), nullable=False)  # e.g., "afternoon_focus"
    scene = Column(String(20), nullable=True)  # e.g., "sleep", "relax"
    duration_minutes = Column(Integer, nullable=False)
    parameters = Column(JSON, default={})  # BPM, key, instrument, ambient, etc.
    healing_score = Column(Integer, nullable=True)
    hrv_improve_percent = Column(Integer, nullable=True)  # HRV improvement percentage
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="sessions")
    hrv_records = relationship("HRVRecord", back_populates="session")


class HRVRecord(Base):
    __tablename__ = "hrv_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("healing_sessions.id"), nullable=True)
    rmssd = Column(Integer, nullable=False)  # RMSSD in ms
    heart_rate = Column(Integer, nullable=True)  # BPM
    hrv_status = Column(String(20), nullable=True)  # relaxed, normal, stressed, anxious
    bpm_adjusted = Column(Integer, nullable=True)  # Music BPM at this point
    elapsed_seconds = Column(Integer, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("HealingSession", back_populates="hrv_records")


class MusicAsset(Base):
    __tablename__ = "music_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category = Column(String(20), nullable=False)  # time_period classification
    parameters = Column(JSON, default={})
    file_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)