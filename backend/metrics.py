import os
import tempfile
import atexit
import shutil
import logging
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Summary,
    CollectorRegistry,
    multiprocess,
)
from prometheus_client.openmetrics.exposition import generate_latest
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default metrics directory
DEFAULT_METRICS_DIR = os.path.join(tempfile.gettempdir(), "scout_metrics")


def setup_multiprocess_metrics():
    """Initialize multiprocess metrics mode."""
    try:
        # Get metrics directory from environment or use default
        metrics_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR", DEFAULT_METRICS_DIR)
        logger.info(f"Using metrics directory: {metrics_dir}")

        # Create directory if it doesn't exist
        os.makedirs(metrics_dir, exist_ok=True)

        # Ensure directory is writable
        test_file = os.path.join(metrics_dir, ".test")
        try:
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
        except (IOError, OSError) as e:
            logger.error(f"Metrics directory {metrics_dir} is not writable: {e}")
            raise RuntimeError(f"Metrics directory {metrics_dir} is not writable")

        # Clean up any existing metrics files
        for filename in os.listdir(metrics_dir):
            if filename.endswith(".db"):
                try:
                    os.remove(os.path.join(metrics_dir, filename))
                except OSError as e:
                    logger.warning(f"Failed to remove old metrics file {filename}: {e}")

        # Set the environment variable
        os.environ["PROMETHEUS_MULTIPROC_DIR"] = metrics_dir
        logger.info("Successfully initialized metrics directory")

        # Register cleanup function
        atexit.register(cleanup_metrics_dir, metrics_dir)

    except Exception as e:
        logger.error(f"Failed to initialize metrics: {e}")
        raise


def cleanup_metrics_dir(metrics_dir: str):
    """Clean up metrics directory on process exit."""
    try:
        if os.path.exists(metrics_dir):
            shutil.rmtree(metrics_dir)
            logger.info(f"Cleaned up metrics directory: {metrics_dir}")
    except Exception as e:
        logger.warning(f"Failed to clean up metrics directory: {e}")


# Create a multiprocess-safe registry
registry = CollectorRegistry()
multiprocess.MultiProcessCollector(registry)


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

model_reward_average = Summary(
    "model_reward_average",
    "Average reward per model update",
    ["model_id"],
    registry=registry,
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
