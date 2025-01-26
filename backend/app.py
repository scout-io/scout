import asyncio
import random
import docker.errors
from fastapi import Body, FastAPI, HTTPException, status, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import docker
from pydantic import BaseModel
from typing import AsyncGenerator, Dict, Any, Union
from mabwiser.mab import MAB, LearningPolicy, NeighborhoodPolicy
import numpy as np
from collections import Counter
import datetime
import uuid
import json
import os
import joblib
import zlib  # We'll use this for hashing strings
from utils import (
    bucket_data,
    estimate_exploitation_exploration_ratio,
    estimate_relative_reward_increase,
    estimate_exploitation_over_time,
)

CONFIG_FILE = "config.json"


def load_config() -> dict:
    """Load config from a JSON file or return defaults."""
    default_config = {
        "host": "127.0.0.1",
        "port": 8000,
        "debug": False,
        "protected_api": False,  # <-- We'll store whether API is protected
        "auth_token": None,  # <-- We'll store the token here
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                data = json.load(f)
                # Merge any missing keys with defaults
                for k, v in default_config.items():
                    data.setdefault(k, v)
                return data
            except json.JSONDecodeError:
                # If corrupt, revert to default
                return default_config
    return default_config


def save_config(config: dict):
    """Save config to a JSON file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


config = load_config()

app = FastAPI(title="Scout")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # The origin of the frontend app
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Create a Bearer security scheme
security = HTTPBearer(auto_error=False)


def maybe_verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    If 'protected_api' is True, we validate the Bearer token
    against the config's 'auth_token'. Otherwise, we do nothing.
    """
    current_config = load_config()

    # If not protecting, skip check entirely
    if not current_config.get("protected_api"):
        return

    # If we *are* protecting, but there's no credentials or bad scheme, raise an exception
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


class ConfigModel(BaseModel):
    host: str
    port: int
    debug: bool


#
# ------------------- Hashing Trick Helper -------------------
#

N_HASH_BUCKETS = 1  # You can tune this


def hash_features(context: Dict[str, Any]) -> np.ndarray:
    """
    Convert a dictionary of {feature_name -> value} into a single
    numeric vector of length N_HASH_BUCKETS using a simple hashing trick.

    Steps:
    1) For each (feature_name, feature_value):
       - Convert value to a numeric weight (bool->0/1, numeric->float, string->1).
       - Build a token string, e.g. "feature_name=feature_value".
       - Hash it to find the bucket index and sign.
       - out[index] += sign * weight
    2) Return out, a 1D numpy array of length N_HASH_BUCKETS.
    """
    out = np.zeros(N_HASH_BUCKETS, dtype=float)

    for key, value in context.items():
        # Determine numeric weight
        if isinstance(value, bool):
            weight = float(value)  # True=1.0, False=0.0
        elif isinstance(value, (int, float)):
            weight = float(value)
        elif isinstance(value, str):
            # For a string, just treat existence as weight=1.0
            weight = 1.0
        else:
            raise ValueError(f"Unsupported feature type: {type(value).__name__}")

        # Create token from "key=value"
        token = f"{key}={value}"
        h = zlib.adler32(token.encode("utf-8")) & 0xFFFFFFFF

        # Bucket index
        index = h % N_HASH_BUCKETS

        # Sign can be derived from the next bits, or something more advanced.
        # This helps distribute collisions. Example:
        sign = 1 if ((h // N_HASH_BUCKETS) % 2) == 0 else -1

        # Accumulate
        out[index] += sign * weight

    return out


#
# ------------------- wMAB & Model Persistence -------------------
#

MINIMUM_UPDATE_REQUESTS = 5


class wMAB(MAB):
    def __init__(
        self,
        name: str,
        arms,
        variant_labels: Dict[int, Any],
        label_variants: Dict[Any, int],
        *args,
        **kwargs,
    ):
        super().__init__(arms=arms, *args, **kwargs)
        self.name: str = name

        # Inherited from the user
        self.arms = arms  # e.g. [0,1,2,...]
        # Maps internal int -> user-supplied label (string or int)
        self.variant_labels = variant_labels
        # Inverse map: user-supplied label (string or int) -> internal int
        self.label_variants = label_variants

        self.features: list[str] = []  # Optionally track feature names
        self.created_at: datetime.datetime = datetime.datetime.utcnow()
        self.global_variant = None
        self.update_requests: int = 0
        self.prediction_requests: int = 0

        self.latest_update_request: datetime.datetime | None = None
        self.latest_prediction_request: datetime.datetime | None = None

        self.update_request_trail: list[tuple | None] = []
        self.prediction_request_trail: list[tuple | None] = []

        self.active: bool = True
        self.global_rolled_out: bool = False

        # We'll store data for the first $MINIMUM_UPDATE_REQUESTS updates
        self.initial_decisions = []
        self.initial_rewards = []
        self.initial_contexts = []
        self.has_done_initial_fit = False

        # ---------------- Exploitation tracking ----------------
        self.exploitation_count = 0
        # Store (n, ratio_percent) every time we log
        self.exploitation_history: list[tuple[int, float]] = []

    def _incr_update_request(self) -> None:
        self.update_requests += 1

    def _incr_prediction_request(self) -> None:
        self.prediction_requests += 1

    def _incr_latest_update_request(self) -> None:
        self.latest_update_request = datetime.datetime.utcnow()

    def _incr_latest_prediction_request(self) -> None:
        self.latest_prediction_request = datetime.datetime.utcnow()

    def _update_update_request_trail(self, variant: int, reward: float | int) -> None:
        self.update_request_trail.append((variant, reward))

    def _update_prediction_request_trail(self, variant: int) -> None:
        self.prediction_request_trail.append(
            (self.variant_labels.get(variant), datetime.datetime.utcnow())
        )

    def _update_feature_list(self, feature: str) -> None:
        """
        (Optional) Track encountered feature names for debugging.
        Not strictly needed for hashing, but can be useful for logs/UI.
        """
        if feature not in self.features:
            self.features.append(feature)

    def deactivate(self) -> None:
        self.active = False

    def rollout(self, variant: int) -> None:
        self.deactivate()
        self.global_rolled_out = True
        self.global_variant = variant

    def clear_global_rollout(self) -> None:
        self.active = True
        self.global_rolled_out = False
        self.global_variant = None

    def get_global_variant(self) -> int | None:
        return self.global_variant

    def get_prediction_ratio(self) -> dict:
        if not self.prediction_request_trail:
            return {variant: 0 for variant in self.label_variants.keys()}

        counts = Counter([i[0] for i in self.prediction_request_trail])
        total = sum(counts.values())
        if total == 0:
            return {variant: 0 for variant in self.label_variants.keys()}
        return {k: v / total for k, v in counts.items()}


MODEL_DIR = "models"


def save_model(cb_model_id, model):
    if not os.path.exists(MODEL_DIR):
        os.makedirs(MODEL_DIR)
    joblib.dump(model, os.path.join(MODEL_DIR, f"{cb_model_id}.joblib"))


def load_models():
    loaded_models = {}
    if not os.path.exists(MODEL_DIR):
        os.makedirs(MODEL_DIR)
    for filename in os.listdir(MODEL_DIR):
        if filename.endswith(".joblib"):
            cb_model_id = filename[:-7]  # Remove '.joblib' extension
            model = joblib.load(os.path.join(MODEL_DIR, filename))
            loaded_models[cb_model_id] = model
    return loaded_models


def delete_model_file(cb_model_id):
    file_path = os.path.join(MODEL_DIR, f"{cb_model_id}.joblib")
    if os.path.exists(file_path):
        os.remove(file_path)


models: dict[str, wMAB] = load_models()


#
# ------------------- Request Models -------------------
#


class CreateModelRequest(BaseModel):
    variants: Dict[int, Union[str, int]]
    name: str


class UpdateModelRequest(BaseModel):
    updates: list[dict]


class FetchActionRequest(BaseModel):
    cb_model_id: str
    context: dict


class RolloutGlobalVariantRequest(BaseModel):
    variant: Union[str, int]


#
# ------------------- ADMIN ENDPOINTS -------------------
#


@app.get("/admin/get_protection")
def get_protection_status():
    cfg = load_config()
    return {
        "protected_api": cfg["protected_api"],
        "auth_token": cfg["auth_token"],
    }


@app.post("/admin/set_protection")
def set_protection(protected_api: bool = Body(...)):
    cfg = load_config()
    cfg["protected_api"] = protected_api

    # If turning off, remove the token
    if not protected_api:
        cfg["auth_token"] = None
    save_config(cfg)
    return {
        "protected_api": protected_api,
        "auth_token": cfg["auth_token"],
    }


@app.post("/admin/generate_token")
def generate_token():
    """
    Generate a one-time token. Overwrites any existing token.
    Only relevant if protected_api is True.
    """
    cfg = load_config()
    if not cfg.get("protected_api"):
        raise HTTPException(
            status_code=400,
            detail="API protection must be enabled before generating a token.",
        )
    # Create a random token
    new_token = uuid.uuid4().hex  # for demonstration
    cfg["auth_token"] = new_token
    save_config(cfg)
    return {"token": new_token}


#
# ------------------- PROTECTED ENDPOINTS -------------------
#


@app.post("/api/create_model")
async def create_model(
    request: CreateModelRequest,
    _: Any = Depends(maybe_verify_token),  # <-- require token if protected_api
):
    cb_model_id = str(uuid.uuid4())
    arms = sorted(request.variants.keys())
    variant_labels = {k: v for k, v in request.variants.items()}
    label_variants = {v: k for k, v in request.variants.items()}

    models[cb_model_id] = wMAB(
        name=request.name,
        arms=arms,
        variant_labels=variant_labels,
        label_variants=label_variants,
        learning_policy=LearningPolicy.UCB1(alpha=1.25),
        neighborhood_policy=NeighborhoodPolicy.TreeBandit(),
    )
    save_model(cb_model_id, models[cb_model_id])
    return {"message": "Model created successfully", "model_id": cb_model_id}


@app.post("/api/delete_model/{cb_model_id}")
async def delete_model(cb_model_id: str, _: Any = Depends(maybe_verify_token)):
    if cb_model_id not in models:
        raise HTTPException(status_code=400, detail="Model ID does not exist")
    models[cb_model_id].deactivate()
    save_model(cb_model_id, models[cb_model_id])
    delete_model_file(cb_model_id)
    del models[cb_model_id]
    return {"message": "Model deactivated and deleted"}


@app.get("/api/models")
async def get_models():
    # PUBLIC endpoint (no token check) for demonstration
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
            }
        )
    return jsonable_encoder(response)


@app.post("/api/update_model/{cb_model_id}")
async def update_model(
    cb_model_id: str, request: UpdateModelRequest, _: Any = Depends(maybe_verify_token)
):
    model = models.get(cb_model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    for update in request.updates:
        decision = update["decision"]
        reward = update["reward"]

        # Convert decision from user label to internal int if needed
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

        # Gather all keys that are not 'decision' or 'reward' as context
        context_features = {
            k: v for k, v in update.items() if k not in ("decision", "reward")
        }

        # (Optional) record these feature names in the model's .features for reference
        for fname in context_features.keys():
            model._update_feature_list(fname)

        # Use the hashing trick to get a numeric vector
        hashed_vector = hash_features(context_features)  # shape=(N_HASH_BUCKETS,)
        hashed_vector = hashed_vector.reshape(1, -1)  # shape=(1, N_HASH_BUCKETS)

        # Accumulate first MINIMUM_UPDATE_REQUESTS updates, do one big fit, then partial_fit
        if model.update_requests < MINIMUM_UPDATE_REQUESTS:
            model.initial_decisions.append(decision)
            model.initial_rewards.append(reward)
            model.initial_contexts.append(hashed_vector[0])  # single row
            model._incr_update_request()
            model._incr_latest_update_request()
            model._update_update_request_trail(variant=decision, reward=reward)

            if model.update_requests == MINIMUM_UPDATE_REQUESTS:
                all_contexts = np.array(model.initial_contexts)
                all_decisions = np.array(model.initial_decisions)
                all_rewards = np.array(model.initial_rewards)

                model.fit(
                    decisions=all_decisions, rewards=all_rewards, contexts=all_contexts
                )
                model.has_done_initial_fit = True

        else:
            # After MINIMUM_UPDATE_REQUESTS, we do partial_fit
            if not model.has_done_initial_fit:
                # Safety check: do the full fit if we never did
                all_contexts = np.array(model.initial_contexts)
                all_decisions = np.array(model.initial_decisions)
                all_rewards = np.array(model.initial_rewards)

                model.fit(
                    decisions=all_decisions, rewards=all_rewards, contexts=all_contexts
                )
                model.has_done_initial_fit = True

            # Partial fit
            model.partial_fit(
                decisions=[decision], rewards=[reward], contexts=hashed_vector
            )
            model._incr_update_request()
            model._incr_latest_update_request()
            model._update_update_request_trail(variant=decision, reward=reward)

    # Periodically save
    if model.update_requests % 100 == 0:
        save_model(cb_model_id, model)

    return {"message": "Model updated successfully"}


@app.post("/api/rollout_global_variant/{cb_model_id}")
async def rollout_global_variant(
    cb_model_id: str,
    request: RolloutGlobalVariantRequest,
    _: Any = Depends(maybe_verify_token),
):
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
async def clear_global_variant(cb_model_id: str, _: Any = Depends(maybe_verify_token)):
    model = models.get(cb_model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    model.clear_global_rollout()
    save_model(cb_model_id, model)
    return {"message": f"Global variant cleared for model {cb_model_id}"}


@app.post("/api/fetch_recommended_variant")
async def fetch_recommended_variant(
    request: FetchActionRequest, _: Any = Depends(maybe_verify_token)
):
    cb_model_id = request.cb_model_id
    model = models.get(cb_model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    # Check for global rollout first
    if model.global_rolled_out and model.get_global_variant() is not None:
        internal_variant = model.get_global_variant()
        recommended_label = model.variant_labels.get(internal_variant, internal_variant)
        return {"recommended_variant": recommended_label}

    # Convert context to hashed feature vector (or your normal transform)
    hashed_vector = hash_features(request.context).reshape(1, -1)

    # If fewer than MINIMUM_UPDATE_REQUESTS updates, random arm (no fit yet)
    if model.update_requests < MINIMUM_UPDATE_REQUESTS:
        internal_variant = random.choice(model.arms)
    else:
        # If partial fits or the initial big fit has been done:
        internal_variant = model.predict(hashed_vector)

    # ---------------- Exploitation check: only if initial fit is done ----------------
    if model.has_done_initial_fit:
        expectations = model.predict_expectations(hashed_vector)  # shape: (1, #arms)
        best_arm = max(expectations, key=expectations.get)  # purely greedy choice

        if internal_variant == best_arm:
            model.exploitation_count += 1

        # Now increment the standard prediction_requests
        model._incr_prediction_request()
        model._incr_latest_prediction_request()
        model._update_prediction_request_trail(internal_variant)

        # Every 10 predictions, record exploitation ratio
        if model.prediction_requests % 10 == 0:
            ratio = 100.0 * model.exploitation_count / model.prediction_requests
            model.exploitation_history.append((model.prediction_requests, ratio))
    else:
        # If not yet fit, skip exploitation logic
        model._incr_prediction_request()
        model._incr_latest_prediction_request()
        model._update_prediction_request_trail(internal_variant)
    # ----------------------------------------------------------------------------------

    recommended_label = model.variant_labels.get(internal_variant, internal_variant)

    # Periodically save
    if model.prediction_requests % 100 == 0:
        save_model(cb_model_id, model)

    return {"recommended_variant": recommended_label}


@app.get("/logs/stream")
def stream_logs():
    """
    Streams logs from a Docker container in real time.
    No token required by design (public).
    """

    def log_generator():
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
