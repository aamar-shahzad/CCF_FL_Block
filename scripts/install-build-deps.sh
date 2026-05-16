#!/usr/bin/env bash
# Install native dependencies for `make build-virtual` (Ubuntu 20.04+ / CCF dev image).
set -euo pipefail

echo "Installing CCF app build dependencies..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends \
  ninja-build \
  cmake \
  libboost-log-dev \
  libboost-system-dev \
  clang-18 \
  clang-15 \
  clang-10 \
  libc++-18-dev \
  libc++abi-18-dev \
  libc++-15-dev \
  libc++abi-15-dev

echo "Done. Build with: make build-virtual"
