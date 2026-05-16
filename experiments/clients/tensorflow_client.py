from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import tensorflow as tf

from experiments.models.paper_models import build_paper_model, preprocess_batch
from experiments.models.remote_models import (
    build_keras_pretrained,
    maybe_apply_pretrained_url,
)


def build_model(
    dataset: str,
    input_shape: tuple,
    num_classes: int,
    cfg: Optional[Dict[str, Any]] = None,
) -> tf.keras.Model:
    del input_shape
    cfg = cfg or {}
    init = (cfg.get("model_init") or "paper").lower()
    if init == "keras_pretrained":
        return build_keras_pretrained(cfg, num_classes)
    model = build_paper_model(dataset, num_classes)
    return maybe_apply_pretrained_url(model, cfg)


def _preprocess_for_model(
    model: tf.keras.Model,
    dataset: str,
    x: np.ndarray,
    y: np.ndarray,
    num_classes: int,
) -> tuple[np.ndarray, np.ndarray]:
    input_size = getattr(model, "ccf_input_size", None)
    if input_size is not None:
        size = int(input_size)
        if x.ndim == 3:
            x = x[..., np.newaxis]
        x = tf.image.resize(x, (size, size)).numpy()
        if x.shape[-1] == 1:
            x = np.repeat(x, 3, axis=-1)
        y_oh = tf.keras.utils.to_categorical(y, num_classes)
        return x.astype(np.float32), y_oh.astype(np.float32)
    return preprocess_batch(dataset, x, y, num_classes)


def train_local(
    model: tf.keras.Model,
    x: np.ndarray,
    y: np.ndarray,
    epochs: int = 1,
    batch_size: int = 32,
    dataset: str = "mnist",
    num_classes: int = 10,
) -> tf.keras.Model:
    if len(x) == 0:
        return model
    x_p, y_p = _preprocess_for_model(model, dataset, x, y, num_classes)
    model.fit(x_p, y_p, epochs=epochs, batch_size=batch_size, verbose=0)
    return model


def flatten_weights(model: tf.keras.Model) -> list[float]:
    weights = model.get_weights()
    flat: list[float] = []
    for w in weights:
        flat.extend(w.flatten().tolist())
    return flat


def set_weights(model: tf.keras.Model, flat: list[float]) -> None:
    shapes = [w.shape for w in model.get_weights()]
    offset = 0
    new_weights = []
    for shape in shapes:
        size = int(np.prod(shape))
        chunk = np.array(flat[offset : offset + size], dtype=np.float32).reshape(shape)
        new_weights.append(chunk)
        offset += size
    model.set_weights(new_weights)


def evaluate(
    model: tf.keras.Model,
    x_test: np.ndarray,
    y_test: np.ndarray,
    dataset: str = "mnist",
    num_classes: int = 10,
) -> float:
    x_p, y_p = _preprocess_for_model(model, dataset, x_test, y_test, num_classes)
    _, acc = model.evaluate(x_p, y_p, verbose=0)
    return float(acc)
