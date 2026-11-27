"""Which variant does a user get? Decided by a hash, so it never changes for that user."""

import hashlib
from pathlib import Path

import yaml


def load_experiment(path: Path) -> dict:
    """Read an experiment file and check that the traffic shares add up."""
    experiment = yaml.safe_load(path.read_text(encoding="utf-8"))
    if set(experiment["allocation"]) != set(experiment["variants"]):
        raise ValueError("allocation and variants must name the same arms")
    if abs(sum(experiment["allocation"].values()) - 1) > 1e-9:
        raise ValueError("allocation shares must add up to 1")
    return experiment


def bucket_for(experiment_name: str, user_id: str, buckets: int) -> int:
    """SHA-256 of 'experiment:user' picks a bucket. Experiments split users independently."""
    digest = hashlib.sha256(f"{experiment_name}:{user_id}".encode()).hexdigest()
    return int(digest, 16) % buckets


def assign(experiment: dict, user_id: str) -> str:
    """The variant name for this user."""
    buckets = experiment["buckets"]
    bucket = bucket_for(experiment["name"], user_id, buckets)
    upper = 0.0
    for name, share in experiment["allocation"].items():
        upper += share * buckets
        if bucket < upper:
            return name
    return name  # rounding at the very top bucket
