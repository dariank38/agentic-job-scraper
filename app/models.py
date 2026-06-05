"""SQLAlchemy models for database entities."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Channel(Base):
    """Telegram channel configuration."""

    __tablename__ = "channels"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    messages = relationship("Message", back_populates="channel", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="channel", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Channel {self.username}>"


class Message(Base):
    """Raw message from Telegram channel."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, nullable=False, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    date = Column(DateTime, nullable=True)
    text = Column(Text, nullable=True)
    sender_id = Column(Integer, nullable=True)
    sender_username = Column(String, nullable=True)
    sender_first_name = Column(String, nullable=True)
    has_image = Column(Boolean, default=False)
    needs_reanalysis = Column(Boolean, default=False)  # Flag for messages that need re-analysis

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    channel = relationship("Channel", back_populates="messages")
    job = relationship("Job", back_populates="message", uselist=False)

    def __repr__(self) -> str:
        return f"<Message {self.telegram_id} from {self.channel_id}>"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "telegram_id": self.telegram_id,
            "channel_id": self.channel_id,
            "date": self.date.isoformat() if self.date else None,
            "text": self.text,
            "sender_id": self.sender_id,
            "sender_username": self.sender_username,
            "has_image": self.has_image,
        }


class Job(Base):
    """Analyzed job posting (AI-enhanced)."""

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id"), unique=True, nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)

    # AI Analysis results
    category = Column(String, nullable=True)  # job_posting, contact_info, remote_work, other
    confidence = Column(String, nullable=True)  # high, medium, low
    ai_title = Column(String, nullable=True)
    ai_company = Column(String, nullable=True)
    ai_company_link = Column(String, nullable=True)  # Company website/careers link
    ai_location = Column(String, nullable=True)
    ai_remote = Column(Boolean, nullable=True)
    ai_role_type = Column(String, nullable=True)  # frontend, backend, fullstack, devops, etc.
    ai_skills = Column(JSON, default=list)  # List of required skills
    ai_contact = Column(String, nullable=True)
    ai_contact_type = Column(String, nullable=True)  # telegram, email, linkedin, etc.
    ai_summary = Column(Text, nullable=True)

    is_reviewed = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    analyzed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    message = relationship("Message", back_populates="job")
    channel = relationship("Channel", back_populates="jobs")

    def __repr__(self) -> str:
        return f"<Job {self.id} category={self.category}>"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "message_id": self.message_id,
            "channel_id": self.channel_id,
            "category": self.category,
            "confidence": self.confidence,
            "title": self.ai_title,
            "company": self.ai_company,
            "company_link": self.ai_company_link,
            "location": self.ai_location,
            "remote": self.ai_remote,
            "role_type": self.ai_role_type,
            "skills": self.ai_skills or [],
            "contact": self.ai_contact,
            "contact_type": self.ai_contact_type,
            "summary": self.ai_summary,
            "is_reviewed": self.is_reviewed,
            "is_approved": self.is_approved,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
            "message": self.message.to_dict() if self.message else None,
        }


class AnalysisRun(Base):
    """Track analysis/search runs."""

    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True)
    run_type = Column(String, nullable=False)  # single_channel, all_channels
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=True)
    status = Column(String, default="running")  # running, completed, failed
    messages_fetched = Column(Integer, default=0)
    messages_analyzed = Column(Integer, default=0)
    jobs_found = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<AnalysisRun {self.id} {self.status}>"
