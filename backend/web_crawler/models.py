"""Pydantic models for structured extraction from website content."""

from typing import List, Optional

from pydantic import BaseModel, Field


class JobPosting(BaseModel):
    """Structured job posting data."""
    title: Optional[str] = Field(None, description="Job title")
    requirements: Optional[str] = Field(None, description="Job requirements or qualifications")
    deadline: Optional[str] = Field(None, description="Application deadline")
    url: Optional[str] = Field(None, description="Job posting URL")
    company: Optional[str] = Field(None, description="Company name")
    location: Optional[str] = Field(None, description="Job location")
    is_remote: Optional[bool] = Field(None, description="Whether the job is remote")
    salary: Optional[str] = Field(None, description="Salary range")
    category: Optional[str] = Field(None, description="Job category, one of 运营/增长/技术/产品/AI专项/设计/内容/职能/客服/其他")
    contacts: List[dict] = Field(default_factory=list, description="Contact info [{type, value}]")


class DeveloperInfo(BaseModel):
    """Structured developer/team information."""
    team_name: Optional[str] = Field(None, description="Team or company name")
    tech_stack: List[str] = Field(default_factory=list, description="List of technologies used")
    open_source_links: List[str] = Field(default_factory=list, description="GitHub or repository URLs")
    description: Optional[str] = Field(None, description="Team or project description")


class ContactInfo(BaseModel):
    """Structured contact information."""
    emails: List[str] = Field(default_factory=list, description="Email addresses")
    phone_numbers: List[str] = Field(default_factory=list, description="Phone numbers")
    social_links: List[str] = Field(default_factory=list, description="Social media URLs")
    contact_persons: List[str] = Field(default_factory=list, description="Names of contact persons")


class ExtractedData(BaseModel):
    """Complete extracted data from a website."""
    source_url: str = Field(..., description="Original URL of the content")
    job_postings: List[JobPosting] = Field(default_factory=list, description="List of job postings found")
    developer_info: Optional[DeveloperInfo] = Field(None, description="Developer/team information")
    contact_info: Optional[ContactInfo] = Field(None, description="Contact information")
