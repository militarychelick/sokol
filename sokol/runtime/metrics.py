"""Metrics collector for production observability."""

from dataclasses import dataclass
from typing import Callable, Optional
from collections import deque
import time


@dataclass
class Metric:
    """Single metric data point."""
    name: str
    value: float
    timestamp: float
    tags: Optional[dict[str, str]] = None


class MetricsCollector:
    """
    Metrics collector for production observability.
    
    Provides:
    - Counter metrics (increment-only)
    - Gauge metrics (current value)
    - Histogram metrics (distribution)
    - Export to Prometheus/StatsD format
    """
    
    def __init__(self, max_history: int = 1000):
        """
        Initialize metrics collector.
        
        Args:
            max_history: Maximum number of histogram samples to keep
        """
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, deque] = {}
        self._max_history = max_history
        self._lock = None  # Will use threading.Lock if needed for multi-threaded access
    
    def increment_counter(self, name: str, value: float = 1.0, tags: Optional[dict[str, str]] = None) -> None:
        """
        Increment a counter metric.
        
        Args:
            name: Metric name
            value: Value to increment by (default 1.0)
            tags: Optional tags for the metric
        """
        key = self._make_key(name, tags)
        self._counters[key] = self._counters.get(key, 0.0) + value
    
    def set_gauge(self, name: str, value: float, tags: Optional[dict[str, str]] = None) -> None:
        """
        Set a gauge metric.
        
        Args:
            name: Metric name
            value: Current value
            tags: Optional tags for the metric
        """
        key = self._make_key(name, tags)
        self._gauges[key] = value
    
    def observe_histogram(self, name: str, value: float, tags: Optional[dict[str, str]] = None) -> None:
        """
        Observe a histogram metric.
        
        Args:
            name: Metric name
            value: Observed value
            tags: Optional tags for the metric
        """
        key = self._make_key(name, tags)
        if key not in self._histograms:
            self._histograms[key] = deque(maxlen=self._max_history)
        self._histograms[key].append(value)
    
    def get_histogram_stats(self, name: str, tags: Optional[dict[str, str]] = None) -> dict[str, float]:
        """
        Get histogram statistics (p50, p95, p99).
        
        Args:
            name: Metric name
            tags: Optional tags for the metric
        
        Returns:
            Dictionary with count, min, max, p50, p95, p99
        """
        key = self._make_key(name, tags)
        if key not in self._histograms:
            return {}
        
        values = sorted(self._histograms[key])
        if not values:
            return {}
        
        return {
            "count": len(values),
            "min": values[0],
            "max": values[-1],
            "p50": values[len(values) // 2],
            "p95": values[int(len(values) * 0.95)] if len(values) > 0 else 0,
            "p99": values[int(len(values) * 0.99)] if len(values) > 0 else 0,
        }
    
    def export_prometheus(self) -> str:
        """
        Export metrics in Prometheus format.
        
        Returns:
            Prometheus-formatted metrics string
        """
        lines = []
        
        # Counters
        for key, value in self._counters.items():
            name, tags = self._parse_key(key)
            lines.append(f"# TYPE {name} counter")
            if tags:
                lines.append(f'{name}{{{self._format_tags(tags)}}} {value}')
            else:
                lines.append(f"{name} {value}")
        
        # Gauges
        for key, value in self._gauges.items():
            name, tags = self._parse_key(key)
            lines.append(f"# TYPE {name} gauge")
            if tags:
                lines.append(f'{name}{{{self._format_tags(tags)}}} {value}')
            else:
                lines.append(f"{name} {value}")
        
        # Histograms
        for key in self._histograms.keys():
            name, tags = self._parse_key(key)
            stats = self.get_histogram_stats(name, tags)
            lines.append(f"# TYPE {name} histogram")
            for stat, value in stats.items():
                if stat != "count":
                    lines.append(f'{name}_{stat}{{{self._format_tags(tags)}}} {value}')
        
        return "\n".join(lines)
    
    def get_all_metrics(self) -> dict[str, any]:
        """
        Get all metrics as a dictionary.
        
        Returns:
            Dictionary with counters, gauges, and histogram stats
        """
        return {
            "counters": self._counters.copy(),
            "gauges": self._gauges.copy(),
            "histograms": {
                key: self.get_histogram_stats(*self._parse_key(key))
                for key in self._histograms.keys()
            }
        }
    
    def reset(self) -> None:
        """Reset all metrics."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
    
    def _make_key(self, name: str, tags: Optional[dict[str, str]]) -> str:
        """Create a unique key from name and tags."""
        if not tags:
            return name
        tag_str = ",".join(f'{k}="{v}"' for k, v in sorted(tags.items()))
        return f"{name}{{{tag_str}}}"
    
    def _parse_key(self, key: str) -> tuple[str, dict[str, str]]:
        """Parse a key into name and tags."""
        if "{" in key and "}" in key:
            name = key[:key.index("{")]
            tag_str = key[key.index("{")+1:key.index("}")]
            tags = {}
            for pair in tag_str.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    tags[k.strip()] = v.strip('"')
            return name, tags
        return key, {}
    
    def _format_tags(self, tags: dict[str, str]) -> str:
        """Format tags as Prometheus label string."""
        return ",".join(f'{k}="{v}"' for k, v in sorted(tags.items()))
