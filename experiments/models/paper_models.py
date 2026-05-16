"""
Model architectures aligned with FL_Clients.ipynb / paper experiments.
MNIST & Fashion-MNIST: 2x Conv + MaxPool CNN.
CIFAR-10: deeper CNN. HAR: MLP on sensor features.
"""

from __future__ import annotations

import numpy as np
import tensorflow as tf


def build_paper_model(dataset: str, num_classes: int = 10) -> tf.keras.Model:
    ds = dataset.lower().replace("-", "_")
    if ds in ("mnist", "fashion_mnist"):
        model = tf.keras.Sequential(
            [
                tf.keras.layers.Conv2D(
                    64, kernel_size=3, activation="relu", input_shape=(28, 28, 1)
                ),
                tf.keras.layers.MaxPooling2D(pool_size=(2, 2)),
                tf.keras.layers.Conv2D(32, kernel_size=3, activation="relu"),
                tf.keras.layers.MaxPooling2D(pool_size=(2, 2)),
                tf.keras.layers.Flatten(),
                tf.keras.layers.Dense(num_classes, activation="softmax"),
            ],
            name=f"CCFL_CNN_{ds}",
        )
        model.compile(
            optimizer="adam",
            loss="categorical_crossentropy",
            metrics=["accuracy"],
        )
        return model

    if ds == "cifar10":
        model = tf.keras.Sequential(
            [
                tf.keras.layers.Conv2D(32, 3, activation="relu", input_shape=(32, 32, 3)),
                tf.keras.layers.BatchNormalization(),
                tf.keras.layers.MaxPooling2D(),
                tf.keras.layers.Conv2D(64, 3, activation="relu"),
                tf.keras.layers.BatchNormalization(),
                tf.keras.layers.MaxPooling2D(),
                tf.keras.layers.Conv2D(64, 3, activation="relu"),
                tf.keras.layers.Flatten(),
                tf.keras.layers.Dense(64, activation="relu"),
                tf.keras.layers.Dense(num_classes, activation="softmax"),
            ],
            name="CCFL_CIFAR10_CNN",
        )
        model.compile(
            optimizer="adam",
            loss="categorical_crossentropy",
            metrics=["accuracy"],
        )
        return model

    if ds == "har":
        model = tf.keras.Sequential(
            [
                tf.keras.layers.Dense(256, activation="relu", input_shape=(561,)),
                tf.keras.layers.Dropout(0.3),
                tf.keras.layers.Dense(128, activation="relu"),
                tf.keras.layers.Dense(num_classes, activation="softmax"),
            ],
            name="CCFL_HAR_MLP",
        )
        model.compile(
            optimizer="adam",
            loss="categorical_crossentropy",
            metrics=["accuracy"],
        )
        return model

    raise ValueError(f"Unknown dataset: {dataset}")


def preprocess_batch(
    dataset: str, x: np.ndarray, y: np.ndarray, num_classes: int
) -> tuple[np.ndarray, np.ndarray]:
    ds = dataset.lower().replace("-", "_")
    x = x.astype(np.float32)
    if ds in ("mnist", "fashion_mnist"):
        if x.ndim == 3:
            x = x[..., np.newaxis]
    if ds == "cifar10" and x.ndim == 3:
        pass
    y_oh = tf.keras.utils.to_categorical(y, num_classes)
    return x, y_oh.astype(np.float32)
