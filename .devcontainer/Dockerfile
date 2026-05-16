# Official CCF dev image (see microsoft/ccf-app-template)
# Use linux/amd64 on Apple Silicon (see devcontainer.json runArgs).
# Tag confirmed by microsoft/ccf-app-template; for 4.0.7 SDK try :ccf-4.0.7 if available
FROM ghcr.io/microsoft/ccf/app/dev/virtual:ccf-5.0.0

EXPOSE 8080 8000 5000

# Boost log (required by CMakeLists.txt find_package(Boost COMPONENTS log))
RUN apt-get update && apt-get install -y --no-install-recommends \
    libboost-log-dev libboost-system-dev \
    && rm -rf /var/lib/apt/lists/*

# Optional: Node for frontend tooling (failures here must not break the image)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/* \
    || true
