"""Deterministic dimensional discovery from validated upstream knowledge."""

from core.dimensional.discovery import DimensionalDiscoveryConfig, discover_dimensions
from core.dimensional.validation import effective_dimensional_discovery, validate_dimensional_discovery

__all__ = ["DimensionalDiscoveryConfig", "discover_dimensions",
           "effective_dimensional_discovery", "validate_dimensional_discovery"]
