"""Shared error types for Intern Radar."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ValidationError

from internradar.core.models import Company

CollectorErrorType = Literal[
    "network_error",
    "parse_error",
    "rate_limited",
    "unsupported_ats",
    "invalid_config",
    "verification_error",
    "database_error",
    "unknown_error",
]


class CollectorError(BaseModel):
    company_id: str | None
    company_name: str | None
    source_type: str
    error_type: CollectorErrorType
    message: str
    recoverable: bool = True


class InternRadarError(Exception):
    """Base exception with structured collector metadata."""

    error_type: CollectorErrorType = "unknown_error"
    recoverable: bool = True

    def __init__(self, message: str, recoverable: bool | None = None) -> None:
        super().__init__(message)
        if recoverable is not None:
            self.recoverable = recoverable


class NetworkError(InternRadarError):
    error_type = "network_error"


class ParseError(InternRadarError):
    error_type = "parse_error"


class RateLimitedError(InternRadarError):
    error_type = "rate_limited"


class UnsupportedATSError(InternRadarError):
    error_type = "unsupported_ats"


class InvalidConfigError(InternRadarError):
    error_type = "invalid_config"
    recoverable = False


class VerificationError(InternRadarError):
    error_type = "verification_error"


class DatabaseError(InternRadarError):
    error_type = "database_error"
    recoverable = False


def collector_error_from_exception(
    company: Company,
    source_type: str,
    exc: Exception,
) -> CollectorError:
    """Convert arbitrary collector exceptions into a structured error."""
    if isinstance(exc, InternRadarError):
        error_type = exc.error_type
        recoverable = exc.recoverable
        message = str(exc)
    elif isinstance(exc, ValidationError):
        error_type = "parse_error"
        recoverable = True
        message = str(exc)
    else:
        error_type = "unknown_error"
        recoverable = True
        message = str(exc) or exc.__class__.__name__

    return CollectorError(
        company_id=company.id,
        company_name=company.name,
        source_type=source_type,
        error_type=error_type,
        message=message,
        recoverable=recoverable,
    )


__all__ = [
    "CollectorError",
    "CollectorErrorType",
    "DatabaseError",
    "InternRadarError",
    "InvalidConfigError",
    "NetworkError",
    "ParseError",
    "RateLimitedError",
    "UnsupportedATSError",
    "VerificationError",
    "collector_error_from_exception",
]
