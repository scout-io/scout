import os
import json
import uuid
import random
import datetime
import asyncio
import docker
import numpy as np
import joblib
import redis
import pickle
import time
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
import docker.errors
from docker.models.containers import Container as DockerContainer

# FastAPI
from fastapi import (
    FastAPI,
    Body,
    HTTPException,
    status,
    Depends,
    Request,
)
from fastapi.responses import StreamingResponse, Response
from fastapi.encoders import jsonable_encoder
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Pydantic
from pydantic import BaseModel, Field

# mabwiser
from mabwiser.mab import MAB, LearningPolicy, NeighborhoodPolicy

# Local utils
from utils import (
    bucket_data,
    estimate_exploitation_exploration_ratio,
    estimate_exploitation_over_time,
)

# Local metrics
from metrics import (
    http_requests_total,
    http_request_duration_seconds,
    model_predictions_total,
    model_updates_total,
    model_rewards_total,
    model_reward_average,
    redis_operations_total,
    redis_operation_duration_seconds,
    active_models,
    model_creation_timestamp,
    context_storage_operations,
    context_storage_size,
    get_metrics,
    setup_multiprocess_metrics,
)


class PrometheusMiddleware(BaseHTTPMiddleware):
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

            # Record metrics
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
    return defaultdict(float)  # float() defaults to 0.0, which is picklable


###############################################################################
#                               GLOBAL CONSTANTS
###############################################################################

CONFIG_FILE: str = "config.json"
MODEL_DIR: str = "models"
MINIMUM_UPDATE_REQUESTS: int = 10

# Model configuration
TRAIL_TIME_WINDOW_MINUTES: int = 60  # Store data for the last 60 minutes
TRAIL_BUCKET_GRANULARITY_SECONDS: int = 60  # 1-minute buckets

# Redis configuration
REDIS_HOST: str = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT: int = int(os.environ.get("REDIS_PORT", 6379))
REDIS_CONTEXT_TTL: int = int(os.environ.get("REDIS_CONTEXT_TTL", 86400))  # 24 hours

# New Redis constants for model storage and locks
REDIS_MODEL_KEY_PREFIX: str = "scout:model:"
REDIS_LOCK_KEY_PREFIX: str = "scout:lock:model:"
LOCK_EXPIRY_MS: int = 30000  # 30 seconds for a lock
LOCK_RETRY_COUNT: int = 5
LOCK_RETRY_DELAY_S: float = 0.2  # 200ms

# Initialize Redis connection pools
# One for text data (contexts) with decode_responses=True
redis_text_pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True,  # For context storage (JSON)
)

# One for binary data (pickled models) with decode_responses=False
redis_binary_pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=False,  # For pickled model storage
)

# Global Redis clients
redis_text_client = redis.Redis(connection_pool=redis_text_pool)
redis_binary_client = redis.Redis(connection_pool=redis_binary_pool)

###############################################################################
#                                CONFIG MANAGEMENT
###############################################################################


def load_config() -> dict:
    """
    Load the application configuration from a JSON file.
    If the config file is missing or corrupt, return default config.
    """
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
                # Merge any missing keys with defaults
                for k, v in default_config.items():
                    data.setdefault(k, v)
                return data
            except json.JSONDecodeError:
                # If the file is corrupt, revert to default
                return default_config
    return default_config


def save_config(config: dict) -> None:
    """
    Save the application configuration to a JSON file.
    """
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


###############################################################################
#                         REDIS CONTEXT STORAGE
###############################################################################


class RedisContextStorage:
    """
    Handles storage and retrieval of contextual features in Redis.

    This class provides methods to store context information when a variant is
    recommended and retrieve it later when updating the model with reward data.
    """

    @staticmethod
    def get_redis_key(request_id: str) -> str:
        """
        Generate a Redis key for the given request ID.

        Args:
            request_id: The unique identifier for the request

        Returns:
            A formatted Redis key string
        """
        return f"scout:context:{request_id}"

    @staticmethod
    def store_context(
        request_id: str,
        model_id: str,
        context: Dict[str, Any],
        ttl_seconds: int = REDIS_CONTEXT_TTL,
    ) -> bool:
        """
        Store context information in Redis with automatic expiration.

        Args:
            request_id: Unique identifier for the request
            model_id: The model ID associated with this context
            context: A dictionary containing context features
            ttl_seconds: Time-to-live in seconds (defaults to 24 hours)

        Returns:
            True if storage was successful, False otherwise
        """
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
        """
        Retrieve context information from Redis by request ID.

        Args:
            request_id: The unique identifier for the request

        Returns:
            A dictionary containing the stored context, or None if not found
        """
        try:
            key = RedisContextStorage.get_redis_key(request_id)
            value = redis_text_client.get(key)
            if not value:
                return None
            assert isinstance(value, str)  # Ensure value is a string for json.loads
            data = json.loads(value)
            return data.get("context")
        except Exception as e:
            print(f"Error retrieving context from Redis: {e}")
            return None

    @staticmethod
    def delete_context(request_id: str) -> bool:
        """
        Delete context information from Redis.

        Args:
            request_id: The unique identifier for the request

        Returns:
            True if deletion was successful, False otherwise
        """
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
        """
        Check if Redis connection is healthy.

        Returns:
            True if Redis is responding, False otherwise
        """
        try:
            return cast(bool, redis_text_client.ping())
        except Exception:
            return False

    @staticmethod
    def get_all_keys_count() -> int:
        """
        Get count of all context keys in Redis (for monitoring).

        Returns:
            Number of context keys currently stored
        """
        try:
            keys = cast(List[str], redis_text_client.keys("scout:context:*"))
            return len(keys)
        except Exception:
            return -1  # Error indicator


###############################################################################
#                          CONTEXT ENCODING HELPERS
###############################################################################


def encode_value(feature_name: str, value: Any, model: "WrappedMAB") -> float:
    """
    Encode a single context value as a numeric value.

    - Booleans are converted to 1 (True) or 0 (False).
    - Numeric values (int/float) are left unchanged.
    - Strings (categorical features) are mapped to an ordinal integer code.
      New values are assigned the next available integer.
    """
    # Note: do an explicit type-check for booleans (since bool is a subclass of int)
    if type(value) is bool:
        return 1 if value else 0
    elif isinstance(value, (int, float)):
        return value
    elif isinstance(value, str):
        if feature_name not in model.context_encoders:
            model.context_encoders[feature_name] = {}
        encoder = model.context_encoders[feature_name]
        if value not in encoder:
            # Assign next available integer code for this feature's categorical value.
            encoder[value] = float(len(encoder))
        return encoder[value]
    else:
        raise ValueError(
            f"Unsupported type for feature '{feature_name}': {type(value)}"
        )


def encode_context(model: "WrappedMAB", context: Dict[str, Any]) -> np.ndarray:
    """
    Given a dictionary of context values (for keys starting with "feature"),
    return a 1D numpy array of numeric encodings.

    The ordering of features is defined by model.features. If a feature is
    missing from the provided context, a default value of 0.0 is used.

    If model.features is empty (first update or prediction) then we initialize
    it from the keys present (sorted alphabetically).
    """
    # Initialize feature ordering on first use if not already set.
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
            # Feature missing in this context; default to 0.0
            encoded.append(0.0)
    return np.array(encoded)


###############################################################################
#                             FASTAPI INITIALIZATION
###############################################################################

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

security = HTTPBearer(auto_error=False)  # Bearer security scheme


def maybe_verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> None:
    """
    If 'protected_api' is True, validate the Bearer token
    against the config's 'auth_token'. Otherwise, do nothing.
    """
    current_config = load_config()

    if not current_config.get("protected_api"):
        # Protection disabled; skip check
        return

    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid token scheme.",
        )

    token = credentials.credentials
    if token != current_config.get("auth_token"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing token."
        )


###############################################################################
#                            Pydantic Request Models
###############################################################################


class CreateModelRequest(BaseModel):
    """
    Request body for creating a new MAB model.

    variants: Maps internal integer arms to user-defined labels (str or int).
    name: A human-readable name for the model.
    """

    variants: Dict[int, Union[str, int]]
    name: str


class UpdateModelRequest(BaseModel):
    """
    Request body for updating an existing MAB model.

    updates: A list of updates, each containing at least 'decision' (the chosen variant)
             and 'reward' (the observed reward). Additional fields such as 'featureN'
             may be included for contextual MAB usage or 'request_id' for context retrieval.
    """

    updates: List[Dict[str, Any]]


class FetchActionRequest(BaseModel):
    """
    Request body for fetching a recommended variant from a model.

    cb_model_id: The identifier of the model to query.
    context: Optional contextual data (e.g., 'featureX': value). If not provided,
             an empty context is assumed.
    request_id: Optional unique identifier for the request. If not provided,
                a new UUID will be generated.
    """

    cb_model_id: str
    context: Optional[Dict[str, Union[str, float, int, bool]]] = Field(
        default_factory=dict
    )
    request_id: Optional[str] = None


class RolloutGlobalVariantRequest(BaseModel):
    """
    Request body for rolling out a global variant for a model.

    variant: The user-facing label or integer for the variant to roll out.
    """

    variant: Union[str, int]


###############################################################################
#                       Wrapped MAB Class (Extended Functionality)
###############################################################################


class WrappedMAB(MAB):
    """
    A wrapper around the MAB class from mabwiser, providing additional
    metadata and tracking for each model.
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
        self.name: str = name
        self.arms: List[int] = arms  # e.g. [0,1,2,...]
        # Maps internal int -> user-supplied label (string or int)
        self.variant_labels: Dict[int, Any] = variant_labels
        # Inverse map: user-supplied label (string or int) -> internal int
        self.label_variants: Dict[Any, int] = label_variants

        # Tracking
        self.features: List[str] = []
        self.created_at: datetime.datetime = datetime.datetime.utcnow()
        self.global_variant: Optional[int] = None
        self.update_requests: int = 0
        self.prediction_requests: int = 0

        self.latest_update_request: Optional[datetime.datetime] = None
        self.latest_prediction_request: Optional[datetime.datetime] = None

        # NEW: Time-windowed aggregation for request trails
        # Stores counts for the last N minutes (e.g., 60 minutes)
        # Outer key: Rounded minute timestamp
        # Inner key: Variant label (for predictions) or "reward" / "decision_variant_X" (for updates)
        # Value: Count or sum of rewards
        self.recent_prediction_counts: Dict[datetime.datetime, Dict[Any, int]] = (
            defaultdict(_create_default_int_dict)  # Use helper function
        )
        self.recent_update_details: Dict[
            datetime.datetime, Dict[str, Union[int, float]]
        ] = defaultdict(
            _create_default_float_dict  # Use helper function
        )  # Stores sum_rewards and decision_counts

        # Configuration for time-windowed data
        self.trail_time_window_minutes: int = 60  # Store data for the last 60 minutes
        self.trail_bucket_granularity_seconds: int = 60  # 1-minute buckets

        # Flags
        self.active: bool = True
        self.global_rolled_out: bool = False
        self.has_done_initial_fit: bool = False

        # Initial data storage (prior to first batch fit)
        self.initial_decisions: List[int] = []
        self.initial_rewards: List[float] = []
        self.initial_contexts: List[np.ndarray] = []

        # Exploitation tracking
        self.exploitation_count: int = 0
        # Each entry is (n_predictions, ratio_percent)
        self.exploitation_history: List[Tuple[int, float]] = []

        # ---------------------------
        # NEW: Context encoding support
        # ---------------------------
        # Stores mappings per feature for categorical (string) values.
        self.context_encoders: Dict[str, Dict[Any, float]] = {}

        # ---------------------------
        # NEW: Track prediction data by context
        # ---------------------------
        # Each record is a tuple: (context dict, chosen internal variant, timestamp)
        self.feature_prediction_trail: List[
            Tuple[Dict[str, Any], int, datetime.datetime]
        ] = []

    def _incr_update_request(self) -> None:
        """Increment the count of update requests."""
        self.update_requests += 1

    def _incr_prediction_request(self) -> None:
        """Increment the count of prediction requests."""
        self.prediction_requests += 1

    def _incr_latest_update_request(self) -> None:
        """Record the timestamp of the latest update request."""
        self.latest_update_request = datetime.datetime.utcnow()

    def _incr_latest_prediction_request(self) -> None:
        """Record the timestamp of the latest prediction request."""
        self.latest_prediction_request = datetime.datetime.utcnow()

    def _update_update_request_trail(
        self, variant: int, reward: Union[float, int]
    ) -> None:
        """Add a (variant, reward) to the update request trail."""
        now = datetime.datetime.utcnow()
        current_bucket_time = self._get_current_time_bucket(now)

        variant_label = self.variant_labels.get(variant, f"unknown_variant_{variant}")

        # Increment count for this decision
        decision_key = f"decision_{variant_label}"
        self.recent_update_details[current_bucket_time][decision_key] = (
            cast(float, self.recent_update_details[current_bucket_time][decision_key])
            + 1
        )

        # Add to total rewards for this bucket
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
        """Add a (variant_label, timestamp) to the prediction request trail."""
        now = datetime.datetime.utcnow()
        current_bucket_time = self._get_current_time_bucket(now)
        variant_label = self.variant_labels.get(variant)
        if variant_label is not None:
            self.recent_prediction_counts[current_bucket_time][variant_label] += 1
        self._prune_old_trail_data(now)

    def _get_current_time_bucket(
        self, timestamp: datetime.datetime
    ) -> datetime.datetime:
        """Calculates the time bucket for a given timestamp."""
        discard_seconds_and_micros = timestamp.replace(second=0, microsecond=0)
        minute_bucket = discard_seconds_and_micros.minute - (
            discard_seconds_and_micros.minute
            % (self.trail_bucket_granularity_seconds // 60)
        )
        return discard_seconds_and_micros.replace(minute=minute_bucket)

    def _prune_old_trail_data(self, current_time: datetime.datetime) -> None:
        """Removes data older than trail_time_window_minutes from aggregated trails."""
        cutoff = current_time - datetime.timedelta(
            minutes=self.trail_time_window_minutes
        )

        # Prune prediction_counts
        keys_to_delete_preds = [k for k in self.recent_prediction_counts if k < cutoff]
        for k in keys_to_delete_preds:
            del self.recent_prediction_counts[k]

        # Prune update_details
        keys_to_delete_updates = [k for k in self.recent_update_details if k < cutoff]
        for k in keys_to_delete_updates:
            del self.recent_update_details[k]

    def _update_feature_list(self, feature: str) -> None:
        """Ensure the feature list includes the given feature."""
        if feature not in self.features:
            self.features.append(feature)

    def deactivate(self) -> None:
        """Deactivate this model (no longer used for predictions)."""
        self.active = False

    def rollout(self, variant: int) -> None:
        """
        Roll out a global variant, meaning that all predictions will
        return this variant thereafter, effectively deactivating
        the MAB logic.
        """
        self.deactivate()
        self.global_rolled_out = True
        self.global_variant = variant

    def clear_global_rollout(self) -> None:
        """
        Clear a previously rolled out global variant. The model
        becomes active again for normal predictions.
        """
        self.active = True
        self.global_rolled_out = False
        self.global_variant = None

    def get_global_variant(self) -> Optional[int]:
        """Return the globally rolled-out variant (if any)."""
        return self.global_variant

    def get_prediction_ratio(self) -> Dict[Any, float]:
        """
        Return a dictionary of variant_label -> ratio of how often
        that variant has been predicted based on recent_prediction_counts.
        If no predictions, all zeros.
        """
        current_counts: Counter = Counter()
        if not self.recent_prediction_counts:
            # Use variant_labels.values() for the user-facing labels
            return {label: 0.0 for label in self.variant_labels.values()}

        for _bucket_time, bucket_counts in self.recent_prediction_counts.items():
            for variant_label, count in bucket_counts.items():
                current_counts[variant_label] += count

        total = sum(current_counts.values())
        if total == 0:
            # Use variant_labels.values() for the user-facing labels
            return {label: 0.0 for label in self.variant_labels.values()}

        # Ensure all known variants are in the output, even if count is 0
        # Iterate over known variant labels from self.variant_labels.values()
        ratios = {
            label: current_counts.get(label, 0) / total
            for label in self.variant_labels.values()
        }
        return ratios


###############################################################################
#                           MODEL PERSISTENCE HELPERS (Redis)
###############################################################################


def save_model_to_redis(model_id: str, model: WrappedMAB) -> None:
    """Persist a given model to Redis using pickle."""
    start_time = time.time()
    try:
        serialized_model = pickle.dumps(model)
        redis_binary_client.set(get_model_redis_key(model_id), serialized_model)
        redis_operations_total.labels(operation="save_model", status="success").inc()
    except Exception as e:
        redis_operations_total.labels(operation="save_model", status="error").inc()
        print(f"Error saving model {model_id} to Redis: {e}")
        raise HTTPException(
            status_code=500, detail=f"Could not save model {model_id} to Redis."
        )
    finally:
        duration = time.time() - start_time
        redis_operation_duration_seconds.labels(operation="save_model").observe(
            duration
        )


def load_model_from_redis(model_id: str) -> Optional[WrappedMAB]:
    """
    Load a model from Redis using pickle.
    """
    start_time = time.time()
    try:
        serialized_model = cast(
            Optional[bytes], redis_binary_client.get(get_model_redis_key(model_id))
        )
        if serialized_model is not None:
            redis_operations_total.labels(
                operation="load_model", status="success"
            ).inc()
            return pickle.loads(serialized_model)
        redis_operations_total.labels(operation="load_model", status="not_found").inc()
        return None
    except Exception as e:
        redis_operations_total.labels(operation="load_model", status="error").inc()
        print(f"Error loading model {model_id} from Redis: {e}")
        return None
    finally:
        duration = time.time() - start_time
        redis_operation_duration_seconds.labels(operation="load_model").observe(
            duration
        )


def delete_model_from_redis(model_id: str) -> bool:
    """Delete a model from Redis. Returns True if deleted, False otherwise."""
    try:
        deleted_count = cast(
            int, redis_binary_client.delete(get_model_redis_key(model_id))
        )
        return deleted_count > 0
    except Exception as e:
        print(f"Error deleting model {model_id} from Redis: {e}")
        return False


def list_model_ids_from_redis() -> List[str]:
    """Lists all model_ids from Redis."""
    model_ids = []
    try:
        # scan_iter with decode_responses=False returns bytes
        for key in redis_binary_client.scan_iter(match=f"{REDIS_MODEL_KEY_PREFIX}*"):
            # Decode the key from bytes to str
            key_str = key.decode("utf-8")
            model_ids.append(key_str.replace(REDIS_MODEL_KEY_PREFIX, ""))
    except Exception as e:
        print(f"Error listing model IDs from Redis: {e}")
    return model_ids


###############################################################################
#                             IN-MEMORY MODEL STORE (REMOVED)
###############################################################################

# models: Dict[str, WrappedMAB] = load_models() # This is now managed in Redis

###############################################################################
#                              ADMIN ENDPOINTS
###############################################################################


@app.get("/admin/get_protection")
def get_protection_status() -> Dict[str, Any]:
    """
    Get the current protection status and auth token (if any).
    """
    cfg = load_config()
    return {
        "protected_api": cfg["protected_api"],
        "auth_token": cfg["auth_token"],
    }


@app.post("/admin/set_protection")
def set_protection(protected_api: bool = Body(...)) -> Dict[str, Any]:
    """
    Enable or disable API protection. If disabled, the auth token is cleared.
    """
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
    """
    Generate (and overwrite) a one-time token for use when protection is enabled.
    """
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
    """
    Check if Redis connection is healthy and return status information.
    """
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
    """
    Get the current model configuration settings.
    """
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
    """
    Update model configuration settings.
    """
    global TRAIL_TIME_WINDOW_MINUTES, TRAIL_BUCKET_GRANULARITY_SECONDS, MINIMUM_UPDATE_REQUESTS

    # Update global variables
    TRAIL_TIME_WINDOW_MINUTES = time_window_minutes
    TRAIL_BUCKET_GRANULARITY_SECONDS = bucket_granularity_seconds
    MINIMUM_UPDATE_REQUESTS = min_update_requests

    # Update config file
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
    """
    Get the current system configuration.
    """
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
    """
    Update system configuration.
    Note: Some changes may require a restart to take effect.
    """
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
    """
    Update Redis configuration.
    Note: Changes require a restart to take effect.
    """
    global REDIS_HOST, REDIS_PORT, REDIS_CONTEXT_TTL

    # Update environment variables
    os.environ["REDIS_HOST"] = host
    os.environ["REDIS_PORT"] = str(port)
    os.environ["REDIS_CONTEXT_TTL"] = str(ttl)

    # Update global variables
    REDIS_HOST = host
    REDIS_PORT = port
    REDIS_CONTEXT_TTL = ttl

    # Update config file
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


###############################################################################
#                           MODEL MANAGEMENT ENDPOINTS
###############################################################################


@app.post("/api/create_model")
async def create_model(
    request: CreateModelRequest,
    _: None = Depends(maybe_verify_token),
) -> Dict[str, str]:
    """
    Create a new MAB model with the given name and variant labels.
    Saves the model to Redis. Returns the ID of the created model.
    """
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

    # Record metrics
    active_models.inc()
    model_creation_timestamp.labels(model_id=cb_model_id).set(time.time())

    return {"message": "Model created successfully", "model_id": cb_model_id}


@app.post("/api/delete_model/{cb_model_id}")
async def delete_model_endpoint(
    cb_model_id: str, _: None = Depends(maybe_verify_token)
) -> Dict[str, str]:
    """
    Deactivate (conceptually, by deleting) and delete a model by its ID from Redis.
    """
    lock_value = uuid.uuid4().hex
    if not acquire_lock_with_retry(cb_model_id, lock_value):
        raise HTTPException(
            status_code=503, detail="Could not acquire lock for model deletion."
        )

    try:
        model = load_model_from_redis(cb_model_id)
        if not model:
            # If model doesn't exist, consider it successfully "deleted" or raise 404
            # For consistency with old behavior (no error if file not found), return success
            # raise HTTPException(status_code=404, detail="Model ID does not exist in Redis")
            return {"message": "Model not found or already deleted"}

        # Deactivation is implicit by deletion from Redis.
        # If explicit deactivation flag on model is desired before delete:
        # model.deactivate()
        # save_model_to_redis(cb_model_id, model) # Save deactivated state if needed

        if delete_model_from_redis(cb_model_id):
            return {"message": "Model deleted from Redis"}
        else:
            # This case might indicate an issue if load_model_from_redis found it
            # but delete_model_from_redis failed.
            raise HTTPException(
                status_code=500,
                detail="Failed to delete model from Redis after loading.",
            )

    finally:
        release_lock(cb_model_id, lock_value)


@app.get("/api/models")
async def get_models_info() -> Any:
    """
    Public endpoint (no token required).
    Lists all available models and their metadata by loading them from Redis.
    Only returns summary information (cheap to compute from loaded model).
    WARNING: This can be slow if many models exist as it loads each one.
    """
    response = []
    model_ids = list_model_ids_from_redis()

    for model_id in model_ids:
        model = load_model_from_redis(model_id)
        if model:  # Model could have been deleted between list and load
            response.append(
                {
                    "model_id": model_id,  # Use model_id from the key
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
    """
    Returns expensive-to-compute details for the specified model loaded from Redis.
    This includes:
      - Bucketed request trail data
      - Exploitation/exploration ratios
      - Feature-specific prediction breakdowns
    This endpoint is intended to be called only when a user expands the detailed view.
    """
    # No lock needed for read-only operation if eventual consistency is acceptable
    model = load_model_from_redis(cb_model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found in Redis")
    details = {
        "request_trail": bucket_data(model.recent_prediction_counts),
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
    """
    Update a model with new decision/reward data. Model is loaded from and
    saved back to Redis. Context can be provided directly or via request_id from Redis.
    """
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
        redis_enabled = cfg.get("redis_enabled", True)  # For context storage

        processed_updates = 0
        missing_context = 0
        redis_hits = 0
        total_reward = 0.0

        for update in request.updates:
            decision = update.get("decision")
            reward = update.get("reward")

            if decision is None or reward is None:
                continue

            # Convert decision from user label to internal integer
            if isinstance(decision, str):
                if decision not in model.label_variants:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid variant label: {decision}",
                    )
                decision = model.label_variants[decision]
            else:
                if decision not in model.arms:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid variant integer: {decision}",
                    )

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
            model_reward_average.labels(model_id=cb_model_id).observe(reward)
            total_reward += reward

            processed_updates += 1

        # Persist updated model to Redis
        if processed_updates > 0:  # Only save if something changed
            save_model_to_redis(cb_model_id, model)

        return {
            "message": "Model updated successfully",
            "processed_updates": processed_updates,
            "missing_context": missing_context,
            "redis_hits": redis_hits,
            "total_reward": total_reward,
        }
    except HTTPException:  # Re-raise HTTPExceptions
        raise
    except Exception as e:  # Catch other exceptions
        # Log e
        print(f"Unexpected error during model update for {cb_model_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error during model update."
        )
    finally:
        if model:  # Only release lock if it was potentially acquired (model was loaded)
            release_lock(cb_model_id, lock_value)


@app.post("/api/rollout_global_variant/{cb_model_id}")
async def rollout_global_variant(
    cb_model_id: str,
    request: RolloutGlobalVariantRequest,
    _: None = Depends(maybe_verify_token),
) -> Dict[str, str]:
    """
    Roll out a global variant for the specified model. Model loaded from and
    saved to Redis. All predictions will return this variant until cleared.
    """
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
            # Should be caught by Pydantic, but as a safeguard
            raise HTTPException(
                status_code=400, detail="Invalid variant type for rollout."
            )

        if internal_variant_id is not None:
            model.rollout(variant=internal_variant_id)
            save_model_to_redis(cb_model_id, model)
            return {
                "message": f"Global variant '{request.variant}' (internal={internal_variant_id}) rolled out for model {cb_model_id}"
            }
        else:  # Should not happen if validation above is correct
            raise HTTPException(
                status_code=500,
                detail="Failed to determine internal variant for rollout.",
            )
    finally:
        if model:
            release_lock(cb_model_id, lock_value)


@app.post("/api/clear_global_variant/{cb_model_id}")
async def clear_global_variant(
    cb_model_id: str,
    _: None = Depends(maybe_verify_token),
) -> Dict[str, str]:
    """
    Clear any previously rolled out global variant for the specified model.
    Model loaded from and saved to Redis.
    """
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
        if model:
            release_lock(cb_model_id, lock_value)


@app.post("/api/fetch_recommended_variant")
async def fetch_recommended_variant(
    request: FetchActionRequest,
    _: None = Depends(maybe_verify_token),
) -> Dict[str, Any]:
    """
    Fetch a recommended variant from the specified model (loaded from Redis),
    optionally providing contextual features.
    The model's metadata is updated and saved back to Redis.
    Context is stored in Redis (context store) keyed by the request_id.
    """
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
        recommended_label: Any = None  # Initialize
        internal_variant: Optional[int] = None  # Initialize

        # Check for global rollout first
        if model.global_rolled_out:
            internal_variant = model.get_global_variant()
            if (
                internal_variant is not None
            ):  # Should always be not None if global_rolled_out is True
                recommended_label = model.variant_labels.get(
                    internal_variant, internal_variant
                )
            else:  # Fallback or error if global_variant is somehow None despite rollout
                recommended_label = "Error: Global rollout active but no variant set"

            cfg = load_config()
            if cfg.get("redis_enabled", True) and request.context:
                RedisContextStorage.store_context(
                    request_id=request_id, model_id=cb_model_id, context=request.context
                )
            # No model state change for prediction/metadata if global variant is served
            # So, no save_model_to_redis here for this branch
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

        # Store context in Redis for later update, regardless of prediction method
        cfg = load_config()
        if cfg.get("redis_enabled", True) and request.context:
            RedisContextStorage.store_context(
                request_id=request_id, model_id=cb_model_id, context=request.context
            )

        if model.update_requests < MINIMUM_UPDATE_REQUESTS:
            internal_variant = random.choice(model.arms)
        else:
            # Ensure model.predict returns int for our arms configuration
            prediction_result = model.predict(feature_array)
            if not isinstance(prediction_result, int):
                # This case should ideally not happen if model.arms are List[int]
                # and mabwiser behaves as expected. Add robust handling/logging.
                print(
                    f"Warning: model.predict for {cb_model_id} returned non-int: {prediction_result}. Falling back to random."
                )
                internal_variant = random.choice(model.arms)
            else:
                internal_variant = prediction_result

        # Metadata updates
        model._incr_prediction_request()
        model._incr_latest_prediction_request()
        if internal_variant is not None:  # internal_variant should be int here
            model._update_prediction_request_trail(internal_variant)

        if model.has_done_initial_fit and internal_variant is not None:
            expectations_raw = model.predict_expectations(feature_array)
            # Ensure expectations is treated as a Dict for type checking
            expectations: Dict[Any, float] = {}
            if isinstance(expectations_raw, dict):
                expectations = expectations_raw
            elif (
                isinstance(expectations_raw, list) and expectations_raw
            ):  # Handle if it's a list of dicts
                if isinstance(expectations_raw[0], dict):
                    expectations = expectations_raw[
                        0
                    ]  # take the first element if it's a list of dicts

            if expectations:  # Ensure expectations is not empty and is a dict
                # Get the arm (key) with the maximum value (expectation)
                best_arm = max(
                    expectations.keys(),
                    key=lambda arm: expectations.get(arm, float("-inf")),
                )
            else:
                # Fallback if expectations is empty or not in expected format
                # This might indicate an issue with model.predict_expectations or feature_array
                print(
                    f"Warning: Expectations for model {cb_model_id} were empty or in unexpected format. Falling back."
                )
                best_arm = (
                    internal_variant  # Or some other robust default or error handling
                )

            if internal_variant == best_arm:
                model.exploitation_count += 1

            if model.prediction_requests % 10 == 0:
                ratio = 0.0
                if model.prediction_requests > 0:  # Avoid division by zero
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

        save_model_to_redis(cb_model_id, model)  # Save updated model state

        return {"recommended_variant": recommended_label, "request_id": request_id}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error during fetch variant for {cb_model_id}: {e}")
        # Potentially log the full stack trace for e
        raise HTTPException(
            status_code=500, detail="Internal server error during variant fetch."
        )
    finally:
        if model:  # Only release if model was loaded (lock potentially acquired)
            release_lock(cb_model_id, lock_value)


###############################################################################
#                            HELPER: Feature Prediction Data
###############################################################################


def compute_feature_prediction_data(model: WrappedMAB) -> Dict[str, Any]:
    """
    Process model.feature_prediction_trail to compute, for each feature,
    a bucketed breakdown of prediction ratios per variant.
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
        # Determine feature type.
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
                # Treat each value as its own bucket.
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
            # For categorical or boolean features, each distinct value is a bucket.
            for val, variant in entries:
                bucket_label = str(val)
                buckets.setdefault(bucket_label, []).append(variant)

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
        if feature_type == "numeric":
            try:
                bucket_list.sort(key=lambda x: float(x["bucket"].split("-")[0]))
            except Exception:
                bucket_list.sort(key=lambda x: x["bucket"])
        else:
            bucket_list.sort(key=lambda x: x["bucket"])
        result[feature] = {"type": feature_type, "buckets": bucket_list}
    return result


###############################################################################
#                            LOG STREAMING ENDPOINT
###############################################################################


@app.get("/logs/stream")
async def stream_logs() -> StreamingResponse:
    """
    Stream logs from all 'backend' service Docker containers for the 'scout' project in real time.
    This endpoint is public (no token check).
    """

    async def log_generator() -> AsyncGenerator[str, None]:
        """
        Yields log lines from running 'backend' Docker containers for the 'scout' project.
        If Docker is not available or no relevant containers are found, provides fallback messages.
        """
        project_name = "scout"  # Assumed from workspace path
        service_name = "backend"  # Based on 'docker compose ... --scale backend=...'

        try:
            client = docker.from_env()
            client.ping()  # Quick check for Docker daemon responsiveness

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
                # Original static fallback messages
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
            current_loop = asyncio.get_running_loop()  # Get current event loop

            async def stream_single_container_logs(
                container: DockerContainer,
                queue: asyncio.Queue,
                loop: asyncio.AbstractEventLoop,
            ):
                container_info = f"[{container.short_id} ({container.name})]"

                def blocking_log_reader():
                    try:
                        # Stream new logs, and get the last 50 lines
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
                    except Exception as e_reader:  # Renamed to avoid conflict
                        asyncio.run_coroutine_threadsafe(
                            queue.put(
                                f"{container_info} Error streaming logs: {str(e_reader)}\n"
                            ),
                            loop,
                        )
                    finally:
                        # Signal that this container's log stream has ended for this task
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
            # Original fallback if Docker daemon itself is the issue
            original_fallback_message = """
            Logs are only returned when running via Docker.
            INFO: this is an info log
            WARNING: this is a warning
            ERROR: this is an error
            TRACE: this is a trace
            """
            for line in original_fallback_message.strip().splitlines():
                yield line + "\\n"
        except Exception as e:
            # Catch-all for other unexpected errors
            yield f"An unexpected error occurred in log streaming: {str(e)}\\n"

    return StreamingResponse(log_generator(), media_type="text/plain")


###############################################################################
#                            STARTUP EVENT HANDLERS
###############################################################################


@app.on_event("startup")
async def startup_event():
    """
    Startup event handler that runs when the application starts.
    Checks Redis connection and initializes metrics.
    """
    # Initialize multiprocess metrics
    setup_multiprocess_metrics()

    # Check Redis connection
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


###############################################################################
#                            HELPER: Redis Key Generation
###############################################################################


def get_model_redis_key(model_id: str) -> str:
    return f"{REDIS_MODEL_KEY_PREFIX}{model_id}"


def get_lock_redis_key(model_id: str) -> str:
    return f"{REDIS_LOCK_KEY_PREFIX}{model_id}"


###############################################################################
#                            HELPER: Redis Lock Management
###############################################################################


def acquire_lock_with_retry(model_id: str, lock_value: str) -> bool:
    """
    Attempt to acquire a distributed lock for a model_id with retries.
    """
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
    """
    Release a distributed lock.
    Uses a Lua script to ensure atomicity of checking value before deleting.
    """
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
        # Log this error, as failure to release a lock can be problematic
        print(f"Error releasing lock {lock_key} for value {lock_value}: {e}")


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.
    Returns metrics in OpenMetrics format.
    """
    return Response(
        content=get_metrics(),
        media_type="application/openmetrics-text; version=1.0.0; charset=utf-8",
    )
