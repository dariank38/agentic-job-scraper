"""SQLAlchemy models for database entities."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, BigInteger, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Operation(Base):
    """Track ongoing operations (fetch, analyze) for state management."""

    __tablename__ = "operations"

    id = Column(Integer, primary_key=True)
    operation_type = Column(String, nullable=False)  # 'fetch', 'analyze', 'bulk-analyze', 'bulk-fetch-analyze'
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=True)
    channel_username = Column(String, nullable=True)
    bulk_operation_id = Column(String, nullable=True)  # Links channels to a bulk operation (e.g., 'analyze-all-abc123')
    status = Column(String, default="running")  # 'running', 'completed', 'stopped', 'error'
    current = Column(Integer, default=0)  # Current progress (batch number)
    total = Column(Integer, default=0)  # Total progress (total batches)
    total_messages = Column(Integer, default=0)  # Total messages to process
    analyzed = Column(Integer, default=0)  # Number of messages analyzed
    jobs_found = Column(Integer, default=0)
    developers_found = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    channel = relationship("Channel")

    def __repr__(self) -> str:
        return f"<Operation {self.operation_type} for {self.channel_username}>"


class Channel(Base):
    """Telegram channel configuration."""

    __tablename__ = "channels"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    telegram_account_id = Column(Integer, ForeignKey("telegram_accounts.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    is_listened = Column(Boolean, default=False)  # Whether channel is monitored by real-time listener
    last_fetch_new_count = Column(Integer, default=0)  # Number of new messages from last fetch
    last_fetch_at = Column(DateTime, nullable=True)  # Timestamp of last fetch
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    messages = relationship("Message", back_populates="channel", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="channel", cascade="all, delete-orphan")
    developers = relationship("Developer", back_populates="channel", cascade="all, delete-orphan")
    telegram_account = relationship("TelegramAccount")

    def __repr__(self) -> str:
        return f"<Channel {self.username}>"


class Message(Base):
    """Raw message from Telegram channel or website."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, nullable=True, index=True)  # Null for website sources
    website_post_id = Column(String, nullable=True, index=True)  # For website sources
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=True)  # Null for website sources
    website_source_id = Column(Integer, ForeignKey("website_sources.id"), nullable=True)  # For website sources
    source_type = Column(String, default="telegram")  # 'telegram' or 'website'
    date = Column(DateTime, nullable=True)
    text = Column(Text, nullable=True)
    sender_id = Column(BigInteger, nullable=True)
    sender_username = Column(String, nullable=True)
    sender_first_name = Column(String, nullable=True)
    has_image = Column(Boolean, default=False)
    needs_reanalysis = Column(Boolean, default=False)  # Flag for messages that need re-analysis
    analysis_status = Column(String, default="pending")  # pending, analyzed, skipped, failed
    skip_reason = Column(String, nullable=True)  # Reason why message was skipped

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    channel = relationship("Channel", back_populates="messages")
    website_source = relationship("WebsiteSource", back_populates="messages")
    job = relationship("Job", back_populates="message", uselist=False, cascade="all, delete-orphan")
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
            "skip_reason": self.skip_reason,
            "source_type": self.source_type,
            "channel": {
                "id": self.channel.id,
                "username": self.channel.username,
                "name": self.channel.name,
            } if self.channel else None,
            "website_source": {
                "id": self.website_source.id,
                "name": self.website_source.name,
                "url": self.website_source.url,
            } if self.website_source else None,
            "job": {
                "id": self.job.id,
                "title": self.job.title,
                "company": self.job.company,
            } if self.job else None,
            "developer": {
                "id": self.developer.id,
                "name": self.developer.name,
            } if self.developer else None,
        }


class Job(Base):
    """Job posting (AI-enhanced)."""

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id"), unique=True, nullable=True)  # Nullable for website sources
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=True)  # Null for website sources
    website_source_id = Column(Integer, ForeignKey("website_sources.id"), nullable=True)  # For website sources
    channel_name = Column(String, nullable=True)  # Store channel/source name for reference
    source_type = Column(String, nullable=True)  # 'telegram' or 'website'

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
    skills = Column(JSON, nullable=True)
    contact = Column(String, nullable=True)
    contact_type = Column(String, nullable=True)
    summary = Column(Text, nullable=True)

    is_applied = Column(Boolean, default=False)
    applied_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    analyzed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    message = relationship("Message", back_populates="job")
    channel = relationship("Channel", back_populates="jobs")
    website_source = relationship("WebsiteSource", back_populates="jobs")

    def __repr__(self) -> str:
        return f"<Job {self.id} title={self.title}>"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "message_id": self.message_id,
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "source_type": self.source_type,
            "website_source_id": self.website_source_id,
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
            "is_applied": self.is_applied,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "notes": self.notes,
            "message": self.message.to_dict() if self.message else None,
        }


class Developer(Base):
    """Developer personal info (AI-enhanced)."""

    __tablename__ = "developers"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id"), unique=True, nullable=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=True)  # Null for website sources
    website_source_id = Column(Integer, ForeignKey("website_sources.id"), nullable=True)  # For website sources

    # AI Analysis results
    confidence = Column(String, nullable=True)  # high, medium, low
    translated_text = Column(Text, nullable=True)  # English translation of original message

    # Personal info fields
    name = Column(String, nullable=True)
    skills = Column(JSON, nullable=True)
    experience = Column(Text, nullable=True)
    portfolio = Column(String, nullable=True)
    github = Column(String, nullable=True)
    linkedin = Column(String, nullable=True)
    contact = Column(String, nullable=True)
    contact_type = Column(String, nullable=True)
    looking_for_work = Column(Boolean, nullable=True)
    summary = Column(Text, nullable=True)

    is_contacted = Column(Boolean, default=False)
    contacted_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    analyzed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    message = relationship("Message", back_populates="developer")
    channel = relationship("Channel", back_populates="developers")
    website_source = relationship("WebsiteSource", back_populates="developers")

    def __repr__(self) -> str:
        return f"<Developer {self.id} name={self.name}>"

    @staticmethod
    def _extract_str(value) -> Optional[str]:
        """Normalize a field that may be a string, dict, or list to a plain string."""
        if value is None:
            return None
        if isinstance(value, str):
            # Try to parse as JSON in case it was stored as a raw Python repr
            try:
                import json
                parsed = json.loads(value)
                if isinstance(parsed, dict) and "value" in parsed:
                    return str(parsed["value"])
                if isinstance(parsed, list) and parsed:
                    first = parsed[0]
                    if isinstance(first, dict) and "value" in first:
                        return str(first["value"])
                    return str(first)
            except Exception:
                pass
            # Handle Python repr format: {'type': '...', 'value': '...'}
            import re
            m = re.search(r"'value'\s*:\s*'([^']+)'", value)
            if m:
                return m.group(1)
            return value
        if isinstance(value, dict):
            return str(value.get("value") or "")
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and item.get("value"):
                    return str(item["value"])
                if item:
                    return str(item)
        return str(value)

    @staticmethod
    def _normalize_portfolio(value):
        """Normalize portfolio field — returns list of {type, value} dicts or None."""
        if value is None:
            return None
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            return [value]
        if isinstance(value, str):
            import json
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
                if isinstance(parsed, dict):
                    return [parsed]
            except Exception:
                pass
            # Handle Python repr list format
            import re
            entries = re.findall(r"\{[^}]+\}", value)
            result = []
            for entry in entries:
                t_match = re.search(r"'type'\s*:\s*'([^']+)'", entry)
                v_match = re.search(r"'value'\s*:\s*'([^']+)'", entry)
                if v_match:
                    result.append({"type": t_match.group(1) if t_match else "Portfolio", "value": v_match.group(1)})
            if result:
                return result
            return value  # Fallback: plain string URL
        return value

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
            "portfolio": self._normalize_portfolio(self.portfolio),
            "github": self._extract_str(self.github),
            "linkedin": self._extract_str(self.linkedin),
            "contact": self._extract_str(self.contact),
            "contact_type": self.contact_type,
            "looking_for_work": self.looking_for_work,
            "summary": self.summary,
            "is_contacted": self.is_contacted,
            "contacted_at": self.contacted_at.isoformat() if self.contacted_at else None,
            "notes": self.notes,
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


class WebsiteSource(Base):
    """Website source configuration for job crawling."""

    __tablename__ = "website_sources"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)  # e.g., "V2EX", "电鸭社区"
    url = Column(String, nullable=False, unique=True)  # Base URL
    site_type = Column(String, nullable=False)  # 'v2ex', 'eleduck', etc.
    is_active = Column(Boolean, default=True)
    last_fetch_new_count = Column(Integer, default=0)  # Number of new posts from last fetch
    last_fetch_at = Column(DateTime, nullable=True)  # Timestamp of last fetch
    extraction_prompt = Column(Text, nullable=True)  # Custom prompt for this site
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    messages = relationship("Message", back_populates="website_source", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="website_source", cascade="all, delete-orphan")
    developers = relationship("Developer", back_populates="website_source", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<WebsiteSource {self.name} ({self.site_type})>"


class TelegramAccount(Base):
    """Telegram account for multi-account support."""

    __tablename__ = "telegram_accounts"

    id = Column(Integer, primary_key=True)
    api_id = Column(Integer, nullable=False)
    api_hash = Column(String, nullable=False)
    phone_number = Column(String, nullable=False, unique=True)
    username = Column(String, nullable=True)  # Telegram username (e.g., @username)
    session_name = Column(String, nullable=False, unique=True)  # e.g., session_+1234567890
    is_active = Column(Boolean, default=True)
    is_authenticated = Column(Boolean, default=False)
    phone_code_hash = Column(String, nullable=True)  # Temporary hash for authentication flow
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<TelegramAccount {self.id} {self.username or self.phone_number}>"
