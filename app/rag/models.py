"""Embedding and reranking models: real (Hugging Face) and fake (for tests and CI)."""

import gc
import hashlib
import re
from functools import lru_cache
from typing import Any, Protocol

import numpy as np
import yaml

from app.config import PROJECT_ROOT


class Embedder(Protocol):
    """Turns text into vectors. Vectors are length 1, so a dot product is cosine similarity."""

    name: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...

    def release(self) -> None: ...


class Reranker(Protocol):
    """Scores how well each document answers a query. Scores are between 0 and 1."""

    name: str

    def score(self, query: str, documents: list[str]) -> list[float]: ...

    def release(self) -> None: ...


@lru_cache
def load_model_config() -> dict[str, Any]:
    """Read config/models.yaml."""
    return yaml.safe_load((PROJECT_ROOT / "config" / "models.yaml").read_text(encoding="utf-8"))


def free_gpu_memory() -> None:
    """Return unused GPU memory. The caller must have dropped its model references first."""
    import torch

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


class HFEmbedder:
    """A sentence-transformers embedding model."""

    def __init__(self, name: str, device: str) -> None:
        # Imported here so that tests and CI never need to load torch models.
        from sentence_transformers import SentenceTransformer

        config = load_model_config()
        spec = config["embedders"][name]
        self.name = name
        self._query_prompt_name: str | None = spec.get("query_prompt_name")
        self._query_prefix: str = spec.get("query_prefix", "")
        self._model = SentenceTransformer(
            name, device=device, model_kwargs={"dtype": config["dtype"][device]}
        )
        self._model.max_seq_length = spec["max_length"]

    def _encode(self, texts: list[str], prompt_name: str | None = None) -> list[list[float]]:
        vectors = self._model.encode(
            texts,
            prompt_name=prompt_name,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
            batch_size=16,
        )
        return vectors.astype(np.float32).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed knowledge-base chunks."""
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        """Embed a user question, with the query instruction the model was trained with."""
        return self._encode([self._query_prefix + text], self._query_prompt_name)[0]

    def release(self) -> None:
        """Unload the model from memory."""
        self._model = None
        free_gpu_memory()


class HFReranker:
    """A cross-encoder reranker: it reads the question and one chunk together."""

    def __init__(self, name: str, device: str) -> None:
        from sentence_transformers import CrossEncoder

        config = load_model_config()
        spec = config["rerankers"][name]
        self.name = name
        self._batch_size: int = spec["batch_size"]
        self._model = CrossEncoder(
            name,
            device=device,
            max_length=spec["max_length"],
            model_kwargs={"dtype": config["dtype"][device]},
        )

    def score(self, query: str, documents: list[str]) -> list[float]:
        """Return one score per document. Sigmoid squashes raw model output into 0..1."""
        import torch

        if not documents:
            return []
        scores = self._model.predict(
            [(query, document) for document in documents],
            batch_size=self._batch_size,
            activation_fn=torch.nn.Sigmoid(),
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return [float(score) for score in scores]

    def release(self) -> None:
        """Unload the model from memory."""
        self._model = None
        free_gpu_memory()


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class FakeEmbedder:
    """Deterministic word-hashing embedder for tests. It says nothing about real quality."""

    name = "fake-embedder"
    dimensions = 256

    def _embed(self, text: str) -> list[float]:
        vector = np.zeros(self.dimensions, dtype=np.float32)
        for word in _words(text):
            bucket = int(hashlib.sha256(word.encode()).hexdigest(), 16) % self.dimensions
            vector[bucket] += 1.0
        norm = np.linalg.norm(vector)
        if norm == 0:
            vector[0], norm = 1.0, 1.0
        return (vector / norm).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed several texts."""
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        """Embed one question."""
        return self._embed(text)

    def release(self) -> None:
        """Nothing to unload."""


class FakeReranker:
    """Scores by the share of query words found in the document. For tests only."""

    name = "fake-reranker"

    def score(self, query: str, documents: list[str]) -> list[float]:
        """Return one overlap score per document."""
        query_words = set(_words(query))
        if not query_words:
            return [0.0 for _ in documents]
        return [len(query_words & set(_words(doc))) / len(query_words) for doc in documents]

    def release(self) -> None:
        """Nothing to unload."""


def build_embedder(name: str, device: str) -> Embedder:
    """Create the embedder named in settings."""
    return FakeEmbedder() if name == FakeEmbedder.name else HFEmbedder(name, device)


def build_reranker(name: str, device: str) -> Reranker | None:
    """Create the reranker named in settings. 'none' switches reranking off."""
    if name == "none":
        return None
    return FakeReranker() if name == FakeReranker.name else HFReranker(name, device)
