"""Technical-depth scoring from role and text signals."""

from __future__ import annotations

from internradar.core.models import Job

STRONG_KEYWORDS = (
    "c++",
    "low latency",
    "distributed systems",
    "network programming",
    "multithreading",
    "concurrency",
    "performance optimization",
    "market data",
    "exchange connectivity",
    "trading infrastructure",
    "backtesting",
    "simulation",
    "real-time systems",
    "fpga",
    "verilog",
    "hardware acceleration",
    "kernel bypass",
    "order book",
    "matching engine",
)
MEDIUM_KEYWORDS = (
    "python",
    "linux",
    "performance",
    "optimization",
    "real-time",
    "latency-sensitive",
    "profiling",
    "data feeds",
    "signal generation",
    "market microstructure",
)
NEGATIVE_KEYWORDS = (
    "sales",
    "operations",
    "client services",
    "marketing",
    "administrative",
    "accounting",
    "business development",
    "compliance",
)
TECHNICAL_ROLE_FAMILIES = {
    "quant_developer",
    "trading_systems_engineer",
    "algorithmic_trading_engineer",
    "software_engineer_trading",
    "low_latency_engineer",
    "market_data_engineer",
    "infrastructure_engineer",
    "fpga_engineer",
    "hardware_trading_engineer",
    "ml_engineer_quant",
    "data_engineer_quant",
    "research_engineer_quant",
}


def score_technical_depth(job: Job) -> tuple[float, list[str]]:
    """Score the technical depth of a role from its text and classification."""
    title = job.title.casefold()
    description = (job.description or "").casefold()
    score = 25.0
    evidence: list[str] = []

    for keyword in STRONG_KEYWORDS:
        if keyword in title:
            score += 12.0
            evidence.append(f'title matched strong technical signal "{keyword}"')
        elif keyword in description:
            score += 10.0
            evidence.append(f'description matched strong technical signal "{keyword}"')

    for keyword in MEDIUM_KEYWORDS:
        if keyword in title:
            score += 6.0
            evidence.append(f'title matched medium technical signal "{keyword}"')
        elif keyword in description:
            score += 3.0
            evidence.append(f'description matched medium technical signal "{keyword}"')

    for keyword in NEGATIVE_KEYWORDS:
        if keyword in title or keyword in description:
            score -= 18.0
            evidence.append(f'non-technical signal "{keyword}" reduced technical depth')

    if job.role.role_family in TECHNICAL_ROLE_FAMILIES:
        score += 10.0
        evidence.append(f"role family '{job.role.role_family}' is strongly technical")

    score = max(0.0, min(100.0, score))
    if not evidence:
        evidence.append("No strong technical signals were found, so technical depth remained conservative.")
    return round(score, 2), evidence[:8]


__all__ = ["score_technical_depth"]
