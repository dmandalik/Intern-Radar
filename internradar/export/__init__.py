"""Export helpers and shared export row model."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from internradar.core.models import Job

FORMAT_EXTENSIONS = {
    "csv": ".csv",
    "json": ".json",
    "xlsx": ".xlsx",
    "html": ".html",
    "markdown": ".md",
}


@dataclass(slots=True)
class ExportJobView:
    rank: int
    job: Job
    application_status: str = ""
    notes: str = ""
    saved: bool = False
    applied: bool = False

    @property
    def company(self) -> str:
        return self.job.company_name

    @property
    def title(self) -> str:
        return self.job.title

    @property
    def role_family(self) -> str:
        return self.job.role.role_family

    @property
    def role_subtype(self) -> str:
        return self.job.role.role_subtype or ""

    @property
    def status(self) -> str:
        return self.job.status.status

    @property
    def location(self) -> str:
        return ", ".join(self.job.locations)

    @property
    def eligibility_summary(self) -> str:
        parts: list[str] = []
        if self.job.eligibility.graduation_years:
            parts.append("Grad years: " + ", ".join(str(year) for year in self.job.eligibility.graduation_years))
        if self.job.eligibility.degree_levels:
            parts.append("Degrees: " + ", ".join(self.job.eligibility.degree_levels))
        if self.job.eligibility.majors:
            parts.append("Majors: " + ", ".join(self.job.eligibility.majors[:3]))
        if self.job.eligibility.sponsorship:
            parts.append(f"Sponsorship: {self.job.eligibility.sponsorship}")
        return " | ".join(parts)

    @property
    def why_ranked(self) -> str:
        return " | ".join(self.job.scores.explanation[:4])

    @property
    def score_pills(self) -> list[tuple[str, float]]:
        return [
            ("Opportunity", self.job.scores.opportunity_score),
            ("Role Fit", self.job.scores.role_fit_score),
            ("Technical", self.job.scores.technical_depth_score),
            ("Eligibility", self.job.scores.eligibility_score),
            ("Hidden Gem", self.job.scores.hidden_gem_score),
            ("Freshness", self.job.scores.freshness_score),
        ]

    def as_flat_row(self) -> dict[str, Any]:
        return {
            "Rank": self.rank,
            "Company": self.company,
            "Title": self.title,
            "Role Family": self.role_family,
            "Role Subtype": self.role_subtype,
            "Internship": "Yes" if self.job.is_internship else "No",
            "Status": self.status,
            "Season": self.job.season or "",
            "Year": self.job.year or "",
            "Location": self.location,
            "Remote Type": self.job.remote_type or "",
            "Apply URL": self.job.apply_url,
            "Source URL": self.job.source_url,
            "Prestige Tier": self.job.prestige_tier or "",
            "Opportunity Score": round(self.job.scores.opportunity_score, 2),
            "Role Fit Score": round(self.job.scores.role_fit_score, 2),
            "Technical Depth Score": round(self.job.scores.technical_depth_score, 2),
            "Eligibility Score": round(self.job.scores.eligibility_score, 2),
            "Hidden Gem Score": round(self.job.scores.hidden_gem_score, 2),
            "Freshness Score": round(self.job.scores.freshness_score, 2),
            "First Seen": self.job.first_seen.isoformat(),
            "Last Seen": self.job.last_seen.isoformat(),
            "Last Verified": self.job.last_verified.isoformat(),
            "Application Status": self.application_status,
            "Eligibility Summary": self.eligibility_summary,
            "Why Ranked": self.why_ranked,
            "Notes": self.notes,
        }

    def as_json(self) -> dict[str, Any]:
        payload = self.job.model_dump(mode="json")
        payload.update(
            {
                "rank": self.rank,
                "application_status": self.application_status,
                "saved": self.saved,
                "applied": self.applied,
                "notes": self.notes,
                "eligibility_summary": self.eligibility_summary,
                "why_ranked": self.why_ranked,
            },
        )
        return payload


def default_output_path(
    *,
    base_dir: Path,
    format_name: str,
    timestamp: str,
) -> Path:
    return base_dir / f"internradar_jobs_{timestamp}{FORMAT_EXTENSIONS[format_name]}"


__all__ = ["ExportJobView", "FORMAT_EXTENSIONS", "default_output_path"]
