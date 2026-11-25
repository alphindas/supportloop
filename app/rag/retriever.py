"""Hybrid retrieval: BM25 + dense search, merged with RRF, then reranked."""

import json
from dataclasses import dataclass
from pathlib import Path

import bm25s
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.rag.chunking import Chunk, corpus_fingerprint
from app.rag.fusion import reciprocal_rank_fusion
from app.rag.models import Embedder, Reranker


@dataclass(frozen=True)
class RetrievalConfig:
    """How many results each stage keeps."""

    bm25_top_k: int
    dense_top_k: int
    rrf_k: int
    rerank_candidates: int


@dataclass(frozen=True)
class RetrievedChunk:
    """One search result, keeping every stage's evidence so failures can be debugged."""

    chunk: Chunk
    bm25_rank: int | None
    dense_rank: int | None
    rrf_score: float
    rerank_score: float | None


def _chroma_client(index_dir: Path) -> chromadb.ClientAPI:
    # Telemetry off: nothing about this project should be sent to an outside service.
    return chromadb.PersistentClient(
        path=str(index_dir / "chroma"), settings=ChromaSettings(anonymized_telemetry=False)
    )


def _collection_name(embedder_name: str) -> str:
    # One collection per embedding model: vectors from different models cannot be mixed.
    safe = "".join(c if c.isalnum() else "-" for c in embedder_name.lower()).strip("-")
    return f"kb-{safe}"[:63]


def _manifest_path(index_dir: Path, embedder_name: str) -> Path:
    return index_dir / f"{_collection_name(embedder_name)}.manifest.json"


def build_index(chunks: list[Chunk], embedder: Embedder, index_dir: Path) -> None:
    """Embed all chunks and store them in ChromaDB, replacing any earlier index.

    Rebuilding from scratch is simple and also removes chunks of deleted articles.
    It is fast enough for a few hundred chunks.
    """
    index_dir.mkdir(parents=True, exist_ok=True)
    client = _chroma_client(index_dir)
    name = _collection_name(embedder.name)
    if name in [collection.name for collection in client.list_collections()]:
        client.delete_collection(name)
    collection = client.create_collection(
        name, embedding_function=None, configuration={"hnsw": {"space": "cosine"}}
    )
    collection.add(
        ids=[chunk.chunk_id for chunk in chunks],
        embeddings=embedder.embed_documents([chunk.text for chunk in chunks]),
        metadatas=[{"article_id": c.article_id, "category": c.category} for c in chunks],
    )
    manifest = {
        "embedding_model": embedder.name,
        "corpus_fingerprint": corpus_fingerprint(chunks),
        "chunk_count": len(chunks),
    }
    _manifest_path(index_dir, embedder.name).write_text(json.dumps(manifest, indent=2))


class HybridRetriever:
    """Searches the knowledge base."""

    def __init__(
        self,
        chunks: list[Chunk],
        embedder: Embedder,
        reranker: Reranker | None,
        index_dir: Path,
        config: RetrievalConfig,
    ) -> None:
        manifest_file = _manifest_path(index_dir, embedder.name)
        if not manifest_file.exists():
            raise RuntimeError(f"No index for {embedder.name}. Run: make ingest")
        manifest = json.loads(manifest_file.read_text())
        # Refuse to search an index built from older articles: answers would be stale.
        if manifest["corpus_fingerprint"] != corpus_fingerprint(chunks):
            raise RuntimeError("The knowledge base changed since it was indexed. Run: make ingest")

        self.config = config
        self.corpus_fingerprint: str = manifest["corpus_fingerprint"]
        self._chunks = {chunk.chunk_id: chunk for chunk in chunks}
        self._chunk_ids = [chunk.chunk_id for chunk in chunks]
        self._embedder = embedder
        self._reranker = reranker
        self._collection = _chroma_client(index_dir).get_collection(
            _collection_name(embedder.name), embedding_function=None
        )
        # BM25 is rebuilt in memory at start-up; it takes milliseconds at this size.
        self._bm25 = bm25s.BM25()
        self._bm25.index(
            bm25s.tokenize([c.text for c in chunks], stopwords="en", show_progress=False),
            show_progress=False,
        )

    def bm25_search(self, query: str, top_k: int) -> list[str]:
        """Word-matching search. Chunks sharing no words with the query are left out."""
        tokens = bm25s.tokenize([query], stopwords="en", return_ids=False, show_progress=False)
        if not tokens[0]:
            return []
        indexes, scores = self._bm25.retrieve(
            tokens, k=min(top_k, len(self._chunk_ids)), show_progress=False
        )
        return [
            self._chunk_ids[int(index)]
            for index, score in zip(indexes[0], scores[0], strict=True)
            if score > 0
        ]

    def dense_search(self, query: str, top_k: int) -> list[str]:
        """Meaning-based search using the embedding model."""
        result = self._collection.query(
            query_embeddings=[self._embedder.embed_query(query)],
            n_results=min(top_k, len(self._chunk_ids)),
            include=["distances"],
        )
        return list(result["ids"][0])

    def retrieve(self, query: str, top_k: int, mode: str = "hybrid") -> list[RetrievedChunk]:
        """Return the best chunks for a query.

        mode is 'hybrid' in the app. 'bm25' and 'dense' exist so the retrieval eval can
        measure whether each part is actually useful.
        """
        bm25_ids = (
            self.bm25_search(query, self.config.bm25_top_k) if mode in ("hybrid", "bm25") else []
        )
        dense_ids = (
            self.dense_search(query, self.config.dense_top_k) if mode in ("hybrid", "dense") else []
        )
        fused = reciprocal_rank_fusion([bm25_ids, dense_ids], self.config.rrf_k)

        results = [
            RetrievedChunk(
                chunk=self._chunks[chunk_id],
                bm25_rank=bm25_ids.index(chunk_id) + 1 if chunk_id in bm25_ids else None,
                dense_rank=dense_ids.index(chunk_id) + 1 if chunk_id in dense_ids else None,
                rrf_score=score,
                rerank_score=None,
            )
            for chunk_id, score in fused[: self.config.rerank_candidates]
        ]
        if self._reranker is None:
            return results[:top_k]

        scores = self._reranker.score(query, [r.chunk.text for r in results])
        reranked = [
            RetrievedChunk(r.chunk, r.bm25_rank, r.dense_rank, r.rrf_score, score)
            for r, score in zip(results, scores, strict=True)
        ]
        reranked.sort(key=lambda r: (-r.rerank_score, r.chunk.chunk_id))
        return reranked[:top_k]
