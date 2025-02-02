import os
import json
import uuid
import random
import datetime
import asyncio
import docker
import numpy as np
import joblib
from collections import Counter
from typing import (
    Dict,
    Any,
    Union,
    List,
    Tuple,
    Optional,
    Generator,
)
import docker.errors

# FastAPI
from fastapi import (
    FastAPI,
    Body,
    HTTPException,
    status,
    Depends,
)
from fastapi.responses import StreamingResponse
from fastapi.encoders import jsonable_encoder
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware

# Pydantic
from pydantic import BaseModel, Field

# mabwiser
from mabwiser.mab import MAB, LearningPolicy, NeighborhoodPolicy

# Local utils
from utils import (
    bucket_data,
    estimate_exploitation_exploration_ratio,
    estimate_relative_reward_increase,
    estimate_exploitation_over_time,
)

###############################################################################
#                               GLOBAL CONSTANTS
###############################################################################

CONFIG_FILE: str = "config.json"
MODEL_DIR: str = "models"
MINIMUM_UPDATE_REQUESTS: int = 10

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
            # Assign next available integer code for this feature’s categorical value.
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Adjust as needed
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
             may be included for contextual MAB usage.
    """

    updates: List[Dict[str, Any]]


class FetchActionRequest(BaseModel):
    """
    Request body for fetching a recommended variant from a model.

    cb_model_id: The identifier of the model to query.
    context: Optional contextual data (e.g., 'featureX': value). If not provided,
             an empty context is assumed.
    """

    cb_model_id: str
    context: Optional[Dict[str, Union[str, float, int, bool]]] = Field(
        default_factory=dict
    )


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

        # Trails
        self.update_request_trail: List[Tuple[Optional[int], Optional[float]]] = []
        self.prediction_request_trail: List[Tuple[Any, datetime.datetime]] = []

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
        self.update_request_trail.append((variant, reward))

    def _update_prediction_request_trail(self, variant: int) -> None:
        """Add a (variant_label, timestamp) to the prediction request trail."""
        self.prediction_request_trail.append(
            (self.variant_labels.get(variant), datetime.datetime.utcnow())
        )

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
        that variant has been predicted. If no predictions, all zeros.
        """
        if not self.prediction_request_trail:
            return {label: 0.0 for label in self.label_variants.keys()}

        counts = Counter([item[0] for item in self.prediction_request_trail])
        total = sum(counts.values())
        if total == 0:
            return {label: 0.0 for label in self.label_variants.keys()}
        return {k: v / total for k, v in counts.items()}


###############################################################################
#                           MODEL PERSISTENCE HELPERS
###############################################################################


def save_model(cb_model_id: str, model: WrappedMAB) -> None:
    """
    Persist a given model to disk with joblib.
    """
    if not os.path.exists(MODEL_DIR):
        os.makedirs(MODEL_DIR)
    joblib.dump(model, os.path.join(MODEL_DIR, f"{cb_model_id}.joblib"))


def load_models() -> Dict[str, WrappedMAB]:
    """
    Load all models from disk on startup.
    Returns a dictionary of model_id -> WrappedMAB instance.
    """
    loaded_models: Dict[str, WrappedMAB] = {}
    if not os.path.exists(MODEL_DIR):
        os.makedirs(MODEL_DIR)
        return loaded_models

    for filename in os.listdir(MODEL_DIR):
        if filename.endswith(".joblib"):
            cb_model_id = filename[:-7]  # remove '.joblib'
            model: WrappedMAB = joblib.load(os.path.join(MODEL_DIR, filename))
            loaded_models[cb_model_id] = model

    return loaded_models


def delete_model_file(cb_model_id: str) -> None:
    """
    Remove the model file for the given ID from disk, if it exists.
    """
    file_path = os.path.join(MODEL_DIR, f"{cb_model_id}.joblib")
    if os.path.exists(file_path):
        os.remove(file_path)


###############################################################################
#                             IN-MEMORY MODEL STORE
###############################################################################

models: Dict[str, WrappedMAB] = load_models()


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
    Returns the ID of the created model.
    """
    cb_model_id = str(uuid.uuid4())
    arms = sorted(request.variants.keys())
    variant_labels = {k: v for k, v in request.variants.items()}
    label_variants = {v: k for k, v in request.variants.items()}

    models[cb_model_id] = WrappedMAB(
        name=request.name,
        arms=arms,
        variant_labels=variant_labels,
        label_variants=label_variants,
        learning_policy=LearningPolicy.EpsilonGreedy(),
        neighborhood_policy=NeighborhoodPolicy.TreeBandit(),
    )

    save_model(cb_model_id, models[cb_model_id])
    return {"message": "Model created successfully", "model_id": cb_model_id}


@app.post("/api/delete_model/{cb_model_id}")
async def delete_model_endpoint(
    cb_model_id: str, _: None = Depends(maybe_verify_token)
) -> Dict[str, str]:
    """
    Deactivate and delete a model by its ID.
    """
    if cb_model_id not in models:
        raise HTTPException(status_code=400, detail="Model ID does not exist")

    models[cb_model_id].deactivate()
    save_model(cb_model_id, models[cb_model_id])
    delete_model_file(cb_model_id)
    del models[cb_model_id]

    return {"message": "Model deactivated and deleted"}


@app.get("/api/models")
async def get_models_info() -> Any:
    """
    Public endpoint (no token required).
    Lists all available models and their metadata.
    """
    response = []
    for model_id, model in models.items():
        response.append(
            {
                "model_id": model_id,
                "name": model.name,
                "variants": list(model.variant_labels.values()),
                "global_rolled_out": model.global_rolled_out,
                "global_variant": (
                    model.variant_labels.get(model.global_variant, model.global_variant)
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
                "request_trail": bucket_data(model.prediction_request_trail),
                "exploit_explore_ratio": estimate_exploitation_exploration_ratio(model),
                "reward_summary": estimate_relative_reward_increase(model),
                "exploitation_status": estimate_exploitation_over_time(model),
                "feature_prediction_data": compute_feature_prediction_data(model),
            }
        )
    return jsonable_encoder(response)


@app.post("/api/update_model/{cb_model_id}")
async def update_model(
    cb_model_id: str,
    request: UpdateModelRequest,
    _: None = Depends(maybe_verify_token),
) -> Dict[str, str]:
    """
    Update a model with new decision/reward data (and optional context features).
    Stores the first 100 updates to perform a single batch fit, then uses
    partial_fit for subsequent updates.
    """
    model = models.get(cb_model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    for update in request.updates:
        decision = update["decision"]
        reward = update["reward"]

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

        # -------------------------------
        # Encode context features using our helper.
        # -------------------------------
        # Extract only keys starting with "feature"
        context_features = {k: v for k, v in update.items() if k.startswith("feature")}
        encoded_context = encode_context(model, context_features)
        # Wrap into 2D array when calling fit/partial_fit.
        context_array = np.array([encoded_context])
        # --------------------------------

        # =========================================
        # Accumulate first 100 updates, do batch fit
        if model.update_requests < MINIMUM_UPDATE_REQUESTS:
            model.initial_decisions.append(decision)
            # Store the 1D encoded context vector.
            model.initial_contexts.append(encoded_context)
            model.initial_rewards.append(reward)
            model._incr_update_request()
            model._incr_latest_update_request()
            model._update_update_request_trail(variant=decision, reward=reward)

            if model.update_requests == MINIMUM_UPDATE_REQUESTS:
                # Perform batch fit
                all_contexts = np.array(model.initial_contexts)
                all_decisions = np.array(model.initial_decisions)
                all_rewards = np.array(model.initial_rewards)

                model.fit(
                    decisions=all_decisions, rewards=all_rewards, contexts=all_contexts
                )
                model.has_done_initial_fit = True
        else:
            # Beyond MINIMUM_UPDATE_REQUESTS updates, do partial_fit
            if not model.has_done_initial_fit:
                # Safety check: if we never flipped has_done_initial_fit for some reason
                all_contexts = np.array(model.initial_contexts)
                all_decisions = np.array(model.initial_decisions)
                all_rewards = np.array(model.initial_rewards)

                model.fit(
                    decisions=all_decisions, rewards=all_rewards, contexts=all_contexts
                )
                model.has_done_initial_fit = True

            model.partial_fit(
                decisions=[decision], rewards=[reward], contexts=context_array
            )
            model._incr_update_request()
            model._incr_latest_update_request()
            model._update_update_request_trail(variant=decision, reward=reward)
        # =========================================

    # Persist to disk every 100 updates
    if model.update_requests % 100 == 0:
        save_model(cb_model_id, model)

    return {"message": "Model updated successfully"}


@app.post("/api/rollout_global_variant/{cb_model_id}")
async def rollout_global_variant(
    cb_model_id: str,
    request: RolloutGlobalVariantRequest,
    _: None = Depends(maybe_verify_token),
) -> Dict[str, str]:
    """
    Roll out a global variant for the specified model. All predictions
    will return this variant until cleared.
    """
    model = models.get(cb_model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    variant = request.variant
    if isinstance(variant, str):
        if variant not in model.label_variants:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid variant label: {variant}",
            )
        variant = model.label_variants[variant]
    else:
        if variant not in model.arms:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid variant integer: {variant}",
            )

    model.rollout(variant=variant)
    save_model(cb_model_id, model)

    return {
        "message": f"Global variant '{request.variant}' (internal={variant}) rolled out for model {cb_model_id}"
    }


@app.post("/api/clear_global_variant/{cb_model_id}")
async def clear_global_variant(
    cb_model_id: str,
    _: None = Depends(maybe_verify_token),
) -> Dict[str, str]:
    """
    Clear any previously rolled out global variant for the specified model.
    """
    model = models.get(cb_model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    model.clear_global_rollout()
    save_model(cb_model_id, model)

    return {"message": f"Global variant cleared for model {cb_model_id}"}


@app.post("/api/fetch_recommended_variant")
async def fetch_recommended_variant(
    request: FetchActionRequest,
    _: None = Depends(maybe_verify_token),
) -> Dict[str, Any]:
    """
    Fetch a recommended variant from the specified model,
    optionally providing contextual features.
    """
    cb_model_id = request.cb_model_id
    model = models.get(cb_model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    # Check for global rollout
    if model.global_rolled_out and model.get_global_variant() is not None:
        internal_variant = model.get_global_variant()
        recommended_label = model.variant_labels.get(internal_variant, internal_variant)
        return {"recommended_variant": recommended_label}

    # -------------------------------
    # Encode context for prediction.
    # If no context is provided, use an empty 2D array.
    if request.context:
        context_features = {
            k: v for k, v in request.context.items() if k.startswith("feature")
        }
        encoded_context = encode_context(model, context_features)
        feature_array = np.array([encoded_context])
    else:
        feature_array = np.empty((1, 0))
    # -------------------------------

    # If not enough updates for an initial fit, random choice
    if model.update_requests < MINIMUM_UPDATE_REQUESTS:
        internal_variant = random.choice(model.arms)
    else:
        internal_variant = model.predict(feature_array)

    # Exploitation check only if initial fit is done
    if model.has_done_initial_fit:
        expectations = model.predict_expectations(feature_array)
        best_arm = max(expectations, key=expectations.get)
        if internal_variant == best_arm:
            model.exploitation_count += 1

        model._incr_prediction_request()
        model._incr_latest_prediction_request()
        model._update_prediction_request_trail(internal_variant)

        # Every 10 predictions, record exploitation ratio
        if model.prediction_requests % 10 == 0:
            ratio = 100.0 * model.exploitation_count / model.prediction_requests
            model.exploitation_history.append((model.prediction_requests, ratio))
    else:
        model._incr_prediction_request()
        model._incr_latest_prediction_request()
        model._update_prediction_request_trail(internal_variant)

    # NEW: If context is provided, record feature-specific prediction data.
    if request.context and len(request.context) > 0:
        model.feature_prediction_trail.append(
            (request.context, internal_variant, datetime.datetime.utcnow())
        )

    recommended_label = model.variant_labels.get(internal_variant, internal_variant)

    # Persist to disk every 100 predictions
    if model.prediction_requests % 100 == 0:
        save_model(cb_model_id, model)

    return {"recommended_variant": recommended_label}


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
def stream_logs() -> StreamingResponse:
    """
    Stream logs from a Docker container in real time.
    This endpoint is public (no token check).
    """

    def log_generator() -> Generator[str, None, None]:
        """
        Yields log lines from a running Docker container.
        If the container is not found or not running in Docker, returns a static message.
        """
        try:
            client = docker.from_env()
            container = client.containers.get("fastapi_container")
            log_stream = container.logs(stream=True, follow=True)
            for line in log_stream:
                yield line.decode("utf-8")
        except docker.errors.DockerException:
            message = """
            Logs are only returned when running via Docker.
            INFO: this is an info log
            WARNING: this is a warning
            ERROR: this is an error
            TRACE: this is a trace
            """
            for line in message.strip().splitlines():
                yield line + "\n"

    return StreamingResponse(log_generator(), media_type="text/plain")
