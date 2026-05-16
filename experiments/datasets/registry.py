from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict

import numpy as np


def _split_iid(x: np.ndarray, y: np.ndarray, num_clients: int) -> list[tuple[np.ndarray, np.ndarray]]:
    idx = np.random.permutation(len(x))
    x, y = x[idx], y[idx]
    shards = np.array_split(idx, num_clients)
    return [(x[s], y[s]) for s in shards]


def _split_non_iid(
    x: np.ndarray, y: np.ndarray, num_clients: int, alpha: float = 0.5
) -> list[tuple[np.ndarray, np.ndarray]]:
    num_classes = int(y.max()) + 1
    label_indices = [np.where(y == c)[0] for c in range(num_classes)]
    client_indices: list[list[int]] = [[] for _ in range(num_clients)]
    for c in range(num_classes):
        np.random.shuffle(label_indices[c])
        proportions = np.random.dirichlet([alpha] * num_clients)
        proportions = (np.cumsum(proportions) * len(label_indices[c])).astype(int)[:-1]
        splits = np.split(label_indices[c], proportions)
        for i, s in enumerate(splits):
            client_indices[i].extend(s.tolist())
    out = []
    for indices in client_indices:
        if not indices:
            out.append((x[:0], y[:0]))
            continue
        idx = np.array(indices)
        out.append((x[idx], y[idx]))
    return out


def _read_idx_images(url: str) -> np.ndarray:
    import gzip
    import struct
    import urllib.request

    with urllib.request.urlopen(url, timeout=120) as resp:
        buf = gzip.decompress(resp.read())
    _, n, rows, cols = struct.unpack(">IIII", buf[:16])
    return np.frombuffer(buf, dtype=np.uint8, offset=16).reshape(n, rows, cols).astype(np.float32) / 255.0


def _read_idx_labels(url: str) -> np.ndarray:
    import gzip
    import struct
    import urllib.request

    with urllib.request.urlopen(url, timeout=120) as resp:
        buf = gzip.decompress(resp.read())
    n = struct.unpack(">II", buf[:8])[1]
    return np.frombuffer(buf, dtype=np.uint8, offset=8).astype(np.int32)


def _load_mnist_urls(base: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    x_train = _read_idx_images(f"{base}/train-images-idx3-ubyte.gz")
    y_train = _read_idx_labels(f"{base}/train-labels-idx1-ubyte.gz")
    x_test = _read_idx_images(f"{base}/t10k-images-idx3-ubyte.gz")
    y_test = _read_idx_labels(f"{base}/t10k-labels-idx1-ubyte.gz")
    return x_train, y_train, x_test, y_test


def _load_mnist_openml() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    try:
        from sklearn.datasets import fetch_openml

        data = fetch_openml("mnist_784", version=1, as_frame=False, parser="auto")
        x = data["data"].reshape(-1, 28, 28).astype(np.float32) / 255.0
        y = data["target"].astype(np.int32)
        return x[:60000], y[:60000], x[60000:], y[60000:]
    except Exception:
        return _load_mnist_urls("https://storage.googleapis.com/cvdf-datasets/mnist")


def _load_fashion_openml() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    base = "http://fashion-mnist.s3-website.eu-central-1.amazonaws.com"
    try:
        return _load_mnist_urls(base)
    except Exception:
        from sklearn.datasets import fetch_openml

        data = fetch_openml("Fashion-MNIST", version=1, as_frame=False, parser="auto")
        x = data["data"].reshape(-1, 28, 28).astype(np.float32) / 255.0
        y = data["target"].astype(np.int32)
        return x[:60000], y[:60000], x[60000:], y[60000:]


def load_mnist() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if os.environ.get("FL_BACKEND", "").lower() == "numpy":
        return _load_mnist_openml()
    try:
        import tensorflow as tf

        (x_train, y_train), (x_test, y_test) = tf.keras.datasets.mnist.load_data()
    except Exception:
        return _load_mnist_openml()
    x_train = x_train.astype(np.float32) / 255.0
    x_test = x_test.astype(np.float32) / 255.0
    return x_train, y_train, x_test, y_test


def load_fashion_mnist() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if os.environ.get("FL_BACKEND", "").lower() == "numpy":
        return _load_fashion_openml()
    try:
        import tensorflow as tf

        (x_train, y_train), (x_test, y_test) = tf.keras.datasets.fashion_mnist.load_data()
    except Exception:
        return _load_fashion_openml()
    x_train = x_train.astype(np.float32) / 255.0
    x_test = x_test.astype(np.float32) / 255.0
    return x_train, y_train, x_test, y_test


def load_cifar10() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    import tensorflow as tf

    (x_train, y_train), (x_test, y_test) = tf.keras.datasets.cifar10.load_data()
    y_train = y_train.squeeze()
    y_test = y_test.squeeze()
    x_train = x_train.astype(np.float32) / 255.0
    x_test = x_test.astype(np.float32) / 255.0
    return x_train, y_train, x_test, y_test


def load_har(synthetic_if_missing: bool = True) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """HAR-like sensor data; synthetic fallback for reproducibility."""
    path = Path("data/har/train.csv")

    if path.exists():
        import pandas as pd

        df = pd.read_csv(path)
        y = df["label"].values.astype(np.int32)
        x = df.drop(columns=["label"]).values.astype(np.float32)
        from sklearn.model_selection import train_test_split

        x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.2, random_state=42)
        return x_train, y_train, x_test, y_test

    if not synthetic_if_missing:
        raise FileNotFoundError("HAR data not found at data/har/train.csv")

    rng = np.random.default_rng(42)
    x_train = rng.normal(size=(5000, 561)).astype(np.float32)
    y_train = rng.integers(0, 6, size=5000)
    x_test = rng.normal(size=(1000, 561)).astype(np.float32)
    y_test = rng.integers(0, 6, size=1000)
    return x_train, y_train, x_test, y_test


LOADERS: Dict[str, Callable[[], tuple]] = {
    "mnist": load_mnist,
    "fashion_mnist": load_fashion_mnist,
    "cifar10": load_cifar10,
    "har": load_har,
}


def load_dataset(
    name: str,
    num_clients: int,
    distribution: str = "iid",
    alpha: float = 0.5,
) -> dict[str, Any]:
    loader = LOADERS[name.lower().replace("-", "_")]
    x_train, y_train, x_test, y_test = loader()
    if distribution == "non_iid":
        shards = _split_non_iid(x_train, y_train, num_clients, alpha)
    else:
        shards = _split_iid(x_train, y_train, num_clients)
    return {
        "name": name,
        "shards": shards,
        "x_test": x_test,
        "y_test": y_test,
    }
