"""Collector framework exports."""

from internradar.collectors.base import BaseCollector, collect_for_company
from internradar.collectors.registry import CollectorRegistry

__all__ = ["BaseCollector", "CollectorRegistry", "collect_for_company"]
