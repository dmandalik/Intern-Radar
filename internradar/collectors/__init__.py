"""Collector framework exports."""

from internradar.collectors.base import BaseCollector, collect_for_company
from internradar.collectors.greenhouse import GreenhouseCollector
from internradar.collectors.registry import CollectorRegistry

__all__ = ["BaseCollector", "CollectorRegistry", "GreenhouseCollector", "collect_for_company"]
