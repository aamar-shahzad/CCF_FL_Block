# Building CCFL (Linux / Dev Container only)

CCF application builds **only on Linux** with the CCF SDK installed. Do not run `cmake` on macOS against this repo — `ccf_virtual` is not available there.

## Quick start

1. Open the repo in VS Code / Cursor.
2. **Reopen in Container** (uses `ghcr.io/microsoft/ccf/app/dev/virtual:ccf-5.0.0`).
3. Inside the container, build the app (not done automatically — avoids setup failures):

```bash
make build-virtual
```

4. Start the network:

```bash
make run-virtual
```

Sandbox: `https://127.0.0.1:8000` (port forwarded from the container).

## Manual build (inside container)

```bash
cd /workspace
rm -rf build
mkdir -p build
cd build
CC=cc CXX=c++ cmake -DCOMPILE_TARGET=virtual -DCMAKE_EXPORT_COMPILE_COMMANDS=1 -GNinja ..
ninja
```

## Dev container troubleshooting

| Problem | Fix |
|---------|-----|
| "Failed to set up container" | Rebuild: Command Palette → **Dev Containers: Rebuild Container** |
| Image pull fails on Apple Silicon | `runArgs: ["--platform=linux/amd64"]` is already set in devcontainer.json |
| Tag `ccf-4.0.7` not found | Edit `.devcontainer/Dockerfile` → use `ccf-5.0.0` (see [ccf-app-template](https://github.com/microsoft/ccf-app-template)) |
| `remoteUser vscode` errors | Do not set `remoteUser` — CCF image has no `vscode` user |

## Common mistakes

| Problem | Fix |
|---------|-----|
| `ccf_virtual` not found | Use dev container, not host macOS |
| Ninja vs Makefiles cache clash | `rm -rf build` then reconfigure |
| Nested `build/build/` | Always `cmake ..` from `build/` at repo root only |
| Git version warning | Harmless without tags; defaults to `0.0.0` |

## Run experiments

```bash
make run-virtual   # terminal 1
python -m experiments.runner.run_ccf_fl --platform virtual --config experiments/config/mnist_iid.yaml
```
