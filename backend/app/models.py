"""SQLAlchemy models for database entities."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, BigInteger, String, Text, Boolean, DateTime, ForeignKey, JSON
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
    developers = relationship("Developer", back_populates="channel", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Channel {self.username}>"


class Message(Base):
    """Raw message from Telegram channel."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    date = Column(DateTime, nullable=True)
    text = Column(Text, nullable=True)
    sender_id = Column(BigInteger, nullable=True)
    sender_username = Column(String, nullable=True)
    sender_first_name = Column(String, nullable=True)
    has_image = Column(Boolean, default=False)
    needs_reanalysis = Column(Boolean, default=False)  # Flag for messages that need re-analysis
    analysis_status = Column(String, default="pending")  # pending, analyzed, skipped

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    channel = relationship("Channel", back_populates="messages")
    job = relationship("Job", back_populates="message", uselist=False)
    developer = relationship("Developer", back_populates="message", uselist=False)

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
            "sender_first_name": self.sender_first_name,
            "has_image": self.has_image,
            "analysis_status": self.analysis_status,
            "channel": {
                "id": self.channel.id,
                "username": self.channel.username,
                "name": self.channel.name,
            } if self.channel else None,
        }


class Job(Base):
    """Job posting (AI-enhanced)."""

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id"), unique=True, nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)

    # AI Analysis results
    confidence = Column(String, nullable=True)  # high, medium, low
    translated_text = Column(Text, nullable=True)  # English translation of original message

    # Job posting fields
    title = Column(String, nullable=True)
    company = Column(String, nullable=True)
    company_link = Column(String, nullable=True)
    location = Column(String, nullable=True)
    is_remote = Column(Boolean, nullable=True)
    role_type = Column(String, nullable=True)
    skills = Column(JSON, default=list)
    contact = Column(String, nullable=True)
    contact_type = Column(String, nullable=True)
    summary = Column(Text, nullable=True)

    is_reviewed = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=False)
    is_applied = Column(Boolean, default=False)
    applied_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    analyzed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    message = relationship("Message", back_populates="job")
    channel = relationship("Channel", back_populates="jobs")

    def __repr__(self) -> str:
        return f"<Job {self.id} title={self.title}>"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "message_id": self.message_id,
            "channel_id": self.channel_id,
            "confidence": self.confidence,
            "translated_text": self.translated_text,
            "title": self.title,
            "company": self.company,
            "company_link": self.company_link,
            "location": self.location,
            "is_remote": self.is_remote,
            "role_type": self.role_type,
            "skills": self.skills or [],
            "contact": self.contact,
            "contact_type": self.contact_type,
            "summary": self.summary,
            "is_reviewed": self.is_reviewed,
            "is_approved": self.is_approved,
            "is_applied": self.is_applied,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
            "message": self.message.to_dict() if self.message else None,
        }


class Developer(Base):
    """Developer personal info (AI-enhanced)."""

    __tablename__ = "developers"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id"), unique=True, nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)

    # AI Analysis results
    confidence = Column(String, nullable=True)  # high, medium, low
    translated_text = Column(Text, nullable=True)  # English translation of original message

    # Personal info fields
    name = Column(String, nullable=True)
    skills = Column(JSON, default=list)
    experience = Column(Text, nullable=True)
    portfolio = Column(String, nullable=True)
    github = Column(String, nullable=True)
    linkedin = Column(String, nullable=True)
    contact = Column(String, nullable=True)
    contact_type = Column(String, nullable=True)
    looking_for_work = Column(Boolean, nullable=True)
    summary = Column(Text, nullable=True)

    is_reviewed = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=False)
    is_contacted = Column(Boolean, default=False)
    contacted_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    analyzed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    message = relationship("Message", back_populates="developer")
    channel = relationship("Channel", back_populates="developers")

    def __repr__(self) -> str:
        return f"<Developer {self.id} name={self.name}>"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "message_id": self.message_id,
            "channel_id": self.channel_id,
            "confidence": self.confidence,
            "translated_text": self.translated_text,
            "name": self.name,
            "skills": self.skills or [],
            "experience": self.experience,
            "portfolio": self.portfolio,
            "github": self.github,
            "linkedin": self.linkedin,
            "contact": self.contact,
            "contact_type": self.contact_type,
            "looking_for_work": self.looking_for_work,
            "summary": self.summary,
            "is_reviewed": self.is_reviewed,
            "is_approved": self.is_approved,
            "is_contacted": self.is_contacted,
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
