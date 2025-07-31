# Standard library imports
import os
import json
import uuid
import random
import datetime
import asyncio
import time
import pickle
from collections import Counter, defaultdict
from typing import (
    Dict,
    Any,
    Union,
    List,
    Tuple,
    Optional,
    Generator,
    cast,
    AsyncGenerator,
)

# Third-party imports
import docker
import numpy as np
import joblib
import redis
import docker.errors
from docker.models.containers import Container as DockerContainer
from fastapi import FastAPI, Body, HTTPException, status, Depends, Request
from fastapi.responses import StreamingResponse, Response
from fastapi.encoders import jsonable_encoder
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from pydantic import BaseModel, Field
from mabwiser.mab import MAB, LearningPolicy, NeighborhoodPolicy

# Local imports
from utils import (
    bucket_data,
    estimate_exploitation_exploration_ratio,
    estimate_exploitation_over_time,
)
from metrics import (
    http_requests_total,
    http_request_duration_seconds,
    model_predictions_total,
    model_updates_total,
    model_rewards_total,
    redis_operations_total,
    redis_operation_duration_seconds,
    active_models,
    model_creation_timestamp,
    context_storage_operations,
    context_storage_size,
    get_metrics,
    model_reward,
)

# ------------------------------------------------------------------------------
# Configuration Constants
# ------------------------------------------------------------------------------

# Core settings
CONFIG_FILE = "config.json"
MODEL_DIR = "models"
MINIMUM_UPDATE_REQUESTS = 10

# Model configuration
TRAIL_TIME_WINDOW_MINUTES = 60  # Store data for the last hour
TRAIL_BUCKET_GRANULARITY_SECONDS = 60  # 1-minute buckets

# Redis settings
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_CONTEXT_TTL = int(os.environ.get("REDIS_CONTEXT_TTL", 86400))  # 24 hours
REDIS_MODEL_KEY_PREFIX = "scout:model:"
REDIS_LOCK_KEY_PREFIX = "scout:lock:model:"
LOCK_EXPIRY_MS = 30000  # 30 seconds
LOCK_RETRY_COUNT = 5
LOCK_RETRY_DELAY_S = 0.2

# Versioning & local cache
REDIS_MODEL_VERSION_KEY_PREFIX = "scout:model_version:"

# In-memory cache: model_id -> (model, version)
MODEL_CACHE: Dict[str, Tuple["WrappedMAB", int]] = {}


def get_model_version_key(model_id: str) -> str:
    """Return Redis key that stores the version counter for a given model."""
    return f"{REDIS_MODEL_VERSION_KEY_PREFIX}{model_id}"


def _get_model_version_from_redis(model_id: str) -> int:
    """Read current model version from Redis. Missing key -> 0."""
    try:
        val = redis_text_client.get(get_model_version_key(model_id))
        if val is None:
            return 0
        # Redis client is configured with decode_responses=True so we expect a str
        return int(cast(str, val))
    except Exception:
        return 0


# Initialize Redis connection pools
redis_text_pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True,  # For context storage (JSON)
)

redis_binary_pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=False,  # For pickled model storage
)

redis_text_client = redis.Redis(connection_pool=redis_text_pool)
redis_binary_client = redis.Redis(connection_pool=redis_binary_pool)

# ------------------------------------------------------------------------------
# Request/Response Models
# ------------------------------------------------------------------------------


class CreateModelRequest(BaseModel):
    """Request body for creating a new MAB model."""

    variants: Dict[int, Union[str, int]]
    name: str


class UpdateModelRequest(BaseModel):
    """Request body for updating an existing MAB model with new data."""

    updates: List[Dict[str, Any]]


class FetchActionRequest(BaseModel):
    """Request body for fetching a recommended variant from a model."""

    cb_model_id: str
    context: Optional[Dict[str, Union[str, float, int, bool]]] = Field(
        default_factory=dict
    )
    request_id: Optional[str] = None


class RolloutGlobalVariantRequest(BaseModel):
    """Request body for rolling out a global variant for a model."""

    variant: Union[str, int]


# ------------------------------------------------------------------------------
# Middleware
# ------------------------------------------------------------------------------


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting Prometheus metrics on HTTP requests."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            raise e
        finally:
            duration = time.time() - start_time
            endpoint = request.url.path
            method = request.method

            http_requests_total.labels(
                method=method, endpoint=endpoint, status=status_code
            ).inc()

            http_request_duration_seconds.labels(
                method=method, endpoint=endpoint
            ).observe(duration)

        return response


# Helper functions for defaultdict pickling
def _create_default_int_dict():
    return defaultdict(int)


def _create_default_float_dict():
    return defaultdict(float)


# ------------------------------------------------------------------------------
# Configuration Management
# ------------------------------------------------------------------------------


def load_config() -> dict:
    """Load application configuration from JSON file with fallback to defaults."""
    default_config = {
        "host": "127.0.0.1",
        "port": 8000,
        "debug": False,
        "protected_api": False,
        "auth_token": None,
        "trail_time_window_minutes": TRAIL_TIME_WINDOW_MINUTES,
        "trail_bucket_granularity_seconds": TRAIL_BUCKET_GRANULARITY_SECONDS,
        "minimum_update_requests": MINIMUM_UPDATE_REQUESTS,
    }

    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                # Merge with defaults
                for k, v in default_config.items():
                    data.setdefault(k, v)
                return data
            except json.JSONDecodeError:
                return default_config
    return default_config


def save_config(config: dict) -> None:
    """Save application configuration to JSON file."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


# ------------------------------------------------------------------------------
# Redis Context Storage
# ------------------------------------------------------------------------------


class RedisContextStorage:
    """Handles storage and retrieval of contextual features in Redis."""

    @staticmethod
    def get_redis_key(request_id: str) -> str:
        """Generate Redis key for given request ID."""
        return f"scout:context:{request_id}"

    @staticmethod
    def store_context(
        request_id: str,
        model_id: str,
        context: Dict[str, Any],
        ttl_seconds: int = REDIS_CONTEXT_TTL,
    ) -> bool:
        """Store context information in Redis with automatic expiration."""
        start_time = time.time()
        try:
            key = RedisContextStorage.get_redis_key(request_id)
            value = json.dumps(
                {
                    "model_id": model_id,
                    "context": context,
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                }
            )
            success = cast(bool, redis_text_client.setex(key, ttl_seconds, value))

            if success:
                context_storage_operations.labels(
                    operation="store", status="success"
                ).inc()
                context_storage_size.inc()
            else:
                context_storage_operations.labels(
                    operation="store", status="error"
                ).inc()
            return success
        except Exception as e:
            context_storage_operations.labels(operation="store", status="error").inc()
            print(f"Error storing context in Redis: {e}")
            return False
        finally:
            duration = time.time() - start_time
            redis_operation_duration_seconds.labels(operation="store_context").observe(
                duration
            )

    @staticmethod
    def get_context(request_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve context information from Redis by request ID."""
        try:
            key = RedisContextStorage.get_redis_key(request_id)
            value = redis_text_client.get(key)
            if not value:
                return None
            assert isinstance(value, str)
            data = json.loads(value)
            return data.get("context")
        except Exception as e:
            print(f"Error retrieving context from Redis: {e}")
            return None

    @staticmethod
    def delete_context(request_id: str) -> bool:
        """Delete context information from Redis."""
        start_time = time.time()
        try:
            key = RedisContextStorage.get_redis_key(request_id)
            deleted_count = cast(int, redis_text_client.delete(key))
            if deleted_count > 0:
                context_storage_operations.labels(
                    operation="delete", status="success"
                ).inc()
                context_storage_size.dec()
            else:
                context_storage_operations.labels(
                    operation="delete", status="not_found"
                ).inc()
            return deleted_count > 0
        except Exception as e:
            context_storage_operations.labels(operation="delete", status="error").inc()
            print(f"Error deleting context from Redis: {e}")
            return False
        finally:
            duration = time.time() - start_time
            redis_operation_duration_seconds.labels(operation="delete_context").observe(
                duration
            )

    @staticmethod
    def check_redis_health() -> bool:
        """Check if Redis connection is healthy."""
        try:
            return cast(bool, redis_text_client.ping())
        except Exception:
            return False

    @staticmethod
    def get_all_keys_count() -> int:
        """Get count of all context keys in Redis."""
        try:
            keys = cast(List[str], redis_text_client.keys("scout:context:*"))
            return len(keys)
        except Exception:
            return -1


# ------------------------------------------------------------------------------
# Context Encoding Helpers
# ------------------------------------------------------------------------------


def encode_value(feature_name: str, value: Any, model: "WrappedMAB") -> float:
    """
    Encode a single context value as a numeric value.
    - Booleans -> 1 (True) or 0 (False)
    - Numbers -> unchanged
    - Strings -> mapped to ordinal integer code
    """
    if type(value) is bool:
        return 1 if value else 0
    elif isinstance(value, (int, float)):
        return value
    elif isinstance(value, str):
        if feature_name not in model.context_encoders:
            model.context_encoders[feature_name] = {}
        encoder = model.context_encoders[feature_name]
        if value not in encoder:
            encoder[value] = float(len(encoder))
        return encoder[value]
    else:
        raise ValueError(
            f"Unsupported type for feature '{feature_name}': {type(value)}"
        )


def encode_context(model: "WrappedMAB", context: Dict[str, Any]) -> np.ndarray:
    """
    Convert a dictionary of context values to a 1D numpy array of numeric encodings.
    Features are ordered according to model.features, with 0.0 as default for missing features.
    """
    if not model.features:
        feature_keys = sorted([k for k in context.keys() if k.startswith("feature")])
        model.features = feature_keys

    encoded = []
    for feature in model.features:
        if feature in context:
            try:
                encoded.append(encode_value(feature, context[feature], model))
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
        else:
            encoded.append(0.0)
    return np.array(encoded)


# ------------------------------------------------------------------------------
# Multi-Armed Bandit Model
# ------------------------------------------------------------------------------


class WrappedMAB(MAB):
    """
    Extended MAB class with additional metadata and tracking capabilities.
    Wraps the base MAB class from mabwiser to provide:
    - Variant label mapping
    - Request tracking
    - Time-windowed aggregation
    - Context encoding
    - Feature prediction trails
    """

    def __init__(
        self,
        name: str,
        arms: List[int],
        variant_labels: Dict[int, Any],
        label_variants: Dict[Any, int],
        *args,
        **kwargs,
    ) -> None:
        super().__init__(arms=arms, *args, **kwargs)
        # Core attributes
        self.name = name
        self.arms = arms
        self.variant_labels = variant_labels
        self.label_variants = label_variants

        # Tracking
        self.features = []
        self.created_at = datetime.datetime.utcnow()
        self.global_variant = None
        self.update_requests = 0
        self.prediction_requests = 0
        self.latest_update_request = None
        self.latest_prediction_request = None

        # Time-windowed aggregation
        self.recent_prediction_counts = defaultdict(_create_default_int_dict)
        self.recent_update_details = defaultdict(_create_default_float_dict)
        self.trail_time_window_minutes = 60
        self.trail_bucket_granularity_seconds = 60

        # State flags
        self.active = True
        self.global_rolled_out = False
        self.has_done_initial_fit = False

        # Initial data storage
        self.initial_decisions = []
        self.initial_rewards = []
        self.initial_contexts = []

        # Exploitation tracking
        self.exploitation_count = 0
        self.exploitation_history = []

        # Context encoding
        self.context_encoders = {}

        # Feature prediction tracking
        self.feature_prediction_trail = []

    def _incr_update_request(self) -> None:
        """Increment update request counter."""
        self.update_requests += 1

    def _incr_prediction_request(self) -> None:
        """Increment prediction request counter."""
        self.prediction_requests += 1

    def _incr_latest_update_request(self) -> None:
        """Update timestamp of latest update request."""
        self.latest_update_request = datetime.datetime.utcnow()

    def _incr_latest_prediction_request(self) -> None:
        """Update timestamp of latest prediction request."""
        self.latest_prediction_request = datetime.datetime.utcnow()

    def _update_update_request_trail(
        self, variant: int, reward: Union[float, int]
    ) -> None:
        """Add variant and reward to update request trail."""
        now = datetime.datetime.utcnow()
        current_bucket_time = self._get_current_time_bucket(now)
        variant_label = self.variant_labels.get(variant, f"unknown_variant_{variant}")

        decision_key = f"decision_{variant_label}"
        self.recent_update_details[current_bucket_time][decision_key] = (
            cast(float, self.recent_update_details[current_bucket_time][decision_key])
            + 1
        )

        self.recent_update_details[current_bucket_time]["total_reward"] = (
            cast(float, self.recent_update_details[current_bucket_time]["total_reward"])
            + reward
        )

        self.recent_update_details[current_bucket_time]["update_count"] = (
            cast(int, self.recent_update_details[current_bucket_time]["update_count"])
            + 1
        )

        self._prune_old_trail_data(now)

    def _update_prediction_request_trail(self, variant: int) -> None:
        """Add variant to prediction request trail."""
        now = datetime.datetime.utcnow()
        current_bucket_time = self._get_current_time_bucket(now)
        variant_label = self.variant_labels.get(variant)
        if variant_label is not None:
            self.recent_prediction_counts[current_bucket_time][variant_label] += 1
        self._prune_old_trail_data(now)

    def _get_current_time_bucket(
        self, timestamp: datetime.datetime
    ) -> datetime.datetime:
        """Calculate time bucket for given timestamp."""
        discard_seconds_and_micros = timestamp.replace(second=0, microsecond=0)
        minute_bucket = discard_seconds_and_micros.minute - (
            discard_seconds_and_micros.minute
            % (self.trail_bucket_granularity_seconds // 60)
        )
        return discard_seconds_and_micros.replace(minute=minute_bucket)

    def _prune_old_trail_data(self, current_time: datetime.datetime) -> None:
        """Remove data older than trail_time_window_minutes from trails."""
        cutoff = current_time - datetime.timedelta(
            minutes=self.trail_time_window_minutes
        )

        keys_to_delete_preds = [k for k in self.recent_prediction_counts if k < cutoff]
        for k in keys_to_delete_preds:
            del self.recent_prediction_counts[k]

        keys_to_delete_updates = [k for k in self.recent_update_details if k < cutoff]
        for k in keys_to_delete_updates:
            del self.recent_update_details[k]

    def _update_feature_list(self, feature: str) -> None:
        """Add feature to feature list if not present."""
        if feature not in self.features:
            self.features.append(feature)

    def deactivate(self) -> None:
        """Deactivate model (no longer used for predictions)."""
        self.active = False

    def rollout(self, variant: int) -> None:
        """Roll out global variant, deactivating MAB logic."""
        self.deactivate()
        self.global_rolled_out = True
        self.global_variant = variant

    def clear_global_rollout(self) -> None:
        """Clear global variant, reactivating MAB logic."""
        self.active = True
        self.global_rolled_out = False
        self.global_variant = None

    def get_global_variant(self) -> Optional[int]:
        """Get currently rolled out global variant."""
        return self.global_variant

    def get_prediction_ratio(self) -> Dict[Any, float]:
        """Get ratio of variant predictions based on recent counts."""
        current_counts = Counter()
        if not self.recent_prediction_counts:
            return {label: 0.0 for label in self.variant_labels.values()}

        for _bucket_time, bucket_counts in self.recent_prediction_counts.items():
            for variant_label, count in bucket_counts.items():
                current_counts[variant_label] += count

        total = sum(current_counts.values())
        if total == 0:
            return {label: 0.0 for label in self.variant_labels.values()}

        ratios = {
            label: current_counts.get(label, 0) / total
            for label in self.variant_labels.values()
        }
        return ratios


# ------------------------------------------------------------------------------
# Redis Model Persistence
# ------------------------------------------------------------------------------


def get_model_redis_key(model_id: str) -> str:
    """Generate Redis key for model storage."""
    return f"{REDIS_MODEL_KEY_PREFIX}{model_id}"


def get_lock_redis_key(model_id: str) -> str:
    """Generate Redis key for model lock."""
    return f"{REDIS_LOCK_KEY_PREFIX}{model_id}"


def save_model_to_redis(model_id: str, model: WrappedMAB) -> None:
    """Serialize model, bump its version and save to Redis + local cache."""
    try:
        data = pickle.dumps(model)

        model_key = get_model_redis_key(model_id)
        version_key = get_model_version_key(model_id)

        # Increment version first; Redis returns the new value
        new_version = cast(int, redis_text_client.incr(version_key))

        # Save pickled blob
        redis_binary_client.set(model_key, data)

        # Update local cache
        MODEL_CACHE[model_id] = (model, new_version)
    except Exception as e:
        print(f"Error saving model {model_id} to Redis: {e}")


def load_model_from_redis(
    model_id: str, use_cache: bool = True
) -> Optional[WrappedMAB]:
    """Load model from Redis with optional local read-through cache."""
    try:
        version = _get_model_version_from_redis(model_id)

        # Fast path – up-to-date cached copy
        if use_cache and model_id in MODEL_CACHE:
            cached_model, cached_version = MODEL_CACHE[model_id]
            if cached_version == version:
                return cached_model

        # Fallback: pull full blob from Redis
        data_raw = redis_binary_client.get(get_model_redis_key(model_id))
        if data_raw is None:
            return None
        model = pickle.loads(cast(bytes, data_raw))

        if use_cache:
            MODEL_CACHE[model_id] = (model, version)

        return model
    except Exception as e:
        print(f"Error loading model {model_id} from Redis: {e}")
        return None


def delete_model_from_redis(model_id: str) -> bool:
    """Delete model and version keys from Redis and local cache."""
    try:
        redis_binary_client.delete(get_model_redis_key(model_id))
        redis_text_client.delete(get_model_version_key(model_id))

        MODEL_CACHE.pop(model_id, None)
        return True
    except Exception as e:
        print(f"Error deleting model {model_id} from Redis: {e}")
        return False


def list_model_ids_from_redis() -> List[str]:
    """List all model IDs from Redis."""
    model_ids = []
    try:
        for key in redis_binary_client.scan_iter(match=f"{REDIS_MODEL_KEY_PREFIX}*"):
            key_str = key.decode("utf-8")
            model_ids.append(key_str.replace(REDIS_MODEL_KEY_PREFIX, ""))
    except Exception as e:
        print(f"Error listing model IDs from Redis: {e}")
    return model_ids


def acquire_lock_with_retry(model_id: str, lock_value: str) -> bool:
    """Acquire distributed lock for model with retries."""
    lock_key = get_lock_redis_key(model_id)
    for _ in range(LOCK_RETRY_COUNT):
        if cast(
            bool,
            redis_text_client.set(lock_key, lock_value, nx=True, px=LOCK_EXPIRY_MS),
        ):
            return True
        time.sleep(LOCK_RETRY_DELAY_S)
    return False


def release_lock(model_id: str, lock_value: str) -> None:
    """Release distributed lock using atomic Lua script."""
    lock_key = get_lock_redis_key(model_id)
    lua_script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """
    try:
        cast(int, redis_text_client.eval(lua_script, 1, lock_key, lock_value))
    except Exception as e:
        print(f"Error releasing lock {lock_key} for value {lock_value}: {e}")


# ------------------------------------------------------------------------------
# Feature Prediction Analysis
# ------------------------------------------------------------------------------


def compute_feature_prediction_data(model: WrappedMAB) -> Dict[str, Any]:
    """
    Process feature prediction trail to compute bucketed breakdown of prediction ratios.
    For each feature, analyzes prediction patterns based on feature values.
    """
    result = {}
    for feature in model.features:
        entries = []
        for record in model.feature_prediction_trail:
            context, variant, timestamp = record
            if feature in context:
                entries.append((context[feature], variant))
        if not entries:
            continue

        # Determine feature type
        sample = entries[0][0]
        if type(sample) is bool:
            feature_type = "bool"
        elif isinstance(sample, (int, float)):
            if all(
                isinstance(val, (int, float)) and type(val) is not bool
                for val, _ in entries
            ):
                feature_type = "numeric"
            else:
                feature_type = "categorical"
        else:
            feature_type = "categorical"

        buckets = {}
        if feature_type == "numeric":
            all_values = [val for val, _ in entries]
            unique_values = sorted(set(all_values))

            if len(unique_values) <= 5:
                # Use exact values as buckets
                for val, variant in entries:
                    bucket_label = str(val)
                    buckets.setdefault(bucket_label, []).append(variant)
            else:
                min_val = min(all_values)
                max_val = max(all_values)
                if min_val == max_val:
                    for val, variant in entries:
                        bucket_label = str(val)
                        buckets.setdefault(bucket_label, []).append(variant)
                else:
                    # Create 5 equal-width bins
                    bin_count = 5
                    bin_width = (max_val - min_val) / bin_count
                    bins_edges = [min_val + i * bin_width for i in range(bin_count + 1)]
                    for val, variant in entries:
                        bin_index = int((val - min_val) / bin_width)
                        if bin_index == bin_count:
                            bin_index = bin_count - 1
                        low = bins_edges[bin_index]
                        high = bins_edges[bin_index + 1]
                        bucket_label = f"{low:.2f}-{high:.2f}"
                        buckets.setdefault(bucket_label, []).append(variant)
        else:
            # Categorical/boolean features use distinct values as buckets
            for val, variant in entries:
                bucket_label = str(val)
                buckets.setdefault(bucket_label, []).append(variant)

        # Compute statistics for each bucket
        bucket_list = []
        for bucket_label, variants in buckets.items():
            total = len(variants)
            counts = {}
            for variant in variants:
                variant_label = model.variant_labels.get(variant, variant)
                counts[variant_label] = counts.get(variant_label, 0) + 1
            ratios = {k: (v / total) * 100 for k, v in counts.items()}
            bucket_list.append(
                {
                    "bucket": bucket_label,
                    "total": total,
                    "predictions": counts,
                    "ratios": ratios,
                }
            )

        # Sort buckets appropriately
        if feature_type == "numeric":
            try:
                bucket_list.sort(key=lambda x: float(x["bucket"].split("-")[0]))
            except Exception:
                bucket_list.sort(key=lambda x: x["bucket"])
        else:
            bucket_list.sort(key=lambda x: x["bucket"])

        result[feature] = {"type": feature_type, "buckets": bucket_list}
    return result


# ------------------------------------------------------------------------------
# FastAPI App Initialization
# ------------------------------------------------------------------------------

config = load_config()
app = FastAPI(title="Scout")

# Add middleware
app.add_middleware(PrometheusMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)


def maybe_verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> None:
    """Verify Bearer token if API protection is enabled."""
    current_config = load_config()

    if not current_config.get("protected_api"):
        return

    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid token scheme.",
        )

    token = credentials.credentials
    if token != current_config.get("auth_token"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token.",
        )


# ------------------------------------------------------------------------------
# Admin Endpoints
# ------------------------------------------------------------------------------


@app.get("/admin/get_protection")
def get_protection_status() -> Dict[str, Any]:
    """Get current protection status and auth token."""
    cfg = load_config()
    return {
        "protected_api": cfg["protected_api"],
        "auth_token": cfg["auth_token"],
    }


@app.post("/admin/set_protection")
def set_protection(protected_api: bool = Body(...)) -> Dict[str, Any]:
    """Enable/disable API protection."""
    cfg = load_config()
    cfg["protected_api"] = protected_api

    if not protected_api:
        cfg["auth_token"] = None

    save_config(cfg)
    return {
        "protected_api": protected_api,
        "auth_token": cfg["auth_token"],
    }


@app.post("/admin/generate_token")
def generate_token() -> Dict[str, str]:
    """Generate new auth token when protection is enabled."""
    cfg = load_config()
    if not cfg.get("protected_api"):
        raise HTTPException(
            status_code=400,
            detail="API protection must be enabled before generating a token.",
        )
    new_token = uuid.uuid4().hex
    cfg["auth_token"] = new_token
    save_config(cfg)
    return {"token": new_token}


@app.get("/admin/redis_health")
def check_redis_health() -> Dict[str, Any]:
    """Check Redis connection health status."""
    is_healthy = RedisContextStorage.check_redis_health()
    keys_count = RedisContextStorage.get_all_keys_count() if is_healthy else -1

    return {
        "redis_healthy": is_healthy,
        "context_keys_count": keys_count,
        "redis_host": REDIS_HOST,
        "redis_port": REDIS_PORT,
        "ttl_seconds": REDIS_CONTEXT_TTL,
    }


@app.get("/admin/model_config")
def get_model_config() -> Dict[str, Any]:
    """Get current model configuration settings."""
    cfg = load_config()
    return {
        "time_window_minutes": cfg.get(
            "trail_time_window_minutes", TRAIL_TIME_WINDOW_MINUTES
        ),
        "bucket_granularity_seconds": cfg.get(
            "trail_bucket_granularity_seconds", TRAIL_BUCKET_GRANULARITY_SECONDS
        ),
        "min_update_requests": cfg.get(
            "minimum_update_requests", MINIMUM_UPDATE_REQUESTS
        ),
    }


@app.post("/admin/model_config")
def update_model_config(
    time_window_minutes: int = Body(...),
    bucket_granularity_seconds: int = Body(...),
    min_update_requests: int = Body(...),
) -> Dict[str, Any]:
    """Update model configuration settings."""
    global TRAIL_TIME_WINDOW_MINUTES, TRAIL_BUCKET_GRANULARITY_SECONDS, MINIMUM_UPDATE_REQUESTS

    TRAIL_TIME_WINDOW_MINUTES = time_window_minutes
    TRAIL_BUCKET_GRANULARITY_SECONDS = bucket_granularity_seconds
    MINIMUM_UPDATE_REQUESTS = min_update_requests

    cfg = load_config()
    cfg.update(
        {
            "trail_time_window_minutes": time_window_minutes,
            "trail_bucket_granularity_seconds": bucket_granularity_seconds,
            "minimum_update_requests": min_update_requests,
        }
    )
    save_config(cfg)

    return {
        "time_window_minutes": time_window_minutes,
        "bucket_granularity_seconds": bucket_granularity_seconds,
        "min_update_requests": min_update_requests,
    }


@app.get("/admin/system_config")
def get_system_config() -> Dict[str, Any]:
    """Get current system configuration."""
    cfg = load_config()
    return {
        "host": cfg.get("host", "127.0.0.1"),
        "port": cfg.get("port", 8000),
        "debug": cfg.get("debug", False),
    }


@app.post("/admin/system_config")
def update_system_config(
    host: str = Body(...),
    port: int = Body(...),
    debug: bool = Body(...),
) -> Dict[str, Any]:
    """Update system configuration."""
    cfg = load_config()
    cfg.update(
        {
            "host": host,
            "port": port,
            "debug": debug,
        }
    )
    save_config(cfg)

    return {
        "host": host,
        "port": port,
        "debug": debug,
        "restart_required": True,
    }


@app.post("/admin/redis_config")
def update_redis_config(
    host: str = Body(...),
    port: int = Body(...),
    ttl: int = Body(...),
) -> Dict[str, Any]:
    """Update Redis configuration."""
    global REDIS_HOST, REDIS_PORT, REDIS_CONTEXT_TTL

    os.environ["REDIS_HOST"] = host
    os.environ["REDIS_PORT"] = str(port)
    os.environ["REDIS_CONTEXT_TTL"] = str(ttl)

    REDIS_HOST = host
    REDIS_PORT = port
    REDIS_CONTEXT_TTL = ttl

    cfg = load_config()
    cfg.update(
        {
            "redis_host": host,
            "redis_port": port,
            "redis_context_ttl": ttl,
        }
    )
    save_config(cfg)

    return {
        "redis_host": host,
        "redis_port": port,
        "redis_context_ttl": ttl,
        "restart_required": True,
    }


# ------------------------------------------------------------------------------
# Model Management Endpoints
# ------------------------------------------------------------------------------


@app.post("/api/create_model")
async def create_model(
    request: CreateModelRequest,
    _: None = Depends(maybe_verify_token),
) -> Dict[str, str]:
    """Create new MAB model with given name and variant labels."""
    cb_model_id = str(uuid.uuid4())
    arms = sorted(request.variants.keys())
    variant_labels = {k: v for k, v in request.variants.items()}
    label_variants = {v: k for k, v in request.variants.items()}

    new_model = WrappedMAB(
        name=request.name,
        arms=arms,
        variant_labels=variant_labels,
        label_variants=label_variants,
        learning_policy=LearningPolicy.EpsilonGreedy(),
        neighborhood_policy=NeighborhoodPolicy.TreeBandit(),
    )

    save_model_to_redis(cb_model_id, new_model)

    active_models.inc()
    model_creation_timestamp.labels(model_id=cb_model_id).set(time.time())

    return {"message": "Model created successfully", "model_id": cb_model_id}


@app.post("/api/delete_model/{cb_model_id}")
async def delete_model_endpoint(
    cb_model_id: str, _: None = Depends(maybe_verify_token)
) -> Dict[str, str]:
    """Delete model by ID from Redis."""
    lock_value = uuid.uuid4().hex
    if not acquire_lock_with_retry(cb_model_id, lock_value):
        raise HTTPException(
            status_code=503, detail="Could not acquire lock for model deletion."
        )

    try:
        model = load_model_from_redis(cb_model_id)
        if not model:
            return {"message": "Model not found or already deleted"}

        if delete_model_from_redis(cb_model_id):
            return {"message": "Model deleted from Redis"}
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete model from Redis after loading.",
            )
    finally:
        release_lock(cb_model_id, lock_value)


@app.get("/api/models")
async def get_models_info() -> Any:
    """List all available models and their metadata."""
    response = []
    model_ids = list_model_ids_from_redis()

    for model_id in model_ids:
        model = load_model_from_redis(model_id)
        if model:
            response.append(
                {
                    "model_id": model_id,
                    "name": model.name,
                    "variants": list(model.variant_labels.values()),
                    "global_rolled_out": model.global_rolled_out,
                    "global_variant": (
                        model.variant_labels.get(
                            model.global_variant, model.global_variant
                        )
                        if model.global_variant is not None
                        else None
                    ),
                    "created_at": model.created_at,
                    "update_requests": model.update_requests,
                    "prediction_requests": model.prediction_requests,
                    "latest_update_request": model.latest_update_request,
                    "latest_prediction_request": model.latest_prediction_request,
                    "prediction_ratio": model.get_prediction_ratio(),
                    "URL": f"http://localhost/api/update_model/{model_id}",
                    "features": model.features,
                    "active": model.active,
                }
            )
    return jsonable_encoder(response)


@app.get("/api/model_details/{cb_model_id}")
async def get_model_details(cb_model_id: str) -> Any:
    """Get detailed model information including request trails and exploitation data."""
    model = load_model_from_redis(cb_model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found in Redis")

    details = {
        "request_trail": bucket_data(
            cast(
                Dict[datetime.datetime, Dict[Any, int]], model.recent_prediction_counts
            )
        ),
        "exploit_explore_ratio": estimate_exploitation_exploration_ratio(model),
        "exploitation_status": estimate_exploitation_over_time(model),
        "feature_prediction_data": compute_feature_prediction_data(model),
    }
    return jsonable_encoder(details)


@app.post("/api/update_model/{cb_model_id}")
async def update_model(
    cb_model_id: str,
    request: UpdateModelRequest,
    _: None = Depends(maybe_verify_token),
) -> Dict[str, Any]:
    """Update model with new decision/reward data."""
    lock_value = uuid.uuid4().hex
    if not acquire_lock_with_retry(cb_model_id, lock_value):
        raise HTTPException(
            status_code=503, detail="Could not acquire lock for model update."
        )

    model = None
    try:
        model = load_model_from_redis(cb_model_id)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found in Redis")

        cfg = load_config()
        redis_enabled = cfg.get("redis_enabled", True)

        processed_updates = 0
        missing_context = 0
        redis_hits = 0
        total_reward = 0.0

        for update in request.updates:
            decision = update.get("decision")
            reward = update.get("reward")

            if decision is None or reward is None:
                continue

            # Convert decision label to internal integer
            if isinstance(decision, str):
                if decision not in model.label_variants:
                    raise HTTPException(
                        status_code=400, detail=f"Invalid variant label: {decision}"
                    )
                decision = model.label_variants[decision]
            else:
                if decision not in model.arms:
                    raise HTTPException(
                        status_code=400, detail=f"Invalid variant integer: {decision}"
                    )

            # Get context features
            context_features = {}
            if redis_enabled and "request_id" in update and update["request_id"]:
                request_id = update["request_id"]
                cached_context = RedisContextStorage.get_context(request_id)
                if cached_context:
                    context_features = {
                        k: v
                        for k, v in cached_context.items()
                        if k.startswith("feature")
                    }
                    redis_hits += 1

            if not context_features:
                context_features = {
                    k: v for k, v in update.items() if k.startswith("feature")
                }

            if not context_features and model.features:
                missing_context += 1
                continue

            # Encode context
            encoded_context = (
                encode_context(model, context_features)
                if context_features
                else np.array([])
            )
            context_array = (
                np.array([encoded_context])
                if encoded_context.size > 0
                else np.empty((1, 0))
            )

            # Handle initial fitting phase
            if model.update_requests < MINIMUM_UPDATE_REQUESTS:
                model.initial_decisions.append(decision)
                model.initial_contexts.append(encoded_context)
                model.initial_rewards.append(reward)
                model._incr_update_request()
                model._incr_latest_update_request()
                model._update_update_request_trail(variant=decision, reward=reward)

                if model.update_requests == MINIMUM_UPDATE_REQUESTS:
                    all_contexts = np.array(model.initial_contexts)
                    all_decisions = np.array(model.initial_decisions)
                    all_rewards = np.array(model.initial_rewards)
                    model.fit(
                        decisions=all_decisions,
                        rewards=all_rewards,
                        contexts=all_contexts,
                    )
                    model.has_done_initial_fit = True
            else:
                if not model.has_done_initial_fit:
                    all_contexts = np.array(model.initial_contexts)
                    all_decisions = np.array(model.initial_decisions)
                    all_rewards = np.array(model.initial_rewards)
                    model.fit(
                        decisions=all_decisions,
                        rewards=all_rewards,
                        contexts=all_contexts,
                    )
                    model.has_done_initial_fit = True

                model.partial_fit(
                    decisions=[decision], rewards=[reward], contexts=context_array
                )
                model._incr_update_request()
                model._incr_latest_update_request()
                model._update_update_request_trail(variant=decision, reward=reward)

            # Record metrics
            model_updates_total.labels(model_id=cb_model_id).inc()
            model_rewards_total.labels(model_id=cb_model_id).inc(reward)
            model_reward.labels(model_id=cb_model_id).observe(reward)
            total_reward += reward
            processed_updates += 1

        if processed_updates > 0:
            save_model_to_redis(cb_model_id, model)

        return {
            "message": "Model updated successfully",
            "processed_updates": processed_updates,
            "missing_context": missing_context,
            "redis_hits": redis_hits,
            "total_reward": total_reward,
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error during model update for {cb_model_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error during model update."
        )
    finally:
        release_lock(cb_model_id, lock_value)


@app.post("/api/rollout_global_variant/{cb_model_id}")
async def rollout_global_variant(
    cb_model_id: str,
    request: RolloutGlobalVariantRequest,
    _: None = Depends(maybe_verify_token),
) -> Dict[str, str]:
    """Roll out global variant for specified model."""
    lock_value = uuid.uuid4().hex
    if not acquire_lock_with_retry(cb_model_id, lock_value):
        raise HTTPException(
            status_code=503, detail="Could not acquire lock for model rollout."
        )

    model = None
    try:
        model = load_model_from_redis(cb_model_id)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found in Redis")

        variant_to_rollout = request.variant
        internal_variant_id: Optional[int] = None

        if isinstance(variant_to_rollout, str):
            if variant_to_rollout not in model.label_variants:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid variant label: {variant_to_rollout}",
                )
            internal_variant_id = model.label_variants[variant_to_rollout]
        elif isinstance(variant_to_rollout, int):
            if variant_to_rollout not in model.arms:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid variant integer: {variant_to_rollout}",
                )
            internal_variant_id = variant_to_rollout
        else:
            raise HTTPException(
                status_code=400, detail="Invalid variant type for rollout."
            )

        if internal_variant_id is not None:
            model.rollout(variant=internal_variant_id)
            save_model_to_redis(cb_model_id, model)
            return {
                "message": f"Global variant '{request.variant}' (internal={internal_variant_id}) rolled out for model {cb_model_id}"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to determine internal variant for rollout.",
            )
    finally:
        release_lock(cb_model_id, lock_value)


@app.post("/api/clear_global_variant/{cb_model_id}")
async def clear_global_variant(
    cb_model_id: str,
    _: None = Depends(maybe_verify_token),
) -> Dict[str, str]:
    """Clear previously rolled out global variant."""
    lock_value = uuid.uuid4().hex
    if not acquire_lock_with_retry(cb_model_id, lock_value):
        raise HTTPException(
            status_code=503,
            detail="Could not acquire lock for clearing global variant.",
        )

    model = None
    try:
        model = load_model_from_redis(cb_model_id)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found in Redis")

        model.clear_global_rollout()
        save_model_to_redis(cb_model_id, model)

        return {"message": f"Global variant cleared for model {cb_model_id}"}
    finally:
        release_lock(cb_model_id, lock_value)


# ------------------------------------------------------------------------------
# Variant Recommendation Endpoint
# ------------------------------------------------------------------------------


@app.post("/api/fetch_recommended_variant")
async def fetch_recommended_variant(
    request: FetchActionRequest,
    _: None = Depends(maybe_verify_token),
) -> Dict[str, Any]:
    """Fetch recommended variant from specified model."""
    cb_model_id = request.cb_model_id
    lock_value = uuid.uuid4().hex
    if not acquire_lock_with_retry(cb_model_id, lock_value):
        raise HTTPException(
            status_code=503, detail="Could not acquire lock for fetching variant."
        )

    model = None
    try:
        model = load_model_from_redis(cb_model_id)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found in Redis")

        request_id = request.request_id or str(uuid.uuid4())
        recommended_label: Any = None
        internal_variant: Optional[int] = None

        # Check for global rollout
        if model.global_rolled_out:
            internal_variant = model.get_global_variant()
            if internal_variant is not None:
                recommended_label = model.variant_labels.get(
                    internal_variant, internal_variant
                )
            else:
                recommended_label = "Error: Global rollout active but no variant set"

            cfg = load_config()
            if cfg.get("redis_enabled", True) and request.context:
                RedisContextStorage.store_context(
                    request_id=request_id, model_id=cb_model_id, context=request.context
                )
            return {"recommended_variant": recommended_label, "request_id": request_id}

        # Regular prediction logic
        context_features = {}
        if request.context:
            context_features = {
                k: v for k, v in request.context.items() if k.startswith("feature")
            }

        encoded_context = (
            encode_context(model, context_features)
            if context_features
            else np.array([])
        )
        feature_array = (
            np.array([encoded_context])
            if encoded_context.size > 0
            else np.empty((1, 0))
        )

        # Store context for later update
        cfg = load_config()
        if cfg.get("redis_enabled", True) and request.context:
            RedisContextStorage.store_context(
                request_id=request_id, model_id=cb_model_id, context=request.context
            )

        if model.update_requests < MINIMUM_UPDATE_REQUESTS:
            internal_variant = random.choice(model.arms)
        else:
            prediction_result = model.predict(feature_array)
            if not isinstance(prediction_result, int):
                print(
                    f"Warning: model.predict for {cb_model_id} returned non-int: {prediction_result}. Falling back to random."
                )
                internal_variant = random.choice(model.arms)
            else:
                internal_variant = prediction_result

        # Update metadata
        model._incr_prediction_request()
        model._incr_latest_prediction_request()
        if internal_variant is not None:
            model._update_prediction_request_trail(internal_variant)

        if model.has_done_initial_fit and internal_variant is not None:
            expectations_raw = model.predict_expectations(feature_array)
            expectations: Dict[Any, float] = {}
            if isinstance(expectations_raw, dict):
                expectations = expectations_raw
            elif isinstance(expectations_raw, list) and expectations_raw:
                if isinstance(expectations_raw[0], dict):
                    expectations = expectations_raw[0]

            if expectations:
                best_arm = max(
                    expectations.keys(),
                    key=lambda arm: expectations.get(arm, float("-inf")),
                )
            else:
                print(
                    f"Warning: Expectations for model {cb_model_id} were empty or in unexpected format. Falling back."
                )
                best_arm = internal_variant

            if internal_variant == best_arm:
                model.exploitation_count += 1

            if model.prediction_requests % 10 == 0:
                ratio = 0.0
                if model.prediction_requests > 0:
                    ratio = 100.0 * model.exploitation_count / model.prediction_requests
                model.exploitation_history.append((model.prediction_requests, ratio))

        if (
            request.context
            and len(request.context) > 0
            and internal_variant is not None
        ):
            model.feature_prediction_trail.append(
                (request.context, internal_variant, datetime.datetime.utcnow())
            )

        recommended_label = (
            model.variant_labels.get(internal_variant, internal_variant)
            if internal_variant is not None
            else "Error: No variant determined"
        )

        save_model_to_redis(cb_model_id, model)

        return {"recommended_variant": recommended_label, "request_id": request_id}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error during fetch variant for {cb_model_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error during variant fetch."
        )
    finally:
        release_lock(cb_model_id, lock_value)


# ------------------------------------------------------------------------------
# Log Streaming
# ------------------------------------------------------------------------------


@app.get("/logs/stream")
async def stream_logs() -> StreamingResponse:
    """Stream logs from backend service Docker containers."""

    async def log_generator() -> AsyncGenerator[str, None]:
        project_name = "scout"
        service_name = "backend"

        try:
            client = docker.from_env()
            client.ping()

            containers = client.containers.list(
                filters={
                    "label": [
                        f"com.docker.compose.project={project_name}",
                        f"com.docker.compose.service={service_name}",
                    ],
                    "status": "running",
                }
            )

            if not containers:
                yield f"No running '{service_name}' containers found for Docker Compose project '{project_name}'.\\n"
                yield "Falling back to generic log messages:\\n"
                fallback_lines = """
                Logs are only returned when running via Docker.
                INFO: this is an info log
                WARNING: this is a warning
                ERROR: this is an error
                TRACE: this is a trace
                """
                for line in fallback_lines.strip().splitlines():
                    yield line + "\\n"
                return

            log_queue = asyncio.Queue()
            active_streamers = len(containers)
            current_loop = asyncio.get_running_loop()

            async def stream_single_container_logs(
                container: DockerContainer,
                queue: asyncio.Queue,
                loop: asyncio.AbstractEventLoop,
            ):
                container_info = f"[{container.short_id} ({container.name})]"

                def blocking_log_reader():
                    try:
                        for log_entry_bytes in container.logs(
                            stream=True, follow=True, timestamps=False, tail=50
                        ):
                            log_line = log_entry_bytes.decode(
                                "utf-8", errors="replace"
                            ).strip()
                            asyncio.run_coroutine_threadsafe(
                                queue.put(f"{container_info} {log_line}\n"), loop
                            )
                    except docker.errors.NotFound:
                        asyncio.run_coroutine_threadsafe(
                            queue.put(
                                f"{container_info} Container not found or stopped streaming.\n"
                            ),
                            loop,
                        )
                    except Exception as e_reader:
                        asyncio.run_coroutine_threadsafe(
                            queue.put(
                                f"{container_info} Error streaming logs: {str(e_reader)}\n"
                            ),
                            loop,
                        )
                    finally:
                        asyncio.run_coroutine_threadsafe(queue.put(None), loop)

                await asyncio.to_thread(blocking_log_reader)

            for container in containers:
                asyncio.create_task(
                    stream_single_container_logs(container, log_queue, current_loop)
                )

            while active_streamers > 0:
                item = await log_queue.get()
                if item is None:
                    active_streamers -= 1
                else:
                    yield item
                log_queue.task_done()

        except docker.errors.DockerException:
            fallback_message = """
            Logs are only returned when running via Docker.
            INFO: this is an info log
            WARNING: this is a warning
            ERROR: this is an error
            TRACE: this is a trace
            """
            for line in fallback_message.strip().splitlines():
                yield line + "\\n"
        except Exception as e:
            yield f"An unexpected error occurred in log streaming: {str(e)}\\n"

    return StreamingResponse(log_generator(), media_type="text/plain")


# ------------------------------------------------------------------------------
# Startup and Metrics
# ------------------------------------------------------------------------------


@app.on_event("startup")
async def startup_event():
    """Initialize metrics and check Redis connection on startup."""
    # setup_multiprocess_metrics() is no longer needed.

    try:
        is_redis_healthy = RedisContextStorage.check_redis_health()
        if is_redis_healthy:
            print(f"Successfully connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
            keys_count = RedisContextStorage.get_all_keys_count()
            print(f"   Found {keys_count} context keys in Redis")
        else:
            print(f"WARNING: Could not connect to Redis at {REDIS_HOST}:{REDIS_PORT}")
            print(
                "   Context storage will not be available unless Redis becomes available."
            )
    except Exception as e:
        print(f"ERROR connecting to Redis: {e}")


# Restore metrics endpoint for per-backend scrape (used by aggregator)


@app.get("/metrics")
async def metrics_endpoint():
    """Return Prometheus metrics for this backend instance."""
    return Response(
        content=get_metrics(),
        media_type="application/openmetrics-text; version=1.0.0; charset=utf-8",
    )
