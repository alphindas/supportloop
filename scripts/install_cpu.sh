#!/usr/bin/env bash
# Install the locked dependencies with the CPU build of PyTorch, into the Python given as
# $1. For Docker and CI, which have no GPU: the default Linux build pulls several GB of
# CUDA libraries. Pass "--dev" as $2 to include test and lint tools.
set -euo pipefail
python_bin="${1:?usage: install_cpu.sh <python> [--dev]}"
dev_flag="--no-dev"
if [[ "${2:-}" == "--dev" ]]; then dev_flag="--all-groups"; fi

requirements="$(mktemp)"
uv export --frozen "$dev_flag" --no-hashes --no-emit-project > "$requirements.all"
torch_pin="$(grep -E '^torch==' "$requirements.all" | cut -d' ' -f1)"
grep -vE '^(torch|nvidia-|cuda-|triton)' "$requirements.all" > "$requirements"

uv pip install --python "$python_bin" "$torch_pin" \
    --index-url https://download.pytorch.org/whl/cpu
# --no-deps keeps every version exactly as locked and stops the GPU libraries returning.
uv pip install --python "$python_bin" --no-deps -r "$requirements"
rm -f -- "$requirements" "$requirements.all"
