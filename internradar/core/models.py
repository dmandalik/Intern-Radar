"""Domain-agnostic data models for Intern Radar."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

JobStatus = Literal[
    "open",
    "likely_open",
    "coming_soon",
    "closed",
    "stale",
    "unknown",
    "requires_login",
]


class Company(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    website: str | None = None
    careers_url: str | None = None
    ats_type: str | None = None
    ats_slug: str | None = None
    categories: list[str] = Field(default_factory=list)
    default_prestige_tier: str | None = None
    locations: list[str] = Field(default_factory=list)
    notes: str | None = None


class RawJob(BaseModel):
    source_type: str
    source_name: str
    company_id: str | None = None
    company_name: str
    title: str
    url: str
    apply_url: str | None = None
    location_raw: str | None = None
    description_raw: str | None = None
    department: str | None = None
    posted_at: datetime | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class EligibilityInfo(BaseModel):
    degree_levels: list[str] = Field(default_factory=list)
    graduation_years: list[int] = Field(default_factory=list)
    majors: list[str] = Field(default_factory=list)
    citizenship_requirement: str | None = None
    sponsorship: str | None = None
    minimum_gpa: float | None = None
    class_years: list[str] = Field(default_factory=list)
    requires_phd: bool = False
    requires_masters: bool = False
    undergrad_friendly: bool | None = None
    freshman_sophomore_friendly: bool | None = None
    confidence: float = 0.0
    raw_evidence: list[str] = Field(default_factory=list)


class ClassifiedRole(BaseModel):
    role_family: str
    role_subtype: str | None = None
    confidence: float
    evidence: list[str] = Field(default_factory=list)


class JobStatusInfo(BaseModel):
    status: JobStatus
    confidence: float
    evidence: list[str] = Field(default_factory=list)
    checked_at: datetime


class JobScores(BaseModel):
    prestige_score: float = 0.0
    role_fit_score: float = 0.0
    technical_depth_score: float = 0.0
    hidden_gem_score: float = 0.0
    freshness_score: float = 0.0
    eligibility_score: float = 0.0
    opportunity_score: float = 0.0
    explanation: list[str] = Field(default_factory=list)


class Job(BaseModel):
    id: str
    company_id: str
    company_name: str
    title: str
    description: str | None = None
    apply_url: str
    source_url: str
    source_type: str
    role: ClassifiedRole
    season: str | None = None
    year: int | None = None
    locations: list[str] = Field(default_factory=list)
    remote_type: str | None = None
    status: JobStatusInfo
    eligibility: EligibilityInfo
    scores: JobScores
    prestige_tier: str | None = None
    tags: list[str] = Field(default_factory=list)
    first_seen: datetime
    last_seen: datetime
    last_verified: datetime
    content_hash: str | None = None


__all__ = [
    "ClassifiedRole",
    "Company",
    "EligibilityInfo",
    "Job",
    "JobScores",
    "JobStatus",
    "JobStatusInfo",
    "RawJob",
]
