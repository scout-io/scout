import logging
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    CollectorRegistry,
)
from prometheus_client.openmetrics.exposition import generate_latest
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a standard, in-memory registry.
# This is simpler and more reliable than multiprocess mode for single-worker applications.
registry = CollectorRegistry()

# HTTP metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status"],
    registry=registry,
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    registry=registry,
)

# Model metrics
model_predictions_total = Counter(
    "model_predictions_total",
    "Total number of model predictions",
    ["model_id", "variant"],
    registry=registry,
)

model_updates_total = Counter(
    "model_updates_total",
    "Total number of model updates",
    ["model_id"],
    registry=registry,
)

model_rewards_total = Counter(
    "model_rewards_total",
    "Total rewards received for model updates",
    ["model_id"],
    registry=registry,
)

# Replaced Summary (not multiprocess-safe) with Histogram so data merges across workers
model_reward = Histogram(
    "model_reward",
    "Reward distribution per model update",
    ["model_id"],
    registry=registry,
    buckets=(0.5, 1, 1.5, 2, 3, 5),
)

# Redis metrics
redis_operations_total = Counter(
    "redis_operations_total",
    "Total number of Redis operations",
    ["operation", "status"],
    registry=registry,
)

redis_operation_duration_seconds = Histogram(
    "redis_operation_duration_seconds",
    "Redis operation duration in seconds",
    ["operation"],
    registry=registry,
)

# System metrics
active_models = Gauge(
    "active_models", "Number of active models in the system", registry=registry
)

model_creation_timestamp = Gauge(
    "model_creation_timestamp",
    "Timestamp when model was created",
    ["model_id"],
    registry=registry,
)

# Context storage metrics
context_storage_operations = Counter(
    "context_storage_operations",
    "Total number of context storage operations",
    ["operation", "status"],
    registry=registry,
)

context_storage_size = Gauge(
    "context_storage_size", "Number of contexts stored in Redis", registry=registry
)


def get_metrics() -> bytes:
    """Generate latest metrics in OpenMetrics format."""
    try:
        return generate_latest(registry)
    except Exception as e:
        logger.error(f"Failed to generate metrics: {e}")
        return b""  # Return empty bytes on error


# No setup_multiprocess_metrics or cleanup functions are needed anymore.
def setup_multiprocess_metrics():
    """This function is no longer needed and can be removed."""
    pass
