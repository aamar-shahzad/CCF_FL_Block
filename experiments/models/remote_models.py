"""Load Keras models with weights fetched from the internet (Applications zoo or URL)."""

from __future__ import annotations

import os
from typing import Any

import tensorflow as tf


def build_keras_pretrained(cfg: dict[str, Any], num_classes: int) -> tf.keras.Model:
    app_name = cfg.get("keras_application", "MobileNetV2")
    size = int(cfg.get("keras_input_size", 96))
    weights = cfg.get("keras_weights", "imagenet")
    if weights == "none":
        weights = None

    if not hasattr(tf.keras.applications, app_name):
        raise ValueError(f"Unknown keras application: {app_name}")

    app_ctor = getattr(tf.keras.applications, app_name)
    base = app_ctor(
        include_top=False,
        weights=weights,
        input_shape=(size, size, 3),
        pooling="avg",
    )
    out = tf.keras.layers.Dense(num_classes, activation="softmax")(base.output)
    model = tf.keras.Model(inputs=base.input, outputs=out, name=f"CCFL_{app_name}_pretrained")
    model.compile(
        optimizer="adam",
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )
    model.ccf_input_size = size  # type: ignore[attr-defined]
    model.ccf_channels = 3  # type: ignore[attr-defined]
    return model


def load_weights_from_url(model: tf.keras.Model, url: str) -> None:
    path = tf.keras.utils.get_file(
        fname=os.path.basename(url.split("?")[0]) or "pretrained.weights.h5",
        origin=url,
        cache_subdir="ccf_fl_pretrained",
    )
    model.load_weights(path)


def maybe_apply_pretrained_url(model: tf.keras.Model, cfg: dict[str, Any]) -> tf.keras.Model:
    url = (cfg.get("pretrained_weights_url") or "").strip()
    if url:
        load_weights_from_url(model, url)
    return model
