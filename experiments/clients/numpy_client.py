"""NumPy-only FL client (no TensorFlow). For CPUs without AVX (e.g. emulated x86 on Apple Silicon)."""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np


class SoftmaxModel:
    name = "CCFL_NumpySoftmax"

    def __init__(self, num_features: int, num_classes: int):
        self.num_features = num_features
        self.num_classes = num_classes
        self.W = np.random.randn(num_features, num_classes).astype(np.float32) * 0.01
        self.b = np.zeros(num_classes, dtype=np.float32)

    def get_weights(self) -> list[np.ndarray]:
        return [self.W, self.b]

    def set_weights(self, arrays: list[np.ndarray]) -> None:
        self.W, self.b = arrays


def _num_features(dataset: str, sample_x: np.ndarray) -> int:
    ds = dataset.lower().replace("-", "_")
    if ds == "har":
        return int(sample_x.shape[-1]) if sample_x.ndim > 1 else sample_x.shape[0]
    if sample_x.ndim == 3:
        return int(np.prod(sample_x.shape[1:]))
    return int(np.prod(sample_x.shape[1:]))


def _flatten_x(x: np.ndarray, dataset: str) -> np.ndarray:
    ds = dataset.lower().replace("-", "_")
    if ds in ("mnist", "fashion_mnist"):
        if x.ndim == 3:
            x = x[..., np.newaxis]
        return x.reshape(x.shape[0], -1).astype(np.float32)
    if ds == "har":
        return x.reshape(x.shape[0], -1).astype(np.float32)
    return x.reshape(x.shape[0], -1).astype(np.float32)


def build_model(
    dataset: str,
    input_shape: tuple,
    num_classes: int,
    cfg: Optional[Dict[str, Any]] = None,
) -> SoftmaxModel:
    del input_shape, cfg
    ds = dataset.lower().replace("-", "_")
    if ds in ("mnist", "fashion_mnist"):
        return SoftmaxModel(28 * 28, num_classes)
    if ds == "cifar10":
        return SoftmaxModel(32 * 32 * 3, num_classes)
    if ds == "har":
        return SoftmaxModel(561, num_classes)
    return SoftmaxModel(784, num_classes)


def train_local(
    model: SoftmaxModel,
    x: np.ndarray,
    y: np.ndarray,
    epochs: int = 1,
    batch_size: int = 32,
    dataset: str = "mnist",
    num_classes: int = 10,
) -> SoftmaxModel:
    del num_classes
    if len(x) == 0:
        return model
    x_flat = _flatten_x(x, dataset)
    y = np.asarray(y, dtype=np.int64)
    lr = 0.1
    for _ in range(epochs):
        idx = np.random.permutation(len(x_flat))
        for start in range(0, len(x_flat), batch_size):
            batch = idx[start : start + batch_size]
            xb = x_flat[batch]
            yb = y[batch]
            logits = xb @ model.W + model.b
            logits -= logits.max(axis=1, keepdims=True)
            exp = np.exp(logits)
            probs = exp / exp.sum(axis=1, keepdims=True)
            y_oh = np.zeros_like(probs)
            y_oh[np.arange(len(yb)), yb] = 1.0
            grad_logits = (probs - y_oh) / len(yb)
            model.W -= lr * (xb.T @ grad_logits)
            model.b -= lr * grad_logits.sum(axis=0)
    return model


def flatten_weights(model: SoftmaxModel) -> list[float]:
    flat: list[float] = []
    for w in model.get_weights():
        flat.extend(w.flatten().tolist())
    return flat


def set_weights(model: SoftmaxModel, flat: list[float]) -> None:
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
    model: SoftmaxModel,
    x_test: np.ndarray,
    y_test: np.ndarray,
    dataset: str = "mnist",
    num_classes: int = 10,
) -> float:
    del num_classes
    if len(x_test) == 0:
        return 0.0
    x_flat = _flatten_x(x_test, dataset)
    y_test = np.asarray(y_test, dtype=np.int64)
    logits = x_flat @ model.W + model.b
    preds = np.argmax(logits, axis=1)
    return float(np.mean(preds == y_test))
