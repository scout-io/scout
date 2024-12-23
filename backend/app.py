import asyncio
import random
import docker.errors
from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
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
from utils import (
    bucket_data,
    estimate_exploitation_exploration_ratio,
    estimate_relative_reward_increase,
    estimate_exploitation_over_time,
)

CONFIG_FILE = "config.json"


def load_config() -> dict:
    """Load config from a JSON file or return defaults."""
    default_config = {"host": "127.0.0.1", "port": 8000, "debug": False}
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


app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # The origin of the frontend app
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConfigModel(BaseModel):
    host: str
    port: int
    debug: bool


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
        # arms are the internal integer arms that MAB uses
        self.arms = arms  # e.g. [0,1,2,...]
        # Maps internal int -> user-supplied label (string or int)
        self.variant_labels = variant_labels
        # Inverse map: user-supplied label (string or int) -> internal int
        self.label_variants = label_variants

        self.features: list[str] = []
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


class CreateModelRequest(BaseModel):
    # Instead of n_variants: int, we now have a dict that may contain
    # int keys -> (string or int) labels
    variants: Dict[int, Union[str, int]]
    name: str


class UpdateModelRequest(BaseModel):
    updates: list[dict]


class FetchActionRequest(BaseModel):
    cb_model_id: str
    context: dict


class RolloutGlobalVariantRequest(BaseModel):
    variant: Union[str, int]


@app.post("/create_model")
async def create_model(request: CreateModelRequest):
    """
    Create a new model. The user passes a dict for 'variants' such as:
        {0: "red", 1: "blue"} or {0: 0, 1: 1}
    Internally, we will keep arms = [0, 1, ...] (the keys),
    plus two mappings:
        variant_labels:  0 -> "red", 1 -> "blue"
        label_variants: "red" -> 0, "blue" -> 1
    """
    cb_model_id = str(uuid.uuid4())

    # Sort or just list out the keys in ascending order:
    # but you can also keep the order as is, if you prefer
    arms = sorted(request.variants.keys())

    # variant_labels: internal_int -> user label
    variant_labels = {k: v for k, v in request.variants.items()}

    # label_variants: user label -> internal_int
    # This is the inverse mapping, allowing us to go from user label to internal arm
    # Note: This only works if the user values are unique.
    # If the user passed e.g. {0: 'red', 1: 'red'} that might cause a conflict.
    # For simplicity, assume they are unique.
    label_variants = {v: k for k, v in request.variants.items()}

    models[cb_model_id] = wMAB(
        name=request.name,
        arms=arms,
        variant_labels=variant_labels,
        label_variants=label_variants,
        learning_policy=LearningPolicy.UCB1(alpha=1.25),
        neighborhood_policy=NeighborhoodPolicy.Radius(radius=5),
    )
    save_model(cb_model_id, models[cb_model_id])
    return {"message": "Model created successfully", "model_id": cb_model_id}


@app.post("/delete_model/{cb_model_id}")
async def delete_model(cb_model_id: str):
    if cb_model_id not in models:
        raise HTTPException(status_code=400, detail="Model ID does not exist")
    models[cb_model_id].deactivate()
    save_model(cb_model_id, models[cb_model_id])  # Save deactivated model
    delete_model_file(cb_model_id)
    del models[cb_model_id]  # Remove from in-memory dict
    return {"message": "Model deactivated and deleted"}


@app.get("/models")
async def get_models():
    response = []
    for model_id, model in models.items():
        # If you prefer to show the user-friendly variant dictionary in the output,
        # you can return model.variant_labels as "variants" below:
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


@app.post("/update_model/{cb_model_id}")
async def update_model(cb_model_id: str, request: UpdateModelRequest):
    model = models.get(cb_model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    for update in request.updates:
        decision = update["decision"]
        reward = update["reward"]

        # Convert decision from user label (string or int) to internal int if needed
        if isinstance(decision, str):
            # If user passes "red" (example), map to 0
            if decision not in model.label_variants:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid variant label: {decision}",
                )
            decision = model.label_variants[decision]
        else:
            # If it is an int, verify it's a valid arm
            if decision not in model.arms:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid variant integer: {decision}",
                )

        features = {k: v for k, v in update.items() if k.startswith("feature")}
        feature_array = np.array([list(features.values())])

        # Update the model's known features if this is the first time
        if model.update_requests == 0:
            for feature in features:
                model._update_feature_list(feature)

        model.partial_fit(
            decisions=[decision], rewards=[reward], contexts=feature_array
        )
        model._incr_update_request()
        model._incr_latest_update_request()
        model._update_update_request_trail(variant=decision, reward=reward)

    # Save on some schedule (currently: if model.update_requests % 100)
    if model.update_requests % 100:
        save_model(cb_model_id, model)

    return {"message": "Model updated successfully"}


@app.post("/rollout_global_variant/{cb_model_id}")
async def rollout_global_variant(
    cb_model_id: str, request: RolloutGlobalVariantRequest
):
    model = models.get(cb_model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    variant = request.variant
    # Convert if user passes a string
    if isinstance(variant, str):
        if variant not in model.label_variants:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid variant label: {variant}",
            )
        variant = model.label_variants[variant]
    else:
        # Check if int is valid
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


@app.post("/clear_global_variant/{cb_model_id}")
async def clear_global_variant(cb_model_id: str):
    model = models.get(cb_model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    model.clear_global_rollout()
    save_model(cb_model_id, model)
    return {"message": f"Global variant cleared for model {cb_model_id}"}


@app.post("/fetch_recommended_variant")
async def fetch_recommended_variant(request: FetchActionRequest):
    cb_model_id = request.cb_model_id
    model = models.get(cb_model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    # If there's a global rollout, return that
    if model.global_rolled_out and model.get_global_variant() is not None:
        internal_variant = model.get_global_variant()
        # convert to user-friendly label
        recommended_label = model.variant_labels.get(internal_variant, internal_variant)
        return {"recommended_variant": recommended_label}

    context = request.context
    features = {k: v for k, v in context.items() if k.startswith("feature")}
    feature_array = np.array([list(features.values())])

    if not model.update_requests:
        internal_variant = random.choice(model.arms)
    else:
        internal_variant = model.predict(feature_array)

    # Record usage metrics
    model._incr_prediction_request()
    model._incr_latest_prediction_request()
    model._update_prediction_request_trail(internal_variant)

    # Convert internal arm to the user-friendly label if possible
    recommended_label = model.variant_labels.get(internal_variant, internal_variant)

    # Periodic save
    if model.prediction_requests % 100:
        save_model(cb_model_id, model)

    return {"recommended_variant": recommended_label}


@app.get("/logs/stream")
def stream_logs():
    """
    Streams logs from a specific container in real time using the Docker SDK.
    Returns a message if not running in Docker.
    """

    def log_generator():
        try:
            # Create a Docker client from environment (docker socket).
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
            for line in message.strip().splitlines():  # Split the message into lines
                yield line + "\n"  # Add newline to each line

    return StreamingResponse(log_generator(), media_type="text/plain")
